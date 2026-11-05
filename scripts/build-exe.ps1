# Build steamfix.exe (Windows) - target machine does NOT need Python.
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/build-exe.ps1
#
# Output:
#   dist-exe\steamfix\steamfix.exe        (+ _internal folder)
#   dist-exe\steamfix-<version>-windows-x64.zip
#
# NOTE: keep this file ASCII-only so Windows PowerShell 5.1 parses it
# correctly regardless of the file encoding.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (& python -c "import sys; sys.path.insert(0,'src'); import steamfix; print(steamfix.__version__)").Trim()
if (-not $version) { throw 'Cannot read version from steamfix.__version__' }
Write-Host "Packaging SteamFix $version ..." -ForegroundColor Cyan

& python -m pip install --upgrade --quiet pyinstaller
& python -m PyInstaller --onedir --console --name steamfix --paths src `
    --distpath dist-exe --workpath build-exe --specpath build-exe --noconfirm `
    packaging/steamfix_exe.py

$zip = Join-Path $root "dist-exe\steamfix-$version-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $root 'dist-exe\steamfix') -DestinationPath $zip -Force

Write-Host "Done:" -ForegroundColor Green
Write-Host "  $root\dist-exe\steamfix\steamfix.exe"
Write-Host "  $zip"
