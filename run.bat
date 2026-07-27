@echo off
REM Starts the OutboundAI stack: backend (FastAPI), frontend (Vite), and an
REM ngrok tunnel so Twilio can reach the backend. Each runs in its own console
REM window so logs stay separate.

setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "ENV_FILE=%ROOT%backend\.env"

if not exist "%ENV_FILE%" (
    echo ERROR: %ENV_FILE% not found.
    echo Copy backend\.env.example to backend\.env and fill in your credentials first.
    pause
    exit /b 1
)

where ngrok >nul 2>nul
if errorlevel 1 (
    echo ERROR: ngrok is not on PATH. Install it from https://ngrok.com/download
    pause
    exit /b 1
)

REM --- Make sure MongoDB is running (the backend needs it on localhost:27017).
REM     Starting/stopping the service requires admin rights, so this triggers
REM     a one-time UAC prompt only when the service isn't already running. ---
sc query MongoDB | find "RUNNING" >nul
if errorlevel 1 (
    echo Starting MongoDB service - approve the UAC prompt if one appears...
    powershell -NoProfile -Command "Start-Process powershell -ArgumentList '-NoProfile','-Command','Start-Service -Name MongoDB' -Verb RunAs -Wait"
    sc query MongoDB | find "RUNNING" >nul
    if errorlevel 1 (
        echo ERROR: MongoDB service could not be started. Start it manually and re-run this script.
        pause
        exit /b 1
    )
)

REM --- Ngrok tunnel exposing the backend on port 8080 (not 8000 - some
REM     Windows setups leave stuck stale listeners on 8000 that survive
REM     process kills; 8080 sidesteps that entirely).
REM     No reserved static domain is configured, so this is a plain random
REM     free-tier URL - it changes every restart. That's why we sync it into
REM     backend\.env and Twilio automatically below instead of hardcoding it. ---
start "OutboundAI Ngrok" cmd /k "ngrok http 8080"

echo Waiting for ngrok tunnel and syncing BASE_URL + Twilio TwiML App...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\sync-ngrok.ps1"
if errorlevel 1 (
    echo ERROR: Could not sync the ngrok URL. Check the Ngrok window, then re-run this script.
    pause
    exit /b 1
)

REM --- Re-read BASE_URL, now updated by sync-ngrok.ps1, for display below ---
set "BASE_URL="
for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
    if "%%A"=="BASE_URL" set "BASE_URL=%%B"
)

REM --- Backend (FastAPI via uvicorn, inside the venv). Started AFTER the
REM     sync above so it loads the fresh BASE_URL from backend\.env. ---
start "OutboundAI Backend" cmd /k "cd /d "%ROOT%backend" && call "%ROOT%venv\Scripts\activate.bat" && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080"

REM --- Frontend (Vite dev server) ---
start "OutboundAI Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

echo.
echo Backend  : http://localhost:8080
echo Frontend : http://localhost:5173
echo Ngrok    : %BASE_URL%
echo Twilio TwiML App Voice Request URL was auto-updated to:
echo   %BASE_URL%/calls/twiml-app
echo.
