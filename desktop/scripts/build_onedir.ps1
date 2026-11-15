$ErrorActionPreference = "Stop"

$desktopRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $desktopRoot ".venv\Scripts\python.exe"
$specPath = Join-Path $desktopRoot "packaging\PostGuard.spec"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Desktop virtual environment was not found: $pythonPath"
}

& $pythonPath -m PyInstaller `
    --clean `
    --noconfirm `
    --distpath (Join-Path $desktopRoot "dist") `
    --workpath (Join-Path $desktopRoot "build") `
    $specPath

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

$exePath = Join-Path $desktopRoot "dist\PostGuard\PostGuard.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Build completed but PostGuard.exe was not found."
}

Write-Host "PostGuard onedir build is ready: $exePath"
