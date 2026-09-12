# Pico 2 W + Waveshare 7.5" e-Paper (B) desk dashboard

Pico-only desk dashboard: Wi‑Fi fetch → draw e-ink → sleep → repeat. Time zone is **America/Phoenix** (UTC−7, no DST).

Default refresh: **every 6 hours** at Phoenix **00:00 / 06:00 / 12:00 / 18:00**.

## Hardware

```
UPS (LiPo) → RTC (DS3231 + coin cell) → e-Paper 7.5 B → Pico 2 W
```

Bring-up scripts: [`bringup/`](bringup/).

### Two batteries (different jobs)

| Battery | Role |
|---------|------|
| **Big (UPS LiPo)** | Powers Pico + screen when laptop USB is unplugged. Keep UPS **switch ON** for desk use. |
| **Small (RTC CR2032)** | Keeps **date/time** only when main power is dead. Does **not** run the Pico, refresh the panel, or wake every N hours. |

Wake/refresh is a **software loop** on UPS power (`time.sleep` chunks), not the coin cell. RTC alarm wake (solder **R5** → GP3 on the Waveshare RTC HAT) is possible but **not used** — no soldering required for the current design.

### UPS / unplug

1. Run `./run_pico.sh main` (or power-cycle so on-device `main.py` starts).  
2. Wait for `Next draw target …` / `Sleep …s (time.sleep chunks, USB optional)...`.  
3. Unplug laptop USB. Serial will drop — normal.  
4. Board keeps looping on UPS. Watch panel `as of HH:MM` for the next update.

Optional: leave a wall USB charger in the **UPS** port for always-charged desk use; LiPo then covers outages only.

### Battery life (UPS LiPo, rough)

Most time is idle sleep (Wi‑Fi off). Every 6h: short Wi‑Fi + fetch + e-ink (~1–2 min). Ballpark average draw ~20–40 mA:

| Pack | Estimate |
|------|----------|
| ~1000 mAh | 1–2 days |
| ~2000 mAh | 2–4 days |
| ~3000 mAh+ | ~3–6 days |

Footer `%` / voltage are from the UPS INA219. Track `%` over a day for a real number. Deepsleep + RTC INT wake would last longer; we skip that for reliability without soldering.

## Layout (3 columns)

| Left | Center | Right |
|------|--------|-------|
| Date / greeting, weather (now + next 12h) | Today + tomorrow calendar, last workout | Next workout (parsed agent run) |

Footer: UPS battery % and `as of HH:MM` (Phoenix).

## What you need

1. Wi‑Fi SSID / password  
2. Google Calendar **secret iCal** URL  
3. Cursor API key + agent ID (newest run = **Next**, previous = **Last**)  
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

`rtc_check` only reads the clock; it does **not** refresh the panel. Panel updates only while `main.py` is looping.

## Refresh schedule (`secrets.py`)

| Setting | Effect |
|---------|--------|
| `ENABLE_DEEPSLEEP = True` | Loop: draw → sleep → draw (name is historical; uses chunked `time.sleep`) |
| `REFRESH_HOURS = 6` | Phoenix **00:00 / 06:00 / 12:00 / 18:00** when `TEST_SLEEP_SECONDS=None` |
| `TEST_SLEEP_SECONDS = 300` | Override: every **5 min** (testing; wears e-ink faster) |
| `FORCE_REFRESH = True` | Always redraw each cycle |

Only one sleep mode applies: test seconds **or** `REFRESH_HOURS`. Production default: **6 hours**.

## Time / RTC

- DS3231 stores **Phoenix local** time.  
- Bad/missing coin cell → often `2000-01-01` + **OSF=1** (weather/calendar look wrong until fixed).  
- `main.py` detects that, **NTP-syncs Phoenix**, writes the DS3231.  
- Manual set: `./run_pico.sh set_rtc`  
- Diagnose: `./run_pico.sh rtc_check`  
  - After a fresh sync, OSF can look OK even with a dead cell — unplug **all** power (USB + UPS) for a minute, power back, re-run `rtc_check`. If time is 2000 + OSF again, replace the CR2032.

## Behavior notes

- SoftI2C for RTC (GP20/21) and UPS INA219 (GP6/7 `@ 0x43`).  
- E-ink full refresh flickers ~15–25s — normal. Prefer 6h (or hourly) over 5‑min for panel life.  
- Sleep uses chunked `time.sleep` (not deepsleep/lightsleep): higher power, wakes reliably after USB unplug on UPS.  
- Calendar ICS can be large; use a smaller calendar if memory fails.  
- Workout cards parse agent markdown (RUN / GYM / BIKE / SWIM). Non-ASCII is folded for the 8×8 font.  
- Recovery if stuck: BOOTSEL → flash nuke → reflash MicroPython UF2 → `./run_pico.sh main`. Don’t put the long loop in `boot.py` (blocks REPL).
