@echo off
color 0C
echo ====================================================
echo 🚑 OPS-AGENT: TRICH XUAT HOP DEN (NEXUS CRASH LOG)
echo ====================================================
echo Dang lay du lieu tu vung khong gian chet...

:: Trích xuất riêng log của Frontend và xuất ra file text
docker-compose logs nexus_ui > nexus_crash_report.txt

:: Tự động mở file text bằng Notepad
start notepad nexus_crash_report.txt

echo Hoan tat! File Notepad da duoc mo.
