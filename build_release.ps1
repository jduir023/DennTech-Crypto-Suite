$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$compiledRoot = Join-Path (Split-Path $PSScriptRoot -Parent) "Compiled_Apps\DennTech-Crypto-Suite"
$standaloneRoot = Join-Path $compiledRoot "Crypto_Suite_Standalone"
$stamp = Get-Date -Format "yyyyMMdd"
$eliteVenvPython = "C:\Users\Jduir\Elite_Bot\.venv\Scripts\python.exe"
if (Test-Path $eliteVenvPython) {
    $pythonExe = $eliteVenvPython
} else {
    $pythonExe = "python"
}
$env:PYTHONPATH = $null

function Assert-LastExitCode {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

Write-Host "[1/5] Using Python: $pythonExe"
Write-Host "[2/5] Ensuring dependencies..."
& $pythonExe -m pip install -r requirements.txt pyinstaller --disable-pip-version-check
Assert-LastExitCode "dependency install"

Write-Host "[3/5] Cleaning old build artifacts..."
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path $compiledRoot) { Remove-Item -Recurse -Force $compiledRoot }
New-Item -ItemType Directory -Force -Path $compiledRoot | Out-Null
New-Item -ItemType Directory -Force -Path $standaloneRoot | Out-Null

Write-Host "[4/5] Building no-console executable..."
& $pythonExe -m PyInstaller `
  --noconfirm `
  --clean `
  --distpath $compiledRoot `
  --workpath (Join-Path $PSScriptRoot "build\pyi") `
  .\DennTechCryptoSuite.spec
Assert-LastExitCode "PyInstaller build"

# Stage Crypto_Suite_Standalone portable folder
Copy-Item -Force (Join-Path $compiledRoot "DennTechCryptoSuite.exe") (Join-Path $standaloneRoot "DennTechCryptoSuite.exe")
if (Test-Path (Join-Path $PSScriptRoot "data")) {
    Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "data") (Join-Path $standaloneRoot "data")
}
foreach ($a in @("suite_icon.ico","suite_logo.png","crypto-suite-manual.html","icon.ico","logo.png")) {
    $src = Join-Path $PSScriptRoot $a
    if (Test-Path $src) { Copy-Item -Force $src (Join-Path $standaloneRoot $a) }
}

Write-Host "[5/5] Build complete."
Write-Host "Executable: $compiledRoot\DennTechCryptoSuite.exe"
Write-Host "Standalone: $standaloneRoot"
