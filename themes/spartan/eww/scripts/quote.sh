#!/usr/bin/env bash
set -euo pipefail
file="${XDG_CONFIG_HOME:-$HOME/.config}/eww/quotes"
if [[ -s "$file" ]]; then
  mapfile -t lines < "$file"
  printf '%s\n' "${lines[RANDOM % ${#lines[@]}]}"
  exit 0
fi
printf '\n'
