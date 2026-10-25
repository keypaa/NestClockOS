"""Weather via Open-Meteo (no API key)."""
import json, os, urllib.request

CONDITIONS = {
    0: ("Clear sky", "Ciel dégagé"),
    1: ("Mainly clear", "Peu nuageux"),
    2: ("Partly cloudy", "Partiellement nuageux"),
    3: ("Overcast", "Couvert"),
    45: ("Fog", "Brouillard"),
    48: ("Depositing rime fog", "Brouillard givrant"),
    51: ("Light drizzle", "Bruine légère"),
    53: ("Moderate drizzle", "Bruine modérée"),
    55: ("Dense drizzle", "Bruine dense"),
    61: ("Slight rain", "Pluie légère"),
    63: ("Moderate rain", "Pluie modérée"),
    65: ("Heavy rain", "Pluie forte"),
    71: ("Slight snow", "Neige légère"),
    73: ("Moderate snow", "Neige modérée"),
    75: ("Heavy snow", "Neige forte"),
    80: ("Slight showers", "Averses légères"),
    81: ("Moderate showers", "Averses modérées"),
    82: ("Violent showers", "Averses violentes"),
    95: ("Thunderstorm", "Orage"),
    96: ("Thunderstorm with hail", "Orage avec grêle"),
    99: ("Thunderstorm with heavy hail", "Orage avec grêle"),
}


def fetch(lat=None, lon=None):
    lat = float(os.environ.get("NESTCLOCK_CITY_LAT", lat if lat is not None else 48.8566))
    lon = float(os.environ.get("NESTCLOCK_CITY_LON", lon if lon is not None else 2.3522))
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&current=temperature_2m,weather_code,wind_speed_10m")
    with urllib.request.urlopen(url, timeout=8) as r:
        data = json.load(r)
    cur = data.get("current", {})
    code = cur.get("weather_code", -1)
    en, fr = CONDITIONS.get(code, ("Unknown", "Inconnu"))
    return {
        "lat": lat, "lon": lon,
        "temp_c": cur.get("temperature_2m"),
        "wind_kmh": cur.get("wind_speed_10m"),
        "code": code,
        "condition_en": en,
        "condition_fr": fr,
    }
