@echo off
rem ============================================================================
rem  SteamFix - double-click de sua loi Steam Store / Community bi chan.
rem
rem  Cach dung tren may moi:
rem    1. Tai file nay tu GitHub (Raw -> Save link as...)
rem    2. Double-click
rem    3. Bam Yes o hop thoai UAC
rem
rem  Script se tu: xin quyen admin -> tai ban moi nhat -> giai nen vao
rem  %LOCALAPPDATA%\SteamFix -> chay "steamfix fix" -> bao ket qua.
rem
rem  Co the truyen lenh khac:  SteamFix.cmd check   |   SteamFix.cmd revert
rem
rem  File nay co tinh chi chua ky tu ASCII.
rem ============================================================================
setlocal EnableExtensions
chcp 65001 >nul 2>nul
title SteamFix

set "BASE=%LOCALAPPDATA%\SteamFix"
set "EXE=%BASE%\steamfix\steamfix.exe"
set "URL=https://github.com/BaoTaoBao/steamfix/releases/latest/download/steamfix-windows-x64.zip"
rem Cho phep doi nguon tai (chu yeu de test): dat bien moi truong STEAMFIX_URL
if defined STEAMFIX_URL set "URL=%STEAMFIX_URL%"
set "SHAURL=%URL%.sha256"

set "ARGS=%*"
if not defined ARGS set "ARGS=fix"
if "%~1"=="" (set "DO_PAUSE=1") else (set "DO_PAUSE=")

rem ---------------------------------------------------------------- quyen admin
set "ISADMIN="
fltmc >nul 2>&1 && set "ISADMIN=1"
if not defined ISADMIN (
    net session >nul 2>&1 && set "ISADMIN=1"
)

if not defined ISADMIN (
    echo.
    echo   SteamFix can quyen Administrator de sua file hosts.
    echo   Dang mo cua so moi - hay bam YES o hop thoai UAC...
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Start-Process -FilePath '%~f0' -Verb RunAs -ErrorAction Stop } catch { exit 1 }"
    if errorlevel 1 (
        echo   [X] Khong mo duoc voi quyen Administrator.
        echo       Hay chuot phai file nay, chon "Run as administrator".
        echo.
        pause
        exit /b 2
    )
    exit /b 0
)

echo.
echo   ==========================================================
echo     SteamFix - sua loi Steam Store / Community bi chan
echo   ==========================================================
echo.

rem ---------------------------------------------------------------- tai ve
if exist "%EXE%" goto run

echo   Chua co SteamFix tren may - dang tai ban moi nhat...
if not exist "%BASE%" mkdir "%BASE%" >nul 2>&1
set "ZIP=%TEMP%\steamfix-%RANDOM%%RANDOM%.zip"

call :download "%URL%" "%ZIP%"
if errorlevel 1 goto dlfail
if not exist "%ZIP%" goto dlfail

call :verify "%ZIP%"
if errorlevel 2 goto badhash

echo   Dang giai nen...
call :extract "%ZIP%" "%BASE%"
if errorlevel 1 goto dlfail
if exist "%ZIP%" del /f /q "%ZIP%" >nul 2>&1
if exist "%ZIP%.sha256" del /f /q "%ZIP%.sha256" >nul 2>&1
if not exist "%EXE%" goto dlfail

:run
echo   Dang chay: steamfix %ARGS%
echo.
"%EXE%" %ARGS%
set "CODE=%ERRORLEVEL%"
echo.

if "%CODE%"=="0" echo   [OK] Xong. Neu Steam dang mo, hay thoat ra va mo lai.
if "%CODE%"=="2" echo   [!]  Can quyen Administrator - hay bam Yes o hop thoai UAC.
if "%CODE%"=="3" echo   [!]  Khong tim duoc IP nao dung duoc - mang co the chan sau hon, thu VPN.
if "%CODE%"=="4" echo   [!]  Da sua hosts nhung kiem tra van loi - thu lai hoac dung VPN.
if not "%CODE%"=="0" if not "%CODE%"=="2" if not "%CODE%"=="3" if not "%CODE%"=="4" echo   [!]  Ket thuc voi ma %CODE%.

echo.
echo   Go cau hinh Steam:  "%EXE%" revert
echo.

if defined DO_PAUSE pause
exit /b %CODE%

rem ---------------------------------------------------------------- loi tai ve
:badhash
echo.
echo   [X] File tai ve bi loi (SHA-256 khong khop). Da dung de an toan.
echo       Hay chay lai, hoac tai thu cong:
echo       https://github.com/BaoTaoBao/steamfix/releases/latest
echo.
if exist "%ZIP%" del /f /q "%ZIP%" >nul 2>&1
if exist "%ZIP%.sha256" del /f /q "%ZIP%.sha256" >nul 2>&1
pause
exit /b 1

:dlfail
echo.
echo   [X] Khong tai hoac giai nen duoc SteamFix.
echo       Kiem tra ket noi mang ROI THU LAI, hoac tai thu cong:
echo       https://github.com/BaoTaoBao/steamfix/releases/latest
echo.
if exist "%ZIP%" del /f /q "%ZIP%" >nul 2>&1
pause
exit /b 1

rem ================================================================ ham phu
:download
rem %1 = url, %2 = file dich ; tra 0 neu OK
if exist "%~2" del /f /q "%~2" >nul 2>&1
set "TRY=0"
:dl_try
set /a TRY+=1
where curl.exe >nul 2>&1
if not errorlevel 1 (
    curl.exe -fsSL --connect-timeout 15 --max-time 300 -o "%~2" "%~1"
    if not errorlevel 1 if exist "%~2" exit /b 0
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%~1','%~2') } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 if exist "%~2" exit /b 0
)
if %TRY% LSS 3 (
    timeout /t 1 >nul
    goto dl_try
)
exit /b 1

:verify
rem %1 = file zip ; tra 0 = OK, 2 = checksum sai, 1 = khong co checksum (bo qua)
if not exist "%~1" exit /b 1
call :download "%SHAURL%" "%~1.sha256" >nul 2>&1
if not exist "%~1.sha256" (
    echo   [!]  Khong tai duoc checksum - bo qua buoc kiem tra.
    exit /b 1
)
set "EXPECTED="
for /f "usebackq tokens=1" %%H in ("%~1.sha256") do if not defined EXPECTED set "EXPECTED=%%H"
set "ACTUAL="
rem certutil co san tren moi ban Windows, khong phu thuoc PowerShell module
for /f "skip=1 tokens=* delims=" %%H in ('certutil -hashfile "%~1" SHA256 2^>nul') do (
    if not defined ACTUAL set "ACTUAL=%%H"
)
if defined ACTUAL set "ACTUAL=%ACTUAL: =%"
if not defined ACTUAL (
    rem .NET thuan (khong can module PowerShell)
    for /f "usebackq delims=" %%H in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$h=[Security.Cryptography.SHA256]::Create();$s=[IO.File]::OpenRead('%~1');try{$b=$h.ComputeHash($s)}finally{$s.Dispose()};($b|%%{$_.ToString('x2')}) -join ''" 2^>nul`) do set "ACTUAL=%%H"
)
if not defined ACTUAL (
    echo   [!]  Khong tinh duoc SHA-256 - bo qua buoc kiem tra.
    exit /b 1
)
if /i "%ACTUAL%"=="%EXPECTED%" (
    echo   [OK] Da kiem tra SHA-256 %EXPECTED:~0,12%...
    exit /b 0
)
echo   [X] SHA-256 KHONG KHOP - file tai ve bi loi.
exit /b 2

:extract
rem %1 = zip, %2 = thu muc dich
where tar.exe >nul 2>&1
if not errorlevel 1 (
    tar.exe -xf "%~1" -C "%~2"
    if not errorlevel 1 exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Add-Type -AssemblyName System.IO.Compression.FileSystem; [IO.Compression.ZipFile]::ExtractToDirectory('%~1','%~2'); exit 0 } catch { exit 1 }" 2>nul
exit /b %ERRORLEVEL%
