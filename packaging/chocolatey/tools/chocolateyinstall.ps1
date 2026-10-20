$ErrorActionPreference = 'Stop'

$packageName = 'cuttle'
$installerType = 'exe'
$url = 'https://github.com/Ameya79/cuttle/releases/download/v1.0.1/Cuttle-Setup-x64.exe'
$silentArgs = '/VERYSILENT /NORESTART /SP-'

$packageArgs = @{
  packageName   = $packageName
  fileType      = $installerType
  url           = $url
  silentArgs    = $silentArgs
  validExitCodes= @(0)
}

Install-ChocolateyPackage @packageArgs
