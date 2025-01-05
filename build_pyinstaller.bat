@echo off
rmdir /s/q build
rmdir /s/q dist
pyinstaller --noconfirm --onefile --windowed --icon "icon.ico" --name "spotify-scheduler" --add-data "icon.ico;." --version-file "version.txt" "spotifyscheduler.py"
pause