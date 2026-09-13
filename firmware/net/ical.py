"""Google Calendar iCal — stream parse (low RAM).

One or more .ics addresses (secret or public), e.g.
  https://calendar.google.com/calendar/ical/.../private-.../basic.ics
Use secrets.ICAL_URLS = (url1, url2) to merge calendars.
"""

import gc
import time

try:
    import usocket as socket
except ImportError:
    import socket
try:
    import ussl as ssl
except ImportError:
    import ssl


def _mktime(y, m, d, h=12, mi=0):
    """Portable mktime (CPython wants 9-tuple; MicroPython often 8)."""
    try:
        return time.mktime((y, m, d, h, mi, 0, 0, 0, -1))
    except (TypeError, OverflowError):
        return time.mktime((y, m, d, h, mi, 0, 0, 0))


def _weekday(y, m, d):
    """0=Mon … 6=Sun (MicroPython localtime)."""
    return time.localtime(_mktime(y, m, d))[6]


def _ymd_add(y, m, d, days):
    t = _mktime(y, m, d) + int(days) * 86400
    lt = time.localtime(t)
    return lt[0], lt[1], lt[2]


def _us_dst(y, mo, d):
    """Rough US DST (2nd Sun Mar → 1st Sun Nov)."""
    if mo < 3 or mo > 11:
        return False
    if mo > 3 and mo < 11:
        return True
    if mo == 3:
        # second Sunday
        w = _weekday(y, 3, 1)  # 0=Mon
        first_sun = 1 + (6 - w) % 7
        second_sun = first_sun + 7
        return d >= second_sun
    # November: before first Sunday = DST
    w = _weekday(y, 11, 1)
    first_sun = 1 + (6 - w) % 7
    return d < first_sun


def _eu_dst(y, mo, d):
    """EU DST last Sunday March → last Sunday October."""
    if mo < 3 or mo > 10:
        return False
    if mo > 3 and mo < 10:
        return True
    if mo == 3:
        w = _weekday(y, 3, 31)
        last_sun = 31 - ((w - 6) % 7)
        return d >= last_sun
    w = _weekday(y, 10, 31)
    last_sun = 31 - ((w - 6) % 7)
    return d < last_sun


def _tz_ahead_of_phx(tzid, y, mo, d):
    if not tzid:
        return 0
    tzid = tzid.strip().strip('"')
    if tzid in ("America/Phoenix", "MST"):
        return 0
    if tzid in ("UTC", "Z"):
        return 7
    if tzid == "America/Denver":
        return 1 if _us_dst(y, mo, d) else 0
    if tzid in ("America/Los_Angeles", "America/Pacific"):
        return 0 if _us_dst(y, mo, d) else -1
    if tzid == "America/Chicago":
        return 2 if _us_dst(y, mo, d) else 1
    if tzid in ("America/New_York", "America/Toronto", "America/Detroit"):
        return 3 if _us_dst(y, mo, d) else 2
    if tzid in ("Europe/Belgrade", "Europe/Zagreb"):
        return 9 if _eu_dst(y, mo, d) else 8
    return 0


def _shift_hours(y, mo, d, h, mi, hours):
    """Add hours (can be negative) to a local wall clock."""
    total = h * 60 + mi + int(hours) * 60
    while total < 0:
        total += 24 * 60
        y, mo, d = _ymd_add(y, mo, d, -1)
    while total >= 24 * 60:
        total -= 24 * 60
        y, mo, d = _ymd_add(y, mo, d, 1)
    return y, mo, d, total // 60, total % 60


def _param(line, name):
    upper = line.upper()
    key = name.upper() + "="
    idx = upper.find(key)
    if idx < 0:
        return None
    start = idx + len(key)
    end = start
    while end < len(line) and line[end] not in (";", ":"):
        end += 1
    return line[start:end]


def _parse_dt(line):
    """Parse DTSTART/DTEND line → (y, mo, d, h, mi, all_day) in America/Phoenix."""
    val = line.split(":", 1)[1].strip() if ":" in line else ""
    tzid = _param(line, "TZID")
    if "T" not in val:
        y = int(val[0:4])
        mo = int(val[4:6])
        d = int(val[6:8])
        return y, mo, d, 0, 0, True
    from_utc = val.endswith("Z")
    val = val.rstrip("Z")
    y = int(val[0:4])
    mo = int(val[4:6])
    d = int(val[6:8])
    h = int(val[9:11]) if len(val) >= 11 else 0
    mi = int(val[11:13]) if len(val) >= 13 else 0
    if from_utc:
        y, mo, d, h, mi = _shift_hours(y, mo, d, h, mi, -7)
    elif tzid:
        ahead = _tz_ahead_of_phx(tzid, y, mo, d)
        # wall clock in tzid → Phoenix: subtract ahead
        y, mo, d, h, mi = _shift_hours(y, mo, d, h, mi, -ahead)
    return y, mo, d, h, mi, False


def _add_days(y, m, d, days):
    return _ymd_add(y, m, d, days)


def _ymd_cmp(a, b):
    return (a > b) - (a < b)


def _parse_rrule(text):
    parts = {}
    for chunk in (text or "").split(";"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.upper()] = v
    return parts


_BYDAY = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def _parse_until(val):
    val = (val or "").rstrip("Z")
    if len(val) < 8:
        return None
    return (int(val[0:4]), int(val[4:6]), int(val[6:8]))


def _week_id(y, m, d, wkst):
    """Stable week id aligned to WKST (0=Mon…6=Sun)."""
    t = int(_mktime(y, m, d))
    wd = time.localtime(t)[6]
    t0 = t - ((wd - wkst) % 7) * 86400
    return t0 // 86400


def _rrule_on_day(day_ymd, start, rrule_text, exdates):
    """True if RRULE produces an occurrence on day_ymd (Phoenix date)."""
    if day_ymd in exdates:
        return False
    sy, smo, sd, sh, smi, _all_day = start
    start_ymd = (sy, smo, sd)
    if _ymd_cmp(day_ymd, start_ymd) < 0:
        return False
    parts = _parse_rrule(rrule_text)
    freq = parts.get("FREQ")
    if not freq:
        return False
    interval = int(parts.get("INTERVAL", "1") or "1")
    until = _parse_until(parts.get("UNTIL"))
    if until and _ymd_cmp(day_ymd, until) > 0:
        return False

    wkst_token = parts.get("WKST", "MO")
    wkst = _BYDAY.get(wkst_token, 0)

    if freq == "YEARLY":
        return day_ymd[1] == smo and day_ymd[2] == sd

    if freq == "DAILY":
        t0 = _mktime(sy, smo, sd)
        t1 = _mktime(day_ymd[0], day_ymd[1], day_ymd[2])
        days = int((t1 - t0) // 86400)
        return days % interval == 0

    if freq == "WEEKLY":
        by = parts.get("BYDAY")
        if by:
            days = set()
            for tok in by.split(","):
                tok = tok[-2:].upper()
                if tok in _BYDAY:
                    days.add(_BYDAY[tok])
        else:
            days = {_weekday(sy, smo, sd)}
        if _weekday(day_ymd[0], day_ymd[1], day_ymd[2]) not in days:
            return False
        w0 = _week_id(sy, smo, sd, wkst)
        w1 = _week_id(day_ymd[0], day_ymd[1], day_ymd[2], wkst)
        return ((w1 - w0) // 1) % interval == 0

    if freq == "MONTHLY":
        # BYDAY=3TU etc. not supported yet — fall back to same month-day
        if "BYMONTHDAY" in parts:
            try:
                md = int(parts["BYMONTHDAY"])
            except Exception:
                md = sd
            if day_ymd[2] != md:
                return False
        elif "BYDAY" in parts:
            return False
        elif day_ymd[2] != sd:
            return False
        months = (day_ymd[0] - sy) * 12 + (day_ymd[1] - smo)
        return months % interval == 0

    return False


def _prop(line, name):
    upper = line.upper()
    if not upper.startswith(name):
        return None
    if len(line) > len(name) and line[len(name)] not in (":", ";"):
        return None
    idx = line.find(":")
    if idx < 0:
        return None
    return line[idx + 1 :]


def _parse_url(url):
    if not url.startswith("https://"):
        raise ValueError("ICAL_URL must be https secret .ics address")
    rest = url[8:]
    slash = rest.find("/")
    if slash < 0:
        return rest, "/"
    return rest[:slash], rest[slash:]


def _ymd_int(y, m, d):
    return int(y) * 10000 + int(m) * 100 + int(d)


def _quick_ymd(val):
    """First YYYYMMDD in a DTSTART/DTEND value (no TZ math)."""
    val = (val or "").strip().rstrip("Z")
    if len(val) < 8:
        return None
    try:
        return int(val[0:4]), int(val[4:6]), int(val[6:8])
    except Exception:
        return None


class _LineReader:
    """Buffered line reader — never sock.read(1)."""

    def __init__(self, sock, chunk=2048):
        self.sock = sock
        self.chunk = chunk
        self.buf = bytearray()
        self.eof = False

    def readline(self):
        while True:
            nl = self.buf.find(b"\n")
            if nl >= 0:
                raw = self.buf[:nl]
                # MicroPython bytearray has no slice delete
                self.buf = bytearray(self.buf[nl + 1 :])
                if raw.endswith(b"\r"):
                    raw = raw[:-1]
                if len(raw) > 2000:
                    raw = raw[:2000]
                try:
                    return bytes(raw).decode()
                except Exception:
                    return bytes(raw).decode("latin-1")
            if self.eof:
                if not self.buf:
                    return None
                raw = bytes(self.buf)
                self.buf = bytearray()
                if raw.endswith(b"\r"):
                    raw = raw[:-1]
                try:
                    return raw.decode()
                except Exception:
                    return raw.decode("latin-1")
            try:
                more = self.sock.read(self.chunk)
            except Exception:
                more = None
            if not more:
                self.eof = True
            else:
                self.buf.extend(more)


def _make_item(cur, h, mi, all_day):
    item = {
        "start": None if all_day else "%02d:%02d" % (h, mi),
        "end": None,
        "title": (cur.get("summary") or "")[:40],
        "all_day": all_day,
    }
    if cur.get("end") and not all_day:
        _ey, _emo, _ed, eh, emi, _ = cur["end"]
        item["end"] = "%02d:%02d" % (eh, emi)
    return item


def _append_day(day, item, today_ymd, tomorrow_ymd, events_today, events_tomorrow, max_per_day):
    if day == today_ymd and len(events_today) < max_per_day:
        events_today.append(item)
    elif day == tomorrow_ymd and len(events_tomorrow) < max_per_day:
        events_tomorrow.append(item)


def _in_window_or_span(start_ymd, end_ymd, all_day, today_ymd, tomorrow_ymd):
    if start_ymd == today_ymd or start_ymd == tomorrow_ymd:
        return True
    if all_day and end_ymd:
        for day in (today_ymd, tomorrow_ymd):
            if _ymd_cmp(start_ymd, day) <= 0 and _ymd_cmp(day, end_ymd) < 0:
                return True
    return False


def _handle_event(cur, today_ymd, tomorrow_ymd, events_today, events_tomorrow, max_per_day):
    if cur.get("status") == "CANCELLED" or not cur.get("start"):
        return
    y, mo, d, h, mi, all_day = cur["start"]
    start_ymd = (y, mo, d)
    exdates = cur.get("exdates") or []
    end_ymd = None
    if cur.get("end"):
        ey, emo, ed, _eh, _emi, _ = cur["end"]
        end_ymd = (ey, emo, ed)

    if cur.get("rrule") and not cur.get("recurrence_id"):
        for day in (today_ymd, tomorrow_ymd):
            if _rrule_on_day(day, cur["start"], cur["rrule"], exdates):
                _append_day(
                    day,
                    _make_item(cur, h, mi, all_day),
                    today_ymd,
                    tomorrow_ymd,
                    events_today,
                    events_tomorrow,
                    max_per_day,
                )
        return

    if not _in_window_or_span(start_ymd, end_ymd, all_day, today_ymd, tomorrow_ymd):
        return

    if start_ymd not in exdates:
        _append_day(
            start_ymd,
            _make_item(cur, h, mi, all_day),
            today_ymd,
            tomorrow_ymd,
            events_today,
            events_tomorrow,
            max_per_day,
        )

    if all_day and end_ymd:
        for day in (today_ymd, tomorrow_ymd):
            if _ymd_cmp(start_ymd, day) <= 0 and _ymd_cmp(day, end_ymd) < 0:
                if day == start_ymd:
                    continue
                _append_day(
                    day,
                    _make_item(cur, 0, 0, True),
                    today_ymd,
                    tomorrow_ymd,
                    events_today,
                    events_tomorrow,
                    max_per_day,
                )


def _parse_stream(reader, today_ymd, tomorrow_ymd, events_today, events_tomorrow, max_per_day):
    """Parse one ICS body from a line reader into today/tomorrow lists."""
    today_i = _ymd_int(*today_ymd)
    cur = None
    pending = None
    while True:
        raw = reader.readline()
        if raw is None:
            line = pending
            pending = None
            eof = True
        else:
            if pending is not None and (raw.startswith(" ") or raw.startswith("\t")):
                pending += raw[1:]
                continue
            line = pending
            pending = raw
            eof = False
        if line:
            u = line.upper()
            if u == "BEGIN:VEVENT":
                cur = {
                    "summary": "(no title)",
                    "status": "CONFIRMED",
                    "exdates": [],
                }
            elif u == "END:VEVENT" and cur is not None:
                # Fast skip: old one-shots that cannot hit today/tomorrow
                if not cur.get("rrule"):
                    ymd = cur.get("_ymd")
                    end_q = cur.get("_end_ymd")
                    if ymd is not None:
                        yi = _ymd_int(*ymd)
                        if yi < today_i - 1:
                            if end_q is None or _ymd_int(*end_q) <= today_i:
                                cur = None
                                if eof:
                                    break
                                continue
                if cur.get("dsl") and not cur.get("start"):
                    cur["start"] = _parse_dt(cur["dsl"])
                if cur.get("del") and not cur.get("end"):
                    cur["end"] = _parse_dt(cur["del"])
                _handle_event(
                    cur, today_ymd, tomorrow_ymd, events_today, events_tomorrow, max_per_day
                )
                cur = None
            elif cur is not None:
                if u.startswith("SUMMARY"):
                    val = _prop(line, "SUMMARY")
                    if val is not None:
                        cur["summary"] = val.replace("\\,", ",").replace("\\n", " ")
                elif u.startswith("STATUS"):
                    val = _prop(line, "STATUS")
                    if val:
                        cur["status"] = val.upper()
                elif u.startswith("DTSTART"):
                    cur["dsl"] = line
                    cur["_ymd"] = _quick_ymd(_prop(line, "DTSTART"))
                elif u.startswith("DTEND"):
                    cur["del"] = line
                    cur["_end_ymd"] = _quick_ymd(_prop(line, "DTEND"))
                elif u.startswith("RRULE"):
                    val = _prop(line, "RRULE")
                    if val:
                        cur["rrule"] = val.strip()
                elif u.startswith("EXDATE"):
                    val = _prop(line, "EXDATE")
                    if val:
                        for part in val.split(","):
                            part = part.strip().rstrip("Z")
                            if len(part) >= 8:
                                cur["exdates"].append(
                                    (int(part[0:4]), int(part[4:6]), int(part[6:8]))
                                )
                elif u.startswith("RECURRENCE-ID"):
                    cur["recurrence_id"] = True
        if eof:
            break


def fetch(ical_url, today_ymd, max_per_day=12):
    """Download one .ics over a fresh TLS connection (HTTP/1.0 close)."""
    if "basic.ics" not in ical_url and "/ical/" not in ical_url:
        raise ValueError(
            "Bad ICAL_URL — use Google Settings → Integrate → Secret iCal (.../basic.ics)"
        )

    tomorrow_ymd = _add_days(today_ymd[0], today_ymd[1], today_ymd[2], 1)
    events_today = []
    events_tomorrow = []
    host, path = _parse_url(ical_url)

    t0 = time.ticks_ms() if hasattr(time, "ticks_ms") else None
    gc.collect()
    ai = socket.getaddrinfo(host, 443, 0, socket.SOCK_STREAM)[0]
    sock = socket.socket(ai[0], ai[1], ai[2])
    try:
        try:
            sock.settimeout(45)
        except Exception:
            pass
        sock.connect(ai[-1])
        sock = ssl.wrap_socket(sock, server_hostname=host)
        # HTTP/1.0 + close: Google sends a plain body (no chunked) — reliable on Pico
        sock.write(
            (
                "GET %s HTTP/1.0\r\nHost: %s\r\nUser-Agent: pico-eink\r\nConnection: close\r\n\r\n"
                % (path, host)
            ).encode()
        )
        reader = _LineReader(sock, chunk=2048)
        # Skip response headers
        while True:
            line = reader.readline()
            if line is None or line == "":
                break
        _parse_stream(
            reader, today_ymd, tomorrow_ymd, events_today, events_tomorrow, max_per_day
        )
    finally:
        try:
            sock.close()
        except Exception:
            pass
        gc.collect()

    def sort_key(ev):
        if ev["all_day"]:
            return (0, 0)
        parts = (ev["start"] or "99:99").split(":")
        return (int(parts[0]), int(parts[1]))

    events_today.sort(key=sort_key)
    events_tomorrow.sort(key=sort_key)
    if t0 is not None:
        try:
            ms = time.ticks_diff(time.ticks_ms(), t0)
            print(
                "Calendar events today/tomorrow:",
                len(events_today),
                len(events_tomorrow),
                "(%dms)" % ms,
            )
        except Exception:
            print("Calendar events today/tomorrow:", len(events_today), len(events_tomorrow))
    else:
        print("Calendar events today/tomorrow:", len(events_today), len(events_tomorrow))
    return {"today": events_today, "tomorrow": events_tomorrow}


def _event_key(ev):
    return (ev.get("start"), ev.get("end"), ev.get("title"), bool(ev.get("all_day")))


def _merge_day(dst, src, max_per_day):
    seen = {_event_key(ev) for ev in dst}
    for ev in src:
        if len(dst) >= max_per_day:
            break
        k = _event_key(ev)
        if k in seen:
            continue
        seen.add(k)
        dst.append(ev)


_CACHE_PATH = "cal_cache.json"


def _json():
    try:
        import ujson as json
    except ImportError:
        import json
    return json


def _cache_load(today_ymd):
    """Return cached today/tomorrow if saved for this Phoenix date."""
    try:
        json = _json()
        with open(_CACHE_PATH, "r") as f:
            data = json.loads(f.read())
        ymd = data.get("ymd")
        if not ymd or tuple(ymd) != tuple(today_ymd):
            return None
        return {
            "today": data.get("today") or [],
            "tomorrow": data.get("tomorrow") or [],
        }
    except Exception:
        return None


def _cache_save(today_ymd, result):
    try:
        json = _json()
        payload = {
            "ymd": [int(today_ymd[0]), int(today_ymd[1]), int(today_ymd[2])],
            "today": result.get("today") or [],
            "tomorrow": result.get("tomorrow") or [],
        }
        with open(_CACHE_PATH, "w") as f:
            f.write(json.dumps(payload))
        print("Calendar cached for %04d-%02d-%02d" % tuple(today_ymd))
    except Exception as e:
        print("Calendar cache save failed:", e)


def fetch_many(ical_urls, today_ymd, max_per_day=12, use_cache=True):
    """Fetch several calendars and merge today/tomorrow (deduped).

    use_cache=True: reuse flash cache for the same Phoenix day (no network).
    """
    if use_cache:
        cached = _cache_load(today_ymd)
        if cached is not None:
            print(
                "Calendar from cache today/tomorrow:",
                len(cached["today"]),
                len(cached["tomorrow"]),
            )
            return cached

    if isinstance(ical_urls, str):
        urls = (ical_urls,)
    else:
        urls = tuple(u for u in ical_urls if u)

    if not urls:
        raise ValueError("No ICAL_URL / ICAL_URLS configured")

    events_today = []
    events_tomorrow = []
    errors = []
    t0 = time.ticks_ms() if hasattr(time, "ticks_ms") else None
    for i, url in enumerate(urls):
        try:
            print("Calendar %d/%d..." % (i + 1, len(urls)))
            part = fetch(url, today_ymd, max_per_day=max_per_day)
            _merge_day(events_today, part.get("today") or [], max_per_day)
            _merge_day(events_tomorrow, part.get("tomorrow") or [], max_per_day)
        except Exception as e:
            print("Calendar %d failed:" % (i + 1), e)
            errors.append(e)
        gc.collect()

    if not events_today and not events_tomorrow and errors:
        # Prefer stale cache over total failure
        stale = None
        try:
            json = _json()
            with open(_CACHE_PATH, "r") as f:
                data = json.loads(f.read())
            stale = {
                "today": data.get("today") or [],
                "tomorrow": data.get("tomorrow") or [],
            }
            print("Calendar fetch failed — using older cache")
            return stale
        except Exception:
            pass
        raise errors[0]

    def sort_key(ev):
        if ev["all_day"]:
            return (0, 0)
        parts = (ev["start"] or "99:99").split(":")
        return (int(parts[0]), int(parts[1]))

    events_today.sort(key=sort_key)
    events_tomorrow.sort(key=sort_key)
    extra = ""
    if t0 is not None:
        try:
            extra = " (%dms)" % time.ticks_diff(time.ticks_ms(), t0)
        except Exception:
            pass
    print(
        "Merged calendar today/tomorrow:",
        len(events_today),
        len(events_tomorrow),
        "from",
        len(urls),
        "feeds" + extra,
    )
    result = {"today": events_today, "tomorrow": events_tomorrow}
    if use_cache:
        _cache_save(today_ymd, result)
    return result

