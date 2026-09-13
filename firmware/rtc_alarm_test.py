"""Test DS3231 INT → GP3 alarm wiring (Waveshare R5).

Sets Alarm1 for ~90 seconds from now, watches GP3 go LOW, clears flag.

  ./run_pico.sh rtc_alarm_test

Pass if you see: GP3 LOW + A1F=1 around the alarm time.
"""

import sys
import time

sys.path.insert(0, "/")

from machine import Pin
from drivers.rtc_ds3231 import DS3231

INT_PIN = 3  # Waveshare R5 → GP3


def main():
    print("=== RTC alarm / INT test ===")
    print("Expect: solder R5 (INT → GP3). INT is active-LOW on alarm.")

    rtc = DS3231()
    y, mo, d, wd, h, mi, s = rtc.datetime()
    print("RTC now:", rtc.format(), "OSF=", rtc.oscillator_stopped())
    print("Ctrl=0x%02X Status=0x%02X" % (rtc.control(), rtc.status()))

    pin = Pin(INT_PIN, Pin.IN, Pin.PULL_UP)
    print("GP%d level now (1=idle/high, 0=alarm): %d" % (INT_PIN, pin.value()))

    # Alarm ~90s ahead
    total = h * 3600 + mi * 60 + s + 90
    total %= 86400
    ah, am, asec = total // 3600, (total % 3600) // 60, total % 60
    print("Arming Alarm1 for %02d:%02d:%02d (in ~90s)..." % (ah, am, asec))
    rtc.set_alarm1_hm(ah, am, asec)
    print("Ctrl=0x%02X Status=0x%02X" % (rtc.control(), rtc.status()))
    print("Watching GP%d for 120s..." % INT_PIN)

    saw_low = False
    t0 = time.time()
    last = pin.value()
    while time.time() - t0 < 120:
        v = pin.value()
        if v != last:
            print(
                "  t+%ds GP%d %d→%d  A1F=%s"
                % (int(time.time() - t0), INT_PIN, last, v, rtc.alarm1_fired())
            )
            last = v
        if v == 0:
            saw_low = True
            break
        time.sleep_ms(200)

    print("---")
    print("Final GP%d=%d A1F=%s Status=0x%02X" % (INT_PIN, pin.value(), rtc.alarm1_fired(), rtc.status()))
    if saw_low or rtc.alarm1_fired():
        print("PASS: alarm fired / INT pulled low.")
        rtc.clear_alarm_flags()
        time.sleep_ms(50)
        print("After clear: GP%d=%d A1F=%s (want high/0)" % (INT_PIN, pin.value(), rtc.alarm1_fired()))
    else:
        print("FAIL: no INT low and A1F still clear.")
        print("Check: R5 soldered, stack seated, INT not R6/R7.")
    rtc.disable_alarms()
    print("Alarms disabled. Done.")


if __name__ == "__main__":
    main()
