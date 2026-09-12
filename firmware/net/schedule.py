"""Sleep between dashboard cycles (works without USB).

Chunked time.sleep is higher power than deepsleep/lightsleep but reliably
resumes the main loop on UPS after USB unplug.
"""

import time

_CHUNK_MS = 30_000


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
    """Sleep the full ms (30s chunks); resume here (no full reset)."""
    if ms < 100:
        return
    print("Sleep %ds (time.sleep chunks, USB optional)..." % (ms // 1000))
    time.sleep_ms(300)
    left = ms
    while left > 0:
        chunk = _CHUNK_MS if left > _CHUNK_MS else left
        time.sleep_ms(chunk)
        left -= chunk


def sleep_until_boundary(hour, minute, second, interval_h=6):
    """Sleep until next Phoenix interval boundary (e.g. 00/06/12/18)."""
    want = ms_until_next_interval(hour, minute, second, interval_h)
    nh, nm, _ = next_boundary_hms(hour, minute, second, interval_h)
    print("Next draw target %02d:%02d PHX (%dh) — %ds away" % (nh, nm, interval_h, want // 1000))
    low_power_sleep(want)


def deep_sleep_hours(hour, minute, second, interval_h=6):
    """Back-compat name — uses chunked sleep, not deepsleep."""
    sleep_until_boundary(hour, minute, second, interval_h)
