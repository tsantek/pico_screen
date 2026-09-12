"""
Pico desk dashboard — main entry.

Upload this folder to the Pico (Thonny), copy secrets.example.py → secrets.py,
set FORCE_REFRESH=True for first test, then ENABLE_DEEPSLEEP=True for daily use.
"""

import gc
import sys
import time

# Ensure firmware root is on path when run as main.py from root
sys.path.insert(0, "/")

try:
    import secrets
except ImportError:
    print("Missing secrets.py — copy secrets.example.py and fill values.")
    raise


def _load_optional(name, default=None):
    return getattr(secrets, name, default)


def build_model(rtc_tuple, battery_pct):
    y, mo, d, weekday, hour, minute, second = rtc_tuple
    # DS3231: 1=Sun .. 7=Sat → display name
    names = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
    months = (
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
    )
    wname = names[(weekday - 1) % 7]
    date_str = "%s, %s %d, %04d" % (wname.upper(), months[mo - 1], d, y)
    updated_str = "as of %02d:%02d" % (hour, minute)

    model = {
        "date_str": date_str,
        "updated_str": updated_str,
        "hour": hour,
        "minute": minute,
        "battery_pct": battery_pct,
        "battery_low": battery_pct is not None and battery_pct < 20,
        "calendar": {"today": [], "tomorrow": []},
        "weather": {},
        "agent": {},
        "offline": False,
        "temp_unit": "F"
        if _load_optional("WEATHER_TEMP_UNIT", "fahrenheit") == "fahrenheit"
        else "C",
    }

    today_ymd = (y, mo, d)
    offline = False

    try:
        from net import wifi

        wifi.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    except Exception as e:
        print("WiFi failed:", e)
        offline = True

    if not offline:
        # Calendar
        try:
            from net import ical

            gc.collect()
            model["calendar"] = ical.fetch(secrets.ICAL_URL, today_ymd)
            print(
                "Calendar today:",
                len(model["calendar"]["today"]),
                "tomorrow:",
                len(model["calendar"]["tomorrow"]),
            )
        except Exception as e:
            print("Calendar failed:", e)
            offline = True
        gc.collect()

        # Weather
        try:
            from net import weather

            model["weather"] = weather.fetch(
                secrets.WEATHER_LAT,
                secrets.WEATHER_LON,
                _load_optional("WEATHER_TEMP_UNIT", "fahrenheit"),
                _load_optional("TZ_NAME", "America/Phoenix"),
                now_ymd=today_ymd,
                now_hour=hour,
                hours_ahead=12,
            )
            print("Weather OK, hourly:", len(model["weather"].get("hourly") or []))
        except Exception as e:
            print("Weather failed:", e)
            offline = True
        gc.collect()

        # Cursor agent — same agent: next = newest run, last = previous run
        try:
            from net import cursor_agent

            agent_id = _load_optional("CURSOR_AGENT_ID", None) or _load_optional(
                "CURSOR_AGENT_NEXT_ID", None
            )
            model["agent"] = cursor_agent.fetch(secrets.CURSOR_API_KEY, agent_id)
            print(
                "Next workout:",
                (model["agent"].get("workout_next") or {}).get("kind"),
                (model["agent"].get("workout_next") or {}).get("title"),
            )
            print(
                "Last workout:",
                (model["agent"].get("workout_last") or {}).get("kind"),
                (model["agent"].get("workout_last") or {}).get("title"),
            )
        except Exception as e:
            print("Agent failed:", e)
            offline = True
        gc.collect()

        try:
            from net import wifi as wifi_mod

            wifi_mod.disconnect()
        except Exception:
            pass

    model["offline"] = offline
    return model


def run_once():
    print("=== Dashboard cycle ===")
    rtc_tuple = None
    battery_pct = None
    rtc = None

    # Give CYW43 time after wake before any I2C (matches working project)
    time.sleep_ms(1500)

    try:
        from drivers.rtc_ds3231 import DS3231

        rtc = DS3231()
        rtc_tuple = rtc.datetime()
        print("RTC:", rtc.format(), "OSF=", rtc.oscillator_stopped())
    except Exception as e:
        print("RTC failed:", e)
        tm = time.localtime()
        rtc_tuple = (tm[0], tm[1], tm[2], (tm[6] + 1) % 7 + 1, tm[3], tm[4], tm[5])

    # If clock is wrong (e.g. 2000 / dead coin cell), fix from NTP as Phoenix
    try:
        from net.phx_time import rtc_needs_sync, sync_rtc_phoenix
        from net import wifi

        if rtc_needs_sync(rtc_tuple, rtc):
            print("RTC needs sync — fetching Phoenix time from NTP...")
            wifi.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
            if rtc is not None:
                rtc_tuple = sync_rtc_phoenix(rtc)
            else:
                from net.phx_time import ntp_phoenix_tuple

                rtc_tuple = ntp_phoenix_tuple()
                print("NTP Phoenix (no DS3231 write):", rtc_tuple)
    except Exception as e:
        print("Time sync failed:", e)

    try:
        from drivers.ina219 import INA219

        ina = INA219()
        battery_pct = ina.battery_percent()
        print("Battery:", battery_pct, "%", "V=", ina.bus_voltage_v())
    except Exception as e:
        print("UPS failed:", e)
        battery_pct = None

    gc.collect()
    time.sleep_ms(200)

    model = build_model(rtc_tuple, battery_pct if battery_pct is not None else 0)

    from drivers.epd_7in5_b import EPD_7in5_B
    from ui import dashboard

    epd = EPD_7in5_B()  # __init__ already calls init()
    dashboard.draw(epd, model)
    print("Refreshing panel...")
    epd.display()
    try:
        epd.sleep()
    except Exception:
        pass
    print("Done.")
    return rtc_tuple


def main():
    """Loop forever: draw → sleep → draw. Survives USB unplug on UPS power."""
    # Short window so laptop can grab REPL after reset / power-cycle
    print("Dashboard starting in 3s (Ctrl+C / mpremote OK now)...")
    time.sleep_ms(3000)

    enable_sleep = bool(_load_optional("ENABLE_DEEPSLEEP", False))
    interval_h = int(_load_optional("REFRESH_HOURS", 6))
    test_s = _load_optional("TEST_SLEEP_SECONDS", None)

    from drivers import status_led
    from net.schedule import low_power_sleep, sleep_until_boundary

    print("=== Pico desk dashboard ===")
    if test_s:
        print("Loop sleep: TEST %ss" % int(test_s))
    else:
        print("Loop sleep:", enable_sleep, " every", interval_h, "h")

    while True:
        status_led.on()
        hour = minute = second = 0
        try:
            rtc_tuple = run_once()
            _y, _mo, _d, _w, hour, minute, second = rtc_tuple
        except Exception as e:
            print("Cycle error:", e)
        finally:
            status_led.off()

        if not enable_sleep:
            print("ENABLE_DEEPSLEEP=False — exiting loop (REPL OK).")
            return

        if test_s is not None and int(test_s) > 0:
            low_power_sleep(int(test_s) * 1000)
        else:
            sleep_until_boundary(hour, minute, second, interval_h=interval_h)


if __name__ == "__main__":
    main()
