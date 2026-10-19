<#
.SYNOPSIS
    Registers the Cuttle Windows 11 sparse package and COM shell extension.
.DESCRIPTION
    Per task card P4-04:
    - Registers cuttle_shell.dll in HKCU.
    - Registers packaging/AppxManifest.xml using Add-AppxPackage -Register.
#>

[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ManifestPath = Join-Path $ProjectRoot "packaging\AppxManifest.xml"
$DllPath = Join-Path $ProjectRoot "cuttle\platform\windows\shell_extension\cuttle_shell.dll"

Write-Host "=== Cuttle Windows 11 Sparse Package Registration ===" -ForegroundColor Cyan

# 1. Verify OS Build
$OSBuild = [System.Environment]::OSVersion.Version.Build
if ($OSBuild -lt 22000) {
    Write-Warning "Windows 11 (build 22000+) is required for top-level IExplorerCommand sparse package. (Current build: $OSBuild)"
    Write-Host "Falling back to Windows 10 HKCU cascading menus."
    Exit 0
}

# 2. Verify DLL exists
if (-not (Test-Path $DllPath)) {
    Write-Host "Building cuttle_shell.dll..."
    python (Join-Path $ProjectRoot "scripts\build_shell_extension.py")
    if (-not (Test-Path $DllPath)) {
        Write-Error "cuttle_shell.dll not found at $DllPath"
    }
}

# 3. Register InProc COM Server in HKCU
Write-Host "Registering COM InProcServer32..."
Start-Process -FilePath "regsvr32.exe" -ArgumentList "/s", "`"$DllPath`"" -Wait -NoNewWindow

# 4. Register Sparse Package Identity
Write-Host "Registering Sparse Package Manifest ($ManifestPath)..."
try {
    Add-AppxPackage -Register $ManifestPath -AllowUnsigned -ErrorAction Stop
    Write-Host "[OK] Cuttle sparse package registered successfully!" -ForegroundColor Green
    Write-Host "Right-click any file in Windows 11 File Explorer to see 'Convert with Cuttle' directly on the top-level menu."
} catch {
    Write-Warning "Direct registration with -AllowUnsigned reported: $($_.Exception.Message)"
    Write-Host "Ensure 'Developer Mode' is enabled in Windows Settings -> System -> For developers." -ForegroundColor Yellow
}
