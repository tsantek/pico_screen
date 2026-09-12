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
# One agent: newest run = Next workout, previous run = Last workout
CURSOR_AGENT_ID = "bc-xxxxxxxx-workout-agent"

# Phoenix, AZ
WEATHER_LAT = 33.4484
WEATHER_LON = -112.0740
WEATHER_TEMP_UNIT = "fahrenheit"  # or "celsius"

# America/Phoenix = UTC-7 year-round (no DST). Keep DS3231 set to Phoenix local time.
TZ_NAME = "America/Phoenix"

# True = always draw on wake (keep True for 6h schedule).
FORCE_REFRESH = True

# After draw, sleep then fetch+draw again.
# Every 5 min: TEST_SLEEP_SECONDS=300
# Hourly: REFRESH_HOURS=1, TEST_SLEEP_SECONDS=None
# Every 6h: REFRESH_HOURS=6, TEST_SLEEP_SECONDS=None
ENABLE_DEEPSLEEP = True
REFRESH_HOURS = 6
TEST_SLEEP_SECONDS = None

