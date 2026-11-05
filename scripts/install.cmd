@echo off
rem ============================================================
rem  Cai SteamFix vao PATH cua user (khong can quyen admin).
rem  Sau khi chay, mo cmd moi va go:  steamfix fix -r
rem
rem  Chay:
rem    curl -fsSL -o "%TEMP%\steamfix-install.cmd" https://raw.githubusercontent.com/BaoTaoBao/steamfix/main/scripts/install.cmd
rem    "%TEMP%\steamfix-install.cmd"
rem ============================================================
setlocal EnableExtensions
chcp 65001 >nul 2>nul

set "BASE=%LOCALAPPDATA%\SteamFix"
set "EXE=%BASE%\steamfix\steamfix.exe"
set "BIN=%LOCALAPPDATA%\Microsoft\WindowsApps"
set "LAUNCHER=%BIN%\steamfix.cmd"
set "URL=https://github.com/BaoTaoBao/steamfix/releases/latest/download/steamfix-windows-x64.zip"

echo.
echo   Cai SteamFix vao: %BASE%
echo.

if not exist "%BASE%" mkdir "%BASE%" >nul 2>&1
set "ZIP=%TEMP%\steamfix-install-%RANDOM%.zip"
rem Luon tai ban moi nhat khi chay installer
if exist "%BASE%\steamfix" rmdir /s /q "%BASE%\steamfix" >nul 2>&1

where curl.exe >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%' -UseBasicParsing" >nul 2>&1
) else (
    curl.exe -fsSL -o "%ZIP%" "%URL%"
)
if errorlevel 1 goto dlfail
where tar.exe >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%BASE%' -Force" >nul 2>&1
) else (
    tar.exe -xf "%ZIP%" -C "%BASE%"
)
if errorlevel 1 goto dlfail
del "%ZIP%" >nul 2>&1
if not exist "%EXE%" goto dlfail

:havefiles
if not exist "%BIN%" mkdir "%BIN%" >nul 2>&1
if not exist "%BIN%" (
    echo   [X] Khong tim thay thu muc WindowsApps cua user.
    echo       Them thu cong thu muc sau vao PATH: %BASE%\steamfix
    exit /b 1
)

rem Tao launcher 1 dong trong WindowsApps (thu muc nay da co trong PATH)
> "%LAUNCHER%" echo @echo off
>> "%LAUNCHER%" echo "%EXE%" %%*

if not exist "%LAUNCHER%" (
    echo   [X] Khong ghi duoc launcher vao %BIN%
    exit /b 1
)

echo   [OK] Da cai dat.
echo.
echo   Mo cmd MOI roi chay:
echo       steamfix check
echo       steamfix fix -r
echo.
echo   Go cai dat: xoa 2 thu muc sau
echo       %BASE%
echo       %LAUNCHER%
echo.
exit /b 0

:dlfail
echo.
echo   [X] Khong tai hoac giai nen duoc SteamFix.
echo       Kiem tra mang, hoac tai thu cong: %URL%
echo.
exit /b 1
