#!/usr/bin/env bash
# Copy firmware/ to the Pico, then run a script.
#
# Usage:
#   ./run_pico.sh main              # copy firmware + run main.py
#   ./run_pico.sh --upload-only     # copy firmware only
#   ./run_pico.sh wifi_test
#   MPREMOTE_PORT=/dev/cu.usbmodemXXXX ./run_pico.sh main
#
# If deepsleep (no REPL): plug USB into Pico → press RESET → run this within a few seconds.
# Quit Thonny first (locks the port).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
MP="$ROOT/.venv/bin/mpremote"

if [[ ! -x "$MP" ]]; then
  echo "Creating venv + installing mpremote..."
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -q mpremote
fi

soft_reset() {
  local port="$1"
  if command -v gtimeout >/dev/null 2>&1; then
    gtimeout 3 "$MP" connect "$port" reset >/dev/null 2>&1 || true
  elif command -v timeout >/dev/null 2>&1; then
    timeout 3 "$MP" connect "$port" reset >/dev/null 2>&1 || true
  else
    "$MP" connect "$port" reset >/dev/null 2>&1 &
    local rpid=$!
    sleep 3
    kill "$rpid" 2>/dev/null || true
    wait "$rpid" 2>/dev/null || true
  fi
}

probe_port() {
  local port="$1"
  if command -v gtimeout >/dev/null 2>&1; then
    gtimeout 4 "$MP" connect "$port" eval "print('pico-ok')" 2>/dev/null | grep -q pico-ok
  elif command -v timeout >/dev/null 2>&1; then
    timeout 4 "$MP" connect "$port" eval "print('pico-ok')" 2>/dev/null | grep -q pico-ok
  else
    "$MP" connect "$port" eval "print('pico-ok')" >/tmp/pico_probe_out 2>/tmp/pico_probe_err &
    local rpid=$!
    sleep 4
    kill "$rpid" 2>/dev/null || true
    wait "$rpid" 2>/dev/null || true
    grep -q pico-ok /tmp/pico_probe_out 2>/dev/null
  fi
}

pick_port() {
  if [[ -n "${MPREMOTE_PORT:-}" ]]; then
    echo "$MPREMOTE_PORT"
    return
  fi

  # Optional project hint (port numbers can change after replug)
  if [[ -f "$ROOT/.pico_port" ]]; then
    local hint
    hint="$(tr -d '[:space:]' < "$ROOT/.pico_port")"
    if [[ -n "$hint" && -e "$hint" ]]; then
      echo "    hint $hint ..." >&2
      if probe_port "$hint"; then
        echo "$hint"
        return
      fi
    fi
  fi

  local candidates=()
  while IFS= read -r p; do
    [[ -n "$p" ]] && candidates+=("$p")
  done < <(ls /dev/cu.usbmodem* 2>/dev/null | sort | grep -E 'usbmodem[0-9]{4,}' || true)

  while IFS= read -r p; do
    [[ -n "$p" ]] || continue
    local seen=0
    for c in "${candidates[@]:-}"; do
      [[ "$c" == "$p" ]] && seen=1 && break
    done
    [[ $seen -eq 0 ]] && candidates+=("$p")
  done < <(ls /dev/cu.usbmodem* 2>/dev/null | sort || true)

  if [[ ${#candidates[@]} -eq 0 ]]; then
    echo "auto"
    return
  fi

  echo "==> Probing ports: ${candidates[*]}" >&2
  for p in "${candidates[@]}"; do
    echo "    trying $p ..." >&2
    if probe_port "$p"; then
      echo "$p"
      return
    fi
  done
  echo "" >&2
  echo "No MicroPython REPL on any usbmodem port." >&2
  echo "  • If you see a disk named RP2350: you are in BOOTSEL mode — flash UF2, or release BOOTSEL and RESET." >&2
  echo "  • If asleep: USB into Pico → press RESET → retry within a few seconds." >&2
  return 1
}

UPLOAD_ONLY=0
TARGET="wifi_test"
for arg in "$@"; do
  case "$arg" in
    --upload-only) UPLOAD_ONLY=1 ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *) TARGET="${arg%.py}" ;;
  esac
done

SCRIPT="$ROOT/firmware/${TARGET}.py"
if [[ "$UPLOAD_ONLY" -eq 0 && ! -f "$SCRIPT" ]]; then
  echo "Missing: $SCRIPT"
  exit 1
fi

PORT="$(pick_port)" || {
  exit 1
}
echo "==> Port: $PORT"

if [[ "$PORT" != "auto" && ! -e "$PORT" ]]; then
  echo "Port missing. Press Pico RESET, wait 2s, retry."
  exit 1
fi

echo "==> Soft-reset (3s timeout)..."
soft_reset "$PORT"
sleep 1

if [[ -z "${MPREMOTE_PORT:-}" ]]; then
  PORT="$(pick_port)" || exit 1
  echo "==> Port after reset: $PORT"
fi

echo "==> Copying firmware/ → Pico ..."
cd "$ROOT/firmware"

if [[ "$TARGET" == "set_rtc" ]]; then
  python3 - <<'PY'
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/Phoenix"))
except Exception:
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
  echo "Firmware copy failed (no raw REPL)."
  echo "  Quit Thonny → USB into Pico → press RESET → retry ./run_pico.sh $TARGET"
  exit 1
fi
echo "==> Firmware copy OK"
rm -f "$ROOT/firmware/rtc_now.py"

if [[ "$UPLOAD_ONLY" -eq 1 ]]; then
  echo "==> Upload only — done"
  exit 0
fi

echo "==> Running ${TARGET}.py (Ctrl+C to stop)..."
echo "---------------------------------------------------"
soft_reset "$PORT"
sleep 1
"$MP" connect "$PORT" run "$SCRIPT"
echo "---------------------------------------------------"
echo "==> Finished"
