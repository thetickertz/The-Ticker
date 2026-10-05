@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py -3 scripts\ticker.py) || (python scripts\ticker.py)
if errorlevel 1 pause
