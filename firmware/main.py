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

        # Cursor agent — POST status template (or fall back to reading runs)
        try:
            from net import cursor_agent

            agent_id = _load_optional("CURSOR_AGENT_ID", None) or _load_optional(
                "CURSOR_AGENT_NEXT_ID", None
            )
            prompt_on = bool(_load_optional("AGENT_PROMPT_ON_REFRESH", True))
            model["agent"] = cursor_agent.fetch(
                secrets.CURSOR_API_KEY,
                agent_id,
                prompt_on_refresh=prompt_on,
                prompt_text=_load_optional("AGENT_STATUS_PROMPT", None),
                poll_s=int(_load_optional("AGENT_POLL_SECONDS", 8)),
                timeout_s=int(_load_optional("AGENT_POLL_TIMEOUT", 240)),
            )
            print(
                "Agent source:",
                model["agent"].get("source"),
                "| Next:",
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


def _splash(msg, line2=""):
    """Fast on-screen proof of life before Wi‑Fi (helps diagnose UPS loops)."""
    try:
        from drivers.epd_7in5_b import EPD_7in5_B
        from ui.dashboard import text_big

        epd = EPD_7in5_B()
        bk, rd = epd.imageblack, epd.imagered
        bk.fill(0xFF)
        rd.fill(0x00)
        text_big(bk, (msg or "?")[:12], 40, 120, 0x00, scale=3)
        if line2:
            bk.text((line2 or "")[:48], 40, 220, 0x00)
        epd.display()
        try:
            epd.sleep()
        except Exception:
            pass
    except Exception as e:
        print("Splash failed:", e)


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


def _read_rtc_tuple():
    try:
        from drivers.rtc_ds3231 import DS3231

        rtc = DS3231()
        return rtc.datetime(), rtc
    except Exception as e:
        print("RTC failed:", e)
        tm = time.localtime()
        return (tm[0], tm[1], tm[2], (tm[6] + 1) % 7 + 1, tm[3], tm[4], tm[5]), None


def _countdown_unplug(seconds=10, next_wake=""):
    """Give time to unplug laptop USB before deepsleep (mpremote RTS can reset)."""
    print("")
    print("=" * 48)
    print("  UNPLUG LAPTOP USB FROM PICO NOW")
    if next_wake:
        print("  Next wake: %s" % next_wake)
    print("  (keeps UPS running; avoids serial reset)")
    print("=" * 48)
    for i in range(int(seconds), 0, -1):
        print("  >>> unplug countdown: %d <<<" % i)
        time.sleep(1)
    print("  Entering deepsleep...")
    print("")


def _enter_sleep(hour, minute, second, interval_h, test_s, mode, draw_hours):
    from net.schedule import (
        deep_sleep_ms,
        hms_after_seconds,
        low_power_sleep,
        next_draw_hms,
        sleep_until_boundary,
        sleep_until_rtc_alarm,
    )

    use_alarm = bool(_load_optional("USE_RTC_ALARM", False))
    alarm_test_min = _load_optional("RTC_ALARM_TEST_MINUTES", None)
    int_pin = int(_load_optional("RTC_INT_PIN", 3))

    if use_alarm and (test_s is None or int(test_s) <= 0):
        try:
            from drivers.rtc_ds3231 import DS3231

            rtc = DS3231()
            if alarm_test_min is not None and int(alarm_test_min) > 0:
                add_s = int(alarm_test_min) * 60
                ah, am, asec = hms_after_seconds(hour, minute, second, add_s)
                print(
                    "Alarm TEST: every ~%d min → %02d:%02d:%02d (deepsleep+INT)"
                    % (int(alarm_test_min), ah, am, asec)
                )
                sleep_until_rtc_alarm(
                    rtc,
                    ah,
                    am,
                    asec,
                    int_pin=int_pin,
                    now_hms=(hour, minute, second),
                    use_deep=True,
                )
                return

            hours = draw_hours or tuple(range(0, 24, max(1, interval_h)))
            nh, nm, _ns = next_draw_hms(hour, minute, second, hours)
            print("Arming RTC alarm: %02d:%02d PHX" % (nh, nm))
            sleep_until_rtc_alarm(
                rtc,
                nh,
                nm,
                0,
                int_pin=int_pin,
                now_hms=(hour, minute, second),
                use_deep=(mode == "deep"),
            )
            return
        except Exception as e:
            print("RTC alarm sleep failed (%s) — falling back to timed sleep" % e)

    if test_s is not None and int(test_s) > 0:
        ms = int(test_s) * 1000
        if mode == "idle":
            low_power_sleep(ms)
        else:
            deep_sleep_ms(ms)
        return

    sleep_until_boundary(
        hour, minute, second, interval_h=interval_h, mode=mode, draw_hours=draw_hours
    )


def _load_draw_hours():
    raw = _load_optional("DRAW_HOURS", None)
    if raw:
        try:
            return tuple(int(h) for h in raw)
        except Exception:
            pass
    return None


def _should_skip_sleep_for_usb():
    """Opt-in: stay awake with laptop USB so ./run_pico.sh keeps working.

    Default is False — UPS often backfeeds VBUS so WL_GPIO2 can look "USB"
    even with the laptop unplugged, which used to skip deepsleep forever.
    Set SKIP_SLEEP_WHEN_USB=True only while developing on USB.
    """
    if _load_optional("RTC_ALARM_TEST_MINUTES", None):
        return False  # allow alarm test with USB connected
    # Legacy alias
    if bool(_load_optional("SLEEP_WHEN_USB", False)):
        return False
    if not bool(_load_optional("SKIP_SLEEP_WHEN_USB", False)):
        return False
    try:
        from drivers.usb_power import usb_connected

        return usb_connected()
    except Exception:
        return False


def main():
    """Draw → RTC alarm / deepsleep → wake → draw."""
    import machine

    # Clear leftover wake-test flag so it can't steal boots
    try:
        import os

        os.remove("WAKE_TEST")
    except Exception:
        pass

    from drivers import status_led
    from net.schedule import should_draw_now

    enable_sleep = bool(_load_optional("ENABLE_DEEPSLEEP", False))
    interval_h = int(_load_optional("REFRESH_HOURS", 6))
    test_s = _load_optional("TEST_SLEEP_SECONDS", None)
    draw_hours = _load_draw_hours()
    use_alarm = bool(_load_optional("USE_RTC_ALARM", False))
    alarm_test_min = _load_optional("RTC_ALARM_TEST_MINUTES", None)
    mode = (_load_optional("SLEEP_MODE", "deep") or "deep").lower()
    if mode not in ("deep", "idle"):
        mode = "deep"

    woke_deep = False
    try:
        woke_deep = machine.reset_cause() == machine.DEEPSLEEP_RESET
    except Exception:
        pass

    usb_now = _should_skip_sleep_for_usb()

    # Wake from deepsleep: clear INT; only full-draw inside DRAW_HOURS window
    if woke_deep and use_alarm:
        print("=== Wake from deepsleep (alarm path) ===")
        time.sleep_ms(400)
        rtc_tuple = None
        try:
            from machine import Pin
            from drivers.rtc_ds3231 import DS3231

            rtc = DS3231()
            pin_n = int(_load_optional("RTC_INT_PIN", 3))
            pin = Pin(pin_n, Pin.IN, Pin.PULL_UP)
            a1f = bool(rtc.alarm1_fired())
            print("A1F=%s GP%d=%d" % (a1f, pin_n, pin.value()))
            rtc.clear_alarm_flags()
            for _ in range(40):
                if pin.value() == 1:
                    break
                rtc.clear_alarm_flags()
                time.sleep_ms(25)
            if pin.value() == 0:
                # Stuck INT used to force a full Wi‑Fi draw every nap — drain UPS
                print("INT stuck LOW after clear — disable alarm IRQ")
                try:
                    rtc.disable_alarms()
                except Exception:
                    pass
            rtc_tuple = rtc.datetime()
        except Exception as e:
            print("Alarm clear:", e)
            rtc_tuple, _ = _read_rtc_tuple()

        _y, _mo, _d, _w, hour, minute, second = rtc_tuple
        # Gate on clock window only (not pin-low). Mid-naps must stay silent.
        if alarm_test_min:
            at_window = True
        elif draw_hours:
            at_window = should_draw_now(hour, minute, second, draw_hours=draw_hours)
        else:
            at_window = True
        if not at_window:
            print(
                "Mid-nap %02d:%02d:%02d — silent deepsleep again (no Wi‑Fi/draw)"
                % (hour, minute, second)
            )
            status_led.off()
            _enter_sleep(hour, minute, second, interval_h, test_s, mode, draw_hours)
            return
        print("Draw window — fetching dashboard")
        _splash("WAKE", "%02d:%02d" % (hour, minute))
    elif woke_deep and not usb_now:
        print("=== Wake from deepsleep ===")
        time.sleep_ms(300)
        _splash("WAKE", "fetching...")
    else:
        print("Dashboard starting in 3s (Ctrl+C / mpremote OK now)...")
        time.sleep_ms(3000)
        if usb_now:
            print("USB host detected — will skip deepsleep after draw (deploy mode).")
        if alarm_test_min:
            print("Alarm test: unplug during countdown after draw.")

    print("=== Pico desk dashboard ===")
    if alarm_test_min:
        print(
            "Sleep: RTC alarm TEST every %s min (GP%s)"
            % (alarm_test_min, _load_optional("RTC_INT_PIN", 3))
        )
    elif use_alarm and draw_hours:
        print("Sleep: RTC alarm at", draw_hours, "PHX")
    elif test_s:
        print("Sleep: TEST %ss mode=%s" % (int(test_s), mode))
    elif draw_hours:
        print("Sleep:", enable_sleep, "at hours", draw_hours, "PHX mode=%s" % mode)
    else:
        print("Sleep:", enable_sleep, "every", interval_h, "h mode=%s" % mode)

    # Timed mid-naps when not using RTC alarm path
    if (
        enable_sleep
        and woke_deep
        and not usb_now
        and not use_alarm
        and (test_s is None or int(test_s) <= 0)
        and mode == "deep"
    ):
        rtc_tuple, _rtc = _read_rtc_tuple()
        _y, _mo, _d, _w, hour, minute, second = rtc_tuple
        print("RTC gate:", "%02d:%02d:%02d" % (hour, minute, second))
        if draw_hours:
            at_window = should_draw_now(hour, minute, second, draw_hours=draw_hours)
        else:
            legacy = tuple(range(0, 24, max(1, interval_h)))
            at_window = should_draw_now(hour, minute, second, draw_hours=legacy)
        if not at_window:
            print("Not at draw window — deepsleep again (no redraw).")
            status_led.off()
            _enter_sleep(hour, minute, second, interval_h, test_s, mode, draw_hours)
            return

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

        # Always count down first so you can unplug before we decide to sleep
        next_label = ""
        try:
            if bool(_load_optional("USE_RTC_ALARM", False)):
                alarm_test_min = _load_optional("RTC_ALARM_TEST_MINUTES", None)
                if alarm_test_min is not None and int(alarm_test_min) > 0:
                    from net.schedule import hms_after_seconds

                    ah, am, asec = hms_after_seconds(hour, minute, second, int(alarm_test_min) * 60)
                    next_label = "%02d:%02d:%02d" % (ah, am, asec)
                elif draw_hours:
                    from net.schedule import next_draw_hms

                    nh, nm, _ = next_draw_hms(hour, minute, second, draw_hours)
                    next_label = "%02d:%02d PHX" % (nh, nm)
        except Exception:
            pass
        _countdown_unplug(
            int(_load_optional("UNPLUG_COUNTDOWN_SECONDS", 10)),
            next_wake=next_label,
        )

        if _should_skip_sleep_for_usb():
            print("USB still connected after countdown — skipping deepsleep (REPL OK).")
            print("Unplug USB, then press RESET for desk/UPS mode.")
            return

        try:
            from drivers.usb_power import usb_connected

            print("VBUS sense=%s (ignored unless SKIP_SLEEP_WHEN_USB)" % usb_connected())
        except Exception:
            pass

        _enter_sleep(hour, minute, second, interval_h, test_s, mode, draw_hours)
        # Alarm test / production deepsleep usually does not return here.
        if mode == "deep" and use_alarm and not alarm_test_min:
            return
        if mode == "deep" and not use_alarm and not alarm_test_min:
            return


if __name__ == "__main__":
    main()
