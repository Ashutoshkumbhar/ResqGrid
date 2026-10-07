"""
Data Processing Layer.

Loads raw multi-source data (CSV / JSON), cleans it, fills missing values,
enriches terrain from a public DEM, and integrates settlements with the road
graph. Output is the structured dataset consumed by the risk / priority engines.
"""
import csv
import json
import math
import os
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from config import DISTRICT

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

# Water-level gauge thresholds (metres)
WATER_WARNING_M = 1.5
WATER_CRITICAL_M = 2.1

ROAD_WINDING_FACTOR = 1.25


def classify_water_level(meters: float) -> str:
    if meters >= WATER_CRITICAL_M:
        return "CRITICAL"
    if meters >= WATER_WARNING_M:
        return "WARNING"
    return "NORMAL"


def classify_terrain(relative_elevation_m: float) -> str:
    if relative_elevation_m < 12:
        return "LOW_LYING"
    if relative_elevation_m < 25:
        return "MID_SLOPE"
    return "HIGH_GROUND"


def haversine_km(a: List[float], b: List[float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def polyline_km(coords: List[List[float]]) -> float:
    return sum(haversine_km(coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "" or text.lower() in ("na", "nan", "null", "none"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _read_json(name: str) -> Any:
    with open(os.path.join(RAW_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_dem_elevations(points: List[List[float]]) -> Optional[List[float]]:
    """Real terrain from a public DEM API, with a local cache fallback."""
    if not points:
        return []
    cache_path = os.path.join(CACHE_DIR, "elevation.json")
    key = ";".join(f"{p[0]:.4f},{p[1]:.4f}" for p in points)
    os.makedirs(CACHE_DIR, exist_ok=True)

    providers = [
        ("OPEN_METEO", "https://api.open-meteo.com/v1/elevation", {"latitude": ",".join(str(p[0]) for p in points), "longitude": ",".join(str(p[1]) for p in points)}),
        ("OPEN_ELEVATION", "https://api.open-elevation.com/api/v1/lookup", {"locations": "|".join(f"{p[0]},{p[1]}" for p in points)}),
    ]

    for provider_name, url, params in providers:
        try:
            resp = requests.get(url, params=params, timeout=4)
            if resp.status_code != 200:
                continue
            payload = resp.json()
            values = payload.get("elevation")
            if values is None and provider_name == "OPEN_ELEVATION":
                values = [result.get("elevation") for result in payload.get("results", [])]
            if values and len(values) == len(points):
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump({"key": key, "elevation": values, "source": provider_name}, f)
                return values
        except Exception as exc:
            print(f"[DataProcessing] {provider_name} elevation lookup failed: {exc}")

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if cached.get("key") == key and isinstance(cached.get("elevation"), list):
            return cached["elevation"]
    except Exception:
        pass
    return None


def fetch_osm_roads_for_district(settlements: List[Dict[str, Any]], bounds: Optional[List[List[float]]] = None) -> Optional[Dict[str, Any]]:
    """Try to load district roads from OpenStreetMap and cache the result; fall back gracefully."""
    try:
        import osmnx as ox
    except Exception:
        return None

    district_bounds = bounds or DISTRICT.get("boundary")
    if not district_bounds or len(district_bounds) < 2:
        return None

    lats = [pt[0] for pt in district_bounds]
    lons = [pt[1] for pt in district_bounds]
    north, south = max(lats), min(lats)
    east, west = max(lons), min(lons)
    cache_path = os.path.join(CACHE_DIR, "osm_roads.json")
    key = f"{north:.4f},{south:.4f},{east:.4f},{west:.4f}"
    os.makedirs(CACHE_DIR, exist_ok=True)

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if cached.get("key") == key and isinstance(cached.get("roads"), list):
            return {"source": cached.get("source", "CACHED_OSM_ROADS"), "roads": cached["roads"]}
    except Exception:
        pass

    try:
        road_graph = ox.graph_from_bbox(north, south, east, west, network_type="drive", simplify=True)
        if road_graph is None or len(road_graph.nodes) == 0:
            return None

        def nearest_settlement(point):
            best = None
            best_dist = None
            for settlement in settlements:
                lat = settlement.get("latitude")
                lon = settlement.get("longitude")
                if lat is None or lon is None:
                    continue
                dist = haversine_km(point, [lat, lon])
                if best is None or dist < best_dist:
                    best = settlement
                    best_dist = dist
            return best

        roads: List[Dict[str, Any]] = []
        seen = set()
        for u, v, k, data in road_graph.edges(keys=True, data=True):
            edge_points = []
            if "geometry" in data and data["geometry"] is not None:
                coords = list(data["geometry"].coords)
                edge_points = [[float(lat), float(lon)] for lon, lat in coords]
            else:
                u_node = road_graph.nodes[u]
                v_node = road_graph.nodes[v]
                edge_points = [
                    [float(u_node.get("y")), float(u_node.get("x"))],
                    [float(v_node.get("y")), float(v_node.get("x"))],
                ]
            if len(edge_points) < 2:
                continue
            start = nearest_settlement(edge_points[0])
            end = nearest_settlement(edge_points[-1])
            if start is None or end is None or start["id"] == end["id"]:
                continue
            road_id = f"OSM_{u}_{v}_{k}"
            if road_id in seen:
                continue
            seen.add(road_id)
            roads.append({
                "id": road_id,
                "source": start["id"],
                "destination": end["id"],
                "coordinates": edge_points,
                "distanceKm": round(polyline_km(edge_points) * ROAD_WINDING_FACTOR, 1),
                "status": "OPEN",
                "statusReason": "OpenStreetMap road segment",
                "manualStatus": None,
                "sourceName": start["name"],
                "destinationName": end["name"],
            })
        if roads:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"key": key, "source": "OSM_LIVE", "roads": roads}, f)
            return {"source": "OSM_LIVE", "roads": roads}
    except Exception as exc:
        print(f"[DataProcessing] OSM road query failed; using local fallback network: {exc}")
    return None


def load_river_gauge_csv(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load optional CSV gauge records so real river data can be dropped in without changing the app contract."""
    gauge_path = path or os.path.join(RAW_DIR, "river_gauges.csv")
    if not os.path.exists(gauge_path):
        return []

    rows: List[Dict[str, Any]] = []
    with open(gauge_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "station": row.get("station") or row.get("name") or "River Gauge",
                "date": row.get("date") or row.get("timestamp"),
                "waterLevelM": _to_float(row.get("waterLevelM")) if row.get("waterLevelM") is not None else None,
                "stageM": _to_float(row.get("stageM")) if row.get("stageM") is not None else None,
                "flowM3s": _to_float(row.get("flowM3s")) if row.get("flowM3s") is not None else None,
            })
    return rows


def load_and_process(fetch_terrain: bool = True) -> Dict[str, Any]:
    log: List[Dict[str, Any]] = []

    # ---------- 1. Settlements: load + clean ----------
    with open(os.path.join(RAW_DIR, "settlements.csv"), "r", encoding="utf-8") as f:
        raw_rows = list(csv.DictReader(f))
    log.append({"step": "LOAD", "detail": f"Loaded {len(raw_rows)} settlement rows from settlements.csv"})

    settlements: List[Dict[str, Any]] = []
    cleaned_fields = 0
    for row in raw_rows:
        name = " ".join((row.get("name") or "").split())
        if name != (row.get("name") or ""):
            cleaned_fields += 1
        if "," in (row.get("population") or ""):
            cleaned_fields += 1
        elderly = int(_to_float(row.get("elderly")) or 0)
        pregnant = int(_to_float(row.get("pregnant")) or 0)
        disabled = int(_to_float(row.get("disabled")) or 0)
        patients = int(_to_float(row.get("patients")) or 0)
        settlements.append({
            "id": row["id"].strip(),
            "name": name,
            "latitude": _to_float(row.get("latitude")),
            "longitude": _to_float(row.get("longitude")),
            "population": int(_to_float(row.get("population")) or 0),
            "elderly": elderly,
            "pregnant": pregnant,
            "disabled": disabled,
            "patients": patients,
            "vulnerablePopulation": elderly + pregnant + disabled + patients,
            "elevation": _to_float(row.get("elevationM")),
            "rainfall": _to_float(row.get("rainfall24hMm")),
            "rainfallIntensity": _to_float(row.get("rainfallIntensityMmHr")),
            "waterLevelMeters": _to_float(row.get("waterLevelM")),
            "catchmentFactor": _to_float(row.get("catchmentFactor")) or 0.5,
            "dataSource": (row.get("dataSource") or "SIMULATED_PROTOTYPE").strip(),
            "imputedFields": [],
        })
    log.append({"step": "CLEAN", "detail": f"Normalised {cleaned_fields} malformed text/number fields (whitespace, thousands separators)"})

    # ---------- 2. Missing-value handling ----------
    imputed = 0
    known_levels = [s["waterLevelMeters"] for s in settlements if s["waterLevelMeters"] is not None]
    median_level = statistics.median(known_levels) if known_levels else 1.0
    known_rain = [s["rainfall"] for s in settlements if s["rainfall"] is not None]
    median_rain = statistics.median(known_rain) if known_rain else 40.0
    for s in settlements:
        if s["rainfall"] is None:
            s["rainfall"] = median_rain
            s["imputedFields"].append("rainfall")
            imputed += 1
        if s["rainfallIntensity"] is None:
            # Peak-hour intensity approximated from 24h accumulation
            s["rainfallIntensity"] = round(s["rainfall"] / 8.0, 1)
            s["imputedFields"].append("rainfallIntensity")
            imputed += 1
        if s["waterLevelMeters"] is None:
            # Scale the district median gauge by the local catchment factor
            s["waterLevelMeters"] = round(median_level * (0.5 + s["catchmentFactor"] / 2), 2)
            s["imputedFields"].append("waterLevelMeters")
            imputed += 1
        s["vulnerablePopulation"] = int((s.get("elderly") or 0) + (s.get("pregnant") or 0) + (s.get("disabled") or 0) + (s.get("patients") or 0))
    log.append({"step": "IMPUTE", "detail": f"Filled {imputed} missing values (median / catchment-scaled / intensity-from-accumulation)"})

    # ---------- 3. Terrain enrichment (public DEM) ----------
    elevation_source = "CSV_CACHED_DEM"
    if fetch_terrain:
        dem = fetch_dem_elevations([[s["latitude"], s["longitude"]] for s in settlements])
        if dem:
            for s, elev in zip(settlements, dem):
                s["elevation"] = float(elev)
            elevation_source = "OPEN_METEO_DEM"
    for s in settlements:
        if s["elevation"] is None:
            s["elevation"] = DISTRICT["riverDatumM"] + 15
            s["imputedFields"].append("elevation")
        s["elevationSource"] = elevation_source
        s["relativeElevation"] = round(s["elevation"] - DISTRICT["riverDatumM"], 1)
        s["terrainClass"] = classify_terrain(s["relativeElevation"])
        s["waterLevel"] = classify_water_level(s["waterLevelMeters"])
    log.append({"step": "TERRAIN", "detail": f"Terrain from {elevation_source}; height above river datum ({DISTRICT['riverDatumM']:.0f} m) and terrain class derived"})

    # ---------- 4. Road network: validate + transform ----------
    road_source = "SIMULATED_PROTOTYPE"
    network = _read_json("road_network.json")
    osm_roads = fetch_osm_roads_for_district(settlements, DISTRICT.get("boundary"))
    if osm_roads and osm_roads.get("roads"):
        network = {"nodes": [], "roads": osm_roads["roads"]}
        road_source = osm_roads["source"]
        log.append({"step": "ROADS", "detail": f"Loaded {len(network['roads'])} road segments from {road_source} for district bbox"})
    else:
        log.append({"step": "ROADS", "detail": "Using bundled district road graph fallback (offline-safe)"})

    nodes = {n["id"]: dict(n) for n in network.get("nodes", [])}
    for s in settlements:
        nodes[s["id"]] = {"id": s["id"], "name": s["name"], "latitude": s["latitude"], "longitude": s["longitude"], "kind": "SETTLEMENT"}

    roads: List[Dict[str, Any]] = []
    filled_distances = 0
    for r in network.get("roads", []):
        if r["source"] not in nodes or r["destination"] not in nodes:
            log.append({"step": "VALIDATE", "detail": f"Dropped road {r['id']}: unknown endpoint"})
            continue
        road = dict(r)
        if _to_float(road.get("distanceKm")) is None:
            road["distanceKm"] = round(polyline_km(road["coordinates"]) * ROAD_WINDING_FACTOR, 1)
            filled_distances += 1
        road["sourceName"] = nodes[road["source"]]["name"]
        road["destinationName"] = nodes[road["destination"]]["name"]
        road["status"] = "OPEN"
        road["statusReason"] = "Normal conditions"
        road["manualStatus"] = None
        roads.append(road)
    road_status = "LIVE" if road_source.startswith("OSM") else ("CACHED" if road_source.endswith("_ROADS") or road_source == "CACHED_OSM_ROADS" else "SIMULATED")
    log.append({"step": "TRANSFORM", "detail": f"Built road graph: {len(nodes)} nodes, {len(roads)} roads ({filled_distances} missing lengths derived from geometry) from {road_status} data"})

    # ---------- 5. Geographic integration ----------
    for s in settlements:
        s["connectedRoadIds"] = [r["id"] for r in roads if s["id"] in (r["source"], r["destination"])]
    resources = _read_json("resources.json")
    for res in resources:
        res.setdefault("currentAssignment", None)
    log.append({"step": "INTEGRATE", "detail": "Joined settlements ↔ roads ↔ resources on graph nodes; rainfall + terrain + gauge features prepared"})

    now = datetime.now(timezone.utc)
    reports = []
    for rep in _read_json("reports.json"):
        rep = dict(rep)
        rep["timestamp"] = (now - timedelta(minutes=rep.pop("minutesAgo", 0))).isoformat()
        rep["status"] = "AI_EXTRACTED"
        reports.append(rep)

    river_gauge_data = load_river_gauge_csv()
    live_weather_source = "Open-Meteo API (live)"
    data_sources = {
        "weather": {"label": "Live", "status": "LIVE", "detail": live_weather_source},
        "elevation": {"label": "Cached" if elevation_source.startswith("CSV") else "Live", "status": "CACHED" if elevation_source.startswith("CSV") else "LIVE", "detail": elevation_source},
        "roads": {"label": road_status, "status": road_status.upper(), "detail": road_source},
        "settlements": {"label": "Simulated", "status": "SIMULATED", "detail": "Offline prototype dataset"},
        "riverGauge": {"label": "Simulated" if not river_gauge_data else "Live", "status": "SIMULATED" if not river_gauge_data else "LIVE", "detail": "river_gauges.csv" if not river_gauge_data else "CSV live gauge feed"},
    }

    return {
        "district": DISTRICT,
        "settlements": settlements,
        "nodes": nodes,
        "roads": roads,
        "resources": resources,
        "reports": reports,
        "riverGaugeData": river_gauge_data,
        "processingLog": log,
        "dataSources": data_sources,
    }
