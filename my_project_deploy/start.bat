@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "MODE=%~1"
if not defined MODE set "MODE=online"

if /i not "%MODE%"=="online" if /i not "%MODE%"=="offline" goto :usage

set "BACKEND_IMAGE_OVERRIDE="
set "FRONTEND_IMAGE_OVERRIDE="

if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="BACKEND_IMAGE" set "BACKEND_IMAGE_OVERRIDE=%%B"
    if /i "%%A"=="FRONTEND_IMAGE" set "FRONTEND_IMAGE_OVERRIDE=%%B"
  )

  if defined BACKEND_IMAGE_OVERRIDE (
    echo Detected custom backend image from .env: !BACKEND_IMAGE_OVERRIDE!
  )
  if defined FRONTEND_IMAGE_OVERRIDE (
    echo Detected custom frontend image from .env: !FRONTEND_IMAGE_OVERRIDE!
  )
)

if /i "%MODE%"=="offline" (
  if defined BACKEND_IMAGE_OVERRIDE echo Detected custom image overrides in .env; offline mode will use bundled local image tags.
  if not defined BACKEND_IMAGE_OVERRIDE if defined FRONTEND_IMAGE_OVERRIDE echo Detected custom image overrides in .env; offline mode will use bundled local image tags.

  if not exist "enc-chat-release.tar" (
    echo.
    echo Offline startup failed. enc-chat-release.tar was not found.
    pause
    exit /b 1
  )

  echo Loading offline images from enc-chat-release.tar...
  docker load -i "enc-chat-release.tar"
  if errorlevel 1 goto :error

  set "BACKEND_IMAGE=enc-chat-docker-backend:latest"
  set "FRONTEND_IMAGE=enc-chat-docker-frontend:latest"
  echo Using offline backend image: !BACKEND_IMAGE!
  echo Using offline frontend image: !FRONTEND_IMAGE!
) else (
  echo Pulling images from GHCR...
  docker compose pull
  if errorlevel 1 goto :error
)

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

:usage
echo.
echo Usage: start.bat [offline]
echo Default mode pulls images from GHCR. Offline mode loads enc-chat-release.tar.
pause
exit /b 1

:error
echo.
echo Startup failed. Check Docker Desktop and try again.
pause
exit /b 1
