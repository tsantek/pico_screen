"""DS3231 on GP20/GP21 — SoftI2C preferred, HW I2C fallback with retries."""

from machine import SoftI2C, I2C, Pin
import time

ADDR = 0x68
SDA, SCL = 20, 21


def _bcd2dec(x):
    return (x // 16) * 10 + (x % 16)


def _dec2bcd(x):
    return (x // 10) * 16 + (x % 10)


class DS3231:
    def __init__(self, sda=SDA, scl=SCL):
        self.addr = ADDR
        self.i2c = None
        last = None
        for kind, factory in (
            ("SoftI2C", lambda: SoftI2C(sda=Pin(sda), scl=Pin(scl), freq=50_000, timeout=1000)),
            ("I2C0", lambda: I2C(0, sda=Pin(sda), scl=Pin(scl), freq=100_000)),
        ):
            for attempt in range(1, 4):
                try:
                    self.i2c = factory()
                    time.sleep_ms(40)
                    # Probe with a real read (scan alone is flaky after WiFi/reset)
                    self._read(0x00, 1)
                    print("RTC via", kind, "attempt", attempt)
                    return
                except Exception as e:
                    last = e
                    time.sleep_ms(80)
        raise OSError("DS3231 not found: %s" % last)

    def _read(self, reg, n):
        self.i2c.writeto(self.addr, bytes([reg]), False)
        return self.i2c.readfrom(self.addr, n)

    def _write(self, reg, data):
        self.i2c.writeto(self.addr, bytes([reg]) + bytes(data))

    def datetime(self):
        raw = self._read(0x00, 7)
        second = _bcd2dec(raw[0] & 0x7F)
        minute = _bcd2dec(raw[1] & 0x7F)
        hour = _bcd2dec(raw[2] & 0x3F)
        weekday = _bcd2dec(raw[3] & 0x07)
        day = _bcd2dec(raw[4] & 0x3F)
        month = _bcd2dec(raw[5] & 0x1F)
        year = _bcd2dec(raw[6]) + 2000
        return year, month, day, weekday, hour, minute, second

    def set_datetime(self, year, month, day, weekday, hour, minute, second):
        payload = bytes(
            [
                _dec2bcd(second),
                _dec2bcd(minute),
                _dec2bcd(hour),
                _dec2bcd(weekday),
                _dec2bcd(day),
                _dec2bcd(month),
                _dec2bcd(year - 2000),
            ]
        )
        self._write(0x00, payload)
        # Clear OSF (oscillator-stop) in status register 0x0F
        try:
            st = self._read(0x0F, 1)[0]
            self._write(0x0F, bytes([st & 0x7F]))
        except Exception:
            pass

    def oscillator_stopped(self):
        """True if coin-cell backup failed / time was lost."""
        return bool(self._read(0x0F, 1)[0] & 0x80)

    def format(self):
        y, mo, d, _w, h, mi, s = self.datetime()
        return "%04d-%02d-%02d %02d:%02d:%02d" % (y, mo, d, h, mi, s)
