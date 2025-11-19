@echo off
REM Instagram Post Planner - Windows EXE Build Script
REM This script builds a standalone Windows executable using PyInstaller

echo ========================================
echo Instagram Post Planner - EXE Builder
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo [1/4] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [2/4] Installing dependencies...
python -m pip install pandas openpyxl pyinstaller

echo.
echo [3/4] Building standalone EXE (this may take a few minutes)...
python -m PyInstaller --onefile --noconsole ^
    --name InstagramPostPlanner ^
    --hidden-import openpyxl ^
    --hidden-import openpyxl.cell._writer ^
    --add-data "config.py;." ^
    --add-data "validator.py;." ^
    --add-data "constraint_analyzer.py;." ^
    --add-data "planner.py;." ^
    --add-data "instagram_auto_post.py;." ^
    gui_app_v2.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo [4/4] Build complete!
echo.
echo ========================================
echo Executable location:
echo   dist\InstagramPostPlanner.exe
echo ========================================
echo.
echo You can now copy InstagramPostPlanner.exe to any Windows machine
echo and run it without needing Python installed.
echo.
echo NOTE: The EXE file will be large (80-100MB) due to pandas.
echo This is normal and expected.
echo.

pause
