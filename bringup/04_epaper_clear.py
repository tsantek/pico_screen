"""Minimal e-Paper 7.5" B smoke test: init + clear to white.

Pins match Waveshare Pico-ePaper-7.5-B (SPI1).
Full refresh takes ~15–25s and the panel will flicker — that is normal.
"""

from machine import Pin, SPI
import time

RST_PIN = 12
DC_PIN = 8
CS_PIN = 9
BUSY_PIN = 13

EPD_WIDTH = 800
EPD_HEIGHT = 480


class EPD:
    def __init__(self):
        self.reset_pin = Pin(RST_PIN, Pin.OUT)
        self.dc_pin = Pin(DC_PIN, Pin.OUT)
        self.cs_pin = Pin(CS_PIN, Pin.OUT)
        self.busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        self.spi = SPI(1, baudrate=4_000_000, sck=Pin(10), mosi=Pin(11))
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT

    def _write(self, pin, value):
        pin.value(value)

    def reset(self):
        self._write(self.reset_pin, 1)
        time.sleep_ms(200)
        self._write(self.reset_pin, 0)
        time.sleep_ms(2)
        self._write(self.reset_pin, 1)
        time.sleep_ms(200)

    def send_command(self, command):
        self._write(self.dc_pin, 0)
        self._write(self.cs_pin, 0)
        self.spi.write(bytearray([command]))
        self._write(self.cs_pin, 1)

    def send_data(self, data):
        self._write(self.dc_pin, 1)
        self._write(self.cs_pin, 0)
        self.spi.write(bytearray([data]))
        self._write(self.cs_pin, 1)

    def send_data1(self, data):
        self._write(self.dc_pin, 1)
        self._write(self.cs_pin, 0)
        self.spi.write(bytearray(data))
        self._write(self.cs_pin, 1)

    def wait_busy(self):
        print("  waiting for BUSY...", end="")
        while self.busy_pin.value() == 1:
            time.sleep_ms(50)
        print(" ok")

    def turn_on(self):
        self.send_command(0x12)
        time.sleep_ms(100)
        self.wait_busy()

    def init(self):
        print("reset")
        self.reset()
        self.send_command(0x01)  # POWER SETTING
        self.send_data(0x07)
        self.send_data(0x07)
        self.send_data(0x3f)
        self.send_data(0x3f)

        self.send_command(0x04)  # POWER ON
        time.sleep_ms(100)
        self.wait_busy()

        self.send_command(0x00)  # PANEL SETTING
        self.send_data(0x0F)

        self.send_command(0x61)  # RESOLUTION
        self.send_data(0x03)
        self.send_data(0x20)
        self.send_data(0x01)
        self.send_data(0xE0)

        self.send_command(0x15)
        self.send_data(0x00)

        self.send_command(0x50)
        self.send_data(0x11)
        self.send_data(0x07)

        self.send_command(0x60)
        self.send_data(0x22)

    def clear_white(self):
        wide = self.width // 8
        high = self.height
        row = [0xFF] * high

        print("send black plane (white)")
        self.send_command(0x10)
        for _ in range(wide):
            self.send_data1(row)

        print("send red plane (white)")
        self.send_command(0x13)
        for _ in range(wide):
            self.send_data1(row)

        print("refresh (flicker is normal)")
        self.turn_on()


print("e-Paper 7.5 B clear test")
print(f"BUSY pin idle level before init: {Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP).value()}")
epd = EPD()
epd.init()
epd.clear_white()
print("Done — panel should be white.")
