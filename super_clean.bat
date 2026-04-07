@echo off
color 0B
chcp 65001 > nul
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║       SNIPER-X :: SUPER CLEAN OPERATION              ║
echo  ║       Dọn sạch chiến trường - Tái thiết trung tâm   ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: ─────────────────────────────────────────────────────
:: BƯỚC 1: TIÊU DIỆT TIẾN TRÌNH CHIẾM PORT
:: ─────────────────────────────────────────────────────
echo [BƯỚC 1/4] Dang quet tieu diet tien trinh chiem cong 3000, 3333, 8000, 8888...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " 2^>nul') do (
    taskkill /PID %%a /F > nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3333 " 2^>nul') do (
    taskkill /PID %%a /F > nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " 2^>nul') do (
    taskkill /PID %%a /F > nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8888 " 2^>nul') do (
    taskkill /PID %%a /F > nul 2>&1
)
echo [OK] Cong 3000, 3333, 8000, 8888 da duoc giai phong!

:: ─────────────────────────────────────────────────────
:: BƯỚC 2: TIÊU DIỆT PORTAINER VÀ DOCKER ZOMBIE
:: ─────────────────────────────────────────────────────
echo.
echo [BƯỚC 2/4] Dang tieu diet Portainer va container zombie cu...
docker stop portainer > nul 2>&1
docker rm -f portainer > nul 2>&1
docker container prune -f > nul 2>&1
docker network prune -f > nul 2>&1
echo [OK] Portainer va zombie container da bi tieu diet!

:: ─────────────────────────────────────────────────────
:: BƯỚC 3: CÀI LẠI PLAYWRIGHT CHROMIUM
:: ─────────────────────────────────────────────────────
echo.
echo [BƯỚC 3/4] Dang kiem tra Phi doi Chromium (Playwright)...
cd /d "%~dp0core-backend"
python -m playwright install chromium
cd /d "%~dp0"
echo [OK] Chromium da san sang chien dau!

:: ─────────────────────────────────────────────────────
:: BƯỚC 4: XÁC NHẬN TRẠNG THÁI CỔNG
:: ─────────────────────────────────────────────────────
echo.
echo [BƯỚC 4/4] Kiem tra trang thai cong sau khi don dep...
echo.
netstat -aon | findstr ":3333 :8888" 2>nul
if errorlevel 1 (
    echo [CLEAR] Cong 3333 va 8888 hoan toan trong - San sang hoat dong!
)

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   [SUCCESS] CHIEN TRUONG DA SACH SE HOAN TOAN!      ║
echo  ║                                                      ║
echo  ║   BUOC TIEP THEO:                                    ║
echo  ║   1. Chay: run_core.bat      (Backend :8888)         ║
echo  ║   2. Chay: native_nexus.bat  (Frontend :3333)        ║
echo  ║   3. Mo:   http://localhost:3333                      ║
echo  ║   4. Test: http://localhost:8888/api/health           ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
pause
