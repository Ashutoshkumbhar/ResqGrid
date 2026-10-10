"""
Baseline-vs-predictive evaluation on HELD-OUT events (P2, Addition 2).

Both methods get the same trip at the same decision time:
  BASELINE   : shortest route over roads that are open RIGHT NOW (current-status-only routing)
  PREDICTIVE : route with the best chance of staying open until the team gets there

Each planned route is then driven against the simulated truth, hour by hour:
  - if the team reaches a road that is closed at that moment, the planned route was INVALID
  - the team re-plans once from where it stands (current-status routing); if that also fails
    or no path exists, the village is UNSERVED
Reported: invalid-route rate, re-plan rate, unserved rate, response time, paired differences.

All results are on SIMULATED closures driven by real (or labelled synthetic) rain.
They show the method works on this setup, not real-world accuracy.
"""
import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from services.access_model import (AccessPredictor, FEATURES, HORIZONS, approx_rain_features)
from services.disruption_sim import Event, road_profile
from services.routing_engine import (MOBILISATION_MIN, _describe, _shortest, build_graph, plan_route_predictive)

UNSERVED_PENALTY_MIN = 240.0   # used only for the "penalised" mean response time


# ---------------------------------------------------------------- toy network (offline testing)
def toy_network() -> Dict[str, Any]:
    """A small district graph so everything can be tested without the platform data."""
    def node(i, name, lat, lon, kind="SETTLEMENT"):
        return {"id": i, "name": name, "latitude": lat, "longitude": lon, "kind": kind}

    nodes = {n["id"]: n for n in [
        node("BASE", "Rescue Base", 18.60, 73.80, "BASE"), node("J1", "Junction", 18.58, 73.84, "JUNCTION"),
        node("S1", "Village A", 18.62, 73.86), node("S2", "Village B", 18.57, 73.89), node("S3", "Village C", 18.55, 73.82),
        node("S4", "Village D", 18.52, 73.86), node("S5", "Village E", 18.54, 73.78), node("S6", "Village F", 18.60, 73.92),
    ]}

    def road(rid, name, a, b, km, infra="ROAD", prone=False):
        na, nb = nodes[a], nodes[b]
        return {"id": rid, "name": name, "source": a, "destination": b, "distanceKm": km, "status": "OPEN",
                "infrastructure": infra, "floodProne": prone,
                "coordinates": [[na["latitude"], na["longitude"]], [nb["latitude"], nb["longitude"]]]}

    roads = [
        road("R1", "Riverside Causeway", "BASE", "S1", 6, "CAUSEWAY", True),
        road("R2", "Hill Road", "BASE", "J1", 8),
        road("R3", "Ridge Road", "J1", "S1", 7),
        road("R4", "Sangvi Bridge", "S1", "S2", 4, "BRIDGE", True),
        road("R5", "Upper Road", "J1", "S2", 9),
        road("R6", "Plateau Road", "J1", "S3", 7),
        road("R7", "Mula Causeway", "S3", "S4", 5, "CAUSEWAY", True),
        road("R8", "Western Road", "BASE", "S5", 12),
        road("R9", "Pawana Link", "S5", "S4", 6),
        road("R10", "Kasarwadi Bridge", "S2", "S6", 5, "BRIDGE", True),
        road("R11", "Ring Road", "J1", "S6", 11),
        road("R12", "Wakad Bridge Causeway", "S3", "S5", 6, "BRIDGE", True),
    ]
    settlements = [{"id": f"S{i}", "name": nodes[f"S{i}"]["name"], "population": 2000 + 500 * i,
                    "relativeElevation": e} for i, e in zip(range(1, 7), (9, 8, 22, 15, 28, 10))]
    resources = [
        {"id": "BOAT-01", "name": "Rescue Boat 01", "type": "BOAT", "nodeId": "BASE", "locationName": "Rescue Base",
         "speedKmh": 30, "mobile": True, "status": "AVAILABLE"},
        {"id": "AMB-01", "name": "Ambulance 01", "type": "AMBULANCE", "nodeId": "J1", "locationName": "Junction",
         "speedKmh": 40, "mobile": True, "status": "AVAILABLE"},
    ]
    return {"nodes": nodes, "roads": roads, "settlements": settlements, "resources": resources,
            "center": (18.57, 73.85)}


def node_elevations(settlements: List[Dict[str, Any]]) -> Dict[str, float]:
    return {s["id"]: float(s.get("relativeElevation", 20.0)) for s in settlements}


# ---------------------------------------------------------------- trip execution
def _status_roads(roads: List[Dict[str, Any]], closed_col: np.ndarray) -> List[Dict[str, Any]]:
    return [{**r, "status": "BLOCKED" if closed_col[i] else "OPEN"} for i, r in enumerate(roads)]


def _path_to_road_ids(G, path: List[str]) -> List[str]:
    return [G[u][v]["road"]["id"] for u, v in zip(path, path[1:])]


def execute_trip(road_seq: List[str], start_node: str, dst: str, roads: List[Dict[str, Any]], road_index: Dict[str, int],
                 closed: np.ndarray, t0: int, speed_kmh: float) -> Dict[str, Any]:
    """Drive a planned route against the simulated truth. One re-plan allowed."""
    by_id = {r["id"]: r for r in roads}
    T = closed.shape[1]
    clock = t0 + MOBILISATION_MIN / 60.0          # hours since event start
    elapsed = float(MOBILISATION_MIN)
    node, seq, replans, invalid = start_node, list(road_seq), 0, False
    while True:
        failed = False
        for rid in seq:
            r = by_id[rid]
            hour = min(int(clock), T - 1)
            if closed[road_index[rid], hour]:
                if replans == 0:
                    invalid = True
                failed = True
                break
            minutes = r["distanceKm"] / max(speed_kmh, 1) * 60.0
            clock += minutes / 60.0
            elapsed += minutes
            node = r["destination"] if r["source"] == node else r["source"]
        if not failed:
            return {"invalid": invalid, "replanned": replans > 0, "unserved": False, "response_min": round(elapsed, 1)}
        if replans >= 1:
            return {"invalid": invalid, "replanned": True, "unserved": True, "response_min": None}
        replans += 1
        hour = min(int(clock), T - 1)
        G = build_graph(_status_roads(roads, closed[:, hour]), respect_status=True)
        path = _shortest(G, node, dst)
        if path is None:
            return {"invalid": invalid, "replanned": True, "unserved": True, "response_min": None}
        seq = _path_to_road_ids(G, path)


def _nearest_horizon(minutes: float) -> int:
    hours = max(1.0, math.ceil(minutes / 60.0))
    return min(HORIZONS, key=lambda h: abs(h - hours))


# ---------------------------------------------------------------- comparison
def run_comparison(events: List[Event], sims: Dict[str, Dict[str, Any]], roads: List[Dict[str, Any]],
                   nodes: Dict[str, Any], resources: List[Dict[str, Any]], settlements: List[Dict[str, Any]],
                   predictor: AccessPredictor, profiles: Dict[str, Dict[str, Any]],
                   decision_step: int = 6, min_t: int = 24, max_trips: Optional[int] = None,
                   seed: int = 0, risk_aversion_km: float = 25.0) -> Dict[str, Any]:
    from services.access_model import _forecast_noise, forecast_feature, observed_features

    road_index = {r["id"]: i for i, r in enumerate(roads)}
    prof_list = [profiles[r["id"]] for r in roads]
    mobile = [r for r in resources if r.get("mobile") and r.get("status") != "UNAVAILABLE"]
    rows: List[Dict[str, Any]] = []
    skipped_unreachable = 0

    for ev in events:
        sim = sims[ev.event_id]
        closed = sim["closed"]
        T = closed.shape[1]
        for t in range(min_t, T - 8, decision_step):
            if not closed[:, t - 1].any() and ev.rain[max(0, t - 6):t].sum() < 5.0:
                continue                                  # quiet moment: both methods would be identical
            roads_t = _status_roads(roads, closed[:, t - 1])   # what the operator can see at decision time
            G_t = build_graph(roads_t, respect_status=True)
            prob_cache: Dict[int, Dict[str, Any]] = {}

            def probs_for(h: int):
                if h not in prob_cache:
                    state = {}
                    for i, r in enumerate(roads):
                        o = observed_features(ev.rain, closed[i], sim["rep_hours"][i], sim["rep_signs"][i], prof_list[i], t)
                        state[r["id"]] = {k: o[k] for k in ("hours_in_state", "report_signal", "reports_3h")}
                    o0 = observed_features(ev.rain, closed[0], sim["rep_hours"][0], sim["rep_signs"][0], prof_list[0], t)
                    rain = {"rain_1h": o0["rain_1h"], "rain_3h": o0["rain_3h"], "rain_6h": o0["rain_6h"],
                            "rain_24h": o0["rain_24h"],
                            "fc_rain_h": forecast_feature(ev.rain, t, h, _forecast_noise(ev.event_id, t, h))}
                    prob_cache[h] = predictor.predict(roads_t, profiles, rain, h, state)
                return prob_cache[h]

            for res in mobile:
                for s in settlements:
                    src, dst = res["nodeId"], s["id"]
                    base_nodes = _shortest(G_t, src, dst)
                    if base_nodes is None:
                        skipped_unreachable += 1
                        continue
                    base_desc = _describe(G_t, base_nodes, nodes)
                    speed = res.get("speedKmh") or 40
                    base_eta = base_desc["distanceKm"] / max(speed, 1) * 60 + MOBILISATION_MIN
                    pr = probs_for(_nearest_horizon(base_eta))
                    pred = plan_route_predictive(res, {"id": dst, "name": s["name"]}, nodes, roads_t, pr["p"], pr["p_low"],
                                                 risk_aversion_km=risk_aversion_km)
                    if pred.get("escalationRequired"):
                        pred_ids = base_desc["roadIds"]          # fall back to baseline route if nothing acceptable
                        pred_rel = None
                    else:
                        pred_ids, pred_rel = pred["roadIds"], pred["reliability"]
                    for method, ids, rel in (("BASELINE_CURRENT_STATUS", base_desc["roadIds"], None),
                                             ("PREDICTIVE", pred_ids, pred_rel)):
                        out = execute_trip(ids, src, dst, roads, road_index, closed, t, speed)
                        rows.append({"event_id": ev.event_id, "group_id": ev.group_id, "scale": ev.scale,
                                     "decision_hour": t, "unit": res["id"], "settlement": dst, "method": method,
                                     "planned_roads": ">".join(ids), "predicted_reliability": rel, **out})
    df = pd.DataFrame(rows)
    if max_trips and len(df) > 2 * max_trips:
        keep = df.drop_duplicates(["event_id", "decision_hour", "unit", "settlement"]).sample(max_trips, random_state=seed)
        df = df.merge(keep[["event_id", "decision_hour", "unit", "settlement"]], how="inner")
    return {"trips": df, "summary": summarise(df), "skippedUnreachableAtDecision": skipped_unreachable}


def summarise(df: pd.DataFrame) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for method, g in df.groupby("method"):
        served = g[~g["unserved"]]
        out[method] = {
            "trips": int(len(g)),
            "invalidRoutePct": round(100 * g["invalid"].mean(), 2),
            "replanPct": round(100 * g["replanned"].mean(), 2),
            "unservedPct": round(100 * g["unserved"].mean(), 2),
            "meanResponseMinServed": round(float(served["response_min"].mean()), 1) if len(served) else None,
            "meanResponseMinPenalised": round(float(g["response_min"].fillna(UNSERVED_PENALTY_MIN).mean()), 1),
        }
    key = ["event_id", "decision_hour", "unit", "settlement"]
    b = df[df["method"] == "BASELINE_CURRENT_STATUS"].set_index(key)
    p = df[df["method"] == "PREDICTIVE"].set_index(key)
    j = b.join(p, lsuffix="_b", rsuffix="_p", how="inner")
    if len(j):
        out["paired"] = {
            "trips": int(len(j)),
            "baselineInvalid_predictiveValid": int((j["invalid_b"] & ~j["invalid_p"]).sum()),
            "predictiveInvalid_baselineValid": int((~j["invalid_b"] & j["invalid_p"]).sum()),
            "unservedAvoidedByPredictive": int((j["unserved_b"] & ~j["unserved_p"]).sum()),
            "unservedOnlyUnderPredictive": int((~j["unserved_b"] & j["unserved_p"]).sum()),
            "routesDiffer": int((j["planned_roads_b"] != j["planned_roads_p"]).sum()),
        }
    return out