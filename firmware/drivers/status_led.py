"""Onboard status LED (Pico W / Pico 2 W)."""

_led = None


def _get():
    global _led
    if _led is not None:
        return _led
    try:
        from machine import Pin

        try:
            _led = Pin("LED", Pin.OUT)
        except Exception:
            _led = Pin(25, Pin.OUT)
        return _led
    except Exception as e:
        print("LED unavailable:", e)
        _led = False
        return None


def on():
    led = _get()
    if led:
        led.value(1)


def off():
    led = _get()
    if led:
        led.value(0)
