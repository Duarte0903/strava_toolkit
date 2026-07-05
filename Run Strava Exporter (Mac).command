#!/bin/bash
# Double-click to launch the exporter on macOS.
# (If macOS blocks it the first time: right-click → Open, or run
#  'chmod +x' on this file in Terminal.)
cd "$(dirname "$0")"
python3 strava_gui.py
