"""Parse Cursor agent workout markdown into a small e-ink card."""

# MicroPython may only have limited re — keep matching simple.


def _lower(s):
    return (s or "").lower()


def _strip_md(s):
    """Remove light markdown noise for display."""
    if not s:
        return ""
    out = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "*" or ch == "`" or ch == "#":
            i += 1
            continue
        if ch == "|" or ch == "\r":
            i += 1
            continue
        if ch == "\n":
            out.append(" ")
            i += 1
            continue
        out.append(ch)
        i += 1
    text = "".join(out)
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


def _ascii_fold(s):
    # Enough for Croatian workout text on 8x8 font
    repl = {
        "ć": "c",
        "č": "c",
        "š": "s",
        "ž": "z",
        "đ": "d",
        "Ć": "C",
        "Č": "C",
        "Š": "S",
        "Ž": "Z",
        "Đ": "D",
        "—": "-",
        "–": "-",
        "×": "x",
        "·": "-",
        "↔": "/",
        "→": "->",
        "~": "~",
    }
    out = []
    for ch in s or "":
        out.append(repl.get(ch, ch if ord(ch) < 128 else "?"))
    return "".join(out)


def detect_type(text):
    t = _lower(text)
    # Title / first-line cues win
    head = t[:80]
    if any(w in head for w in ("bike", "bicikl", "cycl")):
        return "BIKE"
    if any(w in head for w in ("swim", "pliv", "pool", "bazen")):
        return "SWIM"
    if any(w in head for w in ("gym", "teretan", "lift", "strength")):
        return "GYM"
    if any(w in head for w in ("run", "trka", "trc", "traka", "long", "jog")):
        return "RUN"

    swim = ("swim", "pliv", "bazen", "pool")
    bike = ("bike", "cycl", "bicikl", "spin", "watt")
    gym = ("gym", "teretan", "lift", "strength", "weight", "hypertroph")
    run = ("run", "trka", "trc", "traka", "jog", "tempo", "long", "hod", "km/h")
    scores = {"SWIM": 0, "BIKE": 0, "GYM": 0, "RUN": 0}
    for w in swim:
        if w in t:
            scores["SWIM"] += 2
    for w in bike:
        if w in t:
            scores["BIKE"] += 3
    for w in gym:
        if w in t:
            scores["GYM"] += 2
    for w in run:
        if w in t:
            scores["RUN"] += 1
    if "long" in t or "traka" in t:
        scores["RUN"] += 2
    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "WORKOUT"
    return best


def _find_after(label_words, text, maxlen=40):
    """Find value after a label like 'Avg HR' or 'Cilj'."""
    low = _lower(text)
    for lab in label_words:
        i = low.find(_lower(lab))
        if i < 0:
            continue
        # skip label
        j = i + len(lab)
        while j < len(text) and text[j] in " :|\t*-":
            j += 1
        chunk = text[j : j + maxlen]
        # cut at newline-ish or double space table next cell end
        for stop in ("\n", "  |", "|"):
            k = chunk.find(stop)
            if k > 0:
                chunk = chunk[:k]
        chunk = _strip_md(chunk)
        if chunk:
            return chunk[:maxlen]
    return None


def _first_heading(text):
    for line in (text or "").split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            return _strip_md(s)
        # first non-empty content line
        if len(s) > 3 and not s.startswith("|") and not s.startswith("---"):
            return _strip_md(s)[:80]
    return None


def _clean_duration(s):
    """Prefer compact '2:30-2:45' from noisy Cilj text."""
    if not s:
        return s
    s = _ascii_fold(_strip_md(s))
    # collect HH:MM tokens
    times = []
    i = 0
    while i < len(s) - 3:
        if s[i].isdigit() and ":" in s[i : i + 5]:
            chunk = []
            j = i
            while j < len(s) and (s[j].isdigit() or s[j] == ":"):
                chunk.append(s[j])
                j += 1
            tok = "".join(chunk)
            if tok.count(":") == 1 and len(tok) >= 4:
                times.append(tok)
                i = j
                continue
        i += 1
    if len(times) >= 2:
        return "%s-%s" % (times[0], times[1])
    if len(times) == 1:
        return times[0]
    return s[:28]


def _duration(text):
    for lab in ("Cilj", "Goal", "Duration", "Trajanje", "Vrijeme"):
        v = _find_after((lab,), text, 50)
        if v:
            return _clean_duration(v)
    t = text or ""
    i = 0
    while i < len(t) - 4:
        if t[i].isdigit() and ":" in t[i : i + 12]:
            chunk = t[i : i + 20]
            clean = []
            for ch in chunk:
                if ch.isdigit() or ch in ":.-–— ":
                    clean.append(ch if ch not in "–—" else "-")
                else:
                    break
            s = "".join(clean).strip().rstrip("-").strip()
            if ":" in s and len(s) >= 4:
                return _clean_duration(s)
        i += 1
    return None


def parse_workout(result_md, agent_name=None):
    """Return a compact workout card dict from agent result markdown."""
    raw = result_md or ""
    if not raw or raw == "Working...":
        return {
            "ok": False,
            "kind": "NONE",
            "title": _ascii_fold(agent_name or "No workout"),
            "lines": [],
        }

    kind = detect_type(raw)
    title = _first_heading(raw) or (agent_name or "Workout")
    title = _ascii_fold(title)

    duration = _duration(raw)
    hr = _find_after(("Avg HR", "HR", "Puls"), raw, 48)
    pace = _find_after(("Run", "Pace", "Brzina", "Tempo"), raw, 48)
    walk = _find_after(("Hod", "Walk"), raw, 40)
    incline = _find_after(("Nagib", "Incline"), raw, 24)
    soft = _find_after(("Soft max", "Max HR"), raw, 40)

    # Fuel one-liner
    fuel_bits = []
    low = _lower(raw)
    if "tailwind" in low:
        fuel_bits.append("TW")
    if "gel" in low:
        fuel_bits.append("gel")
    if "waffle" in low:
        fuel_bits.append("waffle")
    if "voda" in low or "water" in low:
        fuel_bits.append("water")
    fuel = " + ".join(fuel_bits) if fuel_bits else None

    # Interval cue e.g. 25/5
    interval = None
    if "25/5" in raw:
        interval = "25/5 run/walk"
    elif "run 25" in low and "hod 5" in low:
        interval = "25/5 run/walk"

    lines = []
    if duration:
        lines.append(("Duration", _ascii_fold(duration)))
    if interval:
        lines.append(("Pattern", interval))
    if pace:
        lines.append(("Run pace", _ascii_fold(pace)))
    if walk:
        lines.append(("Walk", _ascii_fold(walk)))
    if incline:
        lines.append(("Incline", _ascii_fold(incline)))
    if hr:
        lines.append(("Avg HR", _ascii_fold(hr)))
    if soft:
        lines.append(("Soft max", _ascii_fold(soft)))
    if fuel:
        lines.append(("Fuel", fuel))

    # If we failed to extract structured stats, fall back to a few clean lines
    if not lines:
        plain = _ascii_fold(_strip_md(raw))
        chunk = plain[:160]
        while chunk:
            lines.append(("", chunk[:28]))
            chunk = chunk[28:]
            if len(lines) >= 5:
                break

    return {
        "ok": True,
        "kind": kind,  # RUN / GYM / BIKE / SWIM / WORKOUT
        "title": title,
        "lines": lines[:8],
    }
