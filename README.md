# Pico 2 W + Waveshare 7.5" e-Paper (B) desk dashboard

Pico-only desk dashboard: Wi‑Fi fetch → draw e-ink → **deepsleep** → wake → repeat. Time zone is **America/Phoenix** (UTC−7, no DST).

Default refresh: **every 6 hours** at Phoenix **00:00 / 06:00 / 12:00 / 18:00** (draw window = first 5 minutes after each boundary).

## Hardware

```
UPS (LiPo) → RTC (DS3231 + coin cell) → e-Paper 7.5 B → Pico 2 W
```

Bring-up scripts: [`bringup/`](bringup/).

### Two batteries (different jobs)

| Battery | Role |
|---------|------|
| **Big (UPS LiPo)** | Powers Pico + screen when laptop USB is unplugged. Keep UPS **switch ON** for desk use. |
| **Small (RTC CR2032)** | Keeps **date/time** only when main power is dead. Does **not** run the Pico or wake it. |

Wake is **`machine.deepsleep`** (software timer, max ~70 min per nap). For a 6h gap the Pico wakes, checks the RTC, and deepsleeps again **without redrawing** until the next boundary. RTC alarm / solder **R5→GP3** is optional and **not used**.

### UPS / unplug

1. `./run_pico.sh main` (or power-cycle so on-device `main.py` starts).  
2. Wait for `Deep sleep …s (full power-down, wake resets)...`.  
3. Unplug laptop USB. Serial drops — normal.  
4. Board should wake on its own; full redraw near 00/06/12/18.

If the panel **never** updates after unplug, deepsleep wake failed on your UPS — set `SLEEP_MODE = "idle"` in `secrets.py` (higher power, more reliable).

Optional: wall USB into the **UPS** port for always-charged desk use.

### Battery life

| Mode | Expectation |
|------|-------------|
| **`SLEEP_MODE = "deep"`** (default) | Much better than idle. Often **weeks** on a mid-size LiPo with 6h refreshes (Wi‑Fi only a few minutes/day). |
| **`SLEEP_MODE = "idle"`** | ~20–40 mA average → roughly **1–4 days** depending on pack size. |

Idle mode previously drained ~50% in ~12h — that’s why deepsleep is the default now.

## Layout (3 columns)

| Left | Center | Right |
|------|--------|-------|
| Date / greeting, weather (now + next 12h) | Today + tomorrow calendar, last workout | Next workout (parsed agent run) |

Footer: UPS battery % and `as of HH:MM` (Phoenix).

## What you need

1. Wi‑Fi SSID / password  
2. Google Calendar **secret iCal** URL  
3. Cursor API key + agent ID  
4. Phoenix lat/lon (defaults in `secrets.example.py`)

Copy [`firmware/secrets.example.py`](firmware/secrets.example.py) → `firmware/secrets.py` (gitignored).

## Deploy

Quit Thonny first. From the project root:

```bash
./run_pico.sh main           # upload + start dashboard
./run_pico.sh demo_offline   # layout preview (no Wi‑Fi)
./run_pico.sh set_rtc        # set DS3231 from Mac Phoenix time
./run_pico.sh rtc_check      # coin cell / OSF / year-2000
./run_pico.sh agent_dump     # raw Cursor agent runs
./run_pico.sh wifi_test
./run_pico.sh --upload-only
```

`main.py` auto-runs on power-up. **3s** delay only on non-deepsleep boots so `mpremote` can connect.

## Refresh schedule (`secrets.py`)

| Setting | Effect |
|---------|--------|
| `ENABLE_DEEPSLEEP = True` | After draw, sleep toward next cycle |
| `SLEEP_MODE = "deep"` | `machine.deepsleep` (best battery; wake = full reset) |
| `SLEEP_MODE = "idle"` | Chunked `time.sleep` (safer wake on some UPS setups) |
| `REFRESH_HOURS = 6` | Phoenix **00 / 06 / 12 / 18** when `TEST_SLEEP_SECONDS=None` |
| `TEST_SLEEP_SECONDS = 300` | Override: every **5 min** (testing) |

## Time / RTC

- DS3231 stores **Phoenix local** time.  
- Bad coin cell → often `2000-01-01` + **OSF=1**.  
- `main.py` NTP-syncs Phoenix and writes the DS3231 when needed.  
- `./run_pico.sh set_rtc` / `rtc_check`

## Cursor agent data (how it works)

Each dashboard refresh (when `AGENT_PROMPT_ON_REFRESH = True`):

1. `POST /v1/agents/{id}/runs` with a fixed **status prompt** (template in `firmware/net/cursor_agent.py`)  
2. Poll until the run is `FINISHED` (default up to 4 minutes)  
3. Parse `## NEXT` and `## LAST` sections into the two workout cards  
4. If the prompt/run fails → fall back to reading the newest + previous runs  

Set `AGENT_PROMPT_ON_REFRESH = False` to only **read** existing runs (no new agent work, faster/cheaper).

### Template the agent must return

```markdown
## NEXT
KIND: RUN
TITLE: short title
Duration: ...
Pattern: ...
Run pace: ...
Walk: ...
Incline: ...
Avg HR: ...
Soft max: ...
Fuel: ...

## LAST
KIND: BIKE
TITLE: ...
...
```

`KIND` must be `RUN` / `GYM` / `BIKE` / `SWIM`. Override the prompt via `AGENT_STATUS_PROMPT` in `secrets.py` if needed.

Test without redrawing the panel:

```bash
./run_pico.sh agent_dump
```

## Behavior notes

- SoftI2C: RTC GP20/21, UPS INA219 GP6/7 `@ 0x43`.  
- E-ink full refresh flickers ~15–25s. Prefer 6h over 5‑min for panel life.  
- Deepsleep max ~70 min; longer waits are multiple naps without redraw.  
- Calendar ICS can be large; shrink the calendar if memory fails.  
- Workout cards: RUN / GYM / BIKE / SWIM; non-ASCII folded for 8×8 font.  
- Recovery: BOOTSEL → flash nuke → MicroPython UF2 → `./run_pico.sh main`. Keep `boot.py` light.
