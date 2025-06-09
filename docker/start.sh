#!/bin/bash
# filepath: /Users/Maxi/Desktop/Golf/docker/start.sh

# Start virtual display in background
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &

# Wait a moment for X server to start
sleep 2

# Start the Python application
exec python app.py