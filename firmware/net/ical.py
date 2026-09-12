"""Google Calendar secret iCal — stream parse (low RAM).

ICAL_URL must be the secret .ics address, e.g.
  https://calendar.google.com/calendar/ical/.../private-.../basic.ics
"""

import gc

try:
    import usocket as socket
except ImportError:
    import socket
try:
    import ussl as ssl
except ImportError:
    import ssl

_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _dim(y, m):
    if m == 2 and _leap(y):
        return 29
    return _DAYS[m - 1]


def _shift_phoenix(y, mo, d, h, mi, from_utc):
    if not from_utc:
        return y, mo, d, h, mi
    h -= 7
    while h < 0:
        h += 24
        d -= 1
        if d < 1:
            mo -= 1
            if mo < 1:
                mo = 12
                y -= 1
            d = _dim(y, mo)
    return y, mo, d, h, mi


def _parse_date(value):
    value = value.strip()
    if "T" in value:
        date, tim = value.split("T", 1)
        from_utc = tim.endswith("Z")
        tim = tim.rstrip("Z")
        y = int(date[0:4])
        mo = int(date[4:6])
        d = int(date[6:8])
        h = int(tim[0:2]) if len(tim) >= 2 else 0
        mi = int(tim[2:4]) if len(tim) >= 4 else 0
        y, mo, d, h, mi = _shift_phoenix(y, mo, d, h, mi, from_utc)
        return y, mo, d, h, mi, False
    y = int(value[0:4])
    mo = int(value[4:6])
    d = int(value[6:8])
    return y, mo, d, 0, 0, True


def _add_days(y, m, d, days):
    d += days
    while d > _dim(y, m):
        d -= _dim(y, m)
        m += 1
        if m > 12:
            m = 1
            y += 1
    while d < 1:
        m -= 1
        if m < 1:
            m = 12
            y -= 1
        d += _dim(y, m)
    return y, m, d


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


def _readline(sock):
    buf = bytearray()
    while True:
        ch = sock.read(1)
        if not ch:
            if not buf:
                return None
            break
        if ch == b"\n":
            break
        if ch != b"\r":
            buf.extend(ch)
            if len(buf) > 2000:
                break
    try:
        return bytes(buf).decode()
    except Exception:
        return bytes(buf).decode("latin-1")


def _handle_event(cur, today_ymd, tomorrow_ymd, events_today, events_tomorrow, max_per_day):
    if cur.get("status") == "CANCELLED" or not cur.get("start"):
        return
    y, mo, d, h, mi, all_day = cur["start"]
    day = (y, mo, d)
    item = {
        "start": "%02d:%02d" % (h, mi) if not all_day else None,
        "end": None,
        "title": (cur.get("summary") or "")[:40],
        "all_day": all_day,
    }
    if cur.get("end") and not all_day:
        _ey, _emo, _ed, eh, emi, _ = cur["end"]
        item["end"] = "%02d:%02d" % (eh, emi)
    if day == today_ymd and len(events_today) < max_per_day:
        events_today.append(item)
    elif day == tomorrow_ymd and len(events_tomorrow) < max_per_day:
        events_tomorrow.append(item)


def fetch(ical_url, today_ymd, max_per_day=12):
    if "basic.ics" not in ical_url and "/ical/" not in ical_url:
        raise ValueError(
            "Bad ICAL_URL — use Google Settings → Integrate → Secret iCal (.../basic.ics)"
        )

    tomorrow_ymd = _add_days(today_ymd[0], today_ymd[1], today_ymd[2], 1)
    events_today = []
    events_tomorrow = []
    host, path = _parse_url(ical_url)

    gc.collect()
    ai = socket.getaddrinfo(host, 443, 0, socket.SOCK_STREAM)[0]
    sock = socket.socket(ai[0], ai[1], ai[2])
    try:
        sock.connect(ai[-1])
        sock = ssl.wrap_socket(sock, server_hostname=host)
        sock.write(
            (
                "GET %s HTTP/1.0\r\nHost: %s\r\nUser-Agent: pico-eink\r\nConnection: close\r\n\r\n"
                % (path, host)
            ).encode()
        )

        while True:
            line = _readline(sock)
            if line is None or line == "":
                break

        cur = None
        pending = None
        while True:
            raw = _readline(sock)
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
                    cur = {"summary": "(no title)", "status": "CONFIRMED"}
                elif u == "END:VEVENT" and cur is not None:
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
                        val = _prop(line, "DTSTART")
                        if val:
                            cur["start"] = _parse_date(val)
                    elif u.startswith("DTEND"):
                        val = _prop(line, "DTEND")
                        if val:
                            cur["end"] = _parse_date(val)
            if eof:
                break
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
    print("Calendar events today/tomorrow:", len(events_today), len(events_tomorrow))
    return {"today": events_today, "tomorrow": events_tomorrow}
