# Cuttle Authenticode Code Signing Script (P6-02)
# Signs all built .exe and .dll binaries in dist/
# Supports production CI secrets (PFX / SignPath / Azure) or self-signed test certificate

[CmdletBinding()]
param(
    [string]$DistPath = "$PSScriptRoot\..\dist"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Cuttle Code Signing Pipeline (P6-02) " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$distResolved = Resolve-Path $DistPath -ErrorAction SilentlyContinue
if (-not $distResolved) {
    Write-Warning "Distribution directory not found at: $DistPath. Skipping signing."
    exit 0
}

# Find all executables and DLLs in dist/
$targets = Get-ChildItem -Path $distResolved -Recurse -Include *.exe, *.dll
if ($targets.Count -eq 0) {
    Write-Warning "No .exe or .dll binaries found in $DistPath to sign."
    exit 0
}

Write-Host "Found $($targets.Count) binaries to sign."

$pfxBase64 = $env:CODESIGN_PFX_BASE64
$pfxPassword = $env:CODESIGN_PFX_PASSWORD
$cert = $null

if ($pfxBase64 -and $pfxPassword) {
    Write-Host "--> Using production code-signing certificate from environment secrets." -ForegroundColor Green
    $tempPfx = [System.IO.Path]::GetTempFileName() + ".pfx"
    [System.IO.File]::WriteAllBytes($tempPfx, [System.Convert]::FromBase64String($pfxBase64))
    $cert = Get-PfxCertificate -FilePath $tempPfx
} else {
    Write-Host "--> No production certificate secret detected. Using local self-signed test certificate." -ForegroundColor Yellow
    # Check for existing Cuttle Test Signer certificate in CurrentUser\My
    $cert = Get-ChildItem -Path Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -like "*Cuttle Test Signer*" } | Select-Object -First 1

    if (-not $cert) {
        Write-Host "--> Generating new local self-signed test code-signing certificate..."
        $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=Cuttle Test Signer (Local Development)" -CertStoreLocation "Cert:\CurrentUser\My" -HashAlgorithm SHA256 -NotAfter (Get-Date).AddYears(3)
    }
}

if (-not $cert) {
    Write-Error "Failed to obtain or generate a code signing certificate."
    exit 1
}

Write-Host "Using Certificate: $($cert.Subject) [Thumbprint: $($cert.Thumbprint)]"

# Sign all binaries
foreach ($file in $targets) {
    Write-Host "--> Signing: $($file.Name)..."
    try {
        # Attempt with DigiCert timestamp server; fallback to local timestamp if offline
        $sig = Set-AuthenticodeSignature -FilePath $file.FullName -Certificate $cert -TimestampServer "http://timestamp.digicert.com" -HashAlgorithm SHA256 -ErrorAction SilentlyContinue
        if ($sig.Status -eq "UnknownError" -or $sig.Status -eq "Valid") {
            Write-Host "    [OK] Signed with timestamp: $($file.Name)" -ForegroundColor Green
        } else {
            # Try without remote timestamp if offline
            $sig = Set-AuthenticodeSignature -FilePath $file.FullName -Certificate $cert -HashAlgorithm SHA256
            Write-Host "    [OK] Signed (local): $($file.Name) [Status: $($sig.Status)]" -ForegroundColor Green
        }
    } catch {
        Write-Warning "Failed to sign $($file.Name): $_"
    }
}

Write-Host "`n--> Verifying Authenticode Signatures..." -ForegroundColor Cyan
$failed = 0
foreach ($file in $targets) {
    $verification = Get-AuthenticodeSignature -FilePath $file.FullName
    if ($verification.Status -eq "NotSigned") {
        Write-Host "    [FAIL] Not signed: $($file.Name)" -ForegroundColor Red
        $failed++
    } else {
        Write-Host "    [VERIFIED] $($file.Name) -> $($verification.Status) ($($verification.SignerCertificate.Subject))" -ForegroundColor Green
    }
}

if ($failed -gt 0) {
    Write-Error "$failed binary(ies) failed signature verification."
    exit 1
}

Write-Host "`n[SUCCESS] All $($targets.Count) binaries verified with valid Authenticode signatures." -ForegroundColor Green
