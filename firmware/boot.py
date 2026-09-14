# Give host time to attach mpremote before main.py auto-starts.
# (Otherwise desk deepsleep can start before serial connects.)
import time

print("boot: 5s window for ./run_pico.sh ...")
try:
    time.sleep(5)
except Exception:
    pass

# If laptop USB is present, clear sleep marker so we don't silent-nap
try:
    from machine import Pin

    if Pin("WL_GPIO2", Pin.IN).value():
        try:
            import os

            os.remove("SLEEPING")
        except Exception:
            pass
except Exception:
    pass
