"""Read DS3231 status — useful when coin cell is dead / time reset to 2000.

Prints datetime, OSF (oscillator-stopped), control/status regs, and a verdict.
Does not change the clock.

  ./run_pico.sh rtc_check
"""

import sys

sys.path.insert(0, "/")

from drivers.rtc_ds3231 import DS3231, ADDR

_WDAY = ("?", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


def main():
    print("=== DS3231 check ===")
    try:
        rtc = DS3231()
    except OSError as e:
        print("FAIL: chip not responding:", e)
        print("Check I2C wiring (SDA=GP20, SCL=GP21) and 3V3.")
        return

    y, mo, d, wd, h, mi, s = rtc.datetime()
    osf = rtc.oscillator_stopped()
    try:
        status = rtc._read(0x0F, 1)[0]
        control = rtc._read(0x0E, 1)[0]
    except Exception as e:
        status = control = None
        print("Reg read error:", e)

    print("I2C addr: 0x%02X" % ADDR)
    print("Datetime: %04d-%02d-%02d %02d:%02d:%02d  (%s)" % (y, mo, d, h, mi, s, _WDAY[wd] if 0 <= wd <= 7 else "?"))
    print("OSF (oscillator stopped):", osf)
    if status is not None:
        print("Status 0x0F: 0x%02X  (OSF=%d A2F=%d A1F=%d)" % (status, (status >> 7) & 1, (status >> 1) & 1, status & 1))
    if control is not None:
        print("Control 0x0E: 0x%02X" % control)

    print("---")
    if osf or y < 2024:
        print("VERDICT: BAD / LOST TIME")
        print("  Coin cell missing, dead, or was removed.")
        print("  Year < 2024 or OSF=1 is the usual signature (often 2000-01-01).")
        print("  Fix: replace CR2032, then ./run_pico.sh set_rtc")
        print("  Until then, main.py NTP-syncs Phoenix time when OSF/year is wrong.")
    else:
        print("VERDICT: OK (time looks sane, OSF clear)")
        print("  Note: after a fresh set_rtc/NTP sync, OSF can be clear even with")
        print("  a dead cell — unplug USB (and UPS if needed) for a minute, power")
        print("  back, and re-run this script. If it returns to 2000 + OSF, cell is bad.")


if __name__ == "__main__":
    main()
