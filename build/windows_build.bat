@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

rem Windows setup script for Base Laser App
rem - Creates a virtual environment (.venv)
rem - Installs Python dependencies
rem - Generates run scripts for GUI and MQTT modes
rem - Packages executables with PyInstaller (GUI and MQTT)
rem - Creates Desktop shortcuts for easy launch

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_DIR=%%~fI"
pushd "%REPO_DIR%"

echo ==================================================
echo   Base Laser App - Windows Setup
echo ==================================================

rem Detect Python 3 (prefer the Windows launcher "py")
set "PYEXE="
where py >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=*" %%v in ('py -3 -V 2^>^&1') do (
        set "PYEXE=py -3"
    )
) else (
    where python >nul 2>&1 && set "PYEXE=python"
)

if not defined PYEXE (
    echo [ERROR] Python 3 not found.
    echo Please install Python 3.9+ from https://www.python.org/downloads/
    echo and ensure "Add Python to PATH" is checked during installation.
    exit /b 1
)

echo.
echo Using Python: %PYEXE%
echo Creating virtual environment .venv ...
%PYEXE% -m venv .venv
if errorlevel 1 goto ERR

echo Activating virtual environment ...
call ".venv\Scripts\activate"
if errorlevel 1 goto ERR

echo Upgrading pip, setuptools, wheel ...
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto ERR

echo Installing project requirements ...
pip install -r requirements.txt
if errorlevel 1 goto REQFALLBACK

:POST_REQ
echo Ensuring optional Windows Bluetooth dependency (pywin32) ...
pip install pywin32 --only-binary=:all: >nul 2>&1 || echo Skipping optional pywin32

echo Creating launcher scripts ...
(
  echo @echo off
  echo call "%%~dp0.venv\Scripts\activate"
  echo python main.py --mode gui
) > run_gui.bat

(
  echo @echo off
  echo call "%%~dp0.venv\Scripts\activate"
  echo python main.py --mode mqtt
) > run_mqtt.bat

echo.
echo Installing PyInstaller for packaging ...
pip install pyinstaller==6.10.0
if errorlevel 1 goto ERR

echo.
echo Building Windows executables with PyInstaller ...
rem GUI executable (windowed, no console)
pyinstaller --noconsole --onefile --clean --name BaseLaserGUI bluetooth_gui.py
if errorlevel 1 goto ERR

rem MQTT executable (console), shortcut will pass --mode mqtt
pyinstaller --console --onefile --clean --name BaseLaserMQTT main.py
if errorlevel 1 goto ERR

if not exist "dist\BaseLaserGUI.exe" (
    echo [ERROR] Build failed: dist\BaseLaserGUI.exe not found
    goto ERR
)
if not exist "dist\BaseLaserMQTT.exe" (
    echo [ERROR] Build failed: dist\BaseLaserMQTT.exe not found
    goto ERR
)

echo.
echo Creating Desktop shortcuts ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "^
  $desktop = [Environment]::GetFolderPath('Desktop'); ^
  $ws = New-Object -ComObject WScript.Shell; ^
  $gui = $ws.CreateShortcut((Join-Path $desktop 'Base Laser GUI.lnk')); ^
  $gui.TargetPath = (Resolve-Path 'dist\\BaseLaserGUI.exe'); ^
  $gui.WorkingDirectory = (Resolve-Path '.'); ^
  $gui.Description = 'Base Laser App - GUI'; ^
  $gui.Save(); ^
  $mqtt = $ws.CreateShortcut((Join-Path $desktop 'Base Laser MQTT.lnk')); ^
  $mqtt.TargetPath = (Resolve-Path 'dist\\BaseLaserMQTT.exe'); ^
  $mqtt.Arguments = '--mode mqtt'; ^
  $mqtt.WorkingDirectory = (Resolve-Path '.'); ^
  $mqtt.Description = 'Base Laser App - MQTT mode'; ^
  $mqtt.Save();"

echo.
echo Setup completed successfully.
echo - Virtual env:   .venv
echo - Run scripts:   run_gui.bat / run_mqtt.bat
echo - Binaries:      dist\BaseLaserGUI.exe / dist\BaseLaserMQTT.exe
echo - Shortcuts:     created on Desktop (Base Laser GUI / Base Laser MQTT)

popd
exit /b 0

:REQFALLBACK
echo.
echo [WARNING] Some dependencies failed to install from requirements.txt.
echo Attempting individual installations to provide clearer error messages ...
for /f "usebackq delims=" %%L in ("requirements.txt") do (
    set "LINE=%%L"
    rem Skip comments and empty lines
    if not "!LINE!"=="" if not "!LINE:~0,1!"=="#" (
        echo Installing !LINE! ...
        pip install "!LINE!" || echo   ^> Failed: !LINE!
    )
)
goto POST_REQ

:ERR
echo.
echo [ERROR] Setup failed. See messages above for details.
echo If the failure is related to PyBluez on Windows, you may need to install:
echo - Microsoft Visual C^^+^^+ Build Tools (with C^^+^^+ workload)
echo After installing, re-run this script.
exit /b 1

