# ============================================================================
#  SteamFix - bootstrap script (Windows 10/11 x64)
#
#  Chay bang 1 dong trong PowerShell hoac cmd:
#
#    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/BaoTaoBao/steamfix/main/install.ps1 | iex"
#
#  Script se:
#    1. Tai ban moi nhat tu GitHub Releases (co kiem tra SHA-256)
#    2. Giai nen vao %LOCALAPPDATA%\SteamFix
#    3. Chay: steamfix fix   (kiem tra + sua loi Steam)
#
#  Tuy chon: dat bien moi truong STEAMFIX_ARGS de doi lenh, vi du:
#    $env:STEAMFIX_ARGS = 'check';  irm https://raw.githubusercontent.com/BaoTaoBao/steamfix/main/install.ps1 | iex
#
#  File nay co tinh chi chua ky tu ASCII de chay dung tren moi code page.
# ============================================================================

$ErrorActionPreference = 'Stop'

$ZipUrl = 'https://github.com/BaoTaoBao/steamfix/releases/latest/download/steamfix-windows-x64.zip'
$ShaUrl = 'https://github.com/BaoTaoBao/steamfix/releases/latest/download/steamfix-windows-x64.zip.sha256'
$Base   = Join-Path $env:LOCALAPPDATA 'SteamFix'
$Exe    = Join-Path $Base 'steamfix\steamfix.exe'

function Write-Step([string]$Message) { Write-Host "  $Message" -ForegroundColor Gray }
function Write-Ok([string]$Message)   { Write-Host "  [OK] $Message" -ForegroundColor Green }
function Write-Warn([string]$Message) { Write-Host "  [!]  $Message" -ForegroundColor Yellow }
function Write-Err([string]$Message)  { Write-Host "  [X]  $Message" -ForegroundColor Red }

function Get-RemoteFile([string]$Url, [string]$OutFile) {
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
                & curl.exe -fsSL --retry 2 --connect-timeout 15 -o $OutFile $Url
                if ($LASTEXITCODE -eq 0 -and (Test-Path $OutFile)) { return }
            } else {
                Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
                if (Test-Path $OutFile) { return }
            }
        } catch {
            Start-Sleep -Milliseconds (400 * $attempt)
        }
    }
    throw "Khong tai duoc: $Url"
}

function Expand-Zip([string]$ZipFile, [string]$Destination) {
    if (Get-Command tar.exe -ErrorAction SilentlyContinue) {
        & tar.exe -xf $ZipFile -C $Destination
        if ($LASTEXITCODE -eq 0) { return }
    }
    Expand-Archive -LiteralPath $ZipFile -DestinationPath $Destination -Force
}

try {
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

    Write-Host ''
    Write-Host '  SteamFix - sua loi Steam Store / Community bi chan' -ForegroundColor Cyan
    Write-Host '  --------------------------------------------------' -ForegroundColor DarkGray

    if (-not (Test-Path $Exe)) {
        Write-Step 'Chua co SteamFix tren may - dang tai ban moi nhat...'
        if (-not (Test-Path $Base)) { New-Item -ItemType Directory -Path $Base -Force | Out-Null }

        $zip = Join-Path $env:TEMP ('steamfix-' + [guid]::NewGuid().ToString('N') + '.zip')
        try {
            Get-RemoteFile $ZipUrl $zip
            $size = (Get-Item $zip).Length
            if ($size -lt 1MB) { throw "File tai ve khong hop le ($size bytes)" }

            # Kiem tra SHA-256 (neu asset checksum ton tai); sai thi dung han.
            try {
                $response = Invoke-WebRequest -Uri $ShaUrl -UseBasicParsing -TimeoutSec 20
                $content = $response.Content
                # PS 5.1 co the tra ve byte[] cho file text -> phai giai ma.
                if ($content -is [byte[]]) { $content = [Text.Encoding]::UTF8.GetString($content) }
                $expected = ([string]$content -split '\s+')[0].ToLower()
                if ($expected -match '^[0-9a-f]{64}$') {
                    $actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLower()
                    if ($actual -ne $expected) { throw 'SHA-256 khong khop - file tai ve bi loi, thu lai sau.' }
                    Write-Ok "Da kiem tra SHA-256 ($($expected.Substring(0,12))...)"
                } else {
                    Write-Warn 'File checksum khong hop le - bo qua buoc kiem tra.'
                }
            } catch {
                if ($_.Exception.Message -match 'SHA-256') { throw }
                Write-Warn 'Khong tai duoc file checksum - bo qua buoc kiem tra.'
            }

            Write-Step 'Dang giai nen...'
            Expand-Zip $zip $Base
        } finally {
            if (Test-Path $zip) { Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue }
        }
    } else {
        Write-Ok "Da co san: $Base"
    }

    if (-not (Test-Path $Exe)) { throw "Khong tim thay $Exe sau khi giai nen." }

    $argv = @('fix')
    if ($env:STEAMFIX_ARGS) {
        $argv = @($env:STEAMFIX_ARGS -split '\s+' | Where-Object { $_ })
    }

    Write-Host ''
    & $Exe @argv
    $code = $LASTEXITCODE
    Write-Host ''

    switch ($code) {
        0       { Write-Ok  'Xong. Neu Steam dang mo, hay thoat va mo lai de ap dung.' }
        2       { Write-Warn 'Can quyen Administrator - hay bam Yes o hop thoai UAC roi chay lai.' }
        3       { Write-Warn 'Khong tim duoc IP nao dung duoc. Mang cua ban co the chan sau hon - thu VPN.' }
        4       { Write-Warn 'Da ghi hosts nhung kiem tra van loi. Thu lai, hoac dung VPN.' }
        default { Write-Warn "SteamFix ket thuc voi ma $code." }
    }
    Write-Host '  Go cau hinh:  ' -NoNewline -ForegroundColor DarkGray
    Write-Host 'steamfix revert' -ForegroundColor Gray
    Write-Host ''
}
catch {
    Write-Host ''
    Write-Err $_.Exception.Message
    Write-Host '  Tai thu cong: https://github.com/BaoTaoBao/steamfix/releases/latest' -ForegroundColor DarkGray
    Write-Host ''
}
