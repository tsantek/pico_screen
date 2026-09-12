"""Sleep between dashboard cycles.

Uses machine.deepsleep (very low power). Max sleep ≈ 70 min on RP2, so longer
gaps wake and deepsleep again without redrawing until the next boundary.

Caveat: deepsleep previously failed to wake on some UPS-only setups; if the
panel never updates after unplug, set SLEEP_MODE = \"idle\" in secrets.
"""

import machine
import time

# RP2 deepsleep arg max ≈ 71.5 minutes
_MAX_DEEPSLEEP_MS = 70 * 60 * 1000
_CHUNK_MS = 30_000

# Draw if within this many seconds after 00/06/12/18 (etc.)
_DRAW_WINDOW_S = 5 * 60


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


def ms_since_boundary(hour, minute, second, interval_h=6):
    elapsed = hour * 3600 + minute * 60 + second
    step = max(1, int(interval_h)) * 3600
    return (elapsed % step) * 1000


def next_boundary_hms(hour, minute, second, interval_h=6):
    ms = ms_until_next_interval(hour, minute, second, interval_h)
    total = hour * 3600 + minute * 60 + second + (ms // 1000)
    total %= 86400
    return total // 3600, (total % 3600) // 60, total % 60


def should_draw_now(hour, minute, second, interval_h=6, window_s=_DRAW_WINDOW_S):
    """True in the first window_s seconds after each interval boundary."""
    return (ms_since_boundary(hour, minute, second, interval_h) // 1000) < window_s


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
    print("Deep sleep %ds (full power-down, wake resets)..." % (ms // 1000))
    time.sleep_ms(500)  # flush serial
    machine.deepsleep(ms)


def sleep_until_boundary(hour, minute, second, interval_h=6, mode="deep"):
    """Sleep toward next Phoenix interval boundary."""
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
