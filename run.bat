@echo off
echo ========================================
echo   My Hiking Chatbot - Starting Server
echo ========================================
echo.

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Run the server
python app.py

pause
