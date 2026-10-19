<#
.SYNOPSIS
    Unregisters the Cuttle Windows 11 sparse package and COM shell extension.
.DESCRIPTION
    Per task card P4-04:
    - Removes sparse package identity via Remove-AppxPackage.
    - Unregisters COM server in HKCU via regsvr32 /u.
#>

[CmdletBinding()]
param()

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$DllPath = Join-Path $ProjectRoot "cuttle\platform\windows\shell_extension\cuttle_shell.dll"

Write-Host "=== Cuttle Windows 11 Sparse Package Unregistration ===" -ForegroundColor Cyan

# 1. Remove AppX Package
$pkg = Get-AppxPackage -Name "Cuttle.Converter" -ErrorAction SilentlyContinue
if ($pkg) {
    Write-Host "Removing AppX package $($pkg.PackageFullName)..."
    Remove-AppxPackage -Package $pkg.PackageFullName -ErrorAction SilentlyContinue
    Write-Host "[OK] Sparse package removed." -ForegroundColor Green
} else {
    Write-Host "No registered Cuttle.Converter package found."
}

# 2. Unregister InProc COM Server
if (Test-Path $DllPath) {
    Write-Host "Unregistering COM InProcServer32..."
    Start-Process -FilePath "regsvr32.exe" -ArgumentList "/u", "/s", "`"$DllPath`"" -Wait -NoNewWindow
    Write-Host "[OK] COM server unregistered." -ForegroundColor Green
}
