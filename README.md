# Pico 2 W + Waveshare 7.5" e-Paper (B) desk dashboard

Pico-only desk dashboard: Wi‑Fi fetch → draw e-ink → **deepsleep** → wake → repeat. Time zone is **America/Phoenix** (UTC−7, no DST).

Default refresh: **3×/day** Phoenix **06:00 / 12:00 / 18:00** via **DS3231 alarm → GP3**, Pico in **deepsleep** (UPS battery save). Clock board holds the timer; Pico stays off between draws.

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

Wake is **DS3231 Alarm1 → INT → GP3 (R5)** then Pico **deepsleep**. That is the UPS-friendly design: the RTC keeps time/alarm on the coin cell + board power; the Pico is powered down between draws.  
`RTC_ALARM_TEST_MINUTES = 2` arms alarm in 2 minutes (same deepsleep path) — unplug USB and watch panel `as of`. Set to `None` for 06/12/18.

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

## Host setup (Mac) — Python env + pip

You need **Python 3** on the laptop to talk to the Pico (`mpremote`). Firmware on the Pico is MicroPython — that is separate.

```bash
# 1) Confirm Python 3
python3 --version

# 2) From the project root, create a virtualenv
cd /path/to/pico_screen
python3 -m venv .venv

# 3) Activate it (optional for ./run_pico.sh — the script uses .venv/bin directly)
source .venv/bin/activate

# 4) Upgrade pip, then install host tools
python -m pip install --upgrade pip
pip install -r requirements.txt
# (same as: pip install mpremote)
```

Or let the helper script do it: the first `./run_pico.sh …` creates `.venv` and installs `mpremote` if missing.

Quit **Thonny** before using `run_pico.sh` (it locks the serial port).

## Deploy

Quit Thonny first. From the project root:

```bash
./run_pico.sh main           # upload + start dashboard
./run_pico.sh demo_offline   # layout preview (no Wi‑Fi)
./run_pico.sh set_rtc        # set DS3231 from Mac Phoenix time
./run_pico.sh rtc_check      # coin cell / OSF / year-2000
./run_pico.sh rtc_alarm_test # DS3231 INT→GP3 alarm wiring (~90s, no sleep)
./run_pico.sh rtc_wake_test  # arm → deepsleep → wake → draw TEST + date
./run_pico.sh agent_dump     # raw Cursor agent runs
./run_pico.sh wifi_test
./run_pico.sh --upload-only
```

### Updating while it was deepsleeping

Deepsleep ignores USB serial — `./run_pico.sh` will **hang** until the board is awake.

1. Plug in laptop USB.  
2. Press the Pico **RESET** button (or unplug/replug USB).  
3. Wait ~2s, then `./run_pico.sh main`.

With `SLEEP_WHEN_USB = False` (default): while USB is plugged in, after a draw the board **skips deepsleep** and stays at REPL so the next upload works. For desk battery mode: **unplug USB → press RESET** (on-device `main.py` starts and deepsleeps on the schedule).

`main.py` auto-runs on power-up. **3s** delay on non-deepsleep boots so `mpremote` can connect.

## Refresh schedule (`secrets.py`)

| Setting | Effect |
|---------|--------|
| `DRAW_HOURS = (6, 12, 18)` | Phoenix **06:00 / 12:00 / 18:00** |
| `USE_RTC_ALARM = True` | DS3231 Alarm1 → GP3 (R5); Pico **deepsleep** between draws |
| `RTC_ALARM_TEST_MINUTES = None` | Production. Set `3` to test alarm wake every 3 min |
| `SLEEP_MODE = "deep"` | `machine.deepsleep` until RTC INT |
| `SLEEP_WHEN_USB = False` | Skip deepsleep while laptop USB is plugged in |
| `AGENT_PROMPT_ON_REFRESH` | POST status template each draw (3×/day) |

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
