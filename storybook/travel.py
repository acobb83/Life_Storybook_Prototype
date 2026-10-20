"""Travels: turn photos into an ordered list of destinations for the world map.

A photo's position comes from its own camera GPS when present; otherwise from the place the
user typed, matched against a small built-in list of well-known cities and countries. Nothing
is sent to an online geocoding service. Anything that cannot be matched is reported as unmapped.
"""
from __future__ import annotations

import math
import re

from .core import chronological_photos

# name: (latitude, longitude, country). Approximate city-centre coordinates.
CITIES: dict[str, tuple[float, float, str]] = {
    # Australia
    "Sydney": (-33.8688, 151.2093, "Australia"), "Melbourne": (-37.8136, 144.9631, "Australia"),
    "Brisbane": (-27.4698, 153.0251, "Australia"), "Perth": (-31.9523, 115.8613, "Australia"),
    "Adelaide": (-34.9285, 138.6007, "Australia"), "Canberra": (-35.2809, 149.1300, "Australia"),
    "Hobart": (-42.8821, 147.3272, "Australia"), "Darwin": (-12.4634, 130.8456, "Australia"),
    "Cairns": (-16.9186, 145.7781, "Australia"), "Gold Coast": (-28.0167, 153.4000, "Australia"),
    "Sunshine Coast": (-26.6500, 153.0667, "Australia"), "Byron Bay": (-28.6474, 153.6020, "Australia"),
    "Newcastle": (-32.9283, 151.7817, "Australia"), "Wollongong": (-34.4278, 150.8931, "Australia"),
    "Blue Mountains": (-33.7125, 150.3119, "Australia"), "Katoomba": (-33.7125, 150.3119, "Australia"),
    "Uluru": (-25.3444, 131.0369, "Australia"), "Alice Springs": (-23.6980, 133.8807, "Australia"),
    "Broome": (-17.9614, 122.2359, "Australia"), "Townsville": (-19.2590, 146.8169, "Australia"),
    "Launceston": (-41.4332, 147.1441, "Australia"), "Geelong": (-38.1499, 144.3617, "Australia"),
    "Belconnen": (-35.2389, 149.0656, "Australia"), "Bondi": (-33.8915, 151.2767, "Australia"),
    # New Zealand & Pacific
    "Auckland": (-36.8485, 174.7633, "New Zealand"), "Wellington": (-41.2865, 174.7762, "New Zealand"),
    "Queenstown": (-45.0312, 168.6626, "New Zealand"), "Christchurch": (-43.5321, 172.6362, "New Zealand"),
    "Fiji": (-17.7134, 178.0650, "Fiji"), "Nadi": (-17.7765, 177.4356, "Fiji"),
    "Honolulu": (21.3069, -157.8583, "United States"),
    # Asia
    "Tokyo": (35.6762, 139.6503, "Japan"), "Kyoto": (35.0116, 135.7681, "Japan"),
    "Osaka": (34.6937, 135.5023, "Japan"), "Hiroshima": (34.3853, 132.4553, "Japan"),
    "Sapporo": (43.0618, 141.3545, "Japan"), "Seoul": (37.5665, 126.9780, "South Korea"),
    "Busan": (35.1796, 129.0756, "South Korea"), "Beijing": (39.9042, 116.4074, "China"),
    "Shanghai": (31.2304, 121.4737, "China"), "Hong Kong": (22.3193, 114.1694, "Hong Kong"),
    "Taipei": (25.0330, 121.5654, "Taiwan"), "Singapore": (1.3521, 103.8198, "Singapore"),
    "Kuala Lumpur": (3.1390, 101.6869, "Malaysia"), "Penang": (5.4164, 100.3327, "Malaysia"),
    "Bangkok": (13.7563, 100.5018, "Thailand"), "Phuket": (7.8804, 98.3923, "Thailand"),
    "Chiang Mai": (18.7883, 98.9853, "Thailand"), "Bali": (-8.4095, 115.1889, "Indonesia"),
    "Ubud": (-8.5069, 115.2625, "Indonesia"), "Jakarta": (-6.2088, 106.8456, "Indonesia"),
    "Hanoi": (21.0278, 105.8342, "Vietnam"), "Ho Chi Minh City": (10.8231, 106.6297, "Vietnam"),
    "Manila": (14.5995, 120.9842, "Philippines"), "Delhi": (28.7041, 77.1025, "India"),
    "New Delhi": (28.6139, 77.2090, "India"), "Mumbai": (19.0760, 72.8777, "India"),
    "Agra": (27.1767, 78.0081, "India"), "Kathmandu": (27.7172, 85.3240, "Nepal"),
    "Colombo": (6.9271, 79.8612, "Sri Lanka"), "Dubai": (25.2048, 55.2708, "United Arab Emirates"),
    "Abu Dhabi": (24.4539, 54.3773, "United Arab Emirates"), "Doha": (25.2854, 51.5310, "Qatar"),
    # Europe
    "London": (51.5074, -0.1278, "United Kingdom"), "Edinburgh": (55.9533, -3.1883, "United Kingdom"),
    "Manchester": (53.4808, -2.2426, "United Kingdom"), "Dublin": (53.3498, -6.2603, "Ireland"),
    "Paris": (48.8566, 2.3522, "France"),
    "Lyon": (45.7640, 4.8357, "France"), "Amsterdam": (52.3676, 4.9041, "Netherlands"),
    "Brussels": (50.8503, 4.3517, "Belgium"), "Berlin": (52.5200, 13.4050, "Germany"),
    "Munich": (48.1351, 11.5820, "Germany"), "Frankfurt": (50.1109, 8.6821, "Germany"),
    "Zurich": (47.3769, 8.5417, "Switzerland"), "Geneva": (46.2044, 6.1432, "Switzerland"),
    "Vienna": (48.2082, 16.3738, "Austria"), "Prague": (50.0755, 14.4378, "Czechia"),
    "Budapest": (47.4979, 19.0402, "Hungary"), "Rome": (41.9028, 12.4964, "Italy"),
    "Florence": (43.7696, 11.2558, "Italy"), "Venice": (45.4408, 12.3155, "Italy"),
    "Milan": (45.4642, 9.1900, "Italy"), "Naples": (40.8518, 14.2681, "Italy"),
    "Barcelona": (41.3851, 2.1734, "Spain"), "Madrid": (40.4168, -3.7038, "Spain"),
    "Seville": (37.3891, -5.9845, "Spain"), "Lisbon": (38.7223, -9.1393, "Portugal"),
    "Porto": (41.1579, -8.6291, "Portugal"), "Athens": (37.9838, 23.7275, "Greece"),
    "Santorini": (36.3932, 25.4615, "Greece"), "Istanbul": (41.0082, 28.9784, "Turkey"),
    "Copenhagen": (55.6761, 12.5683, "Denmark"), "Stockholm": (59.3293, 18.0686, "Sweden"),
    "Oslo": (59.9139, 10.7522, "Norway"), "Helsinki": (60.1699, 24.9384, "Finland"),
    "Reykjavik": (64.1466, -21.9426, "Iceland"), "Dubrovnik": (42.6507, 18.0944, "Croatia"),
    # Americas
    "New York": (40.7128, -74.0060, "United States"), "Los Angeles": (34.0522, -118.2437, "United States"),
    "San Francisco": (37.7749, -122.4194, "United States"), "Las Vegas": (36.1699, -115.1398, "United States"),
    "Chicago": (41.8781, -87.6298, "United States"), "Seattle": (47.6062, -122.3321, "United States"),
    "Boston": (42.3601, -71.0589, "United States"), "Washington": (38.9072, -77.0369, "United States"),
    "Miami": (25.7617, -80.1918, "United States"), "Orlando": (28.5383, -81.3792, "United States"),
    "Vancouver": (49.2827, -123.1207, "Canada"), "Toronto": (43.6532, -79.3832, "Canada"),
    "Montreal": (45.5017, -73.5673, "Canada"), "Banff": (51.1784, -115.5708, "Canada"),
    "Mexico City": (19.4326, -99.1332, "Mexico"), "Cancun": (21.1619, -86.8515, "Mexico"),
    "Lima": (-12.0464, -77.0428, "Peru"), "Cusco": (-13.5320, -71.9675, "Peru"),
    "Rio de Janeiro": (-22.9068, -43.1729, "Brazil"), "Sao Paulo": (-23.5505, -46.6333, "Brazil"),
    "Buenos Aires": (-34.6037, -58.3816, "Argentina"), "Santiago": (-33.4489, -70.6693, "Chile"),
    # Africa
    "Cape Town": (-33.9249, 18.4241, "South Africa"), "Johannesburg": (-26.2041, 28.0473, "South Africa"),
    "Nairobi": (-1.2921, 36.8219, "Kenya"), "Cairo": (30.0444, 31.2357, "Egypt"),
    "Marrakech": (31.6295, -7.9811, "Morocco"), "Zanzibar": (-6.1659, 39.2026, "Tanzania"),
}

# Used only when no city matches. Roughly central points.
COUNTRIES: dict[str, tuple[float, float]] = {
    "Australia": (-25.27, 133.78), "New Zealand": (-41.5, 172.5), "Japan": (36.2, 138.25),
    "China": (35.86, 104.2), "South Korea": (36.5, 127.9), "Thailand": (15.87, 100.99),
    "Vietnam": (14.06, 108.28), "Indonesia": (-2.5, 118.0), "Malaysia": (4.2, 101.98),
    "Philippines": (12.88, 121.77), "India": (21.0, 78.0), "Nepal": (28.39, 84.12),
    "Sri Lanka": (7.87, 80.77), "United Kingdom": (54.0, -2.0), "England": (52.36, -1.17),
    "Scotland": (56.49, -4.2), "Ireland": (53.41, -8.24), "France": (46.6, 2.2),
    "Germany": (51.17, 10.45), "Italy": (42.8, 12.6), "Spain": (40.0, -3.7),
    "Portugal": (39.4, -8.2), "Greece": (39.07, 21.82), "Switzerland": (46.82, 8.23),
    "Netherlands": (52.13, 5.29), "Austria": (47.52, 14.55), "Croatia": (45.1, 15.2),
    "Turkey": (38.96, 35.24), "Iceland": (64.96, -19.02), "Norway": (60.47, 8.47),
    "Sweden": (60.13, 18.64), "United States": (39.8, -98.6), "USA": (39.8, -98.6),
    "Canada": (56.13, -106.35), "Mexico": (23.63, -102.55), "Peru": (-9.19, -75.02),
    "Brazil": (-14.24, -51.93), "Argentina": (-38.42, -63.62), "Chile": (-35.68, -71.54),
    "South Africa": (-30.56, 22.94), "Kenya": (-0.02, 37.91), "Egypt": (26.82, 30.8),
    "Morocco": (31.79, -7.09), "Fiji": (-17.71, 178.07), "Singapore": (1.35, 103.82),
    "United Arab Emirates": (23.42, 53.85), "Qatar": (25.35, 51.18),
}

NEAR_KM = 60  # photos this close together count as the same destination


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


_CITY_KEYS = sorted(CITIES, key=len, reverse=True)
_COUNTRY_KEYS = sorted(COUNTRIES, key=len, reverse=True)


def lookup_place(text: str) -> dict | None:
    """Match a typed place ('Gold Coast, Queensland', 'Paris, France') to a known location."""
    t = _norm(text or "")
    if not t:
        return None
    for name in _CITY_KEYS:
        if re.search(rf"\b{re.escape(_norm(name))}\b", t):
            lat, lon, country = CITIES[name]
            return {"name": name, "country": country, "lat": lat, "lon": lon}
    for name in _COUNTRY_KEYS:
        if re.search(rf"\b{re.escape(_norm(name))}\b", t):
            lat, lon = COUNTRIES[name]
            return {"name": name, "country": name, "lat": lat, "lon": lon}
    return None


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2 +
         math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(h))


def nearest_city(lat: float, lon: float, within_km: float = NEAR_KM) -> str | None:
    best = min(CITIES, key=lambda n: distance_km((lat, lon), CITIES[n][:2]))
    return best if distance_km((lat, lon), CITIES[best][:2]) <= within_km else None


def locate(photo: dict) -> dict | None:
    """Where a photo was taken: camera GPS first, then the user's typed place."""
    gps = photo.get("metadata", {}).get("gps")
    typed = photo.get("place", "").strip()
    if gps:
        known = lookup_place(typed)
        if known and distance_km((gps["latitude"], gps["longitude"]), (known["lat"], known["lon"])) <= NEAR_KM:
            name, country = known["name"], known["country"]
        elif (city := nearest_city(gps["latitude"], gps["longitude"])):
            name, country = city, CITIES[city][2]
        else:
            name, country = typed or "Unnamed place", ""
        return {"name": name, "country": country, "lat": gps["latitude"], "lon": gps["longitude"],
                "source": "camera location"}
    known = lookup_place(typed)
    if known:
        return {**known, "source": "place you entered"}
    return None


def camera_place_name(photo: dict) -> str:
    """'Doha, Qatar' for a photo whose camera location is near a known town or city, else ''."""
    gps = photo.get("metadata", {}).get("gps")
    if not gps:
        return ""
    city = nearest_city(gps["latitude"], gps["longitude"])
    if not city:
        return ""
    country = CITIES[city][2]
    return city if country == city else f"{city}, {country}"


def autofill_from_camera(photo: dict) -> bool:
    """Fill empty When/Where boxes from the photo's camera data, once per box.
    Never overwrites what the user typed; if they later clear a box it stays clear.
    Returns True if anything changed."""
    tried = set(photo.get("autofill_tried", []))
    changed = False
    meta = photo.get("metadata", {})
    if "event_date" not in tried and meta.get("capture_date"):
        tried.add("event_date")
        if not photo.get("event_date", "").strip():
            photo["event_date"] = meta["capture_date"]
            photo["event_date_source"] = "camera"
            changed = True
    if "place" not in tried and meta.get("gps"):
        name = camera_place_name(photo)
        if name:
            tried.add("place")
            if not photo.get("place", "").strip():
                photo["place"] = name
                photo["place_source"] = "camera location"
                changed = True
    if tried != set(photo.get("autofill_tried", [])):
        photo["autofill_tried"] = sorted(tried)
        changed = True
    return changed


def photo_date(photo: dict) -> str:
    return photo.get("event_date") or photo.get("metadata", {}).get("capture_date") or ""


def build_trips(photos: list[dict]) -> tuple[list[dict], list[dict]]:
    """Group photos (in date order) into consecutive stops. Returns (stops, unmapped photos)."""
    stops: list[dict] = []
    unmapped: list[dict] = []
    for photo in chronological_photos({"photos": photos}):
        loc = locate(photo)
        if not loc:
            unmapped.append(photo)
            continue
        last = stops[-1] if stops else None
        if last and (last["name"] == loc["name"] or
                     distance_km((last["lat"], last["lon"]), (loc["lat"], loc["lon"])) <= NEAR_KM):
            last["photo_ids"].append(photo["id"])
            last["sources"].add(loc["source"])
            if photo_date(photo):
                last["dates"].append(photo_date(photo))
            continue
        stops.append({"name": loc["name"], "country": loc["country"], "lat": loc["lat"], "lon": loc["lon"],
                      "sources": {loc["source"]}, "photo_ids": [photo["id"]],
                      "dates": [photo_date(photo)] if photo_date(photo) else []})
    for i, stop in enumerate(stops, 1):
        stop["number"] = i
        stop["source"] = " and ".join(sorted(stop.pop("sources")))
        stop["label"] = f"{stop['name']}, {stop['country']}" if stop["country"] and stop["country"] != stop["name"] else stop["name"]
        dates = sorted(stop.pop("dates"))
        stop["start"], stop["end"] = (dates[0], dates[-1]) if dates else ("", "")
        stop["when"] = stop["start"] if stop["start"] == stop["end"] else f"{stop['start']} – {stop['end']}"
    return stops, unmapped


def chapters_from_trips(stops: list[dict], photos: list[dict]) -> list[dict]:
    """One chapter per destination, built only from the user's own notes (nothing invented)."""
    by_id = {p["id"]: p for p in photos}
    chapters = []
    for stop in stops:
        lines = []
        for pid in stop["photo_ids"]:
            p = by_id[pid]
            moment = (p.get("caption", "").strip() or p.get("observation", "").strip()).rstrip(".!? ")
            memory = p.get("memory", "").strip()
            text = " ".join(x for x in ((moment + ".") if moment else "", memory) if x)
            lines.append(text or "Add a memory to tell the story behind this photo.")
        title = stop["label"] + (f" · {stop['start'][:7]}" if stop["start"] else "")
        chapters.append({"title": title, "text": "\n\n".join(lines), "photo_ids": list(stop["photo_ids"])})
    return chapters
