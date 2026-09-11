# Project Controller - ViGEmBus Kernel Driver Installer
# Elevates to Administrator and installs the bundled ViGEmBus driver.

$ErrorActionPreference = "Stop"

# Find python site-packages bundled ViGEm MSI
$pythonPath = (Get-Command python).Source
$sitePackages = python -c "import site; print(site.getsitepackages()[0])"
$msiPath = Join-Path $sitePackages "vgamepad\win\vigem\install\x64\ViGEmBusSetup_x64.msi"

if (-not (Test-Path $msiPath)) {
    Write-Host "[!] Could not locate bundled MSI at: $msiPath" -ForegroundColor Red
    Write-Host "[*] Downloading official ViGEmBus v1.17.333 installer..." -ForegroundColor Yellow
    $downloadUrl = "https://github.com/ViGEm/ViGEmBus/releases/download/setup-v1.17.333/ViGEmBusSetup_x64.msi"
    $msiPath = Join-Path $PSScriptRoot "ViGEmBusSetup_x64.msi"
    Invoke-WebRequest -Uri $downloadUrl -OutFile $msiPath
}

Write-Host "[+] Found ViGEmBus Installer: $msiPath" -ForegroundColor Green
Write-Host "[*] Requesting Administrator elevation to install Windows Kernel Driver..." -ForegroundColor Cyan

Start-Process msiexec.exe -ArgumentList "/i `"$msiPath`" /passive /norestart" -Verb RunAs -Wait

Write-Host "[OK] ViGEmBus installation completed! Native virtual Xbox 360 controllers are now active." -ForegroundColor Green
