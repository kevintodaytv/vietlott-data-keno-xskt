@echo off
color 0B
chcp 65001 >nul
title SNIPER-X HUB — APEX LAUNCH SEQUENCE

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   SNIPER-X HUB v6.0 — APEX IGNITION     ║
echo  ║   Ghost Scraper + Frontend Launch        ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  [*] Giai phong cac port cu...

:: Giai phong port 8888 (backend) va 3333 (frontend)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8888" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3333" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo  [OK] Cac port da duoc giai phong.
echo.
echo  [*] Kiem tra Python va uvicorn...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [!] Python chua duoc cai dat hoac chua co trong PATH!
    echo  [!] Hay cai Python 3.11+ tai python.org
    pause
    exit /b 1
)

echo  [OK] Python da san sang.
echo.
echo  [*] Khoi dong THE CORE (Backend) tai port 8888...
echo      Thu muc: core-backend
echo      Lenh: uvicorn main:app --port 8888 --reload
echo.

:: Mo Backend trong cua so terminal rieng (dung run_server.py de patch EventLoop dung)
start "SNIPER-X CORE [PORT 8888]" cmd /k "cd /d %~dp0core-backend && color 0A && echo [CORE] BACKEND DANG KHOI DONG... && python run_server.py"

:: Doi 3 giay cho backend khoi dong
echo  [*] Cho backend khoi dong (3 giay)...
timeout /t 3 /nobreak >nul

:: Kiem tra backend da song chua
curl -s http://localhost:8888/api/health >nul 2>&1
if errorlevel 1 (
    echo  [!] Backend chua phan hoi sau 3 giay - co the dang load module...
    echo  [!] Vui long kiem tra cua so "SNIPER-X CORE" de xem log.
) else (
    echo  [OK] Backend da ONLINE tai http://localhost:8888
)

echo.
echo  [*] Khoi dong DASHBOARD (Frontend) tai port 3333...
echo      Thu muc: nexus-frontend
echo      Lenh: npm run dev
echo.

:: Mo Frontend trong cua so terminal rieng
start "SNIPER-X DASHBOARD [PORT 3333]" cmd /k "cd /d %~dp0nexus-frontend && color 0B && echo [DASHBOARD] FRONTEND DANG KHOI DONG... && npm run dev"

echo.
echo  [*] Doi 5 giay roi mo trinh duyet...
timeout /t 5 /nobreak >nul

:: Mo trinh duyet tu dong
start "" "http://localhost:3333"

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   HE THONG DA DUOC KHOI DONG!            ║
echo  ║                                          ║
echo  ║   Frontend:  http://localhost:3333       ║
echo  ║   Backend:   http://localhost:8888       ║
echo  ║   Health:    /api/health                 ║
echo  ║                                          ║
echo  ║   >> NHAN "IGNITE PREDICTION" TREN UI   ║
echo  ╚══════════════════════════════════════════╝
echo.
echo  [!] De tat he thong: Dong ca 2 cua so Terminal
echo.
pause
