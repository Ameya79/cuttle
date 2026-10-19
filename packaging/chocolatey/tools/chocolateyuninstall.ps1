$ErrorActionPreference = 'Stop'

$packageName = 'cuttle'
$installerType = 'exe'
$silentArgs = '/VERYSILENT /NORESTART'

# Path to Inno Setup uninstaller
$uninstallerPath = "$env:LOCALAPPDATA\Programs\Cuttle\unins000.exe"

if (Test-Path $uninstallerPath) {
    Uninstall-ChocolateyPackage -PackageName $packageName -FileType $installerType -SilentArgs $silentArgs -File $uninstallerPath
}
