"""Sleep between dashboard cycles.

Uses machine.deepsleep (very low power). Pico max sleep ≈ 70 min, so longer
gaps take silent naps (wake → check RTC → sleep again, NO Wi‑Fi / NO redraw)
until the next draw hour.

Draw times come from secrets DRAW_HOURS, e.g. (6, 12, 18) Phoenix.
"""

import machine
import time

# RP2 deepsleep arg max ≈ 71.5 minutes
_MAX_DEEPSLEEP_MS = 70 * 60 * 1000
_CHUNK_MS = 30_000

# Draw if within this many seconds after a scheduled hour
_DRAW_WINDOW_S = 5 * 60

_DEFAULT_HOURS = (6, 12, 18)


def _norm_hours(draw_hours):
    if not draw_hours:
        return _DEFAULT_HOURS
    out = []
    for h in draw_hours:
        h = int(h) % 24
        if h not in out:
            out.append(h)
    out.sort()
    return tuple(out) if out else _DEFAULT_HOURS


def ms_until_next_draw(hour, minute, second, draw_hours=_DEFAULT_HOURS):
    """Milliseconds until next scheduled draw (Phoenix local wall clock)."""
    hours = _norm_hours(draw_hours)
    now = int(hour) * 3600 + int(minute) * 60 + int(second)
    best = None
    for h in hours:
        target = h * 3600
        if target < now + 60:
            continue
        delta = target - now
        if best is None or delta < best:
            best = delta
    if best is None:
        # First slot tomorrow
        best = (hours[0] * 3600 + 86400) - now
    return best * 1000


def next_draw_hms(hour, minute, second, draw_hours=_DEFAULT_HOURS):
    ms = ms_until_next_draw(hour, minute, second, draw_hours)
    total = int(hour) * 3600 + int(minute) * 60 + int(second) + (ms // 1000)
    total %= 86400
    return total // 3600, (total % 3600) // 60, total % 60


def should_draw_now(hour, minute, second, draw_hours=_DEFAULT_HOURS, window_s=_DRAW_WINDOW_S):
    """True in the first window_s seconds after a scheduled hour."""
    hours = _norm_hours(draw_hours)
    now = int(hour) * 3600 + int(minute) * 60 + int(second)
    for h in hours:
        start = h * 3600
        if start <= now < start + int(window_s):
            return True
    return False


# --- back-compat helpers (interval-based) ---


def ms_until_next_interval(hour, minute, second, interval_h=6):
    elapsed = hour * 3600 + minute * 60 + second
    step = max(1, int(interval_h)) * 3600
    next_at = ((elapsed // step) + 1) * step
    remaining = next_at - elapsed
    if remaining < 60:
        remaining += step
    if remaining > 86400:
        remaining -= 86400
    return remaining * 1000


def next_boundary_hms(hour, minute, second, interval_h=6):
    ms = ms_until_next_interval(hour, minute, second, interval_h)
    total = hour * 3600 + minute * 60 + second + (ms // 1000)
    total %= 86400
    return total // 3600, (total % 3600) // 60, total % 60


def low_power_sleep(ms):
    """Idle sleep (higher power) — full duration in 30s chunks, no reset."""
    if ms < 100:
        return
    print("Sleep %ds (idle chunks)..." % (ms // 1000))
    time.sleep_ms(300)
    left = ms
    while left > 0:
        chunk = _CHUNK_MS if left > _CHUNK_MS else left
        time.sleep_ms(chunk)
        left -= chunk


def deep_sleep_ms(ms):
    """Enter deepsleep for up to ~70 min (chip resets on wake)."""
    if ms < 100:
        ms = 100
    if ms > _MAX_DEEPSLEEP_MS:
        ms = _MAX_DEEPSLEEP_MS
    print("Deep sleep %ds (silent nap, no redraw)..." % (ms // 1000))
    time.sleep_ms(500)  # flush serial
    machine.deepsleep(ms)


def sleep_until_draw(hour, minute, second, draw_hours=_DEFAULT_HOURS, mode="deep"):
    """Sleep toward next DRAW_HOURS slot (e.g. 06:00 / 12:00 / 18:00)."""
    want = ms_until_next_draw(hour, minute, second, draw_hours)
    nh, nm, _ = next_draw_hms(hour, minute, second, draw_hours)
    print(
        "Next draw target %02d:%02d PHX %s — %ds away [%s]"
        % (nh, nm, _norm_hours(draw_hours), want // 1000, mode)
    )
    if mode == "idle":
        low_power_sleep(want)
    else:
        deep_sleep_ms(want)


def sleep_until_boundary(hour, minute, second, interval_h=6, mode="deep", draw_hours=None):
    """Prefer draw_hours schedule; else legacy every-N-hours boundaries."""
    if draw_hours:
        sleep_until_draw(hour, minute, second, draw_hours=draw_hours, mode=mode)
        return
    want = ms_until_next_interval(hour, minute, second, interval_h)
    nh, nm, _ = next_boundary_hms(hour, minute, second, interval_h)
    print(
        "Next draw target %02d:%02d PHX (%dh) — %ds away [%s]"
        % (nh, nm, interval_h, want // 1000, mode)
    )
    if mode == "idle":
        low_power_sleep(want)
    else:
        deep_sleep_ms(want)


def deep_sleep_hours(hour, minute, second, interval_h=6):
    sleep_until_boundary(hour, minute, second, interval_h, mode="deep")


def hms_after_seconds(hour, minute, second, add_s):
    total = (int(hour) * 3600 + int(minute) * 60 + int(second) + int(add_s)) % 86400
    return total // 3600, (total % 3600) // 60, total % 60


def ms_until_hms(now_h, now_m, now_s, th, tm, ts):
    """Ms from now to target clock (rolls to next day if needed)."""
    now = int(now_h) * 3600 + int(now_m) * 60 + int(now_s)
    tgt = int(th) * 3600 + int(tm) * 60 + int(ts)
    if tgt <= now + 2:
        tgt += 86400
    return (tgt - now) * 1000


def sleep_until_rtc_alarm(
    rtc, hour, minute, second=0, int_pin=3, now_hms=None, use_deep=True
):
    """Arm DS3231 alarm + timed deepsleep until then (UPS-safe).

    Never busy-polls (that drains UPS). Uses deepsleep(ms) in ≤70 min slices.
    RTC INT may wake early if the port supports pin-wake; timer is the backup.
    """
    from machine import Pin

    ah, am, asec = int(hour) % 24, int(minute) % 60, int(second) % 60
    if now_hms is None:
        _y, _mo, _d, _w, nh, nm, ns = rtc.datetime()
        now_hms = (nh, nm, ns)
    nh, nm, ns = now_hms
    want_ms = ms_until_hms(nh, nm, ns, ah, am, asec)
    if want_ms < 3000:
        want_ms = 3000

    pin = Pin(int_pin, Pin.IN, Pin.PULL_UP)

    # Release stale INT (stuck low = instant wake loop on UPS)
    rtc.clear_alarm_flags()
    for _ in range(40):
        if pin.value() == 1:
            break
        rtc.clear_alarm_flags()
        time.sleep_ms(25)
    if pin.value() == 0:
        print("INT stuck LOW — disabling alarm IRQ, timed sleep only")
        try:
            rtc.disable_alarms()
        except Exception:
            pass
        time.sleep_ms(150)
        rtc.clear_alarm_flags()
        # Timed path only — do not re-enable INT this cycle
        use_int = False
    else:
        use_int = True
        rtc.set_alarm1_hm(ah, am, asec)
        time.sleep_ms(50)
        if pin.value() == 0 or rtc.alarm1_fired():
            print("INT asserted right after arm — clear & timed sleep only")
            rtc.clear_alarm_flags()
            try:
                rtc.disable_alarms()
            except Exception:
                pass
            use_int = False

    # Timed deepsleep only — do not arm Pin.irq. On Pico W / 2 W, GPIO wake
    # from deepsleep is unreliable and a low INT can cause instant wake loops.
    sleep_ms = want_ms if want_ms <= _MAX_DEEPSLEEP_MS else _MAX_DEEPSLEEP_MS
    print(
        "Sleep toward %02d:%02d:%02d (%ds total, this nap %ds, alarm_armed=%s)"
        % (ah, am, asec, want_ms // 1000, sleep_ms // 1000, use_int)
    )

    # Kill Wi‑Fi radio
    try:
        import network

        wlan = network.WLAN(network.STA_IF)
        try:
            wlan.disconnect()
        except Exception:
            pass
        wlan.active(False)
        try:
            wlan.deinit()
        except Exception:
            pass
    except Exception:
        pass

    time.sleep_ms(300)
    if use_deep:
        try:
            machine.deepsleep(sleep_ms)
        except Exception as e:
            print("deepsleep failed (%s) — idle chunk sleep" % e)
            low_power_sleep(sleep_ms)
    else:
        low_power_sleep(sleep_ms)

    # Only reached if deepsleep returned (shouldn't) or idle path
    try:
        rtc.clear_alarm_flags()
    except Exception:
        pass
