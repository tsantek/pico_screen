"""Waveshare Pico-UPS-B INA219 — SoftI2C then HW I2C fallback."""

from machine import SoftI2C, I2C, Pin
import time

ADDR_CANDIDATES = (0x43, 0x40, 0x41, 0x42)
REG_CONFIG = 0x00
REG_BUS = 0x02
REG_CAL = 0x05
SDA, SCL = 6, 7


class INA219:
    def __init__(self, sda=SDA, scl=SCL):
        self.i2c = None
        self.addr = None
        last = None
        for kind, factory in (
            ("SoftI2C", lambda: SoftI2C(sda=Pin(sda), scl=Pin(scl), freq=50_000, timeout=1000)),
            ("I2C1", lambda: I2C(1, sda=Pin(sda), scl=Pin(scl), freq=100_000)),
        ):
            for attempt in range(1, 4):
                try:
                    bus = factory()
                    time.sleep_ms(40)
                    found = bus.scan()
                    addr = next((a for a in ADDR_CANDIDATES if a in found), None)
                    if addr is None:
                        raise OSError("no INA219 in %s" % [hex(x) for x in found])
                    self.i2c = bus
                    self.addr = addr
                    self._current_lsb = 1
                    self._configure()
                    print("UPS via", kind, "@", hex(addr), "attempt", attempt)
                    return
                except Exception as e:
                    last = e
                    time.sleep_ms(80)
        raise OSError("INA219 not found: %s" % last)

    def _write(self, reg, value):
        payload = bytes([(value >> 8) & 0xFF, value & 0xFF])
        try:
            self.i2c.writeto_mem(self.addr, reg, payload)
        except Exception:
            self.i2c.writeto(self.addr, bytes([reg]) + payload)

    def _read(self, reg):
        self.i2c.writeto(self.addr, bytes([reg]), False)
        raw = self.i2c.readfrom(self.addr, 2)
        return (raw[0] << 8) | raw[1]

    def _configure(self):
        self._write(REG_CAL, 4096)
        config = (0x01 << 13) | (0x03 << 11) | (0x0D << 7) | (0x0D << 3) | 0x07
        self._write(REG_CONFIG, config)
        time.sleep_ms(80)

    def bus_voltage_v(self):
        return (self._read(REG_BUS) >> 3) * 0.004

    def battery_percent(self):
        v = self.bus_voltage_v()
        pct = (v - 3.0) / 1.2 * 100.0
        if pct < 0:
            return 0
        if pct > 100:
            return 100
        return int(pct)
