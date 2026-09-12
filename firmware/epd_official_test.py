"""Exact Waveshare smoke test — Clear then sample text.

If this shows nothing, check FPC cable / stack power / panel orientation.
"""

from drivers.epd_7in5_b import EPD_7in5_B


print("1) init")
epd = EPD_7in5_B()
print("2) Clear (flicker ~20s is normal)")
epd.Clear()
print("3) draw text buffers")
epd.imageblack.fill(0xFF)
epd.imagered.fill(0x00)
epd.imageblack.text("Waveshare", 5, 10, 0x00)
epd.imagered.text("Pico_ePaper-7.5-B", 5, 40, 0xFF)
epd.imageblack.text("If you see this, OK", 5, 70, 0x00)
print("4) display()")
epd.display()
print("5) done")
