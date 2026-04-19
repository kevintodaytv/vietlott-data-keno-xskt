@echo off
color 0E
echo ====================================================
echo 🚀 KICH HOAT THE NEXUS TRUC TIEP TREN WINDOWS
echo ====================================================
echo.
echo Dang tien vao thu muc nexus-frontend...
cd _code\nexus-frontend

echo.
echo Dang quet va sua loi thu vien (co the mat 1-2 phut)...
call npm install --legacy-peer-deps

echo.
echo Khoi dong Giao dien 3D...
call npm run dev

echo.
pause
