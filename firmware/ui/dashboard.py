"""Three-column desk dashboard (inspired by clean e-ink layout).

Colors that work on this 7.5" B panel:
  red paper + black ink + white accents.
"""

import framebuf

_FOLD = {
    ord("ć"): "c",
    ord("Ć"): "C",
    ord("č"): "c",
    ord("Č"): "C",
    ord("š"): "s",
    ord("Š"): "S",
    ord("ž"): "z",
    ord("Ž"): "Z",
    ord("đ"): "d",
    ord("Đ"): "D",
    ord("á"): "a",
    ord("à"): "a",
    ord("ä"): "a",
    ord("â"): "a",
    ord("é"): "e",
    ord("è"): "e",
    ord("ë"): "e",
    ord("í"): "i",
    ord("ì"): "i",
    ord("ó"): "o",
    ord("ö"): "o",
    ord("ú"): "u",
    ord("ü"): "u",
    ord("ñ"): "n",
    ord("—"): "-",
    ord("–"): "-",
    ord("’"): "'",
    ord("‘"): "'",
    ord("“"): '"',
    ord("”"): '"',
    ord("…"): "...",
}


def ascii(s):
    if not s:
        return ""
    if isinstance(s, bytes):
        try:
            s = s.decode("utf-8")
        except Exception:
            s = str(s)
    out = []
    for ch in str(s):
        o = ord(ch)
        if ch in ("\n", "\r", "\t"):
            out.append(" ")
        elif o < 128:
            out.append(ch)
        elif o in _FOLD:
            out.append(_FOLD[o])
        else:
            out.append("?")
    return "".join(out)


def clip(s, n):
    s = ascii(s)
    if len(s) <= n:
        return s
    return s[: max(0, n - 1)] + "."


def text_big(fb, s, x, y, ink, scale=2):
    s = ascii(s)
    if not s:
        return 0
    if scale <= 1:
        fb.text(s, x, y, ink)
        return 8
    tw = len(s) * 8
    buf = bytearray((tw // 8) * 8)
    tmp = framebuf.FrameBuffer(buf, tw, 8, framebuf.MONO_HLSB)
    tmp.fill(0xFF)
    tmp.text(s, 0, 0, 0x00)
    row_b = tw // 8
    for py in range(8):
        for px in range(tw):
            b = buf[py * row_b + (px >> 3)]
            if (b & (0x80 >> (px & 7))) == 0:
                fb.fill_rect(x + px * scale, y + py * scale, scale, scale, ink)
    return 8 * scale


def _icon(fb, kind, x, y, ink=0x00, s=2):
    p = lambda dx, dy, w=1, h=1: fb.fill_rect(x + dx * s, y + dy * s, w * s, h * s, ink)
    k = kind or "cloud"
    if k == "sun":
        p(3, 3, 4, 4)
        p(4, 0, 2, 1)
        p(4, 9, 2, 1)
        p(0, 4, 1, 2)
        p(9, 4, 1, 2)
        p(1, 1, 1, 1)
        p(8, 1, 1, 1)
        p(1, 8, 1, 1)
        p(8, 8, 1, 1)
    elif k == "partly":
        p(5, 1, 3, 3)
        p(1, 5, 7, 2)
        p(2, 4, 5, 1)
        p(2, 7, 5, 1)
    elif k == "cloud":
        p(1, 4, 8, 3)
        p(2, 3, 5, 1)
        p(3, 2, 3, 1)
        p(2, 7, 6, 1)
    elif k == "rain":
        p(1, 2, 8, 3)
        p(2, 1, 5, 1)
        p(2, 6, 1, 2)
        p(4, 7, 1, 2)
        p(6, 6, 1, 2)
        p(8, 7, 1, 2)
    elif k == "snow":
        p(1, 2, 8, 3)
        p(2, 1, 5, 1)
        p(2, 6, 1, 1)
        p(4, 7, 1, 1)
        p(6, 6, 1, 1)
        p(8, 7, 1, 1)
    elif k == "storm":
        p(1, 2, 8, 3)
        p(2, 1, 5, 1)
        p(5, 5, 2, 1)
        p(4, 6, 2, 1)
        p(3, 7, 2, 1)
        p(2, 8, 2, 1)
    elif k == "fog":
        p(1, 3, 8, 1)
        p(2, 5, 7, 1)
        p(1, 7, 8, 1)
    else:
        p(2, 3, 6, 4)


# Short ASCII quotes for the greeting line (Goggins / Jocko / Rogan / Hanes).
_QUOTES = (
    # David Goggins
    "Stay hard.",
    "Who's gonna carry the boats?",
    "Don't stop when you're tired.",
    "Callous your mind.",
    "You don't find willpower. You create it.",
    # Jocko Willink
    "Discipline equals freedom.",
    "Good.",
    "Get after it.",
    "Default aggressive.",
    "Extreme ownership.",
    # Joe Rogan
    "Be the hero of your own movie.",
    "Just keep moving forward.",
    "Work out. Eat clean. Repeat.",
    "Don't be afraid to reinvent yourself.",
    # Cameron Hanes
    "Keep hammering.",
    "Nobody cares. Work harder.",
    "Strive for greatness.",
    "Embrace the grind.",
    "Outwork your potential.",
)


def _greeting(hour):
    if hour is None:
        return "Hello", 0
    h = int(hour)
    if h < 12:
        return "Good Morning", h
    if h < 17:
        return "Good Afternoon", h
    return "Good Evening", h


def _quote_for(model, hour):
    """Rotate quote by date + hour so it changes through the day."""
    seed = 0
    ds = model.get("date_str") or ""
    for ch in ds:
        seed = (seed + ord(ch)) & 0xFFFF
    seed = (seed + int(hour or 0) * 17) & 0xFFFF
    return _QUOTES[seed % len(_QUOTES)]


def _wrap_lines(text, width_chars):
    """Word-wrap to width_chars; hard-break overlong tokens."""
    text = ascii(text or "").strip()
    if not text or width_chars < 1:
        return []
    lines = []
    while text:
        if len(text) <= width_chars:
            lines.append(text)
            break
        cut = text.rfind(" ", 0, width_chars + 1)
        if cut < 1:
            cut = width_chars
        lines.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return lines


def _max_chars(pixel_w, scale=1):
    """Built-in font is 8px wide per char; leave a small right margin."""
    return max(4, (pixel_w - 8) // (8 * scale))


def _draw_wrapped(fb, text, x, y, max_chars, bottom, line_h=12, ink=0x00, limit=12):
    """Draw wrapped text; return y after last line."""
    for i, line in enumerate(_wrap_lines(text, max_chars)):
        if y + line_h > bottom or i >= limit:
            if y + line_h <= bottom:
                fb.text("...", x, y, ink)
                y += line_h
            break
        # Hard-clip each line so framebuf never paints past the column
        fb.text(line[:max_chars], x, y, ink)
        y += line_h
    return y


def _draw_stat_block(fb, label, value, x, y, max_chars, bottom, line_h=12):
    """Wrap 'Label: value' to column width (no side-by-side overflow)."""
    if y + line_h > bottom:
        return y
    label = ascii(label or "").strip()
    value = ascii(value or "").strip()
    if label and value:
        text = "%s: %s" % (label, value)
    else:
        text = label or value
    return _draw_wrapped(fb, text, x, y, max_chars, bottom, line_h=line_h, limit=5)


def _fmt_ampm(hhmm):
    """'09:00' or hour int -> '9:00 AM'."""
    if hhmm is None:
        return ""
    if isinstance(hhmm, int):
        h, m = hhmm, 0
    else:
        s = ascii(str(hhmm))
        try:
            parts = s.replace(".", ":").split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            return s
    ap = "AM" if h < 12 else "PM"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    if m:
        return "%d:%02d %s" % (h12, m, ap)
    return "%d:00 %s" % (h12, ap)


def _parse_hm(hhmm):
    if hhmm is None:
        return None
    if isinstance(hhmm, int):
        return hhmm * 60
    s = ascii(str(hhmm))
    try:
        parts = s.replace(".", ":").split(":")
        return int(parts[0]) * 60 + (int(parts[1]) if len(parts) > 1 else 0)
    except Exception:
        return None


def _draw_event_row(bk, ev, x, y, col_w, time_w, compact=False):
    if ev.get("all_day"):
        tleft = "all-day"
    else:
        tleft = _fmt_ampm(ev.get("start"))
    bk.text(clip(tleft, 9), x, y + 2, 0x00)
    bh = 22 if compact else 28
    bk.vline(x + time_w, y, bh, 0x00)
    title = ascii(ev.get("title") or "")
    bk.text(clip(title, max(8, (col_w - time_w - 12) // 8)), x + time_w + 10, y + 2, 0x00)
    if not compact:
        end = ev.get("end")
        if end and not ev.get("all_day"):
            bk.text("until " + _fmt_ampm(end), x + time_w + 10, y + 16, 0x00)
            return y + 36
        return y + 28
    return y + 24


def draw(epd, model):
    bk = epd.imageblack
    rd = epd.imagered
    bk.fill(0xFF)
    rd.fill(0x00)

    W, H = epd.width, epd.height
    PAD = 14
    # Three columns like the reference
    C1 = 250
    C2 = 520  # slightly more room for Next workout text
    unit = model.get("temp_unit") or "F"
    hour = model.get("hour")
    minute = model.get("minute") or 0
    greet, _h = _greeting(hour)
    quote = _quote_for(model, hour)

    # Column rules
    bk.vline(C1, PAD, H - 2 * PAD, 0x00)
    bk.vline(C2, PAD, H - 2 * PAD, 0x00)

    # ========== COL 1: date / greeting / weather / next 8h ==========
    x = PAD
    y = PAD
    rd.text(clip(model.get("date_str") or "", 28), x, y, 0xFF)
    y += 14
    bat = model.get("battery_pct")
    meta = model.get("updated_str") or ""
    if bat is not None:
        meta = "%s  BAT %d%%" % (meta, bat)
    rd.text(clip(meta, 28), x, y, 0xFF)
    y += 18

    text_big(bk, greet, x, y, 0x00, scale=2)
    y += 28
    q_chars = _max_chars(C1 - PAD - 8, scale=1)
    y = _draw_wrapped(bk, quote, x, y, q_chars, y + 28, line_h=12, ink=0x00, limit=2)
    y += 4
    bk.hline(x, y, C1 - PAD - 8, 0x00)
    y += 12

    w = model.get("weather") or {}
    cur = w.get("current") or {}
    tw = w.get("today") or {}
    icon = cur.get("icon") or tw.get("icon")
    temp = cur.get("temp")
    if temp is None and tw:
        temp = tw.get("high")
    label = cur.get("label") or tw.get("label") or ""

    _icon(bk, icon, x, y, 0x00, s=4)
    tstr = "--" if temp is None else "%d%s" % (temp, unit)
    text_big(bk, tstr, x + 52, y + 2, 0x00, scale=3)
    y += 42
    bk.text(clip(label, 22), x, y, 0x00)
    y += 14

    hi = tw.get("high", "--")
    lo = tw.get("low", "--")
    bk.text("High: %s%s" % (hi, unit), x, y, 0x00)
    y += 12
    bk.text("Low:  %s%s" % (lo, unit), x, y, 0x00)
    y += 12
    precip = tw.get("precip")
    if precip is None:
        precip = cur.get("precip")
    if precip is not None:
        bk.text("Precip: %s%%" % precip, x, y, 0x00)
        y += 12
    wind = cur.get("wind")
    if wind is not None:
        bk.text("Wind: %s %s" % (wind, cur.get("wind_dir") or ""), x, y, 0x00)
        y += 12

    y += 4
    bk.hline(x, y, C1 - PAD - 8, 0x00)
    y += 8
    text_big(bk, "Next 12h", x, y, 0x00, scale=2)
    y += 22

    # Two columns × 6 rows so 12 hours fit with larger type
    hourly = (w.get("hourly") or [])[:12]
    col_gap = (C1 - PAD - 8) // 2
    row_h = 28
    for i, slot in enumerate(hourly):
        col = i // 6
        row = i % 6
        cx = x + col * col_gap
        cy = y + row * row_h
        if cy + row_h > H - PAD:
            break
        _icon(bk, slot.get("icon"), cx, cy + 2, 0x00, s=2)
        hh = _fmt_ampm(slot.get("hour"))
        # shorter hour label: 6pm / 12am
        if isinstance(slot.get("hour"), int):
            h = int(slot.get("hour")) % 24
            ap = "a" if h < 12 else "p"
            h12 = h % 12
            if h12 == 0:
                h12 = 12
            hh = "%d%s" % (h12, ap)
        ts = "--" if slot.get("temp") is None else str(slot.get("temp"))
        bk.text(clip(hh, 4), cx + 26, cy + 2, 0x00)
        text_big(bk, ts, cx + 26, cy + 12, 0x00, scale=2)

    # ========== COL 2: Today + tomorrow + last workout ==========
    x = C1 + 14
    y = PAD
    col_w = C2 - C1 - 28
    time_w = 72
    cal = model.get("calendar") or {}
    today = cal.get("today") or []
    tomorrow = cal.get("tomorrow") or []

    text_big(bk, "Today", x, y, 0x00, scale=2)
    y += 28
    bk.hline(x, y, col_w, 0x00)
    y += 10

    if not today:
        bk.text("(no meetings)", x, y, 0x00)
        y += 18
    else:
        for ev in today[:5]:
            if y + 36 > 260:
                bk.text("...", x, y, 0x00)
                y += 14
                break
            y = _draw_event_row(bk, ev, x, y, col_w, time_w, compact=False)

    # Tomorrow
    y = max(y + 6, 250)
    bk.hline(x, y, col_w, 0x00)
    y += 8
    text_big(bk, "Tomorrow", x, y, 0x00, scale=2)
    y += 22
    if not tomorrow:
        bk.text("(open day)", x, y, 0x00)
        y += 14
    else:
        for ev in tomorrow[:3]:
            if y + 24 > H - 120:
                break
            y = _draw_event_row(bk, ev, x, y, col_w, time_w, compact=True)

    # Last workout (previous agent run) under calendar
    agent = model.get("agent") or {}
    last_w = agent.get("workout_last") or {}
    y = max(y + 8, H - 130)
    bk.hline(x, y, col_w, 0x00)
    y += 8
    text_big(bk, "Last workout", x, y, 0x00, scale=2)
    y += 22
    last_chars = _max_chars(col_w)
    lk = ascii(last_w.get("kind") or "NONE")
    lt = ascii(last_w.get("title") or "(none yet)")
    if lk and lk != "NONE":
        bk.fill_rect(x, y, min(len(lk) * 8 + 10, col_w), 14, 0x00)
        bk.text(clip(lk, 10), x + 4, y + 3, 0xFF)
        y += 18
    y = _draw_wrapped(bk, lt, x, y, last_chars, H - 12, line_h=12, limit=3)
    for label, value in (last_w.get("lines") or [])[:4]:
        if y >= H - 12:
            break
        # compact: "Label value" wrapped
        bit = ("%s  %s" % (label, value)).strip() if label else value
        y = _draw_wrapped(bk, bit, x, y, last_chars, H - 12, line_h=12, limit=2)

    # ========== COL 3: Next workout (latest agent run) ==========
    x = C2 + 14
    y = PAD
    rw = W - x - PAD
    line_w = _max_chars(rw)
    bottom = H - 36

    workout = agent.get("workout_next") or agent.get("workout") or {}
    kind = ascii(workout.get("kind") or "WORKOUT")
    title = ascii(workout.get("title") or agent.get("name") or "Workout")
    status = ascii(agent.get("status") or "")
    run = ascii(agent.get("run_status") or "")

    text_big(bk, "Next workout", x, y, 0x00, scale=2)
    y += 28
    bk.hline(x, y, rw, 0x00)
    y += 10

    active = status == "ACTIVE" or run in ("RUNNING", "CREATING")
    badge = kind if not active else (run or "RUNNING")
    bw = len(badge) * 16 + 16
    if active:
        rd.text(clip(badge, line_w), x, y, 0xFF)
        y += 18
    else:
        bk.fill_rect(x, y, min(bw, rw), 26, 0x00)
        text_big(bk, clip(badge, 10), x + 6, y + 4, 0xFF, scale=2)
        y += 34

    y = _draw_wrapped(bk, title, x, y, line_w, bottom, line_h=12, limit=4)

    y += 6
    if y < bottom:
        bk.hline(x, y, rw, 0x00)
        y += 10
    if y < bottom:
        bk.text("STATS", x, y, 0x00)
        y += 14

    stats = workout.get("lines") or []
    if not stats:
        if y < bottom:
            bk.text("(no stats yet)", x, y, 0x00)
            y += 12
    else:
        for label, value in stats:
            if y >= bottom:
                break
            y = _draw_stat_block(bk, label, value, x, y, line_w, bottom, line_h=12)
            y += 4  # gap between stats

    y = max(y + 4, H - 34)
    bk.hline(x, y, rw, 0x00)
    y += 8
    foot = "Agent %s / %s" % (status or "?", run or "-")
    if model.get("offline"):
        foot = "OFFLINE"
    rd.text(clip(foot, line_w), x, y, 0xFF)
