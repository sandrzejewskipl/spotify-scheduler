@echo off
set /p "id=Enter Version: "
rmdir /s/q build
rmdir /s/q dist
pyinstaller --noconfirm --onefile --windowed --icon "icon.ico" --name "spotify-scheduler" -n "spotify-scheduler-v%id%.exe" --add-data "icon.ico;." "main.py"
pause