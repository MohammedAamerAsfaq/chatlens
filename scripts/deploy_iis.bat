@echo off
setlocal

set "PYTHON_EXE=C:\inetpub\wwwroot\chatlens\venv\Scripts\python.exe"
set "PROJECT_DIR=C:\inetpub\wwwroot\chatlens\chatlens"
set "FRONTEND_DIR=C:\inetpub\wwwroot\chatlens\chatlens\frontend"
set "ENV_FILE=C:\inetpub\wwwroot\chatlens\chatlens\.env"

set "RUN_PIP_INSTALL=1"
set "RUN_NPM_INSTALL=1"
set "RESTART_IIS=0"

cd /d "%PROJECT_DIR%"
if errorlevel 1 goto :failed

echo ==========================================
echo ChatLens IIS deployment runner
echo ==========================================
echo Python : %PYTHON_EXE%
echo Env    : %ENV_FILE%
echo Project: %PROJECT_DIR%
echo Frontend: %FRONTEND_DIR%
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
  echo [1/7] Installing Python requirements...
  "%PYTHON_EXE%" -m pip install -r requirements.txt
  if errorlevel 1 goto :failed
) else (
  echo [1/7] Skipping Python requirements.
)

echo.
echo [2/7] Running Django system check...
"%PYTHON_EXE%" manage.py check
if errorlevel 1 goto :failed

echo.
echo [3/7] Running database migrations...
"%PYTHON_EXE%" manage.py migrate
if errorlevel 1 goto :failed

echo.
echo [4/7] Building frontend...
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
echo [5/7] Collecting static files...
cd /d "%PROJECT_DIR%"
if errorlevel 1 goto :failed
"%PYTHON_EXE%" manage.py collectstatic --noinput
if errorlevel 1 goto :failed

echo.
echo [6/7] Checking deployment after static collection...
"%PYTHON_EXE%" manage.py check
if errorlevel 1 goto :failed

echo.
if "%RESTART_IIS%"=="1" (
  echo [7/7] Restarting IIS...
  iisreset
  if errorlevel 1 goto :failed
) else (
  echo [7/7] IIS restart skipped. Run iisreset manually if needed.
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
