"""
Rainfall / weather from Open-Meteo (cached 60 s) with a clearly-labelled fallback dataset.
"""
import os
import time
from typing import Any, Dict, List

import requests

PUNE_LAT = 18.5780
PUNE_LON = 73.7950
CACHE_SECONDS = int(os.getenv("WEATHER_CACHE_SECONDS", "60"))
FORECAST_HOURS = int(os.getenv("FORECAST_HORIZON_HOURS", "24"))

FALLBACK_WEATHER = {
    "source": "FALLBACK_DATASET",
    "status": "FALLBACK",
    "location": "Pune District (Mula-Pawana Basin)",
    "latitude": PUNE_LAT,
    "longitude": PUNE_LON,
    "temperature": 24.0,
    "precipitation": 0.0,
    "past24hMm": 0.0,
    "next24hMm": 0.0,
    "maxIntensityNext24h": 0.0,
    "weatherCode": 3,
    "weatherDescription": "Open-Meteo unreachable — offline fallback values",
    "windSpeed": 10.0,
    "hourlyForecast": [
        {"time": f"2026-08-15T{(i // 2):02d}:00:00+05:30", "precipitation": max(0.0, 1.5 + ((i * 3) % 16) * 0.7)}
        for i in range(FORECAST_HOURS)
    ],
}

_cache: Dict[str, Any] = {"at": 0.0, "data": None}


def _build_hourly_forecast(times: List[str], precip: List[float]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for t, p in zip(times, precip):
        records.append({"time": t, "precipitation": float(p or 0.0)})
    return records[:FORECAST_HOURS]


def fetch_live_weather(lat: float = PUNE_LAT, lon: float = PUNE_LON) -> Dict[str, Any]:
    if _cache["data"] and time.time() - _cache["at"] < CACHE_SECONDS:
        return _cache["data"]
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,precipitation,weather_code,wind_speed_10m",
                "hourly": "precipitation",
                "past_days": 1, "forecast_days": 2, "timezone": "Asia/Kolkata",
            },
            timeout=4,
        )
        if resp.status_code == 200:
            data = resp.json()
            current = data.get("current", {})
            hourly = data.get("hourly", {})
            times, precip = hourly.get("time", []), hourly.get("precipitation", [])
            now_key = (current.get("time") or "")[:13]
            idx = next((i for i, t in enumerate(times) if t[:13] == now_key), 24)
            past = [p or 0 for p in precip[max(0, idx - 24):idx]]
            future = [p or 0 for p in precip[idx:idx + FORECAST_HOURS]]
            hourly_forecast = _build_hourly_forecast(times[idx:idx + FORECAST_HOURS], precip[idx:idx + FORECAST_HOURS])
            weather = {
                "source": "OPEN_METEO_API",
                "status": "LIVE",
                "location": "Pune District (Mula-Pawana Basin)",
                "latitude": lat, "longitude": lon,
                "temperature": current.get("temperature_2m"),
                "precipitation": current.get("precipitation", 0.0),
                "past24hMm": round(sum(past), 1),
                "next24hMm": round(sum(future), 1),
                "maxIntensityNext24h": round(max(future), 1) if future else 0.0,
                "weatherCode": current.get("weather_code"),
                "weatherDescription": "Live observation + 24h forecast (Open-Meteo)",
                "windSpeed": current.get("wind_speed_10m"),
                "observedAt": current.get("time"),
                "hourlyForecast": hourly_forecast,
            }
            _cache.update(at=time.time(), data=weather)
            return weather
    except Exception as e:
        print(f"[WeatherService] Open-Meteo request failed, using fallback dataset: {e}")

    # Retry sooner than a full cache window when on fallback
    _cache.update(at=time.time() - CACHE_SECONDS + 15, data=FALLBACK_WEATHER)
    return FALLBACK_WEATHER
