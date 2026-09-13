"""Minimal RTC alarm wake test — no Wi‑Fi / agent / calendar.

  ./run_pico.sh rtc_wake_test

1) Panel shows ARMED + wake clock
2) Script waits 8s — UNPLUG USB in that window (avoids mpremote RTS reset)
3) Pico deepsleeps until DS3231 INT (GP3)
4) On wake, main.py sees flag → panel shows TEST + date/time

Watch the e-ink — serial will be gone after unplug.
"""

import sys
import time

sys.path.insert(0, "/")

import machine

from drivers.epd_7in5_b import EPD_7in5_B
from drivers.rtc_ds3231 import DS3231
from net.schedule import hms_after_seconds, sleep_until_rtc_alarm
from ui.dashboard import text_big

FLAG = "WAKE_TEST"  # on Pico FS root (no leading slash)
INT_PIN = 3
ALARM_SECONDS = 120
UNPLUG_GRACE_S = 8


def _draw(label, line2, line3=""):
    epd = EPD_7in5_B()
    bk = epd.imageblack
    rd = epd.imagered
    # Same planes as dashboard: red paper, black ink
    bk.fill(0xFF)
    rd.fill(0x00)

    text_big(bk, (label or "?")[:10], 60, 100, 0x00, scale=4)
    bk.text((line2 or "")[:48], 60, 220, 0x00)
    if line3:
        bk.text((line3 or "")[:48], 60, 240, 0x00)
    bk.text("rtc_wake_test", 60, 300, 0x00)

    print("Panel:", label, "|", line2, "|", line3)
    epd.display()
    try:
        epd.sleep()
    except Exception:
        pass


def _flag_write(when):
    f = open(FLAG, "w")
    f.write(when + "\n")
    f.close()


def _flag_exists():
    try:
        open(FLAG).close()
        return True
    except OSError:
        return False


def _flag_clear():
    try:
        import os

        os.remove(FLAG)
    except Exception:
        pass


def on_boot():
    """Draw TEST after alarm wake (called from main.py)."""
    print("=== rtc_wake_test WAKE ===")
    rtc = None
    try:
        rtc = DS3231()
        rtc.clear_alarm_flags()
    except Exception as e:
        print("RTC:", e)
    _flag_clear()
    now = rtc.format() if rtc else "no-rtc"
    _draw("TEST", now[:10], now[11:] if len(now) > 11 else "")
    print("PASS — TEST on screen.")


def main():
    print("=== rtc_wake_test ===")
    if _flag_exists():
        # Leftover flag (e.g. reset during sleep) — show TEST
        on_boot()
        return

    rtc = DS3231()
    _y, _mo, _d, _w, h, mi, s = rtc.datetime()
    ah, am, asec = hms_after_seconds(h, mi, s, ALARM_SECONDS)
    when = "%02d:%02d:%02d" % (ah, am, asec)
    now = rtc.format()
    print("Now:", now, "→ alarm", when)

    _flag_write(when)
    _draw("ARMED", "wake at %s" % when, "unplug USB now")

    print("")
    print("*** UNPLUG USB within %ds (stops mpremote from resetting you) ***" % UNPLUG_GRACE_S)
    for i in range(UNPLUG_GRACE_S, 0, -1):
        print("  deepsleep in %d..." % i)
        time.sleep(1)

    sleep_until_rtc_alarm(rtc, ah, am, asec, int_pin=INT_PIN, use_deep=True)
    # Should not return; if it does, show failure
    print("deepsleep returned unexpectedly")
    _draw("FAIL", "deepsleep returned", now)


# Alias used by main.py
run_wake_cycle = on_boot


if __name__ == "__main__":
    main()
