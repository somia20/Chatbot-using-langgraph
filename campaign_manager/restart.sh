#!/bin/bash
# Find the PID of the running Python application
PID=$(pgrep -f "python chatapp.py")
if [ -n "$PID" ]; then
    echo "Stopping existing application (PID: $PID)"
    kill $PID
    sleep 2  # Give the application time to shut down gracefully

    # Check if the process is still running and force kill if necessary
    if ps -p $PID > /dev/null; then
        echo "Application did not shut down gracefully. Force killing..."
        kill -9 $PID
    fi
else
    echo "No existing application found running"
fi
echo "Starting application..."
nohup python chatapp.py >> app.log 2>&1 &
echo "Application restarted. PID: $!"
echo "Logs are being appended to app.log"
