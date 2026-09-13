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

    def status(self):
        return self._read(0x0F, 1)[0]

    def control(self):
        return self._read(0x0E, 1)[0]

    def clear_alarm_flags(self):
        """Clear A1F/A2F so INT can go high again."""
        st = self._read(0x0F, 1)[0]
        self._write(0x0F, bytes([st & 0xFC]))

    def alarm1_fired(self):
        return bool(self._read(0x0F, 1)[0] & 0x01)

    def set_alarm1_hm(self, hour, minute, second=0):
        """Alarm1 matches hour:minute:second every day (INT active-low).

        Requires Waveshare R5 soldered (INT → GP3).
        """
        # Alarm1 regs 0x07..0x0A; bit7=1 means "ignore this field"
        # Match sec + min + hour; ignore day/date (A1M4=1)
        payload = bytes(
            [
                _dec2bcd(int(second) % 60),  # 0x07 A1M1=0
                _dec2bcd(int(minute) % 60),  # 0x08 A1M2=0
                _dec2bcd(int(hour) % 24),  # 0x09 A1M3=0
                0x80,  # 0x0A ignore day/date
            ]
        )
        self._write(0x07, payload)
        # Control 0x0E: INTCN=1, A1IE=1, A2IE=0, EOSC=0
        ctrl = self._read(0x0E, 1)[0]
        ctrl = (ctrl | 0x05) & ~0x02  # set INTCN|A1IE, clear A2IE
        ctrl &= ~0x40  # ensure oscillator on (EOSC=0 means enabled on DS3231)
        self._write(0x0E, bytes([ctrl & 0xFF]))
        self.clear_alarm_flags()

    def disable_alarms(self):
        ctrl = self._read(0x0E, 1)[0]
        self._write(0x0E, bytes([ctrl & ~0x03]))
        self.clear_alarm_flags()

    def format(self):
        y, mo, d, _w, h, mi, s = self.datetime()
        return "%04d-%02d-%02d %02d:%02d:%02d" % (y, mo, d, h, mi, s)
