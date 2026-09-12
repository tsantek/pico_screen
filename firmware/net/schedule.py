"""Low-power sleep that resumes in-place (works without USB).

Pico deepsleep resets the chip and often fails to wake when USB is unplugged.
lightsleep (+ time.sleep fallback) keeps main.py looping on UPS power alone.
"""

import machine
import time

# RP2: sleep arg max ≈ 71.5 minutes
_MAX_SLEEP_MS = 70 * 60 * 1000


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
    """Sleep ms milliseconds; resume here (no full reset)."""
    if ms < 100:
        return
    if ms > _MAX_SLEEP_MS:
        ms = _MAX_SLEEP_MS
    print("Sleep %ds (lightsleep, USB optional)..." % (ms // 1000))
    time.sleep_ms(300)
    try:
        machine.lightsleep(ms)
    except Exception as e:
        print("lightsleep failed (%s) — using time.sleep" % e)
        # Chunk time.sleep so we can still recover
        left = ms
        while left > 0:
            chunk = 30000 if left > 30000 else left
            time.sleep_ms(chunk)
            left -= chunk


def sleep_until_boundary(hour, minute, second, interval_h=6):
    """Sleep until next interval; may return early if max-sleep capped."""
    want = ms_until_next_interval(hour, minute, second, interval_h)
    nh, nm, _ = next_boundary_hms(hour, minute, second, interval_h)
    print("Next draw target %02d:%02d PHX (%dh) — %ds away" % (nh, nm, interval_h, want // 1000))
    low_power_sleep(want)


def deep_sleep_hours(hour, minute, second, interval_h=6):
    """Back-compat name — uses lightsleep, not deepsleep."""
    sleep_until_boundary(hour, minute, second, interval_h)
