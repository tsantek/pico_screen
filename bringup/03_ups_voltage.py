"""Waveshare Pico-UPS-B bring-up (INA219 @ 0x43 on GP6/GP7).

Uses SoftI2C. Configures the chip like Waveshare's demo.

Note: INA219 measures the *battery/load* rail, not the laptop USB
into the Pico. ~0 V usually means no battery / UPS switch off /
powering only via Pico USB.
"""

from machine import SoftI2C, Pin
import time

ADDR_CANDIDATES = (0x43, 0x40, 0x41, 0x42)
REG_CONFIG = 0x00
REG_SHUNT = 0x01
REG_BUS = 0x02
REG_CURRENT = 0x04
REG_CAL = 0x05


class INA219:
    def __init__(self, i2c, addr):
        self.i2c = i2c
        self.addr = addr
        self._current_lsb = 1  # 1 mA per bit with Waveshare 32V/2A cal
        self._configure()

    def _write(self, reg, value):
        payload = bytes([(value >> 8) & 0xFF, value & 0xFF])
        self.i2c.writeto_mem(self.addr, reg, payload)

    def _read(self, reg):
        # SoftI2C: repeated-start read
        self.i2c.writeto(self.addr, bytes([reg]), False)
        raw = self.i2c.readfrom(self.addr, 2)
        return (raw[0] << 8) | raw[1]

    def _configure(self):
        # Waveshare set_calibration_32V_2A (0.1 ohm shunt)
        self._write(REG_CAL, 4096)
        config = (
            (0x01 << 13)  # 32V range
            | (0x03 << 11)  # gain /8, 320mV
            | (0x0D << 7)  # bus ADC 12bit, 32 samples
            | (0x0D << 3)  # shunt ADC 12bit, 32 samples
            | 0x07  # continuous shunt+bus
        )
        self._write(REG_CONFIG, config)
        time.sleep_ms(80)  # first conversion after 32-sample avg

    def bus_voltage_v(self):
        return (self._read(REG_BUS) >> 3) * 0.004

    def shunt_voltage_mv(self):
        value = self._read(REG_SHUNT)
        if value > 32767:
            value -= 65535
        return value * 0.01

    def current_ma(self):
        value = self._read(REG_CURRENT)
        if value > 32767:
            value -= 65535
        return value * self._current_lsb


print("Opening SoftI2C GP6/GP7...")
i2c = SoftI2C(sda=Pin(6), scl=Pin(7), freq=50_000, timeout=1000)
found = i2c.scan()
print("Devices:", [hex(a) for a in found])

addr = next((a for a in ADDR_CANDIDATES if a in found), None)
if addr is None:
    print("INA219 not found.")
    raise SystemExit

ina = INA219(i2c, addr)
bus = ina.bus_voltage_v()
shunt = ina.shunt_voltage_mv()
current = ina.current_ma()
psu = bus + shunt / 1000.0
pct = (bus - 3.0) / 1.2 * 100.0
pct = 0 if pct < 0 else 100 if pct > 100 else pct

print(f"INA219 @ 0x{addr:02X}")
print(f"Bus (load/battery): {bus:.3f} V")
print(f"Shunt:              {shunt:.2f} mV")
print(f"Approx PSU:         {psu:.3f} V")
print(f"Current:            {current:.1f} mA")
print(f"Rough LiPo %:       {pct:.0f} %")

if bus < 2.5:
    print()
    print("Voltage is too low to be a live battery rail.")
    print("Check:")
    print("  1) LiPo plugged into the UPS battery connector")
    print("  2) UPS power switch ON")
    print("  3) After battery swap, press UPS 'ACTIVATE' if present")
    print("  4) Prefer powering via UPS USB (charging), not only Pico USB")
