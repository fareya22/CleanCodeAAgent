@echo off
echo Starting CleanCodeAgent Server with Logging...
cd /d "%~dp0\src\localize_agent"

REM Activate virtual environment
call "%~dp0..\.venv\Scripts\activate.bat"

REM Run server and save output to log file
python server.py 2>&1 | tee server_logs.txt

pause
