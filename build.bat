@echo off
pyinstaller --noconfirm --onefile --console --icon "icon.ico" --name "Spotify Scheduler" --add-data "icon.ico;." "main.py"
pause