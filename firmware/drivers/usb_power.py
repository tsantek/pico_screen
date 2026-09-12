"""Detect laptop USB so we can skip deepsleep while deploying."""

from machine import Pin


def usb_connected():
    """True when Pico USB VBUS looks present (Pico W / 2 W WL_GPIO2)."""
    try:
        # Pico W / Pico 2 W: wireless chip GPIO senses VBUS
        return bool(Pin("WL_GPIO2", Pin.IN).value())
    except Exception:
        pass
    try:
        # Some builds expose this name
        return bool(Pin("USB_VBUS", Pin.IN).value())
    except Exception:
        pass
    return False
