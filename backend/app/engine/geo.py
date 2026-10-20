"""Town coordinates (plan A5) and great-circle distance. Pure."""

from __future__ import annotations

import math

TOWNS: dict[str, tuple[float, float]] = {
    "Midrand": (-25.9992, 28.1263),
    "Soshanguve": (-25.5236, 28.0989),
    "Soweto": (-26.2485, 27.8540),
    "Germiston": (-26.2309, 28.1772),
    "Cape Town": (-33.9249, 18.4241),
}

EARTH_RADIUS_KM = 6371.0


def town_coordinates(name: str | None) -> tuple[float, float] | None:
    if not name:
        return None
    key = " ".join(str(name).split()).lower()
    return next((coords for town, coords in TOWNS.items() if town.lower() == key), None)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))
