@echo off
set /p "id=Enter Version: "
rmdir /s/q build\spotify-scheduler_data
nuitka --standalone --onefile --enable-plugin=tk-inter --include-data-file=icon.ico=icon.ico --windows-icon-from-ico=icon.ico --output-dir=build --windows-console-mode=disable --mingw64 --clang --product-name="Spotify Scheduler" --product-version=%id% --copyright="MIT License - (c) 2024 Szymon Andrzejewski" --output-filename="spotify-scheduler-v%id%.exe" main.py
pause