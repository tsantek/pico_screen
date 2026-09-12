"""America/Phoenix local time via NTP (UTC-7, no DST)."""

import time

try:
    import ntptime
except ImportError:
    ntptime = None

_PHX_OFFSET = -7 * 3600


def _weekday_ds3231(python_wday):
    # Python Mon=0..Sun=6 → DS3231 Sun=1..Sat=7
    return ((python_wday + 1) % 7) + 1


def phoenix_tuple_from_epoch(utc_epoch):
    """Return DS3231-style (y, mo, d, weekday, h, mi, s) in Phoenix local."""
    tm = time.gmtime(int(utc_epoch) + _PHX_OFFSET)
    y, mo, d = tm[0], tm[1], tm[2]
    h, mi, s = tm[3], tm[4], tm[5]
    wd = _weekday_ds3231(tm[6])
    return y, mo, d, wd, h, mi, s


def ntp_phoenix_tuple(host="pool.ntp.org", retries=3):
    """Fetch UTC via NTP, return Phoenix local datetime tuple."""
    if ntptime is None:
        raise OSError("ntptime not available")
    ntptime.host = host
    last = None
    for _ in range(retries):
        try:
            ntptime.settime()
            return phoenix_tuple_from_epoch(time.time())
        except Exception as e:
            last = e
            time.sleep_ms(400)
    raise OSError("NTP failed: %s" % last)


def sync_rtc_phoenix(rtc, host="pool.ntp.org"):
    """Set DS3231 (+ clear OSF) from NTP Phoenix time. Returns datetime tuple."""
    tup = ntp_phoenix_tuple(host=host)
    y, mo, d, wd, h, mi, s = tup
    rtc.set_datetime(y, mo, d, wd, h, mi, s)
    print(
        "Synced RTC from NTP → Phoenix:",
        "%04d-%02d-%02d %02d:%02d:%02d" % (y, mo, d, h, mi, s),
    )
    return tup


def rtc_needs_sync(rtc_tuple, rtc=None):
    if rtc_tuple is None:
        return True
    y = rtc_tuple[0]
    if y < 2024 or y > 2099:
        return True
    if rtc is not None:
        try:
            if rtc.oscillator_stopped():
                return True
        except Exception:
            pass
    return False
