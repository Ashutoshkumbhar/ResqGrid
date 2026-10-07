import os


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _str_env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _parse_coords(value: str, default):
    if not value:
        return default
    try:
        parts = [float(p.strip()) for p in value.split(",")]
        if len(parts) == 2:
            return parts
    except ValueError:
        pass
    return default


def _parse_boundary(value: str, default):
    if not value:
        return default
    coords = []
    for chunk in value.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            coords.append([float(p.strip()) for p in chunk.split(",")])
        except ValueError:
            continue
    return coords or default


DISTRICT = {
    "districtId": _str_env("DISTRICT_ID", "DIST_PUNE_01"),
    "districtName": _str_env("DISTRICT_NAME", "Pune District — Mula-Pawana Basin"),
    "state": _str_env("DISTRICT_STATE", "Maharashtra"),
    "center": [
        _float_env("DISTRICT_LAT", 18.5780),
        _float_env("DISTRICT_LON", 73.7950),
    ],
    "zoom": int(os.getenv("DISTRICT_ZOOM", "13")),
    "riverSystems": [
        _str_env("DISTRICT_RIVER_1", "Mula River"),
        _str_env("DISTRICT_RIVER_2", "Pawana River"),
    ],
    "riverDatumM": _float_env("DISTRICT_RIVER_DATUM_M", 555.0),
    "boundary": _parse_boundary(
        os.getenv("DISTRICT_BOUNDARY"),
        [
            [18.6080, 73.7300],
            [18.6080, 73.8450],
            [18.5500, 73.8450],
            [18.5500, 73.7300],
        ],
    ),
}
