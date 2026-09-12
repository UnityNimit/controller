# Project Controller - ViGEmBus Kernel Driver Installer
# Elevates to Administrator and installs the bundled ViGEmBus driver.

$ErrorActionPreference = "Stop"

$localMsi = Join-Path $PSScriptRoot "ViGEmBusSetup_x64.msi"
if (Test-Path $localMsi) {
    $msiPath = $localMsi
} else {
    try {
        $sitePackages = python -c "import site; print(site.getsitepackages()[0])" 2>$null
        $msiPath = Join-Path $sitePackages "vgamepad\win\vigem\install\x64\ViGEmBusSetup_x64.msi"
    } catch {
        $msiPath = ""
    }
}

if (-not (Test-Path $msiPath)) {
    Write-Host "[*] Downloading official ViGEmBus installer..." -ForegroundColor Yellow
    $downloadUrl = "https://github.com/ViGEm/ViGEmBus/releases/download/setup-v1.17.333/ViGEmBusSetup_x64.msi"
    $msiPath = Join-Path $PSScriptRoot "ViGEmBusSetup_x64.msi"
    Invoke-WebRequest -Uri $downloadUrl -OutFile $msiPath
}

Write-Host "[+] Found ViGEmBus Installer: $msiPath" -ForegroundColor Green
Write-Host "[*] Requesting Administrator elevation to install Windows Kernel Driver..." -ForegroundColor Cyan

Start-Process msiexec.exe -ArgumentList "/i `"$msiPath`" /passive /norestart" -Verb RunAs -Wait

Write-Host "[OK] ViGEmBus installation completed! Native virtual Xbox 360 controllers are now active." -ForegroundColor Green
