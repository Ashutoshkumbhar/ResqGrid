"""
Route Engine.

Decisions are made on the local district road graph with NetworkX, because it
knows the simulated closures. OSRM (public street router) is used only as a
street-level distance/ETA cross-check for the chosen path; if OSRM is
unreachable the local graph ETA is used and the result says so.
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import requests

AT_RISK_PENALTY = 1.3
MOBILISATION_MIN = 3

_osrm_cache: Dict[str, Optional[Dict[str, float]]] = {}
_osrm_disabled_until = 0.0


def build_graph(roads: List[Dict[str, Any]], respect_status: bool) -> nx.Graph:
    """
    respect_status=False -> normal-conditions network (the planned route).
    respect_status=True  -> current network: BLOCKED removed, AT_RISK penalised.
    Parallel roads between the same nodes keep only the cheapest usable one.
    """
    G = nx.Graph()
    for r in roads:
        weight = r["distanceKm"]
        if respect_status:
            if r["status"] == "BLOCKED":
                continue
            if r["status"] == "AT_RISK":
                weight *= AT_RISK_PENALTY
        u, v = r["source"], r["destination"]
        if G.has_edge(u, v) and G[u][v]["weight"] <= weight:
            continue
        G.add_edge(u, v, weight=weight, road=r)
    return G


def _shortest(G: nx.Graph, src: str, dst: str) -> Optional[List[str]]:
    if src not in G or dst not in G:
        return None
    try:
        return nx.shortest_path(G, src, dst, weight="weight")
    except nx.NetworkXNoPath:
        return None


def _node_lookup(nodes: Any) -> Dict[str, Any]:
    if isinstance(nodes, dict):
        return nodes
    if isinstance(nodes, list):
        return {n["id"]: n for n in nodes if isinstance(n, dict) and "id" in n}
    return {}


def _describe(G: nx.Graph, path: List[str], nodes: Any) -> Dict[str, Any]:
    node_map = _node_lookup(nodes)
    roads, coords, dist = [], [], 0.0
    for u, v in zip(path, path[1:]):
        r = G[u][v]["road"]
        seg = r["coordinates"] if r["source"] == u else list(reversed(r["coordinates"]))
        coords.extend(seg if not coords else seg[1:])
        roads.append(r)
        dist += r["distanceKm"]
    return {
        "nodeNames": [node_map.get(n, {}).get("name", n) for n in path],
        "roadIds": [r["id"] for r in roads],
        "roadNames": [f"{r['name']} ({r['id']})" for r in roads],
        "coordinates": coords,
        "distanceKm": round(dist, 1),
        "roads": roads,
    }


def _osrm_estimate(coords: List[List[float]]) -> Optional[Dict[str, float]]:
    """Street-level estimate through the path's waypoints (cached, with circuit breaker)."""
    global _osrm_disabled_until
    if len(coords) < 2:
        return None
    step = max(1, len(coords) // 6)
    waypoints = coords[::step]
    if waypoints[-1] != coords[-1]:
        waypoints.append(coords[-1])
    key = ";".join(f"{lng:.4f},{lat:.4f}" for lat, lng in waypoints)
    if key in _osrm_cache:
        return _osrm_cache[key]
    if time.time() < _osrm_disabled_until:
        return None
    try:
        resp = requests.get(f"https://router.project-osrm.org/route/v1/driving/{key}", params={"overview": "false"}, timeout=2.5)
        data = resp.json()
        if data.get("code") == "Ok":
            route = data["routes"][0]
            result = {"distanceKm": round(route["distance"] / 1000, 1), "durationMin": round(route["duration"] / 60, 1)}
            _osrm_cache[key] = result
            return result
    except Exception as e:
        print(f"[Routing] OSRM unavailable, using local graph ETA: {e}")
    _osrm_disabled_until = time.time() + 300
    return None


def _eta(distance_km: float, speed_kmh: float) -> int:
    return int(round(distance_km / max(speed_kmh, 1) * 60)) + MOBILISATION_MIN


def plan_route(resource: Dict[str, Any], target: Dict[str, Any], nodes: Dict[str, Any], roads: List[Dict[str, Any]], use_osrm: bool = True) -> Dict[str, Any]:
    src, dst = resource["nodeId"], target["id"]
    speed = resource.get("speedKmh") or 40
    base = {
        "routeId": f"RT-{resource['id']}-{dst}",
        "resourceId": resource["id"],
        "resourceName": resource["name"],
        "targetSettlementId": dst,
        "targetSettlementName": target["name"],
        "engine": "NetworkX (local district graph)",
    }

    normal_G = build_graph(roads, respect_status=False)
    planned_nodes = _shortest(normal_G, src, dst)
    if planned_nodes is None:
        return {**base, "originalRouteStatus": "INVALID", "alternativeRouteStatus": "ESCALATION_REQUIRED",
                "originalPath": [], "originalRoadIds": [], "originalCoordinates": [],
                "alternativePath": None, "alternativeRoadIds": [], "alternativeCoordinates": None,
                "activeRoadIds": [], "blockedRoadsOnPath": [], "atRiskRoadsOnPath": [],
                "distanceKm": 0.0, "etaMinutes": None, "escalationRequired": True,
                "explanation": f"No road connection exists between {resource['locationName']} and {target['name']}."}

    planned = _describe(normal_G, planned_nodes, nodes)
    # Re-read live statuses of the planned roads
    live = {r["id"]: r for r in roads}
    blocked = [rid for rid in planned["roadIds"] if live[rid]["status"] == "BLOCKED"]

    result = {
        **base,
        "originalPath": planned["nodeNames"],
        "originalRoadIds": planned["roadIds"],
        "originalCoordinates": planned["coordinates"],
        "originalDistanceKm": planned["distanceKm"],
        "blockedRoadsOnPath": blocked,
    }

    if not blocked:
        active = planned
        at_risk = [rid for rid in planned["roadIds"] if live[rid]["status"] == "AT_RISK"]
        result.update({
            "originalRouteStatus": "VALID",
            "alternativeRouteStatus": "NOT_NEEDED",
            "alternativePath": None, "alternativeRoadIds": [], "alternativeCoordinates": None,
            "atRiskRoadsOnPath": at_risk,
            "escalationRequired": False,
        })
        caution = f" Caution: {', '.join(at_risk)} flagged AT RISK." if at_risk else ""
        result["explanation"] = f"Primary route via {' → '.join(planned['roadNames'])} is open.{caution}"
    else:
        current_G = build_graph(roads, respect_status=True)
        alt_nodes = _shortest(current_G, src, dst)
        if alt_nodes is None:
            result.update({
                "originalRouteStatus": "INVALID",
                "alternativeRouteStatus": "ESCALATION_REQUIRED",
                "alternativePath": None, "alternativeRoadIds": [], "alternativeCoordinates": None,
                "activeRoadIds": [], "atRiskRoadsOnPath": [],
                "distanceKm": 0.0, "etaMinutes": None, "escalationRequired": True,
                "explanation": f"Primary route invalid ({', '.join(blocked)} BLOCKED) and no alternative surface route exists to {target['name']}. Escalation required (aerial / boat-only access).",
            })
            return result
        active = _describe(current_G, alt_nodes, nodes)
        at_risk = [rid for rid in active["roadIds"] if live[rid]["status"] == "AT_RISK"]
        result.update({
            "originalRouteStatus": "INVALID",
            "alternativeRouteStatus": "VALID",
            "alternativePath": active["nodeNames"],
            "alternativeRoadIds": active["roadIds"],
            "alternativeCoordinates": active["coordinates"],
            "atRiskRoadsOnPath": at_risk,
            "escalationRequired": False,
            "explanation": (f"Primary route invalidated: {', '.join(blocked)} BLOCKED. Alternative route via "
                            f"{' → '.join(active['roadNames'])} is VALID "
                            f"(+{round(active['distanceKm'] - planned['distanceKm'], 1)} km)."),
        })

    result["activeRoadIds"] = active["roadIds"]
    result["distanceKm"] = active["distanceKm"]
    result["etaMinutes"] = _eta(active["distanceKm"], speed)
    result["etaSource"] = "LOCAL_GRAPH"
    if use_osrm:
        osrm = _osrm_estimate(active["coordinates"])
        if osrm:
            # Prototype road geometry is simplified, so flag large disagreements instead of hiding them
            osrm = {**osrm, "consistent": osrm["distanceKm"] <= 1.6 * max(active["distanceKm"], 0.5)}
            result["osrmCheck"] = osrm
    return result


def route_feasibility(target: Dict[str, Any], resources: List[Dict[str, Any]], nodes: Dict[str, Any], roads: List[Dict[str, Any]]) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Best surface access to a settlement from any mobile resource: DIRECT / ALTERNATIVE / NONE."""
    best = None
    for res in resources:
        if not res.get("mobile") or res["status"] == "UNAVAILABLE":
            continue
        r = plan_route(res, target, nodes, roads, use_osrm=False)
        if r["escalationRequired"]:
            continue
        if best is None or r["etaMinutes"] < best["etaMinutes"]:
            best = r
    if best is None:
        return "NONE", None
    return ("DIRECT" if best["originalRouteStatus"] == "VALID" else "ALTERNATIVE"), best


def shortest_distance_km(src: str, dst: str, roads: List[Dict[str, Any]]) -> Optional[float]:
    if src == dst:
        return 0.0
    G = build_graph(roads, respect_status=True)
    path = _shortest(G, src, dst)
    if path is None:
        return None
    return round(sum(G[u][v]["road"]["distanceKm"] for u, v in zip(path, path[1:])), 1)
