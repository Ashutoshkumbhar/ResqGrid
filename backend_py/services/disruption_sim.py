"""
Disruption simulator (P2).

Generates SIMULATED road-closure / reopening histories that are driven by REAL
hourly rainfall from the Open-Meteo archive API (no API key needed).

What is real and what is simulated
----------------------------------
REAL       : hourly rainfall (Open-Meteo archive). If the archive cannot be
             reached and no cache exists, a SYNTHETIC rain series is used and
             labelled as such.
SIMULATED  : when each road closes and reopens, and the citizen reports about
             it. These come from the documented rule below, plus randomness.

The closure rule (documented so judges can read it)
---------------------------------------------------
For each road and hour t:
    thr6  = 55 mm, reduced for bridges (x0.65), causeways (x0.70),
            flood-prone roads (x0.85), low ground < 12 m (x0.85),
            then multiplied by a HIDDEN per-road drainage factor (0.8 - 1.25)
    z     = rain_6h / thr6 + 0.5 * rain_24h / (2.2 * thr6)
            (rain is multiplied by a HIDDEN per-road local factor 0.85 - 1.15)
    OPEN   -> CLOSED with probability sigmoid(6 * (z - 1))   (small random
              closures also happen when z is low: debris, accidents)
    CLOSED -> OPEN after a minimum hold time (2 h, +3 h for bridges) once
              z < 0.6, with probability 0.5 per hour
Citizen reports: a closed road gets a BLOCKED report with prob 0.35 per hour,
an open road gets a mistaken BLOCKED report with prob 0.02 per hour, and a
road that just reopened gets an OPEN report with prob 0.4.

Honest limitation: because the labels come from our own rule, a model trained
on them mostly learns this rule. The HIDDEN factors and the random noise stop
it from being a perfect lookup, but the results show the METHOD works on this
setup. They are not real-world accuracy.
"""
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import requests

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "cache"))
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

BASE_THRESHOLD_6H_MM = 55.0


def _seed(*parts: Any) -> int:
    """Stable integer seed from any parts (same input -> same random numbers)."""
    text = "|".join(str(p) for p in parts)
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)


# ---------------------------------------------------------------- rainfall
def fetch_archive_rain(lat: float, lon: float, start_date: str, end_date: str, timeout: int = 25) -> Optional[Dict[str, Any]]:
    """
    Hourly rainfall (mm) from the Open-Meteo archive. Saved to data/cache so the
    demo still works offline. Returns None if the API and the cache both fail.
    Dates are 'YYYY-MM-DD'. The archive lags real time by a few days.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"archive_{lat:.2f}_{lon:.2f}_{start_date}_{end_date}.json")
    try:
        resp = requests.get(
            ARCHIVE_URL,
            params={"latitude": lat, "longitude": lon, "start_date": start_date, "end_date": end_date,
                    "hourly": "precipitation", "timezone": "Asia/Kolkata"},
            timeout=timeout,
        )
        resp.raise_for_status()
        hourly = resp.json()["hourly"]
        rain = [0.0 if v is None else float(v) for v in hourly["precipitation"]]
        out = {"source": "OPEN_METEO_ARCHIVE", "lat": lat, "lon": lon, "start": start_date, "end": end_date,
               "time": hourly["time"], "rain": rain, "fetchedAt": datetime.now(timezone.utc).isoformat()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f)
        return out
    except Exception as exc:
        print(f"[DisruptionSim] Open-Meteo archive failed: {exc}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        cached["source"] = "CACHED_OPEN_METEO_ARCHIVE"
        return cached
    except Exception:
        return None


def synthetic_monsoon_rain(n_hours: int = 24 * 120, start: str = "2025-06-01T00:00", seed: int = 11) -> Dict[str, Any]:
    """Offline stand-in rain series. Always labelled SYNTHETIC_RAIN, never presented as real."""
    rng = np.random.default_rng(seed)
    rain = np.zeros(n_hours)
    wet = rng.random(n_hours) < 0.18
    rain[wet] = rng.gamma(1.2, 0.8, int(wet.sum()))
    for _ in range(max(1, n_hours // 60)):
        centre = int(rng.integers(0, n_hours))
        width = int(rng.integers(4, 18))
        peak = float(rng.gamma(2.5, 4.0))
        idx = np.arange(max(0, centre - width), min(n_hours, centre + width))
        rain[idx] += peak * np.exp(-0.5 * ((idx - centre) / (width / 2.5)) ** 2) * float(rng.uniform(0.6, 1.2))
    t0 = datetime.fromisoformat(start)
    times = [(t0 + timedelta(hours=i)).isoformat(timespec="minutes") for i in range(n_hours)]
    return {"source": "SYNTHETIC_RAIN", "time": times, "rain": [round(float(x), 2) for x in rain]}


# ---------------------------------------------------------------- events
@dataclass
class Event:
    event_id: str
    group_id: str        # all scaled copies of one rain window share a group (kept together in train/test splits)
    scale: float         # rain multiplier (stress variants of the same real window)
    start_time: str
    rain: np.ndarray     # hourly mm


def make_events(series: Dict[str, Any], window_h: int = 96, step_h: int = 48,
                scales=(1.0, 1.6, 2.4), min_total_mm: float = 3.0) -> List[Event]:
    """Cut the rain series into overlapping windows. Scaled copies stress-test heavier storms."""
    rain = np.asarray(series["rain"], dtype=float)
    times = series["time"]
    events: List[Event] = []
    for s in range(0, len(rain) - window_h + 1, step_h):
        window = rain[s:s + window_h]
        if window.sum() < min_total_mm:
            continue
        gid = f"W{s:05d}"
        for sc in scales:
            events.append(Event(event_id=f"{gid}x{sc:g}", group_id=gid, scale=float(sc),
                                start_time=str(times[s]), rain=window * sc))
    return events


# ---------------------------------------------------------------- roads
def road_profile(road: Dict[str, Any], node_elev: Dict[str, float]) -> Dict[str, Any]:
    """Static, observable road attributes (these ARE allowed as model features)."""
    infra = str(road.get("infrastructure") or "").upper()
    name = str(road.get("name") or "").upper()
    rel = min(node_elev.get(road["source"], 20.0), node_elev.get(road["destination"], 20.0))
    return {
        "road_id": road["id"],
        "is_bridge": float("BRIDGE" in infra or "BRIDGE" in name),
        "is_causeway": float("CAUSEWAY" in infra or "CAUSEWAY" in name),
        "flood_prone": float(bool(road.get("floodProne"))),
        "rel_elev_m": float(rel),
        "distance_km": float(road.get("distanceKm") or 1.0),
    }


def _hidden(road_id: str, seed: int) -> Dict[str, float]:
    """Hidden per-road factors. NOT available to the model, so it cannot just memorise the rule."""
    rng = np.random.default_rng(_seed("hidden", road_id, seed))
    return {"drainage": float(rng.uniform(0.8, 1.25)), "spatial": float(rng.uniform(0.85, 1.15))}


def _threshold_6h(p: Dict[str, Any]) -> float:
    thr = BASE_THRESHOLD_6H_MM
    if p["is_bridge"]:
        thr *= 0.65
    if p["is_causeway"]:
        thr *= 0.70
    if p["flood_prone"]:
        thr *= 0.85
    if p["rel_elev_m"] < 12:
        thr *= 0.85
    return thr


def simulate_event(event: Event, profiles: List[Dict[str, Any]], seed: int = 0) -> Dict[str, Any]:
    """
    Returns {"road_ids", "closed" (roads x hours, bool), "rep_hours", "rep_signs"}.
    closed[i, h] = road i is closed during hour h. Reports: sign +1 = BLOCKED, -1 = OPEN.
    """
    rain = event.rain
    T = len(rain)
    cs = np.concatenate([[0.0], np.cumsum(rain)])
    idx = np.arange(T)

    def rolling(k: int) -> np.ndarray:
        return cs[idx + 1] - cs[np.maximum(0, idx + 1 - k)]

    r6, r24 = rolling(6), rolling(24)
    closed = np.zeros((len(profiles), T), dtype=bool)
    rep_hours: List[np.ndarray] = []
    rep_signs: List[np.ndarray] = []

    for i, prof in enumerate(profiles):
        hid = _hidden(prof["road_id"], seed)
        thr6 = _threshold_6h(prof) * hid["drainage"]
        z = (r6 * hid["spatial"]) / thr6 + 0.5 * (r24 * hid["spatial"]) / (2.2 * thr6)
        rng = np.random.default_rng(_seed(event.event_id, prof["road_id"], seed))
        min_hold = 2 + (3 if prof["is_bridge"] else 0)
        state, held = False, 0
        for t in range(T):
            if not state:
                p_close = 1.0 / (1.0 + math.exp(-6.0 * (z[t] - 1.0)))
                if rng.random() < p_close:
                    state, held = True, 0
            else:
                held += 1
                if held >= min_hold and z[t] < 0.6 and rng.random() < 0.5:
                    state = False
            closed[i, t] = state
        rh, rs = [], []
        for t in range(T):
            if closed[i, t]:
                if rng.random() < 0.35:
                    rh.append(t); rs.append(1)
            else:
                if rng.random() < 0.02:
                    rh.append(t); rs.append(1)          # mistaken blockage report
                if t > 0 and closed[i, t - 1] and rng.random() < 0.4:
                    rh.append(t); rs.append(-1)         # "it is open again" report
        rep_hours.append(np.asarray(rh, dtype=float))
        rep_signs.append(np.asarray(rs, dtype=float))

    return {"road_ids": [p["road_id"] for p in profiles], "closed": closed,
            "rep_hours": rep_hours, "rep_signs": rep_signs}