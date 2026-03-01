@echo off
REM CleanCodeAgent Backend Server Launcher
REM Run this file to start the analysis server

echo ========================================
echo   CleanCodeAgent Backend Server
echo ========================================
echo.

cd src\localize_agent
echo Starting server at http://localhost:5000
echo Press Ctrl+C to stop the server
echo.

python server.py

pause
