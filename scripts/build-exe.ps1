# Build steamfix.exe (Windows) - target machine does NOT need Python.
#
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/build-exe.ps1
#
# Output:
#   dist-exe\steamfix\steamfix.exe        (+ _internal folder)
#   dist-exe\steamfix-windows-x64.zip     (stable name used by /releases/latest/download)
#   dist-exe\steamfix-windows-x64.zip.sha256
#
# NOTE: keep this file ASCII-only so Windows PowerShell 5.1 parses it
# correctly regardless of the file encoding.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# ---------------------------------------------------------------- tim Python 3
# "python" co the la App Execution Alias cua Microsoft Store (khong chay that),
# nen phai kiem tra tung ung vien truoc khi dung.
$candidates = New-Object System.Collections.Generic.List[object]
foreach ($name in @('python', 'python3')) {
    Get-Command $name -All -ErrorAction SilentlyContinue | ForEach-Object {
        $candidates.Add(@{ Exe = $_.Source; Prefix = @() })
    }
}
$pyLauncher = Get-Command 'py' -ErrorAction SilentlyContinue
if ($pyLauncher) { $candidates.Add(@{ Exe = $pyLauncher.Source; Prefix = @('-3') }) }
foreach ($glob in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python'),
        'C:\Program Files\Python*',
        'C:\Python*'
    )) {
    Get-ChildItem -Path $glob -Filter 'python.exe' -Recurse -Depth 2 -ErrorAction SilentlyContinue |
        ForEach-Object { $candidates.Add(@{ Exe = $_.FullName; Prefix = @() }) }
}

$pyExe = $null
$pyPrefix = @()
foreach ($candidate in $candidates) {
    $probeArgs = @($candidate.Prefix) + @('-c', 'import sys; print(sys.version_info[0])')
    try {
        $out = & $candidate.Exe @probeArgs 2>$null
        if ($LASTEXITCODE -eq 0 -and ("$out").Trim() -eq '3') {
            $pyExe = $candidate.Exe
            $pyPrefix = @($candidate.Prefix)
            break
        }
    } catch { }
}
if (-not $pyExe) { throw 'Khong tim thay Python 3 (thu cai lai hoac them vao PATH).' }
Write-Host "Python: $pyExe $($pyPrefix -join ' ')" -ForegroundColor DarkGray

$version = (& $pyExe @pyPrefix -c "import sys; sys.path.insert(0,'src'); import steamfix; print(steamfix.__version__)").Trim()
if (-not $version) { throw 'Cannot read version from steamfix.__version__' }
Write-Host "Packaging SteamFix $version ..." -ForegroundColor Cyan

& $pyExe @pyPrefix -m pip install --upgrade --quiet pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'pip install pyinstaller failed' }

& $pyExe @pyPrefix -m PyInstaller --onedir --console --name steamfix --paths src `
    --distpath dist-exe --workpath build-exe --specpath build-exe --noconfirm `
    packaging/steamfix_exe.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }

$folder = Join-Path $root 'dist-exe\steamfix'
$zip = Join-Path $root 'dist-exe\steamfix-windows-x64.zip'
$sha = "$zip.sha256"
foreach ($p in @($zip, $sha)) { if (Test-Path $p) { Remove-Item $p -Force } }

Compress-Archive -Path $folder -DestinationPath $zip -Force
$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLower()
Set-Content -Path $sha -Value "$hash  steamfix-windows-x64.zip`n" -Encoding ASCII -NoNewline

Write-Host "Done:" -ForegroundColor Green
Write-Host "  $folder\steamfix.exe"
Write-Host "  $zip"
Write-Host "  $sha  ($hash)"
