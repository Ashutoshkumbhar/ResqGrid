"""
Explainable Flood Risk Engine (0-100).

Weighted scoring model. Every factor reports its own points so the UI can show
exactly why a settlement received its score.
"""
from typing import Any, Dict, List

WEIGHTS = {
    "rainfall": 28,        # 24h accumulation
    "intensity": 10,       # peak mm/h
    "terrain": 20,         # height above river datum, gated by active water hazard
    "waterLevel": 22,      # river gauge
    "groundReports": 10,   # severity-weighted field reports
    "population": 5,       # exposure
    "accessibility": 5,    # isolation amplifies vulnerability
}

SEVERITY_WEIGHT = {"LOW": 0.3, "MODERATE": 0.6, "HIGH": 1.0, "CRITICAL": 1.4}
ACCESS_WEIGHT = {"OPEN": 0.0, "AT_RISK": 0.6, "CUT_OFF": 1.0}


def classify_risk(score: int) -> str:
    if score >= 81:
        return "CRITICAL"
    if score >= 61:
        return "HIGH"
    if score >= 31:
        return "MODERATE"
    return "LOW"


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def report_load(reports: List[Dict[str, Any]]) -> float:
    return sum(SEVERITY_WEIGHT.get((r.get("severity") or "MODERATE").upper(), 0.6) for r in reports)


def calculate_flood_risk(s: Dict[str, Any], reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    rain = s["rainfall"]
    intensity = s["rainfallIntensity"]
    rel_elev = s["relativeElevation"]
    level_m = s["waterLevelMeters"]

    rain_f = _clamp(rain / 140.0)
    intensity_f = _clamp(intensity / 25.0)
    level_f = _clamp((level_m - 0.6) / 1.5)
    terrain_vuln = _clamp((40.0 - rel_elev) / 34.0)
    # Low ground only matters when water is actually present
    hazard_gate = _clamp(0.3 + max(rain_f, level_f))
    reports_f = _clamp(report_load(reports) / 2.0)
    pop_f = _clamp(s["population"] / 4000.0)
    access_f = ACCESS_WEIGHT.get(s.get("accessibility", "OPEN"), 0.0)

    factors = [
        {
            "key": "rainfall", "label": "Rainfall (24h)",
            "points": WEIGHTS["rainfall"] * rain_f,
            "detail": f"{rain:.0f} mm accumulated in 24h",
            "evidence": ("Heavy rainfall" if rain >= 100 else "Moderate rainfall") + f" ({rain:.0f} mm/24h)",
        },
        {
            "key": "intensity", "label": "Rainfall intensity",
            "points": WEIGHTS["intensity"] * intensity_f,
            "detail": f"{intensity:.0f} mm/h peak",
            "evidence": f"High rainfall intensity ({intensity:.0f} mm/h)",
        },
        {
            "key": "terrain", "label": "Terrain / elevation",
            "points": WEIGHTS["terrain"] * terrain_vuln * hazard_gate,
            "detail": f"{rel_elev:.0f} m above river ({s['elevation']:.0f} m ASL, {s['terrainClass'].replace('_', ' ').lower()})",
            "evidence": f"Low elevation — {rel_elev:.0f} m above river level",
        },
        {
            "key": "waterLevel", "label": "Water-level indicator",
            "points": WEIGHTS["waterLevel"] * level_f,
            "detail": f"Gauge {level_m:.2f} m ({s['waterLevel']})",
            "evidence": f"Water level {s['waterLevel']} ({level_m:.2f} m)",
        },
        {
            "key": "groundReports", "label": "Ground reports",
            "points": WEIGHTS["groundReports"] * reports_f,
            "detail": f"{len(reports)} report(s)",
            "evidence": f"{len(reports)} ground report(s) received",
        },
        {
            "key": "population", "label": "Population exposure",
            "points": WEIGHTS["population"] * pop_f,
            "detail": f"{s['population']:,} residents",
            "evidence": f"High population exposure ({s['population']:,} people)",
        },
        {
            "key": "accessibility", "label": "Road accessibility",
            "points": WEIGHTS["accessibility"] * access_f,
            "detail": s.get("accessibility", "OPEN").replace("_", " "),
            "evidence": "Road accessibility reduced" if access_f < 1 else "Settlement cut off by road closures",
        },
    ]

    for f in factors:
        f["maxPoints"] = WEIGHTS[f["key"]]
        f["points"] = round(f["points"], 1)
        # A factor counts as evidence when it delivers at least 40% of its weight
        f["contributing"] = f["points"] >= 0.4 * f["maxPoints"]

    score = int(round(min(100.0, sum(f["points"] for f in factors))))
    top_reasons = [f["evidence"] for f in sorted(factors, key=lambda item: item["points"], reverse=True)[:3]]
    risk_conf = round(max(0.45, min(0.97, 0.5 + (score / 100) * 0.4 + (0.08 if len([f for f in factors if f["contributing"]]) >= 4 else 0.0))), 2)
    return {
        "riskScore": score,
        "riskStatus": classify_risk(score),
        "riskFactors": factors,
        "evidence": [f["evidence"] for f in factors if f["contributing"]],
        "confidence": risk_conf,
        "topReasons": top_reasons,
    }


def risk_confidence(s: Dict[str, Any], reports: List[Dict[str, Any]], weather_live: bool) -> float:
    """
    Confidence reflects how many independent signal families agree, the AI
    extraction confidence of supporting reports, and data quality.
    """
    agreeing = sum(1 for f in s["riskFactors"] if f["contributing"] and f["key"] in ("rainfall", "intensity", "terrain", "waterLevel", "groundReports", "accessibility"))
    signal_conf = min(0.95, 0.55 + 0.075 * agreeing)
    if reports:
        report_conf = sum((r.get("extractedInfo") or {}).get("confidence", 0.8) for r in reports) / len(reports)
        signal_conf = 0.75 * signal_conf + 0.25 * report_conf
    signal_conf -= 0.03 * len(s.get("imputedFields", []))
    if weather_live:
        signal_conf += 0.01
    return round(max(0.4, min(0.97, signal_conf)), 2)
