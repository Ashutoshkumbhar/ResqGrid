"""
LLM layer (Gemini) — used ONLY for:
  1. extracting structured fields from free-text ground reports
  2. phrasing explanations from structured system facts

It never computes risk, priority, routes or resource decisions. Every Gemini
output is validated; on failure a deterministic parser / template is used.
"""
import base64
import json
import os
import re
from typing import Any, Dict, List, Optional

import requests

GEMINI_MODEL = "gemini-2.5-flash"
SEVERITIES = ["LOW", "MODERATE", "HIGH", "CRITICAL"]
ROAD_STATUSES = ["OPEN", "AT_RISK", "BLOCKED"]
INFRASTRUCTURE = ["BRIDGE", "ROAD", "EMBANKMENT", "DRAINAGE", "HOUSING", "SCHOOL", "HOSPITAL", "OTHER"]


def _load_env_if_needed():
    for p in [os.path.join(os.path.dirname(__file__), "..", ".env"), os.path.join(os.getcwd(), ".env")]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ.setdefault(k.strip(), v.strip())
            except Exception:
                pass


_load_env_if_needed()
CUSTOM_API_KEYS = {"gemini": os.environ.get("GEMINI_API_KEY", "")}


def set_gemini_api_key(key: str):
    CUSTOM_API_KEYS["gemini"] = key.strip()


def get_gemini_api_key() -> str:
    return CUSTOM_API_KEYS.get("gemini") or os.environ.get("GEMINI_API_KEY", "")


def _gemini(prompt: str, json_mode: bool, timeout: float, max_tokens: int = 400) -> str:
    key = get_gemini_api_key()
    if not key:
        raise RuntimeError("no key")
    config = {"temperature": 0.1, "maxOutputTokens": max_tokens, "thinkingConfig": {"thinkingBudget": 0}}
    if json_mode:
        config["responseMimeType"] = "application/json"
    res = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": key},
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": config},
        timeout=timeout,
    )
    if res.status_code != 200:
        # Never log the URL/headers: they carry the API key
        raise RuntimeError(f"Gemini HTTP {res.status_code}")
    return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


# ---------------------------------------------------------------- extraction

def _settlement_aliases(s: Dict[str, Any]) -> List[str]:
    name = s["name"].lower()
    aliases = [name]
    m = re.match(r"(village \w)\s*\(([^)]+)\)", name)
    if m:
        aliases.append(m.group(1))
        aliases.extend(w for w in re.split(r"\s+", m.group(2)) if len(w) > 3 and w not in ("riverside", "lowlands", "heights", "confluence"))
    return aliases


def match_settlement(text: str, settlements: List[Dict[str, Any]]) -> Dict[str, Any]:
    lower = text.lower()
    for s in settlements:
        if s["id"].lower() == lower.strip():
            return s
    for s in settlements:
        for alias in _settlement_aliases(s):
            if re.search(r"\b" + re.escape(alias) + r"\b", lower):
                return s
    return None


def _fallback_extract(text: str, form_location: str, form_severity: str, settlements: List[Dict[str, Any]]) -> Dict[str, Any]:
    lower = text.lower()
    target = match_settlement(text, settlements) or match_settlement(form_location, settlements)

    infra = "OTHER"
    for word, tag in [("bridge", "BRIDGE"), ("causeway", "BRIDGE"), ("embankment", "EMBANKMENT"), ("bund", "EMBANKMENT"),
                      ("drain", "DRAINAGE"), ("school", "SCHOOL"), ("hospital", "HOSPITAL"), ("house", "HOUSING"),
                      ("road", "ROAD"), ("street", "ROAD"), ("highway", "ROAD")]:
        if word in lower:
            infra = tag
            break

    road_status = "OPEN"
    if any(w in lower for w in ["blocked", "block", "impassable", "cut off", "washed away", "closed", "submerged road", "collapsed"]):
        road_status = "BLOCKED"
    elif any(w in lower for w in ["water on road", "waterlogged", "overflowing", "at risk", "rising"]):
        road_status = "AT_RISK"

    severity = form_severity.upper() if form_severity and form_severity.upper() in SEVERITIES else "MODERATE"
    if any(w in lower for w in ["washed away", "trapped", "drowning", "collapsed", "roof"]):
        severity = "CRITICAL"
    elif any(w in lower for w in ["entered houses", "entered nearby houses", "into houses", "blocked", "submerged"]) and severity in ("LOW", "MODERATE"):
        severity = "HIGH"

    signals = sum([target is not None and match_settlement(text, settlements) is not None, infra != "OTHER", road_status != "OPEN"])
    return {
        "location": target["name"] if target else form_location,
        "settlementId": target["id"] if target else None,
        "severity": severity,
        "roadStatus": road_status,
        "infrastructure": infra,
        "confidence": round(0.72 + 0.06 * signals, 2),
        "source": "LOCAL_RULE_PARSER",
    }


_extraction_cache: Dict[str, Dict[str, Any]] = {}


def extract_ground_report_info(text: str, form_location: str, form_severity: str, settlements: List[Dict[str, Any]]) -> Dict[str, Any]:
    cache_key = f"{text}|{form_location}|{form_severity}"
    if cache_key in _extraction_cache:
        return dict(_extraction_cache[cache_key])
    result = _extract(text, form_location, form_severity, settlements)
    if result["source"].startswith("GEMINI"):
        _extraction_cache[cache_key] = result
    return dict(result)


def _extract(text: str, form_location: str, form_severity: str, settlements: List[Dict[str, Any]]) -> Dict[str, Any]:
    if get_gemini_api_key():
        try:
            options = "\n".join(f"- {s['id']}: {s['name']}" for s in settlements)
            prompt = f"""You extract structured fields from a flood ground report. Do not make decisions.
Report: "{text}"
Reporter-selected location: "{form_location}"
Known settlements:
{options}
Return ONLY JSON: {{"settlementId": one of the ids above or null, "severity": {SEVERITIES}, "roadStatus": {ROAD_STATUSES}, "infrastructure": {INFRASTRUCTURE}, "confidence": number 0-1 reflecting how explicit the report is}}"""
            parsed = json.loads(_gemini(prompt, json_mode=True, timeout=8))
            for k in ("severity", "roadStatus", "infrastructure"):
                if isinstance(parsed.get(k), str):
                    parsed[k] = parsed[k].strip().upper().replace(" ", "_")
            ids = {s["id"]: s for s in settlements}
            sid = parsed.get("settlementId")
            if sid not in ids:
                fallback_target = match_settlement(form_location, settlements)
                sid = fallback_target["id"] if fallback_target else None
            if parsed.get("severity") not in SEVERITIES or parsed.get("roadStatus") not in ROAD_STATUSES:
                raise ValueError(f"invalid enum in {parsed}")
            infra = parsed.get("infrastructure")
            if infra not in INFRASTRUCTURE or infra == "OTHER":
                # Keyword match is reliable for infrastructure; prefer it over a vague LLM answer
                infra = _fallback_extract(text, form_location, form_severity, settlements)["infrastructure"]
            return {
                "location": ids[sid]["name"] if sid else form_location,
                "settlementId": sid,
                "severity": parsed["severity"],
                "roadStatus": parsed["roadStatus"],
                "infrastructure": infra,
                "confidence": round(max(0.0, min(0.99, float(parsed.get("confidence", 0.85)))), 2),
                "source": f"GEMINI ({GEMINI_MODEL})",
            }
        except Exception as e:
            print(f"[AI] Gemini extraction failed, using local parser: {e}")
    return _fallback_extract(text, form_location, form_severity, settlements)


# ---------------------------------------------------------------- explanation

def _numbers(text: str) -> set:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def template_explanation(f: Dict[str, Any]) -> str:
    parts = [f"{f['settlement']} is priority #{f['priorityRank']} (score {f['priorityScore']}) with {f['riskStatus'].lower()} flood risk of {f['riskScore']}/100"]
    if f["evidence"]:
        parts.append("driven by " + ", ".join(e[0].lower() + e[1:] for e in f["evidence"][:3]))
    text = "; ".join(parts) + ". "
    text += f"{f['population']:,} people are exposed. "
    if f["routeStatus"] == "ALTERNATIVE_VALID":
        text += f"The primary road ({', '.join(f['blockedRoads'])}) is blocked, so {f['resource']} is routed via {', '.join(f['routeRoads'])} (ETA {f['etaMinutes']} min)."
    elif f["routeStatus"] == "VALID":
        text += f"{f['resource']} can reach it via {', '.join(f['routeRoads'])} (ETA {f['etaMinutes']} min)."
    else:
        text += "No available ground unit can reach it, so escalation to aerial/boat support is required."
    return text


def explain_decision(facts: Dict[str, Any], use_llm: bool = True) -> Dict[str, Any]:
    fallback = template_explanation(facts)
    if use_llm and get_gemini_api_key():
        try:
            prompt = f"""Rewrite these structured flood-response facts as a clear 2-3 sentence explanation for a response coordinator.
Rules: use ONLY the facts given; do not add numbers, places, resources, casualties or recommendations that are not in the facts; do not change any value.
FACTS (JSON): {json.dumps(facts)}"""
            text = _gemini(prompt, json_mode=False, timeout=8, max_tokens=220)
            allowed = _numbers(json.dumps(facts)) | {"1", "2", "3"}
            invented = _numbers(text) - allowed
            if text and not invented:
                return {"text": text, "source": f"GEMINI ({GEMINI_MODEL})", "facts": facts, "guard": "PASSED"}
            print(f"[AI] Explanation rejected, invented numbers: {invented}")
            return {"text": fallback, "source": "TEMPLATE", "facts": facts, "guard": f"LLM output rejected (unsupported numbers: {', '.join(sorted(invented))})"}
        except Exception as e:
            print(f"[AI] Gemini explanation failed, using template: {e}")
            return {"text": fallback, "source": "TEMPLATE", "facts": facts, "guard": "Gemini unavailable — deterministic template used"}
    return {"text": fallback, "source": "TEMPLATE", "facts": facts, "guard": "Template (no LLM call)"}


def parse_photo_report(image_bytes: bytes, mime_type: str = "image/jpeg", text: Optional[str] = None, latitude: Optional[float] = None, longitude: Optional[float] = None) -> Dict[str, Any]:
    """Use Gemini vision when available; otherwise return a manual-review result.

    The returned payload deliberately keeps the structure simple and deterministic so
    the API can pass it through the existing report pipeline without extra schema
    logic.
    """
    manual_review = {
        "manualReview": True,
        "flooded": None,
        "waterDepth": "unknown",
        "roadPassable": None,
        "confidence": 0.0,
        "source": "MANUAL_REVIEW",
        "notes": "Gemini vision is not configured; this photo needs manual review.",
        "text": text or "",
        "latitude": latitude,
        "longitude": longitude,
    }

    key = get_gemini_api_key()
    if not key or not image_bytes:
        return manual_review

    try:
        prompt = (
            "Inspect this flood scene and estimate only from the image. Return JSON only with fields: "
            "{\"flooded\": boolean, \"waterDepth\": \"ankle\"|\"knee\"|\"waist\"|\"above\"|\"unknown\", "
            "\"roadPassable\": boolean|null, \"confidence\": number, \"notes\": string}. "
            "If the image is unclear, set flooded to false and roadPassable to null with a low confidence. "
            "Do not invent extra facts."
        )
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type or "image/jpeg", "data": base64.b64encode(image_bytes).decode("utf-8")}},
                ]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 220, "thinkingConfig": {"thinkingBudget": 0}},
        }
        res = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            headers={"x-goog-api-key": key},
            json=payload,
            timeout=15,
        )
        if res.status_code != 200:
            raise RuntimeError(f"Gemini vision failed: HTTP {res.status_code}")
        raw = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        parsed = json.loads(raw)
        flooded = bool(parsed.get("flooded")) if isinstance(parsed.get("flooded"), bool) else None
        depth = str(parsed.get("waterDepth") or "unknown").lower()
        if depth not in {"ankle", "knee", "waist", "above", "unknown"}:
            depth = "unknown"
        road = parsed.get("roadPassable")
        if road is not None and not isinstance(road, bool):
            if str(road).lower() in {"yes", "true", "passable"}:
                road = True
            elif str(road).lower() in {"no", "false", "blocked", "impassable"}:
                road = False
            else:
                road = None
        result = {
            "manualReview": False,
            "flooded": flooded,
            "waterDepth": depth,
            "roadPassable": road,
            "confidence": round(max(0.0, min(0.99, float(parsed.get("confidence", 0.5)))), 2),
            "source": "GEMINI_VISION",
            "notes": str(parsed.get("notes") or "Photo assessed by Gemini vision."),
            "text": text or "",
            "latitude": latitude,
            "longitude": longitude,
        }
        return result
    except Exception as exc:
        print(f"[AI] Gemini vision parse failed, falling back to manual review: {exc}")
        return {
            **manual_review,
            "notes": f"Gemini vision failed; manual review required ({exc}).",
        }
