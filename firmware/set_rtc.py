"""Set DS3231 to America/Phoenix local time (UTC-7, no DST).

Prefer: host pushes "now" via ./run_pico.sh set_rtc (most accurate).
Fallback: WiFi + NTP, then apply Phoenix offset.
"""

import sys
import time

sys.path.insert(0, "/")

from drivers.rtc_ds3231 import DS3231

# Phoenix = UTC-7 year-round
_PHX_OFFSET_SEC = -7 * 3600


def _weekday_ds3231(python_weekday):
    # Python: Mon=0 .. Sun=6 → DS3231: Sun=1 .. Sat=7
    return ((python_weekday + 1) % 7) + 1


def _set_from_tuple(rtc, y, mo, d, h, mi, s, wday_py):
    wd = _weekday_ds3231(wday_py)
    print("Before:", rtc.format(), "OSF=", rtc.oscillator_stopped())
    rtc.set_datetime(y, mo, d, wd, h, mi, s)
    print("After: ", rtc.format(), "OSF=", rtc.oscillator_stopped())
    print("(RTC stored as America/Phoenix local)")


def from_host_injected():
    """Values injected by run_pico.sh / host before upload (optional file)."""
    try:
        import rtc_now  # generated on host: YEAR, MONTH, ...

        return (
            rtc_now.YEAR,
            rtc_now.MONTH,
            rtc_now.DAY,
            rtc_now.HOUR,
            rtc_now.MINUTE,
            rtc_now.SECOND,
            rtc_now.WDAY_PY,
        )
    except ImportError:
        return None


def from_ntp_phoenix():
    import secrets
    from net import wifi
    import ntptime

    wifi.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    ntptime.host = "pool.ntp.org"
    for _ in range(3):
        try:
            ntptime.settime()  # sets UTC into Pico RTC (machine)
            break
        except Exception as e:
            print("NTP retry:", e)
            time.sleep_ms(500)
    # machine time is UTC epoch-ish on MicroPython
    t = time.time() + _PHX_OFFSET_SEC
    tm = time.localtime(t)
    # tm: y,m,d,h,mi,s,wday,yday
    return tm[0], tm[1], tm[2], tm[3], tm[4], tm[5], tm[6]


def main():
    rtc = DS3231()
    vals = from_host_injected()
    if vals:
        print("Source: host Phoenix now")
        y, mo, d, h, mi, s, wday = vals
    else:
        print("Source: NTP → Phoenix (UTC-7)")
        y, mo, d, h, mi, s, wday = from_ntp_phoenix()
    _set_from_tuple(rtc, y, mo, d, h, mi, s, wday)


if __name__ == "__main__":
    main()
