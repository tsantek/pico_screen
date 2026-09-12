# Pico 2 W + Waveshare 7.5" e-Paper (B) desk dashboard

Pico-only desk dashboard: Wi‑Fi fetch → draw e-ink → **lightsleep** → repeat. Time zone is **America/Phoenix** (UTC−7, no DST).

## Hardware

`UPS → RTC (DS3231) → e-Paper 7.5 B → Pico 2 W`

Bring-up scripts: [`bringup/`](bringup/).

## Layout (3 columns)

| Left | Center | Right |
|------|--------|-------|
| Date / greeting, weather (now + next 12h) | Today + tomorrow calendar, last workout | Next workout (parsed agent run) |

Footer: battery % and `as of HH:MM` (Phoenix).

## What you need

1. Wi‑Fi SSID / password  
2. Google Calendar **secret iCal** URL  
3. Cursor API key + agent ID (newest run = Next, previous = Last)  
4. Phoenix lat/lon (defaults in `secrets.example.py`)

Copy [`firmware/secrets.example.py`](firmware/secrets.example.py) → `firmware/secrets.py` (gitignored).

## Deploy

Quit Thonny first (it locks the serial port). From the project root:

```bash
./run_pico.sh main           # upload + start dashboard loop
./run_pico.sh demo_offline   # layout preview (no Wi‑Fi)
./run_pico.sh set_rtc        # set DS3231 from Mac Phoenix time
./run_pico.sh rtc_check      # diagnose coin cell / OSF / year-2000
./run_pico.sh agent_dump     # raw Cursor agent runs
./run_pico.sh wifi_test
./run_pico.sh --upload-only
```

`main.py` auto-runs on power-up after `boot.py`. There is a **3s** delay at start so `mpremote` can still connect.

## Refresh schedule (`secrets.py`)

| Setting | Effect |
|---------|--------|
| `ENABLE_DEEPSLEEP = True` | Loop: draw → sleep → draw (name is historical; uses **lightsleep**) |
| `TEST_SLEEP_SECONDS = 300` | Sleep **5 minutes** between cycles (overrides hours) |
| `TEST_SLEEP_SECONDS = None` + `REFRESH_HOURS = 1` or `6` | Sleep until next hour / 6h Phoenix boundary |

Only one sleep mode applies: test seconds **or** `REFRESH_HOURS`.

After you see `Sleep 300s (lightsleep, USB optional)...`, you can **unplug USB**. The board should keep looping on UPS. Laptop serial will disconnect — that is normal. Watch the panel `as of` time for the next update.

## Time / RTC

- DS3231 holds **Phoenix local** time.  
- Bad/missing coin cell → often `2000-01-01` + **OSF=1**.  
- `main.py` detects that and **NTP-syncs Phoenix**, then writes the DS3231.  
- Replace the CR2032 when you can; until then NTP re-fixes after power loss.  
- Manual set: `./run_pico.sh set_rtc`  
- Diagnose: `./run_pico.sh rtc_check`

## Behavior notes

- SoftI2C for RTC (GP20/21) and UPS INA219 (GP6/7 `@ 0x43`).  
- E-ink full refresh flickers ~15–25s — normal. Frequent 5‑min refreshes wear the panel faster; use hourly/6h for long-term desk use.  
- Pico MicroPython sleep chunks max ~70 min; longer gaps are split. Prefer **lightsleep** over deepsleep (deepsleep often failed to wake with USB unplugged).  
- Calendar ICS can be large; use a smaller calendar if memory fails.  
- Workout cards parse agent markdown (RUN / GYM / BIKE / SWIM). Non-ASCII is folded for the 8×8 font.
