"""Minimal visibility test: white bg + black text (no ClearRed)."""

from drivers.epd_7in5_b import EPD_7in5_B

print("init")
epd = EPD_7in5_B()

print("buffers white + black text")
epd.imageblack.fill(0xFF)
epd.imagered.fill(0xFF)
epd.imageblack.text("BLACK ON WHITE", 20, 20, 0x00)
epd.imageblack.text("If readable, white mode OK", 20, 50, 0x00)
epd.imageblack.fill_rect(20, 80, 300, 40, 0x00)
epd.imageblack.text("inverted bar", 30, 94, 0xFF)
epd.imagered.text("RED ACCENT LINE", 20, 140, 0x00)

print("display")
epd.display()
print("done — look for black text on white")
