# Secrets — never commit real values.
# Copy to secrets.py on the Pico (Thonny) and fill in.

WIFI_SSID = "your-wifi"
WIFI_PASSWORD = "your-password"
# Optional: set if your AP is on a fixed channel (helped on another Pico project)
WIFI_CHANNEL = 2  # or None
WIFI_COUNTRY = "US"

# Google Calendar → Settings → Integrate calendar → Secret address in iCal format
ICAL_URL = "https://calendar.google.com/calendar/ical/xxx/private-xxx/basic.ics"

# Cursor Dashboard → API Keys
CURSOR_API_KEY = "key_xxx"
# One agent: Pico POSTs a status prompt each refresh (## NEXT / ## LAST template)
CURSOR_AGENT_ID = "bc-xxxxxxxx-workout-agent"
AGENT_PROMPT_ON_REFRESH = True  # False = only read existing runs
AGENT_POLL_SECONDS = 8
AGENT_POLL_TIMEOUT = 240
# AGENT_STATUS_PROMPT = None  # optional override; see net/cursor_agent.py STATUS_PROMPT


# Phoenix, AZ
WEATHER_LAT = 33.4484
WEATHER_LON = -112.0740
WEATHER_TEMP_UNIT = "fahrenheit"  # or "celsius"

# America/Phoenix = UTC-7 year-round (no DST). Keep DS3231 set to Phoenix local time.
TZ_NAME = "America/Phoenix"

# True = always draw when a draw cycle runs.
FORCE_REFRESH = True

# After draw, sleep then wake for next cycle.
# Every 5 min: TEST_SLEEP_SECONDS=300
# Hourly: REFRESH_HOURS=1, TEST_SLEEP_SECONDS=None
# Every 6h: REFRESH_HOURS=6, TEST_SLEEP_SECONDS=None
ENABLE_DEEPSLEEP = True
REFRESH_HOURS = 6
TEST_SLEEP_SECONDS = None
# "deep" = machine.deepsleep (best battery; wake = reset)
# "idle" = time.sleep chunks (higher power; more reliable wake on UPS)
SLEEP_MODE = "deep"
# False = while laptop USB is plugged in, skip deepsleep so ./run_pico.sh works
SLEEP_WHEN_USB = False

