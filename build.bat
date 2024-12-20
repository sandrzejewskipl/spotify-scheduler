@echo off
rmdir /s/q build
rmdir /s/q dist
pyinstaller --noconfirm --onefile --console --icon "icon.ico" --name "spotify-scheduler" --add-data "icon.ico;." --hidden-import='PIL._tkinter_finder' "main.py"
pause