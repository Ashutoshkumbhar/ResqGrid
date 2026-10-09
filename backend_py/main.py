import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

_env_file = Path(__file__).resolve().parent / ".env"
if _env_file.exists():
    for raw_line in _env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

from services.state_manager import state_manager
from services.evaluation_service import get_false_alert_evaluation, get_impact_comparison, get_accuracy_report
from services.forecast_service import build_short_term_forecast
from services.ai_ground_report import set_gemini_api_key, get_gemini_api_key, GEMINI_MODEL
from services.alert_service import TwilioProvider
from services.audit_service import list_audit_entries

REPLAY_FRAME_SECONDS = 4
POLL_SECONDS = 30
DEMO_TICK_SECONDS = int(os.getenv("DEMO_TICK_SECONDS", "15"))
DEMO_DURATION_SECONDS = int(os.getenv("DEMO_DURATION_SECONDS", "120"))

# One writer at a time: every event runs the full recalculation loop
state_lock = asyncio.Lock()
replay_task: Optional[asyncio.Task] = None
demo_task: Optional[asyncio.Task] = None


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        try:
            async with state_lock:
                state = await run_in_threadpool(state_manager.get_full_state)
            await websocket.send_json({"type": "INITIAL_STATE", "data": state})
        except Exception:
            self.disconnect(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


async def poller_task():
    """Refresh live weather periodically and push state to every client."""
    while True:
        try:
            await asyncio.sleep(POLL_SECONDS)
            async with state_lock:
                await run_in_threadpool(state_manager.refresh_live)
                state = await run_in_threadpool(state_manager.get_full_state)
            await manager.broadcast({"type": "WEATHER_TICK", "weather": state["weather"], "data": state})
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Poller Error]: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poller_task())
    yield
    task.cancel()


app = FastAPI(
    title="ResQGrid API",
    description="AI-assisted local flood warning, risk analysis and response coordination platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
_ASSETS_DIR = os.path.join(_FRONTEND_DIST, "assets")

if os.path.isdir(_ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
            await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ------------------------------------------------------------------ request models
Severity = Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
ReporterType = Literal["CITIZEN", "WARD_OFFICER", "FIRST_RESPONDER"]


class GroundReportRequest(BaseModel):
    description: str = Field(min_length=5, max_length=1000)
    location: str = Field(default="Village A (Wakad Khurd)", max_length=120)
    severity: Severity = "HIGH"
    reporterType: ReporterType = "CITIZEN"
    timestamp: Optional[str] = None


class RainfallSimulationRequest(BaseModel):
    incrementMm: float = Field(default=50.0, gt=0, le=300)


class WaterLevelSimulationRequest(BaseModel):
    incrementM: float = Field(default=0.5, gt=0, le=3)


class RoadBlockageRequest(BaseModel):
    roadId: str = "R12"
    status: Optional[Literal["OPEN", "AT_RISK", "BLOCKED"]] = None


class ScenarioRouteRequest(BaseModel):
    scenario: int = Field(ge=1, le=3)
    settlementId: str = "S1"
    apply: bool = False


class ResourceStatusRequest(BaseModel):
    status: Literal["AVAILABLE", "DEPLOYED", "BUSY", "UNAVAILABLE"]
    assignment: Optional[str] = None


class ExplainRequest(BaseModel):
    settlementId: Optional[str] = None


class ApiKeyConfigRequest(BaseModel):
    geminiApiKey: str = Field(min_length=10)


class AlertSendRequest(BaseModel):
    settlementId: str = "S1"
    language: Literal["en", "hi", "mr"] = "en"
    recipient: Optional[str] = None
    channel: Literal["sms", "whatsapp"] = "sms"
    riskLevel: Optional[Severity] = None
    preview: bool = False


class OfficerDecisionRequest(BaseModel):
    settlementId: str = "S1"
    decision: Literal["APPROVE", "REJECT", "OVERRIDE"] = "APPROVE"
    resourceId: Optional[str] = None
    reason: str = "Operator reviewed the recommendation."


# ------------------------------------------------------------------ helpers
async def mutate(event_type: str, fn, *args, **extra) -> Dict[str, Any]:
    """Run a state change under the lock, off the event loop, then broadcast."""
    await stop_replay_task()
    async with state_lock:
        try:
            result = await run_in_threadpool(fn, *args)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=f"Unknown id: {e}")
        state = await run_in_threadpool(state_manager.get_full_state)
    await manager.broadcast({"type": event_type, "data": state, **extra})
    return {"success": True, "result": result, "updatedState": state}


async def stop_replay_task():
    global replay_task
    if replay_task and not replay_task.done():
        replay_task.cancel()
    replay_task = None


async def stop_demo_task():
    global demo_task
    if demo_task and not demo_task.done():
        demo_task.cancel()
    demo_task = None


async def run_replay():
    frames = len(state_manager.replay_script["frames"])
    try:
        for i in range(frames):
            async with state_lock:
                await run_in_threadpool(state_manager.load_replay_frame, i, True)
                state = await run_in_threadpool(state_manager.get_full_state)
            await manager.broadcast({"type": "REPLAY_FRAME", "frame": i + 1, "data": state})
            if i < frames - 1:
                await asyncio.sleep(REPLAY_FRAME_SECONDS)
    except asyncio.CancelledError:
        async with state_lock:
            state_manager.stop_replay()


# ------------------------------------------------------------------ read endpoints
@app.get("/")
def root():
    index_file = os.path.join(_FRONTEND_DIST, "index.html")
    if os.path.isfile(index_file):
        return FileResponse(index_file)
    return {"platform": "ResQGrid", "tagline": "From scattered flood signals to prioritized rescue decisions.",
            "status": "ONLINE", "district": state_manager.district["districtName"], "realTimeWebSocket": "/ws/live"}


@app.get("/api/health")
def api_health():
    return {"platform": "ResQGrid", "status": "HEALTHY", "district": state_manager.district["districtName"], "realTimeWebSocket": "/ws/live"}


@app.get("/api/state")
async def get_system_state():
    # Wait for any in-flight recalculation so readers never see a half-applied event
    async with state_lock:
        return await run_in_threadpool(state_manager.get_full_state)


@app.get("/api/weather/live")
async def get_live_weather():
    async with state_lock:
        return (await run_in_threadpool(state_manager.get_full_state))["weather"]


@app.get("/api/settlements")
def get_settlements():
    return state_manager.settlements


@app.get("/api/roads")
def get_roads():
    return state_manager.roads


@app.get("/api/evacuation/{settlement_id}")
def get_evacuation_plan(settlement_id: str):
    try:
        return state_manager.get_evacuation_plan(settlement_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown settlement: {settlement_id}")


@app.get("/api/resources")
def get_resources():
    return state_manager.resources


@app.get("/api/alerts")
def get_alerts():
    return state_manager.get_alert_history()


@app.post("/api/alerts/send")
async def send_alert(req: AlertSendRequest):
    settlement = next((s for s in state_manager.settlements if s["id"] == req.settlementId), None)
    if settlement is None:
        raise HTTPException(status_code=404, detail=f"Unknown settlement: {req.settlementId}")
    if req.preview:
        return state_manager.preview_alert_message(req.settlementId, risk_level=req.riskLevel, language=req.language)
    payload = await run_in_threadpool(
        state_manager.send_alert_for_settlement,
        settlement,
        req.riskLevel or settlement["riskStatus"],
        language=req.language,
        recipient=req.recipient,
        channel=req.channel,
    )
    return payload


@app.get("/api/audit")
def get_audit():
    return list_audit_entries(limit=100)


@app.get("/api/evaluation")
def get_evaluation():
    return get_false_alert_evaluation()


@app.get("/api/accuracy")
def get_accuracy():
    return get_accuracy_report()


@app.post("/api/resources/decision")
async def set_resource_decision(req: OfficerDecisionRequest):
    async with state_lock:
        return await run_in_threadpool(state_manager.set_officer_decision, req.settlementId, req.decision, req.resourceId, req.reason)


@app.get("/api/forecast")
async def get_forecast():
    async with state_lock:
        weather = state_manager.get_full_state()["weather"]
        return build_short_term_forecast(state_manager.settlements, weather)


@app.get("/api/impact/compare")
def get_impact_compare():
    return get_impact_comparison()


@app.get("/api/config/status")
def get_config_status():
    has_key = bool(get_gemini_api_key())
    twilio_configured = TwilioProvider.is_configured()
    return {
        "geminiConfigured": has_key,
        "aiProvider": f"Gemini ({GEMINI_MODEL}) with local parser fallback" if has_key else "Local rule-based parser (Gemini key not set)",
        "weatherProvider": "Open-Meteo API (cached 60 s, fallback dataset)",
        "routingProvider": "NetworkX district graph + OSRM street ETA check",
        "twilioConfigured": twilio_configured,
        "alertProvider": "Twilio SMS/WhatsApp + console audit" if twilio_configured else "Console audit only (set Twilio env vars for real SMS)",
        "twilioRequiredEnv": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"],
        "webSocketClients": len(manager.active_connections),
    }


@app.post("/api/config/gemini-key")
async def update_gemini_key(req: ApiKeyConfigRequest):
    set_gemini_api_key(req.geminiApiKey)
    return {"success": True, "message": "Gemini API key configured.", "aiProvider": f"Gemini ({GEMINI_MODEL})"}


# ------------------------------------------------------------------ events (each triggers the full dynamic loop)
@app.post("/api/reports")
async def submit_ground_report(req: GroundReportRequest):
    res = await mutate("REPORT_CREATED", state_manager.submit_ground_report, req.description, req.location, req.severity, req.reporterType, req.timestamp)
    res["report"] = res["result"]
    return res


@app.post("/api/reports/photo")
async def submit_photo_report(
    image: UploadFile = File(...),
    text: Optional[str] = Form(default=None),
    latitude: Optional[float] = Form(default=None),
    longitude: Optional[float] = Form(default=None),
):
    image_bytes = await image.read()
    res = await mutate(
        "PHOTO_REPORT_CREATED",
        state_manager.submit_photo_report,
        image_bytes,
        image.content_type or "image/jpeg",
        text,
        latitude,
        longitude,
        "CITIZEN",
    )
    res["report"] = res["result"]
    res["parsed"] = res["report"].get("photoAnalysis") or res["report"].get("parsedMeaning") or {}
    return res


@app.post("/api/simulate/rainfall")
async def simulate_rainfall(req: RainfallSimulationRequest):
    return await mutate("HAZARD_UPDATE", state_manager.simulate_heavy_rainfall, req.incrementMm, event="RAINFALL_SURGE")


@app.post("/api/simulate/waterlevel")
async def simulate_waterlevel(req: WaterLevelSimulationRequest):
    return await mutate("HAZARD_UPDATE", state_manager.simulate_water_level, req.incrementM, event="WATER_LEVEL_SURGE")


@app.post("/api/simulate/road-blockage")
async def simulate_road_blockage(req: RoadBlockageRequest):
    return await mutate("ROAD_STATUS_CHANGED", state_manager.set_road_status, req.roadId, req.status, roadId=req.roadId)


@app.post("/api/simulate/step/{step_id}")
async def trigger_step(step_id: int):
    if not 1 <= step_id <= 6:
        raise HTTPException(status_code=400, detail="step must be 1-6")
    res = await mutate("HACKATHON_STEP_TRIGGERED", state_manager.trigger_demo_step, step_id, step=step_id)
    step = res["result"]
    return {"step": step["step"], "title": step["title"], "description": step["description"], "changes": step["changes"], "state": res["updatedState"]}


@app.post("/api/demo/start")
async def start_demo_story():
    global demo_task
    await stop_demo_task()
    await stop_replay_task()
    state_manager.reset_to_baseline(log_event=False)
    plan = state_manager.get_demo_story_plan()
    state = await run_in_threadpool(state_manager.get_full_state)
    narration = plan[0]["narration"]
    await manager.broadcast({"type": "DEMO_STARTED", "step": 0, "narration": narration, "data": state})
    demo_task = asyncio.create_task(run_demo_story())
    return {"success": True, "demo": {"steps": plan, "active": True, "narration": narration}, "updatedState": state}


@app.post("/api/demo/stop")
async def stop_demo_story():
    await stop_demo_task()
    async with state_lock:
        state_manager.reset_to_baseline(log_event=False)
        state = await run_in_threadpool(state_manager.get_full_state)
    await manager.broadcast({"type": "DEMO_STOPPED", "step": 0, "narration": "Demo story stopped and the system was reset to the baseline.", "data": state})
    return {"success": True, "demo": {"active": False, "narration": "Demo story stopped and the system was reset to the baseline."}, "updatedState": state}


async def run_demo_story():
    """Drive a deterministic, staged flood story over ~2 minutes using the existing state actions."""
    plan = state_manager.get_demo_story_plan()
    try:
        previous_time = 0
        for step in plan:
            delay = max(0, step["timeSeconds"] - previous_time)
            if delay > 0:
                await asyncio.sleep(delay)
            previous_time = step["timeSeconds"]
            async with state_lock:
                await run_in_threadpool(state_manager.run_demo_step, step["step"])
                state = await run_in_threadpool(state_manager.get_full_state)
            await manager.broadcast({
                "type": "DEMO_STEP",
                "step": step["step"],
                "title": step["title"],
                "narration": step["narration"],
                "data": state,
            })
    except asyncio.CancelledError:
        async with state_lock:
            state_manager.reset_to_baseline(log_event=False)
            state = await run_in_threadpool(state_manager.get_full_state)
        await manager.broadcast({"type": "DEMO_STOPPED", "narration": "Demo story stopped.", "data": state})
        raise


@app.post("/api/simulate/replay")
async def trigger_replay():
    global replay_task
    await stop_replay_task()
    replay_task = asyncio.create_task(run_replay())
    await asyncio.sleep(0.3)  # let frame 1 load so the response reflects replay mode
    async with state_lock:
        state = await run_in_threadpool(state_manager.get_full_state)
    return {"success": True, "message": "Replay started (REPLAYED / NOT LIVE)", "updatedState": state}


@app.post("/api/simulate/replay/stop")
async def stop_replay():
    await stop_replay_task()
    async with state_lock:
        state_manager.stop_replay()
        state = await run_in_threadpool(state_manager.get_full_state)
    await manager.broadcast({"type": "REPLAY_STOPPED", "data": state})
    return {"success": True, "updatedState": state}


@app.post("/api/simulate/reset")
async def reset_system():
    return await mutate("SYSTEM_RESET", state_manager.reset_to_baseline)


@app.post("/api/simulate/real-world-live")
async def set_real_world_live():
    return await mutate("REAL_WORLD_LIVE_SYNC", state_manager.set_real_world_live_mode)


@app.post("/api/routes/validate")
async def validate_route_scenario(req: ScenarioRouteRequest):
    if req.apply:
        res = await mutate("ROAD_STATUS_CHANGED", state_manager.run_route_scenario, req.settlementId, req.scenario, True)
        return {**res["result"], "updatedState": res["updatedState"]}
    async with state_lock:
        try:
            return await run_in_threadpool(state_manager.run_route_scenario, req.settlementId, req.scenario, False)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=f"Unknown id: {e}")


@app.post("/api/resources/{resource_id}/status")
async def update_resource_status(resource_id: str, req: ResourceStatusRequest):
    if req.status == "DEPLOYED" and not req.assignment:
        raise HTTPException(status_code=400, detail="assignment (settlement id) required when DEPLOYED")
    return await mutate("RESOURCE_UPDATED", state_manager.set_resource_status, resource_id, req.status, req.assignment)


@app.post("/api/explain")
async def explain_decision(req: ExplainRequest):
    async with state_lock:
        return await run_in_threadpool(state_manager.explain, req.settlementId)


# ------------------------------------------------------------------ Client-side SPA routing fallback
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api") or full_path.startswith("ws") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
        raise HTTPException(status_code=404, detail="Not found")
    if os.path.isdir(_FRONTEND_DIST):
        candidate = os.path.join(_FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        index_file = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
    return {"status": "ok", "service": "ResQGrid API", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
