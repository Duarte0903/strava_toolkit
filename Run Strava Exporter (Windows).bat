@echo off
REM Double-click to launch the exporter on Windows.
cd /d "%~dp0"
python strava_gui.py
if errorlevel 1 pause
