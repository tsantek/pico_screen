"""Simple WiFi connect — pattern that worked on this Pico before."""

import network
import time


def connect(ssid, password, timeout_s=20, **_ignored):
    """Connect STA Wi-Fi. Extra kwargs ignored for secrets compatibility."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("Already connected to Wi-Fi")
        return wlan

    print("Connecting to Wi-Fi...")
    wlan.connect(ssid, password)

    start = time.time()
    while not wlan.isconnected():
        time.sleep(1)
        elapsed = int(time.time() - start)
        if elapsed > 0 and elapsed % 5 == 0:
            print("  Still connecting... (%ss)" % elapsed)
        if elapsed > timeout_s:
            raise OSError("Wi-Fi connection timeout")

    print("Connected! IP:", wlan.ifconfig()[0])
    return wlan


def disconnect():
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.active():
            wlan.active(False)
            print("Wi-Fi disabled")
    except Exception:
        pass
