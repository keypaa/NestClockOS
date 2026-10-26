"""Weather via Open-Meteo (no API key)."""
import datetime, json, os, urllib.request

CONDITIONS = {
    0: ("Clear sky", "Ciel dégagé"),
    1: ("Mainly clear", "Peu nuageux"),
    2: ("Partly cloudy", "Peu nuageux"),
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

EN_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
FR_DAYS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
ADVISORY = {
    # WMO code or ("kind", threshold) -> (en, fr)
}


def _f(env, default):
    v = os.environ.get(env, "")
    try:
        return float(v) if v.strip() else default
    except ValueError:
        return default


def _r(x):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return x
    return int(v) if v == int(v) and abs(v) < 1000 else round(v, 1)


def _advisory(code, temp, wind):
    code = code if code is not None else -1
    if code in (95, 96, 99):
        return (("Thunderstorm advisory", "Risque d'orages"),
                ("Thunderstorms likely. Stay sheltered if outside.", "Orages probables. Restez à l'abri."))
    if code in (75, 77, 85, 86):
        return (("Heavy snow", "Neige forte"),
                ("Snow expected; plan extra travel time.", "Neige attendue; prévoyez un temps de trajet plus long."))
    if code in (65, 67, 82):
        return (("Heavy rain advisory", "Averses fortes"),
                ("Heavy or violent showers likely.", "Averses fortes à violentes probables."))
    if temp is not None and temp <= 0:
        return (("Frost advisory", "Risque de verglas"),
                ("Sub-zero conditions; ice risk overnight.", "Températures négatives; risque de verglas."))
    if wind is not None and wind >= 50:
        return (("Strong wind", "Vent fort"),
                ("Strong winds; secure loose items.", "Vents forts; sécurisez les objets."))
    if code in (45, 48):
        return (("Low visibility", "Visibilité réduite"),
                ("Fog may reduce visibility.", "Brouillard, visibilité réduite."))
    return None


def fetch(lat=None, lon=None):
    lat = _f("NESTCLOCK_CITY_LAT", lat if lat is not None else 48.8566)
    lon = _f("NESTCLOCK_CITY_LON", lon if lon is not None else 2.3522)
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        "&daily=temperature_2m_max,temperature_2m_min,weather_code"
        "&forecast_days=6"
        "&timezone=auto"
    )
    with urllib.request.urlopen(url, timeout=8) as r:
        data = json.load(r)
    cur = data.get("current", {})
    code = cur.get("weather_code", -1)
    en, fr = CONDITIONS.get(code, ("Unknown", "Inconnu"))
    temp = _r(cur.get("temperature_2m"))
    wind = _r(cur.get("wind_speed_10m"))
    hum = _r(cur.get("relative_humidity_2m"))
    adv = _advisory(code, temp, wind)

    daily = data.get("daily", {})
    days = daily.get("time") or []
    # today + up to 5 next days
    forecast = []
    for i, ds in enumerate(days[:6]):
        try:
            wc = datetime.date.fromisoformat(ds).weekday()
        except (ValueError, TypeError):
            wc = 0
        code_i = (daily.get("weather_code") or [])[i] if i < len(daily.get("weather_code") or []) else code
        eni, fri = CONDITIONS.get(code_i, ("Unknown", "Inconnu"))
        forecast.append({
            "date": ds,
            "dayname_en": EN_DAYS[wc],
            "dayname_fr": FR_DAYS[wc],
            "hi": _r((daily.get("temperature_2m_max") or [])[i] if i < len(daily.get("temperature_2m_max") or []) else temp),
            "lo": _r((daily.get("temperature_2m_min") or [])[i] if i < len(daily.get("temperature_2m_min") or []) else temp),
            "code": code_i,
            "condition_en": eni,
            "condition_fr": fri,
        })

    return {
        "lat": lat, "lon": lon,
        "temp_c": temp,
        "wind_kmh": wind,
        "humidity": hum,
        "code": code,
        "condition_en": en,
        "condition_fr": fr,
        "forecast": forecast,
        "advisory_en": (adv[0][0] if adv else None),
        "advisory_fr": (adv[0][1] if adv else None),
        "advisory_body_en": (adv[1][0] if adv else None),
        "advisory_body_fr": (adv[1][1] if adv else None),
    }
