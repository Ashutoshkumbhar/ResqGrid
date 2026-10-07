"""
Dynamic Response Priority Engine.

Priority != risk. It combines flood risk with population exposed, ground
evidence, whether responders can actually reach the place, and whether a
resource is already covering it.
"""
from typing import Any, Dict, List

from services.risk_engine import report_load

WEIGHTS = {
    "risk": 45,
    "population": 15,
    "groundReports": 15,
    "reachability": 10,
    "coverageGap": 15,
}

REACHABILITY = {"DIRECT": 1.0, "ALTERNATIVE": 0.7, "NONE": 0.4}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def calculate_priority(s: Dict[str, Any], reports: List[Dict[str, Any]], feasibility: str, deployed_names: List[str]) -> Dict[str, Any]:
    pop_f = _clamp(s["population"] / 4000.0)
    rep_f = _clamp(report_load(reports) / 2.5)
    reach_f = REACHABILITY[feasibility]
    gap_f = 0.0 if deployed_names else 1.0

    severe = [r for r in reports if (r.get("severity") or "").upper() in ("HIGH", "CRITICAL")]
    reach_text = {
        "DIRECT": "Accessible emergency route (primary road open)",
        "ALTERNATIVE": "Reachable only via alternative route",
        "NONE": "No surface route — escalation required",
    }[feasibility]

    factors = [
        {"key": "risk", "label": "Flood risk", "points": WEIGHTS["risk"] * s["riskScore"] / 100,
         "why": f"{s['riskStatus'].title()} flood risk ({s['riskScore']}/100)"},
        {"key": "population", "label": "Population exposed", "points": WEIGHTS["population"] * pop_f,
         "why": f"{s['population']:,} people exposed"},
        {"key": "groundReports", "label": "Ground reports", "points": WEIGHTS["groundReports"] * rep_f,
         "why": (f"{len(severe)} severe ground report(s)" if severe else f"{len(reports)} ground report(s)") if reports else "No ground reports yet"},
        {"key": "reachability", "label": "Route reachability", "points": WEIGHTS["reachability"] * reach_f,
         "why": reach_text},
        {"key": "coverageGap", "label": "Resource coverage gap", "points": WEIGHTS["coverageGap"] * gap_f,
         "why": "No resource currently deployed" if not deployed_names else f"Already covered by {', '.join(deployed_names)}"},
    ]
    for f in factors:
        f["maxPoints"] = WEIGHTS[f["key"]]
        f["points"] = round(f["points"], 1)

    score = int(round(sum(f["points"] for f in factors)))
    priority_score = max(1, min(100, score))
    top_reasons = [f["why"] for f in sorted(factors, key=lambda item: item["points"], reverse=True)[:3]]
    confidence = round(max(0.45, min(0.97, 0.5 + (priority_score / 100) * 0.35 + (0.08 if len(reports) else 0.0))), 2)
    return {
        "responsePriority": priority_score,
        "priorityFactors": factors,
        "priorityWhy": [f["why"] for f in factors if f["points"] > 0.3 * f["maxPoints"] or f["key"] in ("reachability", "coverageGap")],
        "topReasons": top_reasons,
        "confidence": confidence,
        "routeFeasibility": feasibility,
    }


def rank_settlements(settlements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = sorted(settlements, key=lambda s: (s["responsePriority"], s["riskScore"], s["population"]), reverse=True)
    for i, s in enumerate(ranked, 1):
        s["priorityRank"] = i
    # Explain each rank relative to the next one down
    for upper, lower in zip(ranked, ranked[1:]):
        diffs = {f["key"]: f["points"] for f in upper["priorityFactors"]}
        for f in lower["priorityFactors"]:
            diffs[f["key"]] -= f["points"]
        key = max(diffs, key=diffs.get)
        label = next(f["label"] for f in upper["priorityFactors"] if f["key"] == key)
        upper["rankReason"] = (f"Ranked above {lower['name']} mainly due to {label.lower()} "
                               f"(+{diffs[key]:.1f} pts); total {upper['responsePriority']} vs {lower['responsePriority']}.")
    if ranked:
        ranked[-1]["rankReason"] = "Lowest current response priority in the district."
    return ranked
