"""Scan I2C buses used by Waveshare UPS + RTC.

Expected (when stack is healthy):
  - UPS INA219  @ 0x40 on GP6/GP7 (I2C1)
  - RTC DS3231  @ 0x68 on GP20/GP21 (I2C0)  — newer boards
    or sometimes also on GP6/GP7              — older boards

Run in Thonny with the Pico selected as the interpreter.
"""

from machine import I2C, Pin

BUSES = [
    ("I2C1 UPS bus", 1, 6, 7),
    ("I2C0 RTC bus (new)", 0, 20, 21),
    ("I2C0 alt", 0, 4, 5),
    ("I2C1 alt", 1, 26, 27),
]

KNOWN = {
    0x40: "UPS INA219 (battery monitor)",
    0x41: "INA219 alt address",
    0x42: "INA219 alt address",
    0x43: "UPS INA219 (battery monitor) — Waveshare often uses 0x43",
    0x68: "DS3231 RTC",
}


def scan(name, port, sda, scl):
    print(f"\n=== {name}  SDA=GP{sda} SCL=GP{scl} ===")
    try:
        i2c = I2C(port, sda=Pin(sda), scl=Pin(scl), freq=100_000)
        found = i2c.scan()
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    if not found:
        print("  (no devices)")
        return

    for addr in found:
        label = KNOWN.get(addr, "unknown")
        print(f"  0x{addr:02X}  ({addr})  {label}")


print("Pico stack I2C bring-up")
for args in BUSES:
    scan(*args)

print("\nDone.")
print("Pass if you see 0x40/0x43 (UPS) and 0x68 (RTC) on any bus above.")
