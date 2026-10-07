"""
Resource Recommendation Engine (prototype recommendation, NOT dispatch).

Walks settlements in priority order and assigns each the best AVAILABLE mobile
resource, scored on suitability for the flood conditions and route ETA. A
resource is never recommended to two settlements in the same plan.
"""
from typing import Any, Dict, List

from services.routing_engine import plan_route, shortest_distance_km

ETA_HORIZON_MIN = 45.0


def _is_flooded(s: Dict[str, Any]) -> bool:
    return s["waterLevel"] == "CRITICAL" or s["rainfall"] >= 150 or s["riskStatus"] == "CRITICAL"


def suitability(res_type: str, s: Dict[str, Any]) -> (float, str):
    flooded = _is_flooded(s)
    if res_type == "RESCUE_BOAT":
        if flooded:
            return 1.0, "Boat suited to submerged streets / critical water level"
        if s["waterLevel"] == "WARNING":
            return 0.75, "Boat useful as water level is in WARNING range"
        return 0.4, "Boat not required under current water levels"
    if res_type == "RESCUE_TEAM":
        if flooded:
            return 0.85, "Trained flood-rescue team for evacuation in deep water"
        return 0.9 if s["riskStatus"] == "HIGH" else 0.7, "Rescue team suited to evacuation and perimeter support"
    if res_type == "AMBULANCE":
        if flooded:
            return 0.35, "Ambulance limited in flooded streets"
        return 0.6 if s["riskStatus"] == "HIGH" else 0.9, "Ambulance for medical first response"
    return 0.0, "Not a mobile response unit"


def recommend_resources(ranked: List[Dict[str, Any]], resources: List[Dict[str, Any]], nodes: Dict[str, Any], roads: List[Dict[str, Any]], max_targets: int = 3) -> List[Dict[str, Any]]:
    targets = [s for s in ranked if s["riskStatus"] != "LOW"][:max_targets]
    pool = [r for r in resources if r.get("mobile") and r["status"] == "AVAILABLE"]
    shelters = [r for r in resources if r["type"] == "SHELTER" and r["status"] == "AVAILABLE"]
    recommendations = []

    for s in targets:
        deployed = [r for r in resources if r["status"] == "DEPLOYED" and r.get("currentAssignment") == s["id"]]
        candidates = []
        for res in pool:
            route = plan_route(res, s, nodes, roads, use_osrm=False)
            suit, suit_reason = suitability(res["type"], s)
            if route["escalationRequired"]:
                candidates.append({"resource": res, "route": route, "score": None, "suitability": suit, "suitReason": suit_reason})
                continue
            eta_f = max(0.0, 1 - route["etaMinutes"] / ETA_HORIZON_MIN)
            candidates.append({"resource": res, "route": route, "score": round(0.5 * suit + 0.5 * eta_f, 3),
                               "suitability": suit, "suitReason": suit_reason})

        reachable = [c for c in candidates if c["score"] is not None]
        considered = [{
            "resourceId": c["resource"]["id"], "resourceName": c["resource"]["name"],
            "etaMinutes": c["route"].get("etaMinutes"), "distanceKm": c["route"].get("distanceKm"),
            "score": c["score"], "note": c["suitReason"] if c["score"] is not None else "No valid route",
        } for c in sorted(candidates, key=lambda c: -(c["score"] or -1))]

        shelter_info = None
        for sh in shelters:
            d = shortest_distance_km(s["id"], sh["nodeId"], roads)
            if d is not None and (shelter_info is None or d < shelter_info["distanceKm"]):
                shelter_info = {"name": sh["name"], "distanceKm": d}

        rec = {
            "settlementId": s["id"],
            "settlementName": s["name"],
            "priorityRank": s["priorityRank"],
            "priorityScore": s["responsePriority"],
            "riskScore": s["riskScore"],
            "population": s["population"],
            "alreadyDeployed": [r["name"] for r in deployed],
            "candidatesConsidered": considered,
            "nearestShelter": shelter_info,
        }

        if not reachable:
            no_units = not candidates
            rec.update({
                "recommendedResourceId": None, "recommendedResourceName": None, "recommendedResourceType": None,
                "route": candidates[0]["route"] if candidates else None,
                "distanceKm": None, "etaMinutes": None,
                "routeStatus": "ESCALATION_REQUIRED",
                "recommendedAction": ("Escalate: request additional units — all district units already assigned" if no_units
                                      else "Escalate: request aerial / boat-only support — no surface route"),
                "whySelected": (["All available mobile units are assigned to higher-priority settlements"] if no_units
                                else ["No available ground unit can reach this settlement on the current road network"]),
                "confidenceScore": 0.5,
            })
            recommendations.append(rec)
            continue

        best = max(reachable, key=lambda c: c["score"])
        res, route = best["resource"], best["route"]
        pool.remove(res)
        # Enrich the chosen route with the OSRM street-level cross-check
        route = plan_route(res, s, nodes, roads, use_osrm=True)
        route_status = "VALID" if route["originalRouteStatus"] == "VALID" else "ALTERNATIVE_VALID"
        why = [
            best["suitReason"],
            f"{res['status']} at {res['locationName']}",
            f"Fastest suitable unit: {route['distanceKm']} km, ETA {route['etaMinutes']} min",
        ]
        if route_status == "ALTERNATIVE_VALID":
            why.append(f"Primary road {', '.join(route['blockedRoadsOnPath'])} blocked — using alternative route")
        runner_up = next((c for c in sorted(reachable, key=lambda c: -c["score"]) if c is not best), None)
        if runner_up:
            why.append(f"Preferred over {runner_up['resource']['name']} (score {best['score']:.2f} vs {runner_up['score']:.2f})")

        confidence = 0.6 + 0.25 * best["suitability"] + (0.1 if route_status == "VALID" else 0.04)
        if route["atRiskRoadsOnPath"]:
            confidence -= 0.05
        rec.update({
            "recommendedResourceId": res["id"],
            "recommendedResourceName": res["name"],
            "recommendedResourceType": res["type"],
            "resourceStatus": res["status"],
            "route": route,
            "distanceKm": route["distanceKm"],
            "etaMinutes": route["etaMinutes"],
            "routeStatus": route_status,
            "recommendedAction": f"Deploy {res['name']}",
            "whySelected": why,
            "confidenceScore": round(min(0.97, confidence), 2),
        })
        recommendations.append(rec)

    return recommendations
