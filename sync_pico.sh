#!/usr/bin/env bash
# Alias — prefer ./run_pico.sh (uploads AND runs on the Pico).
exec "$(cd "$(dirname "$0")" && pwd)/run_pico.sh" "$@"
