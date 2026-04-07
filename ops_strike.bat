@echo off
color 0B
echo ====================================================
echo 💀 OPS-AGENT: KICH HOAT THE STRIKE PROTOCOL (WINDOWS)
echo ====================================================

:: 1. Tự động xin quyền Administrator để có quyền sát sinh
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo [INFO] Dang yeu cau quyen Administrator...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    del "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
echo ✅ Da cap quyen Administrator. Tien hanh thanh trung!

echo.
echo [1/4] Dang tieu diet Portainer va cac container cu...
docker rm -f portainer >nul 2>&1
docker rm -f alien_nexus_old >nul 2>&1

echo.
echo [2/4] Giai phong cuong cuong cong 8000 va 3000...
powershell -Command "Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess -Force -ErrorAction SilentlyContinue"
powershell -Command "Stop-Process -Id (Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue).OwningProcess -Force -ErrorAction SilentlyContinue"

echo.
echo [3/4] Xoa bo DNA rac cua Docker (Prune)...
docker system prune -f >nul 2>&1

echo.
echo [4/4] Dang khoi dong lai he sinh thai Alien-Nexus...
docker-compose up -d --build --force-recreate

echo.
echo ====================================================
echo 🌌 THE NEXUS IS ALIVE. HE THONG DA DUOC GIAI CUU!
echo ====================================================
pause
