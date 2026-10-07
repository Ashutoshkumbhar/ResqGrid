"""
Short-term flood forecast.

This intentionally reuses the same explainable risk model already used in the live
state manager. For each settlement, we project a 0-24h rainfall and water-level
trend and then run `calculate_flood_risk()` for each hour so the UI receives a
consistent risk score curve instead of a second, divergent model.
"""
import copy
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from services.data_processing import classify_water_level
from services.risk_engine import calculate_flood_risk
from services.weather_service import fetch_live_weather

DEFAULT_FORECAST_HOURS = int(os.getenv("FORECAST_HORIZON_HOURS", "24"))


def _precipitation_values(weather: Dict[str, Any], hours: int = DEFAULT_FORECAST_HOURS) -> List[float]:
    hourly = weather.get("hourlyForecast") or weather.get("hourly") or []
    values: List[float] = []
    if hourly and isinstance(hourly[0], dict):
        values = [float((item or {}).get("precipitation", 0.0) or 0.0) for item in hourly]
    elif hourly and isinstance(hourly[0], (int, float)):
        values = [float(v) for v in hourly]
    if not values:
        values = [0.0] * hours
    if len(values) < hours:
        values.extend([0.0] * (hours - len(values)))
    return values[:hours]


def build_short_term_forecast(settlements: List[Dict[str, Any]], weather: Dict[str, Any] | None = None, hours: int = DEFAULT_FORECAST_HOURS) -> Dict[str, Any]:
    """Return settlement-level, hour-by-hour risk forecasts for the next 24h."""
    live_weather = weather or fetch_live_weather()
    hourly_precip = _precipitation_values(live_weather, hours)
    forecast = {"generatedAt": datetime.now(timezone.utc).isoformat(), "hours": list(range(hours + 1)), "settlements": {}}

    for settlement in settlements:
        sid = settlement.get("id")
        reports = settlement.get("groundReports", []) or []
        series: List[Dict[str, Any]] = []
        base_rainfall = float(settlement.get("rainfall", 0.0) or 0.0)
        base_intensity = float(settlement.get("rainfallIntensity", 0.0) or 0.0)
        base_level = float(settlement.get("waterLevelMeters", 0.0) or 0.0)

        for hour in range(hours + 1):
            acc = base_rainfall + sum(hourly_precip[:hour])
            peak = max(base_intensity, hourly_precip[hour - 1] if hour > 0 else base_intensity)
            rising_water = base_level + (hour * 0.06) + (sum(hourly_precip[:hour]) * 0.02)
            projected = copy.deepcopy(settlement)
            projected["rainfall"] = round(acc, 1)
            projected["rainfallIntensity"] = round(peak, 1)
            projected["waterLevelMeters"] = round(rising_water, 2)
            projected["waterLevel"] = classify_water_level(rising_water)
            projected["groundReports"] = reports
            projected["riskScore"] = 0
            projected["riskStatus"] = "LOW"
            risk = calculate_flood_risk(projected, reports)
            series.append({
                "hour": hour,
                "riskScore": risk["riskScore"],
                "riskStatus": risk["riskStatus"],
                "riskFactors": risk["riskFactors"],
                "evidence": risk["evidence"],
            })

        first_high = next((point["hour"] for point in series[1:] if point["riskStatus"] == "HIGH"), None)
        first_critical = next((point["hour"] for point in series[1:] if point["riskStatus"] == "CRITICAL"), None)
        forecast["settlements"][sid] = {
            "id": sid,
            "name": settlement.get("name"),
            "riskByHour": series,
            "firstHighHour": first_high,
            "firstCriticalHour": first_critical,
            "currentRisk": series[0],
        }

    return forecast
