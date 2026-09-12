"""Diagnose black plane: 4 patterns. Tell me which numbers you see."""

from drivers.epd_7in5_b import EPD_7in5_B
import time

epd = EPD_7in5_B()

# --- Pattern A: Waveshare docs (0=black, 1=white) ---
print("Pattern A: black text on white (docs)")
epd.imageblack.fill(0xFF)
epd.imagered.fill(0xFF)
epd.imageblack.text("A black-on-white", 10, 10, 0x00)
epd.imageblack.fill_rect(10, 40, 200, 30, 0x00)
epd.display()
time.sleep(3)

# --- Pattern B: inverted black plane ---
print("Pattern B: inverted black (0=white, 1=black)")
epd.imageblack.fill(0x00)
epd.imagered.fill(0xFF)
epd.imageblack.text("B inverted", 10, 10, 0xFF)
epd.imageblack.fill_rect(10, 40, 200, 30, 0xFF)
epd.display()
time.sleep(3)

# --- Pattern C: official red-bg that worked before ---
print("Pattern C: official red bg + black text")
epd.imageblack.fill(0xFF)
epd.imagered.fill(0x00)
epd.imageblack.text("C on red bg", 10, 10, 0x00)
epd.imagered.text("C red-plane text", 10, 40, 0xFF)
epd.display()
time.sleep(3)

# --- Pattern D: swap planes in send (black buf -> red cmd) ---
print("Pattern D: swapped 0x10/0x13 send")
epd.imageblack.fill(0xFF)
epd.imagered.fill(0xFF)
epd.imageblack.text("D should be black", 10, 10, 0x00)
epd.imagered.text("D should be red", 10, 40, 0x00)

high = epd.height
wide = epd.width // 8
epd.send_command(0x10)
for i in range(wide):
    epd.send_data1(epd.buffer_red[(i * high) : ((i + 1) * high)])
epd.send_command(0x13)
for i in range(wide):
    epd.send_data1(epd.buffer_black[(i * high) : ((i + 1) * high)])
epd.TurnOnDisplay()

print("done — which letters A/B/C/D were visible?")
