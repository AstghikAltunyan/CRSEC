#!/bin/bash
# Watches simulation log and sends "run 500" (or N) to the simulation terminal when the current run completes.
# Usage: ./simulation_auto_run_500.sh [path-to-log] [steps]
#        ./simulation_auto_run_500.sh "" 500
#
# Target terminal (pick one):
#   A) Terminal.app: run the simulation in Terminal.app; set window title to "Local".
#   B) Cursor: set TARGET=cursor and click the simulation terminal tab ("Local") once before leaving.
#      Then run this script in another tab (e.g. Local(5)). When it fires, it will activate Cursor
#      and send keys to the focused tab—so you must leave the "Local" tab focused (click it, then
#      use a second machine or a scheduled job to run this script, or run from Terminal.app).
#   Default is Terminal.app window named "Local".

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="${1:-$SCRIPT_DIR/simulation_output.txt}"
STEPS="${2:-500}"
TARGET="${TARGET:-terminal}"

if [[ ! -f "$LOG" ]]; then
  echo "Log file not found: $LOG"
  exit 1
fi

echo "Watching: $LOG"
echo "When 'Completed simulation run' appears, will send 'run $STEPS' in 2s (target: $TARGET)."
echo "---"

tail -n 0 -f "$LOG" | while read -r line; do
  if [[ "$line" == *"Completed simulation run"* ]]; then
    echo "[$(date '+%H:%M:%S')] Run completed. Sending 'run $STEPS' in 2s..."
    sleep 2
    if [[ "$TARGET" == "cursor" ]]; then
      osascript -e 'tell application "Cursor" to activate' \
        -e 'delay 0.8' \
        -e 'tell application "System Events" to tell process "Cursor" to keystroke "run '"$STEPS"'"' \
        -e 'delay 0.1' \
        -e 'tell application "System Events" to tell process "Cursor" to key code 36'
    else
      osascript <<APPLESCRIPT
tell application "Terminal" to activate
delay 0.5
tell application "System Events"
  tell process "Terminal"
    try
      set simWin to first window whose name contains "Local" and name does not contain "Local(5)"
    on error
      set simWin to first window whose name contains "Local"
    end try
    set index of simWin to 1
    set frontmost to true
    delay 0.3
    keystroke "run $STEPS"
    key code 36
  end tell
end tell
APPLESCRIPT
    fi
    echo "[$(date '+%H:%M:%S')] Sent 'run $STEPS'."
    exit 0
  fi
done
