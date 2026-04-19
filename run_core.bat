@echo off
color 0A
echo ====================================================
echo 🧠 KICH HOAT THE CORE (NATIVE WINDOWS)
echo ====================================================
echo Dang di chuyen vao can cu Backend...
cd _code\core-backend

echo.
echo [1/2] Kiem tra va nap thu vien Python...
call pip install -r requirements.txt

echo.
echo [2/2] Khoi dong dong co uvicorn o cong 8888 (Port cao, tranh xung dot)...
call uvicorn main:app --host 0.0.0.0 --port 8888 --reload

echo.
echo ====================================================
echo ⚠️ NEU THAY DONG NAY, HE THONG DA BI DUNG LAI!
pause
