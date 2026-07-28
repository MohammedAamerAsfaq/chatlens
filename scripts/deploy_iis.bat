@echo off
setlocal

set "PYTHON_EXE=C:\inetpub\wwwroot\chatlens\venv\Scripts\python.exe"
set "PROJECT_DIR=C:\inetpub\wwwroot\chatlens\chatlens"
set "FRONTEND_DIR=C:\inetpub\wwwroot\chatlens\chatlens\frontend"
set "WORKER_DIR=C:\inetpub\wwwroot\chatlens\chatlens\whatsapp-worker"
set "ENV_FILE=C:\inetpub\wwwroot\chatlens\chatlens\.env"

set "RUN_PIP_INSTALL=1"
set "RUN_NPM_INSTALL=1"
set "RESTART_IIS=0"

rem WhatsApp worker controls are intentionally disabled until the worker is
rem installed as a Windows Service. For manual worker operation, leave both as 0.
set "RUN_WORKER_NPM_INSTALL=0"
set "RESTART_WORKER_SERVICE=0"
set "WORKER_SERVICE_NAME=ChatLensWorker"

cd /d "%PROJECT_DIR%"
if errorlevel 1 goto :failed

echo ==========================================
echo ChatLens IIS deployment runner
echo ==========================================
echo Python : %PYTHON_EXE%
echo Env    : %ENV_FILE%
echo Project: %PROJECT_DIR%
echo Frontend: %FRONTEND_DIR%
echo Worker : %WORKER_DIR%
echo.

if not exist "%PYTHON_EXE%" (
  echo Python executable was not found.
  goto :failed
)

if not exist "%ENV_FILE%" (
  echo Env file was not found.
  goto :failed
)

set "CHATLENS_ENV_FILE=%ENV_FILE%"

if "%RUN_PIP_INSTALL%"=="1" (
  echo [1/8] Installing Python requirements...
  "%PYTHON_EXE%" -m pip install -r requirements.txt
  if errorlevel 1 goto :failed
) else (
  echo [1/8] Skipping Python requirements.
)

echo.
echo [2/8] Running Django system check...
"%PYTHON_EXE%" manage.py check
if errorlevel 1 goto :failed

echo.
echo [3/8] Running database migrations...
"%PYTHON_EXE%" manage.py migrate
if errorlevel 1 goto :failed

echo.
echo [4/8] Building frontend...
cd /d "%FRONTEND_DIR%"
if errorlevel 1 goto :failed

if "%RUN_NPM_INSTALL%"=="1" (
  call npm install
  if errorlevel 1 goto :failed
) else (
  echo Skipping npm install.
)

call npm run build
if errorlevel 1 goto :failed

echo.
echo [5/8] WhatsApp worker maintenance...
if "%RUN_WORKER_NPM_INSTALL%"=="1" (
  cd /d "%WORKER_DIR%"
  if errorlevel 1 goto :failed
  call npm install
  if errorlevel 1 goto :failed
) else (
  echo Worker npm install skipped.
)

if "%RESTART_WORKER_SERVICE%"=="1" (
  echo Restarting worker service "%WORKER_SERVICE_NAME%"...
  net stop "%WORKER_SERVICE_NAME%"
  rem net stop returns a non-zero exit code when the service is already stopped.
  net start "%WORKER_SERVICE_NAME%"
  if errorlevel 1 goto :failed
) else (
  echo Worker service restart skipped.
)

echo.
echo [6/8] Collecting static files...
cd /d "%PROJECT_DIR%"
if errorlevel 1 goto :failed
"%PYTHON_EXE%" manage.py collectstatic --noinput
if errorlevel 1 goto :failed

echo.
echo [7/8] Checking deployment after static collection...
"%PYTHON_EXE%" manage.py check
if errorlevel 1 goto :failed

echo.
if "%RESTART_IIS%"=="1" (
  echo [8/8] Restarting IIS...
  iisreset
  if errorlevel 1 goto :failed
) else (
  echo [8/8] IIS restart skipped. Run iisreset manually if needed.
)

echo.
echo ==========================================
echo Completed successfully.
echo ==========================================
goto :end

:failed
echo.
echo ==========================================
echo FAILED. Review the output above.
echo ==========================================

:end
echo.
pause
endlocal
