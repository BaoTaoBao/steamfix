@echo off
rem ============================================================
rem  SteamFix - chay khong can cai dat (chi Windows 10/11 x64)
rem
rem  Cach dung tu cmd:
rem    curl -fsSL -o "%TEMP%\steamfix.cmd" https://raw.githubusercontent.com/BaoTaoBao/steamfix/main/scripts/steamfix.cmd
rem    "%TEMP%\steamfix.cmd" fix -r
rem
rem  hoac sau khi cai bang install.cmd thi chi can:  steamfix fix -r
rem
rem  Script nay tu tai ban moi nhat tu GitHub Releases (lan dau),
rem  luu vao %LOCALAPPDATA%\SteamFix roi chay.
rem ============================================================
setlocal EnableExtensions
chcp 65001 >nul 2>nul

set "BASE=%LOCALAPPDATA%\SteamFix"
set "EXE=%BASE%\steamfix\steamfix.exe"
set "URL=https://github.com/BaoTaoBao/steamfix/releases/latest/download/steamfix-windows-x64.zip"

if exist "%EXE%" goto run

echo.
echo   Chua co SteamFix tren may - dang tai ban moi nhat...
echo.

if not exist "%BASE%" mkdir "%BASE%" >nul 2>&1
set "ZIP=%TEMP%\steamfix-dl-%RANDOM%.zip"

where curl.exe >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%' -UseBasicParsing" >nul 2>&1
) else (
    curl.exe -fsSL -o "%ZIP%" "%URL%"
)
if errorlevel 1 goto dlfail
if not exist "%ZIP%" goto dlfail

where tar.exe >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%BASE%' -Force" >nul 2>&1
) else (
    tar.exe -xf "%ZIP%" -C "%BASE%"
)
if errorlevel 1 goto dlfail
del "%ZIP%" >nul 2>&1

if not exist "%EXE%" goto dlfail
echo   Da cai vao: %BASE%
echo.

:run
if "%~1"=="" (
    "%EXE%"
) else (
    "%EXE%" %*
)
exit /b %ERRORLEVEL%

:dlfail
echo.
echo   [X] Khong tai hoac giai nen duoc SteamFix.
echo       Kiem tra mang, hoac tai thu cong:
echo       %URL%
echo.
exit /b 1
