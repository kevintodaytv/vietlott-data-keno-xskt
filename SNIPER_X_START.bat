@echo off
color 0B
chcp 65001 > nul
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║        SNIPER-X HUB :: ONE-CLICK IGNITION v2.0          ║
echo  ║        Khoi dong toan bo he thong tu dong                ║
echo  ║        Backend :8888 | Frontend :3333 | Scraper Keno     ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

:: ─────────────────────────────────────────────────────
:: BƯỚC 1: GIẢI PHÓNG CỔNG
:: ─────────────────────────────────────────────────────
echo [1/4] Dang giai phong cong 3333 va 8888...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3333 " 2^>nul') do (
    taskkill /PID %%a /F > nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8888 " 2^>nul') do (
    taskkill /PID %%a /F > nul 2>&1
)
echo [OK] Cong da san sang!

:: ─────────────────────────────────────────────────────
:: BƯỚC 2: KHỞI ĐỘNG BACKEND (cửa sổ riêng)
:: ─────────────────────────────────────────────────────
echo.
echo [2/4] Dang kich hoat BO NAO (Backend :8888)...
start "SNIPER-X CORE [8888]" cmd /k "color 0A && chcp 65001 > nul && cd /d "%~dp0core-backend" && echo [CORE] Khoi dong uvicorn tren cong 8888... && uvicorn main:app --host 0.0.0.0 --port 8888 --reload"

echo [..] Cho Backend khoi dong (5 giay)...
timeout /t 5 /nobreak > nul

:: ─────────────────────────────────────────────────────
:: BƯỚC 3: KHỞI ĐỘNG PHANTOM KENO SCRAPER (cửa sổ riêng)
:: ─────────────────────────────────────────────────────
echo.
echo [3/4] Dang kich hoat PHANTOM KENO SCRAPER...
start "PHANTOM KENO [SCRAPER]" cmd /k "color 03 && chcp 65001 > nul && cd /d "%~dp0core-backend" && echo [PHANTOM] Phantom Keno Scraper - Source: xoso.com.vn && python agents/phantom_keno_scraper.py"

echo [OK] Phantom Keno Scraper dang chay!
timeout /t 3 /nobreak > nul

:: ─────────────────────────────────────────────────────
:: BƯỚC 4: KHỞI ĐỘNG FRONTEND (cửa sổ riêng)
:: ─────────────────────────────────────────────────────
echo.
echo [4/4] Dang mo TRAM DIEU KHIEN (Frontend :3333)...
start "SNIPER-X NEXUS [3333]" cmd /k "color 0B && chcp 65001 > nul && cd /d "%~dp0nexus-frontend" && echo [NEXUS] Khoi dong Vite tren cong 3333... && npm run dev -- --port 3333"

timeout /t 5 /nobreak > nul

:: ─────────────────────────────────────────────────────
:: MỞ DASHBOARD TỰ ĐỘNG
:: ─────────────────────────────────────────────────────
echo.
echo [!] Dang mo Dashboard trong trinh duyet...
start "" "http://localhost:3333"

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║   [SUCCESS] HE THONG DA DUOC KICH HOAT!                 ║
echo  ║                                                          ║
echo  ║   Dashboard     : http://localhost:3333                  ║
echo  ║   API Health    : http://localhost:8888/api/health       ║
echo  ║   API Docs      : http://localhost:8888/docs             ║
echo  ║   Keno Scraper  : Chay tu dong moi 3 phut               ║
echo  ║                                                          ║
echo  ║   [!] Chuong trinh nay se dong sau 10 giay              ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
timeout /t 10 /nobreak > nul
