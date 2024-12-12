@echo off
rmdir /s/q build
rmdir /s/q dist
pyinstaller --noconfirm --onefile --console --icon "icon.ico" --name "Spotify Scheduler v" --add-data "icon.ico;." "main.py"
pause