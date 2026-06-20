@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
set "SCANNED=0"
set "VALID=0"
set "UPGRADED=0"
set "SKIPPED=0"
set "FAILED=0"

echo.
echo ========================================
echo  pgconnect venv upgrader
echo  Scan root: %ROOT%
echo ========================================
echo.

cd /d "%ROOT%"

for /d /r "%ROOT%" %%V in (venv) do (
    call :ShouldSkip "%%V"
    if not errorlevel 1 (
        set /a SCANNED+=1
        call :ProcessVenv "%%V"
    )
)

echo.
echo ========================================
echo  Done
echo  venv folders found : !SCANNED!
echo  valid venvs        : !VALID!
echo  upgraded           : !UPGRADED!
echo  skipped            : !SKIPPED!
echo  failed             : !FAILED!
echo ========================================
echo.

endlocal
exit /b 0

:ShouldSkip
set "CHECK_PATH=%~1"
echo %CHECK_PATH% | findstr /i ".git" >nul && exit /b 1
echo %CHECK_PATH% | findstr /i "__pycache__" >nul && exit /b 1
echo %CHECK_PATH% | findstr /i ".pytest_cache" >nul && exit /b 1
echo %CHECK_PATH% | findstr /i "node_modules" >nul && exit /b 1
exit /b 0

:ProcessVenv
set "VENV_PATH=%~1"
set "PYTHON=%VENV_PATH%\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [SKIP] Not a valid Windows venv ^(missing Scripts\python.exe^): %VENV_PATH%
    set /a SKIPPED+=1
    goto :eof
)

"%PYTHON%" -c "import sys; raise SystemExit(0 if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [SKIP] Folder named venv but Python is not isolated: %VENV_PATH%
    set /a SKIPPED+=1
    goto :eof
)

set /a VALID+=1

"%PYTHON%" -m pip show pgconnect >nul 2>&1
if errorlevel 1 (
    echo [SKIP] pgconnect not installed: %VENV_PATH%
    set /a SKIPPED+=1
    goto :eof
)

for /f "tokens=2" %%I in ('"%PYTHON%" -m pip show pgconnect ^| findstr /b /c:"Version:"') do set "OLD_VERSION=%%I"
echo.
echo [UPGRADE] %VENV_PATH%
echo           current version: !OLD_VERSION!

"%PYTHON%" -m pip install --upgrade --force-reinstall pgconnect
if errorlevel 1 (
    echo [FAIL] Could not upgrade pgconnect in %VENV_PATH%
    set /a FAILED+=1
    goto :eof
)

for /f "tokens=2" %%I in ('"%PYTHON%" -m pip show pgconnect ^| findstr /b /c:"Version:"') do set "NEW_VERSION=%%I"
echo [OK] Upgraded to !NEW_VERSION!
set /a UPGRADED+=1
goto :eof
