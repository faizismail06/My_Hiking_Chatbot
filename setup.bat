@echo off
echo ========================================
echo   My Hiking Chatbot - Setup Script
echo ========================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak ditemukan!
    echo Silakan install Python 3.10+ dari https://python.org
    pause
    exit /b 1
)

echo [1/4] Membuat virtual environment...
python -m venv venv

echo [2/4] Mengaktifkan virtual environment...
call venv\Scripts\activate.bat

echo [3/4] Menginstall dependencies...
pip install -r requirements.txt

echo [4/4] Menyalin file .env...
if not exist .env (
    copy .env.example .env
    echo.
    echo [PENTING] Edit file .env dan masukkan GEMINI_API_KEY Anda!
    echo Dapatkan API key di: https://makersuite.google.com/app/apikey
)

echo.
echo ========================================
echo   Setup selesai!
echo ========================================
echo.
echo Langkah selanjutnya:
echo 1. Edit file .env dan masukkan GEMINI_API_KEY
echo 2. Jalankan: run.bat
echo.
pause
