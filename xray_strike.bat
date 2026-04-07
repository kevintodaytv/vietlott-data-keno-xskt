@echo off
color 0A
echo ====================================================
echo 🔍 OPS-AGENT: KICH HOAT THE X-RAY PROTOCOL
echo ====================================================
echo.
echo [1/3] Dang the he thong cu va thanh tay rac...
docker-compose down
docker system prune -f >nul 2>&1

echo.
echo [2/3] Tien hanh Build lai toan bo DNA moi nhat...
docker-compose build

echo.
echo [3/3] Khoi dong He sinh thai (Hien thi LOGS truc tiep)...
echo ====================================================
echo ⚠️ LUU Y: De yen cua so nay. Khi nao thay dong chu
echo "Vite is ready in..." hien ra, cong 3000 da mo!
echo ====================================================
docker-compose up
pause
