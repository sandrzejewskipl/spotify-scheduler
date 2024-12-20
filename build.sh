python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pip install pyinstaller
pyinstaller --noconfirm --onefile --console --icon "icon.ico" --name "Spotify Scheduler" --add-data "icon.ico:." "main.py"