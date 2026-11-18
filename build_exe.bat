@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul || (echo Установи Python 3.10+ и добавь его в PATH.& pause & exit /b 1)
py -3 -m pip install -r requirements.txt pyinstaller
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name "Metaclick Macro" metaclick.py
echo EXE находится в папке dist
pause
