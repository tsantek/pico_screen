#!/usr/bin/env bash
# Recover Pico: wipe filesystem + reinstall MicroPython.
#
# When to use:
#   Board won't talk to mpremote (always deepsleep / no REPL), or filesystem is junk.
#
# Steps:
#   1) Quit Thonny
#   2) Hold BOOTSEL on the Pico, plug USB (or hold BOOTSEL + press RESET)
#   3) Release BOOTSEL when Finder shows disk "RP2350"
#   4) ./recover_pico.sh
#   5) ./run_pico.sh main

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
CACHE="$ROOT/.firmware_cache"
NUKE="$CACHE/flash_nuke.uf2"
FW="$CACHE/RPI_PICO2_W-20260824-v1.29.0.uf2"
VOL="/Volumes/RP2350"

if [[ ! -f "$NUKE" || ! -f "$FW" ]]; then
  echo "Missing UF2 files in .firmware_cache/"
  echo "  Need: flash_nuke.uf2 and RPI_PICO2_W-*.uf2"
  exit 1
fi

wait_vol() {
  local label="$1" secs="${2:-60}"
  echo "Waiting for $VOL ($label, ${secs}s)..."
  for _ in $(seq 1 "$secs"); do
    if [[ -d "$VOL" ]]; then
      echo "Found $VOL"
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_gone() {
  local secs="${1:-25}"
  for _ in $(seq 1 "$secs"); do
    [[ -d "$VOL" ]] || return 0
    sleep 1
  done
  return 0
}

if ! wait_vol "hold BOOTSEL until RP2350 appears" 90; then
  echo "Timed out. Hold BOOTSEL, plug USB / press RESET, release when RP2350 mounts."
  exit 1
fi

echo "==> flash_nuke.uf2 (wipes on-device files)..."
cp "$NUKE" "$VOL/"
wait_gone 25
echo "    waiting for bootloader to return..."
if ! wait_vol "after nuke" 40; then
  echo "RP2350 did not return. Hold BOOTSEL + RESET, then re-run ./recover_pico.sh"
  exit 1
fi
sleep 2

echo "==> MicroPython $(basename "$FW")..."
cp "$FW" "$VOL/"
wait_gone 25
sleep 2

echo "==> Done. Clean MicroPython is installed."
echo "Next: ./run_pico.sh main"
