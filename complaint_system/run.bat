@echo off
cd /d "C:\Users\ASUS\Desktop\scms 2\complaint_system"
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.
echo Running Flask application...
echo Open browser: http://localhost:5000
echo.
python app.py
pause
