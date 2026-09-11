@echo off
REM Project Controller - One-Click ViGEmBus Kernel Driver Installer
echo =====================================================================
echo  Project Controller - Installing ViGEmBus Kernel Driver
echo =====================================================================
powershell.exe -ExecutionPolicy Bypass -File "%~dp0install_driver.ps1"
pause
