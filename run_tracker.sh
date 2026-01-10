#!/bin/bash
#
# Ranger Finance Raise Tracker - Auto Runner
# Runs analysis every 30 minutes until sale ends
#

SCRIPT_DIR="$HOME/ranger-tracker"
LOG_FILE="$SCRIPT_DIR/tracker_output.log"
INTERVAL=1800  # 30 minutes in seconds

echo "=========================================="
echo "Ranger Finance Tracker Starting"
echo "Running every 30 minutes"
echo "Log file: $LOG_FILE"
echo "Press Ctrl+C to stop"
echo "=========================================="

run_count=0

while true; do
    run_count=$((run_count + 1))
    
    echo ""
    echo ">>> Run #$run_count at $(date -u '+%Y-%m-%d %H:%M:%S') UTC"
    echo ""
    
    # Run the analysis and tee to both console and log
    python3 "$SCRIPT_DIR/ranger_analysis.py" 2>&1 | tee -a "$LOG_FILE"
    
    # Check if script indicated sale ended
    if [ $? -eq 1 ]; then
        echo "Sale has ended. Stopping tracker."
        break
    fi
    
    echo ""
    echo ">>> Next run in 30 minutes ($(date -u -d '+30 minutes' '+%H:%M:%S' 2>/dev/null || date -u -v+30M '+%H:%M:%S') UTC)"
    echo ">>> Press Ctrl+C to stop"
    
    sleep $INTERVAL
done

echo ""
echo "Tracker finished. Full log saved to: $LOG_FILE"
