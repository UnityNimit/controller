@echo off
title Controller v1.0.0 - Virtual Gamepad Driver Setup
echo =====================================================================
echo  Controller v1.0.0 - Windows Virtual Gamepad Driver Setup
echo =====================================================================
echo.
echo Installing ViGEmBus driver... Please accept the Windows Administrator prompt.
echo.

set MSI_PATH="%~dp0scripts\ViGEmBusSetup_x64.msi"
if not exist %MSI_PATH% set MSI_PATH="%~dp0ViGEmBusSetup_x64.msi"
if not exist %MSI_PATH% (
    echo Downloading official ViGEmBus installer...
    powershell.exe -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('https://github.com/nefarius/ViGEmBus/releases/download/v1.22.0/ViGEmBusSetup_x64.msi', '%TEMP%\ViGEmBusSetup_x64.msi')"
    set MSI_PATH="%TEMP%\ViGEmBusSetup_x64.msi"
)

powershell.exe -ExecutionPolicy Bypass -Command "Start-Process msiexec.exe -ArgumentList '/i \"%MSI_PATH%\" /passive /norestart' -Verb RunAs -Wait"
echo.
echo [SUCCESS] Gamepad driver installed! You can now launch Controller.exe!
echo.
pause
