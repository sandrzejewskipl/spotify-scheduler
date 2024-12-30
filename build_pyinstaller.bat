@echo off
rmdir /s/q build
rmdir /s/q dist
pyinstaller --noconfirm --onefile --windowed --icon "icon.ico" --name "spotify-scheduler" --add-data "icon.ico;." "main.py"
pause