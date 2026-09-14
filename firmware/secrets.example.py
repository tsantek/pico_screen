# Secrets — never commit real values.
# Copy to secrets.py on the Pico (Thonny) and fill in.

WIFI_SSID = "your-wifi"
WIFI_PASSWORD = "your-password"
# Optional: set if your AP is on a fixed channel (helped on another Pico project)
WIFI_CHANNEL = 2  # or None
WIFI_COUNTRY = "US"

# Google Calendar → Settings → Integrate calendar → Secret (or public) iCal address
# One calendar:
ICAL_URL = "https://calendar.google.com/calendar/ical/xxx/private-xxx/basic.ics"
# Or merge two+ (preferred if set — overrides ICAL_URL):
# ICAL_URLS = (
#     "https://calendar.google.com/calendar/ical/personal/.../basic.ics",
#     "https://calendar.google.com/calendar/ical/work/.../basic.ics",
# )
# Cache today+tomorrow on Pico flash; skip ICS download until next Phoenix day
ICAL_CACHE_DAY = True

# Cursor Dashboard → API Keys
CURSOR_API_KEY = "key_xxx"
# One agent: Pico POSTs a status prompt each refresh (## NEXT / ## LAST template)
CURSOR_AGENT_ID = "bc-xxxxxxxx-workout-agent"
AGENT_PROMPT_ON_REFRESH = True  # False = only read existing runs
AGENT_POLL_SECONDS = 8
AGENT_POLL_TIMEOUT = 90  # keep short on UPS
# AGENT_STATUS_PROMPT = None  # optional override; see net/cursor_agent.py STATUS_PROMPT


# Phoenix, AZ
WEATHER_LAT = 33.4484
WEATHER_LON = -112.0740
WEATHER_TEMP_UNIT = "fahrenheit"  # or "celsius"
WEATHER_CACHE_DAY = True  # one Open-Meteo download per Phoenix day

# America/Phoenix = UTC-7 year-round (no DST). Keep DS3231 set to Phoenix local time.
TZ_NAME = "America/Phoenix"

# True = always draw when a draw cycle runs.
FORCE_REFRESH = True

# After draw, sleep then wake for next cycle.
# Phoenix draw times:
DRAW_HOURS = (6, 12, 18)  # 6am, 12pm, 6pm (no midnight)
TEST_SLEEP_SECONDS = None  # or 300 for every-5-min timed testing
ENABLE_DEEPSLEEP = True
REFRESH_HOURS = 6  # unused when DRAW_HOURS is set
USE_RTC_ALARM = True
RTC_INT_PIN = 3
RTC_ALARM_TEST_MINUTES = None  # or 3 for quick alarm test; None = DRAW_HOURS
SLEEP_MODE = "deep"
SLEEP_WHEN_USB = False  # legacy; prefer SKIP_SLEEP_WHEN_USB
SKIP_SLEEP_WHEN_USB = True  # stay awake after draw while laptop USB plugged in
UNPLUG_COUNTDOWN_SECONDS = 10

