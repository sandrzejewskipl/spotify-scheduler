@echo off
rmdir /s/q build
rmdir /s/q dist
pyinstaller --noconfirm --onedir --windowed --icon "icon.ico" --name "spotify-scheduler" --add-data "icon.ico;." "spotifyscheduler.py"
pause