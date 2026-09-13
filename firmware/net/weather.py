"""Open-Meteo: current + today + next N hours.

Optional same-day flash cache (WEATHER_CACHE_DAY) — one download per Phoenix day.
"""

from net.http import http_get_json

_CACHE_PATH = "wx_cache.json"

_CODES = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Fog",
    51: "Drizzle",
    53: "Drizzle",
    55: "Drizzle",
    61: "Rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Snow",
    73: "Snow",
    75: "Snow",
    80: "Showers",
    81: "Showers",
    82: "Heavy showers",
    95: "Thunderstorm",
    96: "Thunderstorm",
    99: "Thunderstorm",
}


def _label(code):
    return _CODES.get(code, "Code %s" % code)


def icon_key(code):
    c = int(code or 0)
    if c == 0:
        return "sun"
    if c in (1, 2):
        return "partly"
    if c == 3:
        return "cloud"
    if c in (45, 48):
        return "fog"
    if c in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return "rain"
    if c in (71, 73, 75, 77, 85, 86):
        return "snow"
    if c in (95, 96, 99):
        return "storm"
    return "cloud"


def _parse_hour(iso):
    try:
        return int(iso.split("T")[1][0:2])
    except Exception:
        return -1


def _parse_ymd(iso):
    try:
        d = iso.split("T")[0]
        y, m, day = d.split("-")
        return int(y), int(m), int(day)
    except Exception:
        return None


def _wind_dir(deg):
    if deg is None:
        return ""
    dirs = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return dirs[int((deg + 22.5) // 45) % 8]


def _json():
    try:
        import ujson as json
    except ImportError:
        import json
    return json


def _cache_load(today_ymd):
    try:
        json = _json()
        with open(_CACHE_PATH, "r") as f:
            data = json.loads(f.read())
        ymd = data.get("ymd")
        if not ymd or tuple(ymd) != tuple(today_ymd):
            return None
        return data.get("weather")
    except Exception:
        return None


def _cache_save(today_ymd, weather):
    try:
        json = _json()
        payload = {
            "ymd": [int(today_ymd[0]), int(today_ymd[1]), int(today_ymd[2])],
            "weather": weather,
        }
        with open(_CACHE_PATH, "w") as f:
            f.write(json.dumps(payload))
        print("Weather cached for %04d-%02d-%02d" % tuple(today_ymd))
    except Exception as e:
        print("Weather cache save failed:", e)


def _trim_hourly(weather, now_ymd, now_hour, hours_ahead):
    """From a day cache, show hourly starting at current hour."""
    if not weather:
        return weather
    out = {
        "current": weather.get("current"),
        "today": weather.get("today"),
        "hourly": [],
    }
    hourly = weather.get("hourly") or []
    started = False
    for slot in hourly:
        hour = int(slot.get("hour", -1))
        if not started:
            if hour < int(now_hour):
                continue
            started = True
        out["hourly"].append(slot)
        if len(out["hourly"]) >= int(hours_ahead):
            break
    return out


def _fetch_network(
    lat,
    lon,
    temp_unit="fahrenheit",
    timezone="America/Phoenix",
    now_ymd=None,
    now_hour=0,
    hours_ahead=6,
):
    wind_unit = "mph" if temp_unit == "fahrenheit" else "kmh"
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=%s&longitude=%s"
        "&current=temperature_2m,weather_code,precipitation,wind_speed_10m,wind_direction_10m"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        "&hourly=temperature_2m,weather_code,precipitation_probability"
        "&temperature_unit=%s"
        "&wind_speed_unit=%s"
        "&timezone=%s"
        "&forecast_days=2"
    ) % (lat, lon, temp_unit, wind_unit, timezone.replace("/", "%2F"))

    data = http_get_json(url)

    cur = data.get("current") or {}
    cur_code = int(cur.get("weather_code") or 0)
    current = {
        "temp": int(round(cur["temperature_2m"])) if "temperature_2m" in cur else None,
        "code": cur_code,
        "label": _label(cur_code),
        "icon": icon_key(cur_code),
        "precip": cur.get("precipitation"),
        "wind": int(round(cur["wind_speed_10m"])) if "wind_speed_10m" in cur else None,
        "wind_dir": _wind_dir(cur.get("wind_direction_10m")),
    }

    daily = data.get("daily") or {}
    today = None
    if daily.get("time"):
        code = int(daily["weather_code"][0])
        precip = None
        if daily.get("precipitation_probability_max"):
            precip = int(daily["precipitation_probability_max"][0] or 0)
        today = {
            "date": daily["time"][0],
            "high": int(round(daily["temperature_2m_max"][0])),
            "low": int(round(daily["temperature_2m_min"][0])),
            "code": code,
            "label": _label(code),
            "icon": icon_key(code),
            "precip": precip,
        }

    # Store a full day+ of hourly in cache so later draws can trim
    store_hours = max(int(hours_ahead), 24)
    hourly = []
    h = data.get("hourly") or {}
    times = h.get("time") or []
    temps = h.get("temperature_2m") or []
    codes = h.get("weather_code") or []
    precip_h = h.get("precipitation_probability") or []
    started = False
    for i, iso in enumerate(times):
        ymd = _parse_ymd(iso)
        hour = _parse_hour(iso)
        if not started:
            if now_ymd and ymd != now_ymd:
                continue
            if hour < int(now_hour):
                continue
            started = True
        if len(hourly) >= store_hours:
            break
        code = int(codes[i]) if i < len(codes) else 0
        pr = None
        if i < len(precip_h) and precip_h[i] is not None:
            pr = int(precip_h[i])
        hourly.append(
            {
                "hour": hour,
                "temp": int(round(temps[i])) if i < len(temps) else None,
                "code": code,
                "label": _label(code),
                "icon": icon_key(code),
                "precip": pr,
            }
        )

    return {"current": current, "today": today, "hourly": hourly}


def fetch(
    lat,
    lon,
    temp_unit="fahrenheit",
    timezone="America/Phoenix",
    now_ymd=None,
    now_hour=0,
    hours_ahead=6,
    use_cache=True,
):
    if use_cache and now_ymd:
        cached = _cache_load(now_ymd)
        if cached is not None:
            print("Weather from cache")
            return _trim_hourly(cached, now_ymd, now_hour, hours_ahead)

    weather = _fetch_network(
        lat,
        lon,
        temp_unit=temp_unit,
        timezone=timezone,
        now_ymd=now_ymd,
        now_hour=now_hour,
        hours_ahead=hours_ahead,
    )
    if use_cache and now_ymd:
        _cache_save(now_ymd, weather)
    return _trim_hourly(weather, now_ymd, now_hour, hours_ahead)
