#!/usr/bin/env bash
# Upload firmware to Pico AND run a script on the device.
#
# Usage:
#   ./run_pico.sh                 # upload + run wifi_test.py
#   ./run_pico.sh wifi_test       # same
#   ./run_pico.sh main            # upload + run main.py
#   ./run_pico.sh demo_offline    # upload + run demo_offline.py
#   ./run_pico.sh --upload-only   # copy files only
#
# Close Thonny first (it locks the serial port).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
MP="$ROOT/.venv/bin/mpremote"

if [[ ! -x "$MP" ]]; then
  echo "Creating venv + installing mpremote..."
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -q mpremote
fi

PORT="${MPREMOTE_PORT:-}"
if [[ -z "$PORT" ]]; then
  if [[ -e /dev/cu.usbmodem11401 ]]; then
    PORT=/dev/cu.usbmodem11401
  elif ls /dev/cu.usbmodem* >/dev/null 2>&1; then
    # Prefer a MicroPython-looking modem if present
    PORT="$(ls /dev/cu.usbmodem* | head -1)"
  else
    PORT=auto
  fi
fi

UPLOAD_ONLY=0
TARGET="wifi_test"
for arg in "$@"; do
  case "$arg" in
    --upload-only) UPLOAD_ONLY=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) TARGET="${arg%.py}" ;;
  esac
done

SCRIPT="$ROOT/firmware/${TARGET}.py"
if [[ ! -f "$SCRIPT" ]]; then
  echo "Missing: $SCRIPT"
  exit 1
fi

echo "==> Port: $PORT"
echo "==> Waking board (reset) before upload..."
# Soft reset first — needed if a prior script is running. If the Pico is in
# deepsleep it will not answer until you plug USB + press RESET (or wait for wake).
"$MP" connect "$PORT" reset >/dev/null 2>&1 || true
sleep 2

echo "==> Uploading firmware/ ..."
cd "$ROOT/firmware"

# For set_rtc: inject Mac's America/Phoenix "now" onto the Pico
if [[ "$TARGET" == "set_rtc" ]]; then
  python3 - <<'PY'
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/Phoenix"))
except Exception:
    # Fallback if zoneinfo missing: assume Mac is already on PHX
    now = datetime.now()
open("rtc_now.py", "w").write(
    "YEAR=%d\nMONTH=%d\nDAY=%d\nHOUR=%d\nMINUTE=%d\nSECOND=%d\nWDAY_PY=%d\n"
    % (now.year, now.month, now.day, now.hour, now.minute, now.second, now.weekday())
)
print("Injected Phoenix now:", now.isoformat())
PY
fi

if ! "$MP" connect "$PORT" fs cp -r . :; then
  echo ""
  echo "Upload failed / hung."
  echo "If the board was in deepsleep: plug USB, press the Pico RESET button, wait 2s, retry."
  echo "Also quit Thonny completely (it locks the serial port)."
  exit 1
fi
echo "==> Upload OK"

# Don't leave generated inject file as the only source of truth in git
rm -f "$ROOT/firmware/rtc_now.py"

if [[ "$UPLOAD_ONLY" -eq 1 ]]; then
  echo "==> Upload only — done"
  exit 0
fi

echo "==> Running ${TARGET}.py on Pico (Ctrl+C to stop)..."
echo "---------------------------------------------------"
"$MP" connect "$PORT" reset >/dev/null 2>&1 || true
sleep 1
"$MP" connect "$PORT" run "$SCRIPT"
echo "---------------------------------------------------"
echo "==> Finished"
