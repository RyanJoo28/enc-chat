@echo off
setlocal
cd /d "%~dp0"

echo Loading Docker images from enc-chat-release.tar...
docker load -i "enc-chat-release.tar"
if errorlevel 1 goto :error

echo Starting services with docker compose...
docker compose up -d
if errorlevel 1 goto :error

echo =======================================
echo Services started in background.
echo Logs: docker compose logs -f
echo URL: https://localhost:23456
echo =======================================
pause
exit /b 0

:error
echo.
echo Startup failed. Check Docker Desktop and try again.
pause
exit /b 1
