"""DS3231 bring-up with SoftI2C + diagnostics.

Your hardware I2C scan sees 0x68, but HW I2C reads often EIO on
Pico stacks. SoftI2C usually fixes it.
"""

from machine import SoftI2C, I2C, Pin
import time

ADDR = 0x68
SDA, SCL = 20, 21


def bcd2dec(x):
    return (x // 16) * 10 + (x % 16)


def format_time(raw):
    sec = bcd2dec(raw[0] & 0x7F)
    minute = bcd2dec(raw[1] & 0x7F)
    hour = bcd2dec(raw[2] & 0x3F)
    day = bcd2dec(raw[4] & 0x3F)
    month = bcd2dec(raw[5] & 0x1F)
    year = bcd2dec(raw[6]) + 2000
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{sec:02d}"


def try_soft():
    print("\n=== SoftI2C GP20/GP21 @ 50kHz ===")
    i2c = SoftI2C(sda=Pin(SDA), scl=Pin(SCL), freq=50_000, timeout=1000)
    found = i2c.scan()
    print("scan:", [hex(a) for a in found])
    if ADDR not in found:
        raise OSError("0x68 not in SoftI2C scan")

    # 1) write register pointer only
    i2c.writeto(ADDR, b"\x00")
    print("writeto(reg 0): OK")

    # 2) read 1 byte
    one = i2c.readfrom(ADDR, 1)
    print("readfrom(1):", one)

    # 3) proper repeated-start read of 7 time regs
    i2c.writeto(ADDR, b"\x00", False)  # stop=False -> repeated START
    raw = i2c.readfrom(ADDR, 7)
    print("time regs:", [hex(b) for b in raw])
    print("RTC OK:", format_time(raw))
    return True


def try_hw_mem():
    print("\n=== HW I2C0 readfrom_mem fallback ===")
    i2c = I2C(0, sda=Pin(SDA), scl=Pin(SCL), freq=50_000)
    print("scan:", [hex(a) for a in i2c.scan()])
    raw = i2c.readfrom_mem(ADDR, 0x00, 7)
    print("RTC OK:", format_time(raw))
    return True


print("DS3231 diagnostic")
ok = False
for label, fn in (("SoftI2C", try_soft), ("HW readfrom_mem", try_hw_mem)):
    try:
        ok = fn()
        if ok:
            break
    except Exception as e:
        print(f"{label} failed: {e}")

if not ok:
    print("\nStill failing: re-seat RTC module, confirm CR1220 is optional")
    print("(RTC should answer on VCC alone). Then re-run this file.")
