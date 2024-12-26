import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime
import time as t
import psutil
import sys
import tkinter as tk
from tkinter import ttk
import re
from PIL import Image, ImageTk
from io import BytesIO
import requests
import json
import shutil
import subprocess
import platform
from translations import translations
import os
from spotipy_anon import SpotifyAnon
import logging

print(f"! MIT License - © 2024 Szymon Andrzejewski (https://github.com/sandrzejewskipl/spotify-scheduler/blob/main/LICENSE) !\n")
version="1.7.0"
config_file="config.json"
schedule_file="schedule.txt"
default_schedule_file='default-schedule.txt'
log_file="output.log"
schedule_playlists_file = "schedule_playlists.json"

current_pid = os.getpid()
parent_pid = psutil.Process(current_pid).parent().pid

def timestamped_print(message):
    current_time = datetime.now().isoformat(sep=" ", timespec="seconds")
    print(f"{current_time} | {message}")
 
def error(e):
    string=f'\n\033[91m{e}\033[0m'
    return string

# Check if the folder exists, if not, create it
if not os.path.exists("spotify-scheduler_data"):
    os.makedirs("spotify-scheduler_data")

os.chdir('spotify-scheduler_data')
if os.name == 'nt':
    os.system('title Spotify Scheduler Console')

def bundle_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath("..")

    return os.path.join(base_path, relative_path)

required_keys = [
    "LANG", "CLIENT_ID", "CLIENT_SECRET", "DEVICE_NAME", 
    "KILLSWITCH_ON", "WEEKDAYS_ONLY", "AUTO_SPOTIFY"
]

def load_config():
    global required_keys
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {
            "LANG": "en",
            "CLIENT_ID": "",
            "CLIENT_SECRET": "",
            "DEVICE_NAME": "",
            "KILLSWITCH_ON": False,
            "WEEKDAYS_ONLY": False,
            "AUTO_SPOTIFY": False
        }
        try:
            config["DEVICE_NAME"] = platform.node()
        except Exception as e:
            pass
    for key in required_keys:
        if key not in config:
            if key == "KILLSWITCH_ON":
                config[key] = False 
            elif key == "WEEKDAYS_ONLY":
                config[key] = False
            elif key == "AUTO_SPOTIFY":
                config[key] = False
            else:
                config[key] = "" 
            timestamped_print(f"Missing key '{key}' set to default value.")

    with open(config_file, "w") as file:
        json.dump(config, file, indent=4)
    return config
load_config()



# Load config
config = load_config()

CLIENT_ID = config['CLIENT_ID']
CLIENT_SECRET = config['CLIENT_SECRET']
DEVICE_NAME = config['DEVICE_NAME']
KILLSWITCH_ON = config['KILLSWITCH_ON']
WEEKDAYS_ONLY = config['WEEKDAYS_ONLY']
AUTO_SPOTIFY = config['AUTO_SPOTIFY']
LANG = config['LANG']

REDIRECT_URI = "http://localhost:23918"
SCOPE = "user-modify-playback-state user-read-playback-state playlist-modify-public playlist-modify-private playlist-read-private"
PROCNAME = "spotify.exe"

def _(key, **kwargs):
    global LANG
    text = translations.get(LANG, {}).get(key, key)
    return text.format(**kwargs)

# Function to refresh fields in the settings tab
def refresh_settings():
    for key, entry in setting_entries.items():
        if isinstance(entry, ttk.Entry):
            entry.delete(0, tk.END)
            entry.insert(0, config.get(key, ""))
        elif isinstance(entry, ttk.Checkbutton):
            var = setting_vars.get(key)
            var.set(config.get(key, False))

def validate_client_credentials(client=None, secret=None):
    global CLIENT_ID, CLIENT_SECRET
    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    if not (client and secret):
        client=CLIENT_ID
        secret=CLIENT_SECRET

    data = {
        "grant_type": "client_credentials",
        "client_id": client,
        "client_secret": secret
    }
    try:
        response = requests.post(url, headers=headers, data=data)
    except Exception:
        response=""
        timestamped_print("Failed validating client credentials, proceeding as usual.")
    if response:
        if "invalid" in response.text:
            timestamped_print(f"Credentials are not valid: {error((response.status_code))} {error((response.text))}")
            return False
        return True
    return False

fakesplastprint=t.time()
class fake_sp:
    def __call__(self, *args, **kwargs):
        global fakesplastprint
        if t.time()-fakesplastprint>=1:
            timestamped_print(f"Credentials are not valid, Spotipy can't be initialized. Change CLIENT_ID and CLIENT_SECRET or fix internet connection.")
            fakesplastprint=t.time()
        status.set(_("failed_to_fetch_data_console"))

    
    def __getattr__(self, name):
        return self


def initialize_sp():
    global sp, sp_anon, spstatus
    sp=None
    sp_anon=None
    if CLIENT_ID!="" and CLIENT_SECRET!="":
        try:
            if validate_client_credentials():
                sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID,client_secret=CLIENT_SECRET,redirect_uri=REDIRECT_URI,scope=SCOPE))
                spstatus=True
                fetch_user_playlists()
                timestamped_print("Spotipy initialized properly.")
            else:
                sp = fake_sp()
                spstatus=False
            sp_anon = spotipy.Spotify(auth_manager=SpotifyAnon())
        except Exception as e:
            timestamped_print(f"Error during spotipy initalization: {error(e)}")

def save_settings():
    global config, CLIENT_ID, CLIENT_SECRET, KILLSWITCH_ON, WEEKDAYS_ONLY, DEVICE_NAME, LANG, setting_entries, AUTO_SPOTIFY
    if validate_client_credentials(setting_entries['CLIENT_ID'].get(),setting_entries['CLIENT_SECRET'].get()):
        config['CLIENT_ID'] = setting_entries['CLIENT_ID'].get()
        config['CLIENT_SECRET'] = setting_entries['CLIENT_SECRET'].get()
        config['DEVICE_NAME'] = setting_entries['DEVICE_NAME'].get()
        config['LANG'] = language_var.get()
        config['KILLSWITCH_ON'] = setting_vars['KILLSWITCH_ON'].get()
        config['WEEKDAYS_ONLY'] = setting_vars['WEEKDAYS_ONLY'].get() 
        config['AUTO_SPOTIFY'] = setting_vars['AUTO_SPOTIFY'].get() 

        save_config(config)
        refresh_settings()
        config = load_config()
        CLIENT_ID = config['CLIENT_ID']
        CLIENT_SECRET = config['CLIENT_SECRET']
        DEVICE_NAME = config['DEVICE_NAME']
        KILLSWITCH_ON = config['KILLSWITCH_ON']
        WEEKDAYS_ONLY = config['WEEKDAYS_ONLY']
        AUTO_SPOTIFY = config['AUTO_SPOTIFY']
        LANG = config['LANG']
        
        string=_("Saved.")
        settingsstatus_text.set(string)
        initialize_sp()
    else:
        timestamped_print(f"Settings not saved.")
        string=_("Couldn't save. Check console.")
        settingsstatus_text.set(string)



    


# Creating a GUI window
root = tk.Tk()
root.title(f"Spotify Scheduler v{version}")
root.geometry("800x600")
root.resizable(False, False) 


# Adding bookmarks
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

now_playing_frame = ttk.Frame(notebook)
notebook.add(now_playing_frame, text=_("Now Playing"))

schedule_frame = ttk.Frame(notebook)
notebook.add(schedule_frame, text=_("Schedule"))

playlist_frame = ttk.Frame(notebook)
notebook.add(playlist_frame, text=_("Playlist"))

settings_frame = ttk.Frame(notebook)
notebook.add(settings_frame, text=_("Settings"))

info_frame = ttk.Frame(notebook)
notebook.add(info_frame, text=_("About"))

def open_link(url):
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception as e:
        print(f"Failed to open link: {error(e)}")    
try:
    icon_image = Image.open(bundle_path("icon.ico"))
    icon_photo = ImageTk.PhotoImage(icon_image)
    icon_label = tk.Label(info_frame, image=icon_photo)
    icon_label.image = icon_photo 
    icon_label.pack(pady=10)
except Exception as e:
    print(f"Failed to load icon: {error(e)}")    

info_text = tk.Text(info_frame, wrap="word", height=10, width=70, font=("Arial", 12))
info_text.pack(expand=True, pady=20, padx=20)

info_text.insert("insert", _( "Spotify Scheduler") + "\n", "header")
info_text.insert("insert", f"{_('Version')}: {version}\n")
info_text.insert("insert", f"{_('Author')}: ")
info_text.insert("insert", f"Szymon Andrzejewski\n", "link1")

info_text.insert("insert", f"{_('GitHub')}: ")
info_text.insert("insert", "https://github.com/sandrzejewskipl/Spotify-Scheduler\n", "link2")

info_text.insert("insert", f"\n{_('Made_with')}\n{_('Greetings')}\n\nMIT License - © 2024 Szymon Andrzejewski")

info_text.tag_config("header", font=("Arial", 14, "bold"), justify="center")
info_text.tag_config("link1", foreground="blue", underline=True)
info_text.tag_config("link2", foreground="blue", underline=True)

info_text.tag_bind("link1", "<Button-1>", lambda e: open_link("https://szymonandrzejewski.pl"))
info_text.tag_bind("link2", "<Button-1>", lambda e: open_link("https://github.com/sandrzejewskipl/Spotify-Scheduler"))

info_text.config(state="disabled")

# Function to save configuration
def save_config(config, config_file=config_file):
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)
    timestamped_print("The configuration has been saved.")

def refresh_settings():
    for key, entry in setting_entries.items():
        if isinstance(entry, ttk.Entry):
            entry.delete(0, tk.END)
            entry.insert(0, config.get(key, ""))
        elif isinstance(entry, ttk.Checkbutton):
            var = setting_vars.get(key)
            var.set(config.get(key, False))

def delete_spotify_cache(ex=None):
    if validate_client_credentials():
        if "access" in ex:
            with open('.cache', 'r') as file:
                data = json.load(file)

            data["expires_at"] = 0

            with open('.cache', 'w') as file:
                json.dump(data, file, indent=4)
            timestamped_print("Forced access token to renew.")
            initialize_sp()
            return True
        if os.path.exists(".cache"):
            killswitch("Spotipy cache deleted - killed for safety because OAuth freezes app.")
            try:
                timestamped_print("Cache file with access token has been deleted.")
                os.remove(".cache")
                initialize_sp()
                return True
            except Exception as e:
                timestamped_print(f"Failed to delete cache file: {error(e)}")
    else:
        timestamped_print("Credentials are not valid and cached token can't be deleted. Change CLIENT_ID and CLIENT_SECRET.")
        status.set(_("failed_to_fetch_data_console"))
    return False

setting_entries = {}
setting_vars = {}

# Language selection 
ttk.Label(settings_frame, text=_("Language")).grid(row=0, column=0, padx=10, pady=5, sticky=tk.E)
language_var = tk.StringVar(value=config.get('LANG', 'en'))

language_combobox = ttk.Combobox(settings_frame, textvariable=language_var, state="readonly", width=47)
language_combobox['values'] = ('en', 'pl')
language_combobox.grid(row=0, column=1, padx=10, pady=5)

# CLIENT ID
ttk.Label(settings_frame, text="CLIENT ID").grid(row=1, column=0, padx=10, pady=5, sticky=tk.E)
setting_entries['CLIENT_ID'] = ttk.Entry(settings_frame, width=50)
setting_entries['CLIENT_ID'].grid(row=1, column=1, padx=10, pady=5)

# CLIENT SECRET
ttk.Label(settings_frame, text="CLIENT SECRET").grid(row=2, column=0, padx=10, pady=5, sticky=tk.E)
setting_entries['CLIENT_SECRET'] = ttk.Entry(settings_frame, show="*", width=50)
setting_entries['CLIENT_SECRET'].grid(row=2, column=1, padx=10, pady=5)

# DEVICE NAME
ttk.Label(settings_frame, text="DEVICE NAME").grid(row=3, column=0, padx=10, pady=5, sticky=tk.E)
setting_entries['DEVICE_NAME'] = ttk.Entry(settings_frame, width=50)
setting_entries['DEVICE_NAME'].grid(row=3, column=1, padx=10, pady=5)

# SWITCHES
setting_vars['KILLSWITCH_ON'] = tk.BooleanVar(value=config.get('KILLSWITCH_ON', False))
ttk.Checkbutton(settings_frame, text=_("Killswitch"), variable=setting_vars['KILLSWITCH_ON']).grid(row=5, columnspan=2, pady=5,padx=5)

setting_vars['WEEKDAYS_ONLY'] = tk.BooleanVar(value=config.get('WEEKDAYS_ONLY', False))
ttk.Checkbutton(settings_frame, text=_("Weekdays Only"), variable=setting_vars['WEEKDAYS_ONLY']).grid(row=4, columnspan=2, pady=5,padx=5)

setting_vars['AUTO_SPOTIFY'] = tk.BooleanVar(value=config.get('AUTO_SPOTIFY', False))
ttk.Checkbutton(settings_frame, text=_("Auto Spotify"), variable=setting_vars['AUTO_SPOTIFY']).grid(row=6, columnspan=2, pady=5,padx=5)

buttons_frame = ttk.Frame(settings_frame)
buttons_frame.grid(row=7, column=0, columnspan=2, pady=10)

save_btn = ttk.Button(buttons_frame, text=_("Save Settings"), command=save_settings)
save_btn.pack(side="left", padx=5)

deletecache_btn = ttk.Button(buttons_frame, text=_("Delete cache (logout)"), command=delete_spotify_cache)
deletecache_btn.pack(side="left", padx=5)

settingsstatus_text = tk.StringVar()
settingsstatus_text.set("")

settingsstatus = ttk.Label(settings_frame, textvariable=settingsstatus_text, wraplength=500, anchor="w")
settingsstatus.grid(row=8, columnspan=2)

text_label = ttk.Label(settings_frame, text="EN: After changing the language, restart the application to apply the changes. \nPL: Po zmianie języka zrestartuj aplikację, aby zastosować zmiany.", foreground="green")
text_label.grid(row=9, columnspan=2, pady=10)

devices_list = tk.StringVar()
devices_list.set("")

devices_label = ttk.Label(settings_frame, textvariable=devices_list, wraplength=500, anchor="w")
devices_label.place(x=10, y=350)



log_file = open(log_file, "a", encoding="utf-8")

# Redirecting stdout to console and file
class Logger:
    def __init__(self, file, terminal):
        self.file = file
        self.terminal = terminal

    def write(self, message):
        self.file.write(message)
        self.terminal.write(message)
        self.flush() 

    def flush(self):
        self.file.flush()
        self.terminal.flush()

sys.stdout = Logger(log_file, sys.__stdout__)

def load_schedule_to_table():
    try:
        with open(schedule_file, "r") as file:
            lines = file.readlines()
            schedule_table.delete(*schedule_table.get_children())
            for line in lines:
                if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?-([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$", line.strip()):
                    start_time, end_time = line.strip().split("-")
                    schedule_table.insert("", "end", values=(start_time, end_time))
        timestamped_print("Schedule loaded into table.")
        refresh_playlist_gui()
    except FileNotFoundError:
        timestamped_print("The file schedule.txt does not exist.")
    except Exception as e:
        timestamped_print(f"Error during loading schedule: {error(e)}")
def save_default_schedule():
    try:
        shutil.copy(schedule_file, default_schedule_file)
        load_schedule_to_table()
        timestamped_print("Schedule loaded into table.")
    except Exception as e:
        timestamped_print(f"Error during saving schedule: {error(e)}")
        
def replace_schedule_with_default():
    try:
        shutil.copy(default_schedule_file, schedule_file)
        timestamped_print("Setting schedule to default.")
        load_schedule_to_table()
        generate_schedule_playlists()
        refresh_playlist_gui()

    except Exception as e:
        timestamped_print(f"Error while changing schedule: {error(e)}")

# Create default schedule
def generate_default(force=True):
    global default_schedule_file, default_schedule
    if (not os.path.exists(default_schedule_file)) or force==True:
        with open(default_schedule_file, "w") as file:
            default_schedule = """8:45-8:55
9:40-9:45
10:30-10:45
11:30-11:35
12:20-12:25
13:10-13:25
14:10-14:15"""
            file.write(default_schedule)
        if force:
            timestamped_print("Regenerated default schedule")
            
generate_default(False)

def save_schedule_from_table():
    try:
        # Get all entries from table
        rows = []
        for row in schedule_table.get_children():
            start_time, end_time = schedule_table.item(row, "values")
            rows.append((start_time, end_time))

        # Sort entries by start time
        rows.sort(key=lambda x: datetime.strptime(x[0], "%H:%M:%S" if ":" in x[0] and x[0].count(":") == 2 else "%H:%M"))

        # Save sorted entries to file
        with open(schedule_file, "w") as file:
            for start_time, end_time in rows:
                file.write(f"{start_time}-{end_time}\n")

        timestamped_print("Schedule has been saved.")
        load_schedule_to_table()
        refresh_playlist_gui()
    except Exception as e:
        timestamped_print(f"Error during saving schedule: {error(e)}")
def generate_schedule_playlists():
    try:
        new_data={}
        if os.path.exists(schedule_playlists_file):
            with open(schedule_playlists_file, "r+") as json_file:
                data = json.load(json_file)
                if "default" in data:
                    default_key=data["default"]
                    new_data={"default": default_key}
                json_file.seek(0)
                json_file.truncate()
                json.dump(new_data, json_file, indent=4)
        else:
            with open(schedule_playlists_file, "w") as json_file:
                json.dump(new_data, json_file, indent=4)
    except Exception as e:
        timestamped_print(f"Error during saving playlists file: {error(e)}")
def get_playlist_for_schedule(key=None):
    global last_schedule, schedule_playlists_file
    try:
        with open(schedule_file, "r+") as file:
            lines = file.readlines()
            now = datetime.now().time()
            if key==None:
                for line in lines:
                    if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?-([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$", line.strip()):
                        start_str, end_str = line.strip().split("-")
                        start_time = datetime.strptime(start_str, "%H:%M:%S" if ":" in start_str and start_str.count(":") == 2 else "%H:%M").time()
                        end_time = datetime.strptime(end_str, "%H:%M:%S" if ":" in end_str and end_str.count(":") == 2 else "%H:%M").time()
                        if start_time <= now <= end_time:
                            key=line
            if key:
                try:
                    with open(schedule_playlists_file, "r") as file:
                        data = json.load(file)
                        key = key.strip()
                        if key in data:
                            return data[key]

                        elif "default" in data:
                            return data["default"]
                        else:
                            return None
                except FileNotFoundError:
                    generate_schedule_playlists()
                except Exception as e:
                    timestamped_print(f"Error during loading playlists file: {error(e)}")
    except Exception as e:
        timestamped_print(f"Error during reading schedule: {error(e)}")
    return False

def is_valid_time_format(time_str):
    time_pattern = r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$"  # Hours: 00-23, Minutes: 00-59
    return re.match(time_pattern, time_str) is not None

def add_entry(event=None):
    start_time = (start_time_entry.get()).replace(';',':')
    end_time = (end_time_entry.get()).replace(';',':')

    if not is_valid_time_format(start_time):
        timestamped_print(f"Incorrect time format: {start_time}. Use HH:MM or HH:MM:SS.")
        return

    if not is_valid_time_format(end_time):
        timestamped_print(f"Incorrect time format: {end_time}. Use HH:MM or HH:MM:SS.")
        return

    start_dt = datetime.strptime(start_time, "%H:%M:%S" if ":" in start_time and start_time.count(":") == 2 else "%H:%M")
    end_dt = datetime.strptime(end_time, "%H:%M:%S" if ":" in end_time and end_time.count(":") == 2 else "%H:%M")

    if end_dt <= start_dt:
        timestamped_print("Error: End time must be later than start time.")
        return

    if start_time and end_time:
        schedule_table.insert("", "end", values=(start_time, end_time))
        start_time_entry.delete(0, tk.END)
        end_time_entry.delete(0, tk.END)
        timestamped_print(f"Added to schedule: {start_time} - {end_time}")
        save_schedule_from_table() 
    else:
        timestamped_print("Cannot add an empty entry.")



def delete_selected_entry():
    selected_item = schedule_table.selection()
    if selected_item:
        for item in selected_item:
            start_time, end_time = schedule_table.item(item, "values")
            remove_playlist(f"{start_time}-{end_time}")
            schedule_table.delete(item)
        timestamped_print("The selected entry has been deleted.")
        save_schedule_from_table()
    else:
        timestamped_print("No entries have been marked for deletion.")

def regenerate():
    generate_default()
    replace_schedule_with_default()

# Schedule table
columns = ("start", "end")
schedule_table = ttk.Treeview(schedule_frame, columns=columns, show="headings", height=10)
schedule_table.heading("start", text=_("Start Time"))
schedule_table.heading("end", text=_("End Time"))
schedule_table.pack(fill="both", expand=True, padx=10, pady=(10, 0))

# Entry frame
entry_frame = ttk.Frame(schedule_frame)
entry_frame.pack(fill="x", padx=10, pady=5)

start_time_label = ttk.Label(entry_frame, text=_("START_LABEL"))
start_time_label.pack(side="left", padx=5)
start_time_entry = ttk.Entry(entry_frame, width=10)
start_time_entry.pack(side="left", padx=5)
start_time_entry.bind('<Return>', add_entry)

end_time_label = ttk.Label(entry_frame, text=_("END_LABEL"))
end_time_label.pack(side="left", padx=5)
end_time_entry = ttk.Entry(entry_frame, width=10)
end_time_entry.pack(side="left", padx=5)
end_time_entry.bind('<Return>', add_entry)

add_button = ttk.Button(entry_frame, text=_("Add Entry"), command=add_entry)
add_button.pack(side="left", padx=5)

delete_button = ttk.Button(entry_frame, text=_("Delete Selected"), command=delete_selected_entry)
delete_button.pack(side="left", padx=5)

# Buttons
button_frame = ttk.Frame(schedule_frame)
button_frame.pack(fill="x", padx=10, pady=10)



replace_button = ttk.Button(button_frame, text=_("Load default"), command=replace_schedule_with_default)
replace_button.pack(side="left", padx=5)

save_button = ttk.Button(button_frame, text=_("Save as default"), command=save_default_schedule)
save_button.pack(side="left", padx=5)

regenerate_button = ttk.Button(button_frame, text=_("Restore default"), command=regenerate)
regenerate_button.pack(side="left", padx=5)

load_button = ttk.Button(button_frame, text=_("Reload Schedule"), command=load_schedule_to_table)
load_button.pack(side="right", padx=5)




is_paused = False

def toggle_pause():
    global is_paused
    is_paused = not is_paused
    status = "Paused" if is_paused else "Running"
    timestamped_print(f"App state: {status}")
    pause_button.config(text=_("Resume Automation") if is_paused else _("Pause Automation"))
    pause_play_btn.config(text=_("Pause music and stop automation") if not is_paused else _("Resume Automation"))


def pauseandauto():
    global is_paused
    if is_paused:
        is_paused = False
        pause_button.config(text=_("Resume Automation") if is_paused else _("Pause Automation"))
        pause_play_btn.config(text=_("Pause music and stop automation"))
    else:
        is_paused = True
        pause_button.config(text=_("Resume Automation") if is_paused else _("Pause Automation"))
        pause_play_btn.config(text=_("Resume Automation"))
        pause_music()


control_frame = ttk.Frame(root)
control_frame.pack(side="top", fill="x", padx=10, pady=5)
def run_spotify():
    if os.name == 'nt':
        try:
            result = subprocess.run(["where", "spotify"], capture_output=True, text=True, check=True)
            subprocess.run(["spotify"])
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            userdir = os.path.join(os.environ['USERPROFILE'], 'AppData\\Roaming\\Spotify\\Spotify.exe')
            if os.path.exists(userdir):
                subprocess.Popen([userdir], shell=True)
            else:
                timestamped_print("Spotify not found.")
        except Exception as e:
            timestamped_print(f"Error during launching Spotify: {error(e)}")
            
def spotify_button_check():
    if os.name == 'nt':
        try:
            result = subprocess.run(["where", "spotify"], capture_output=True, text=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            userdir = os.path.join(os.environ['USERPROFILE'], 'AppData\\Roaming\\Spotify\\Spotify.exe')
            if os.path.exists(userdir):
                return True
    return False

if spotify_button_check():
    spotify_button = ttk.Button(control_frame, text=_("Run Spotify"), command=run_spotify)
    spotify_button.pack(side="left")

device_label = ttk.Label(control_frame, text=platform.node(), font=("Arial", 10))
device_label.pack(side="left", padx=10)



# Pause button
pause_button = ttk.Button(control_frame, text=_("Pause Automation"), command=toggle_pause)
pause_button.pack(side="right",)


status = tk.StringVar()
status.set("")

# Text near pause
status_label = ttk.Label(control_frame, textvariable=status, font=("Arial", 10))
status_label.pack(side="right", padx=10)


# Playlist section 



# Load playlist scheduling
def load_schedule_playlists():
    try:
        with open(schedule_playlists_file, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"default": ""} 
    
# Save playlist scheduling
def save_schedule_playlists():
    try:
        with open(schedule_playlists_file, "w") as file:
            json.dump(schedule_playlists, file, indent=4)
        timestamped_print("Schedule playlists saved successfully.")
    except Exception as e:
        timestamped_print(f"Error saving schedule playlists: {error(e)}")

# Load default scheduled playlists
schedule_playlists = load_schedule_playlists()

# Read schedule file
def read_schedule_file():
    try:
        with open("schedule.txt", "r") as file:
            return ["default"] + [line.strip() for line in file.readlines()] 
    except FileNotFoundError:
        return ["default"]

schedule = read_schedule_file()
selected_time = tk.StringVar()

def refresh_playlist_gui(last=None):
    global schedule, schedule_playlists

    schedule = read_schedule_file()
    schedule_playlists = load_schedule_playlists()

    schedule_with_ids = [f"{hour} ({get_playlist_id_for_hour(hour)})" for hour in schedule]

    time_dropdown['values'] = schedule_with_ids

    if schedule_with_ids:
        if last:
            matching_item = next((item for item in schedule_with_ids if item.startswith(last + " ")), None)
            if matching_item:
                selected_time.set(matching_item)
            else:
                selected_time.set(schedule_with_ids[0])
        else:
            selected_time.set(schedule_with_ids[0])

    update_view_for_time()


def get_playlist_id_for_hour(hour):
    # The function returns the playlist ID for the given time value. If the time does not exist in schedule_playlists, it returns the text "default".
    default_text=_("same as default")
    if hour=="default":
        default_text=_("No ID set")

    return schedule_playlists.get(hour, default_text)


# Function to update the view based on the selected time
def update_view_for_time(*args):
    current_time = selected_time.get()

    hour = current_time.split("(")[0].rstrip(" ")
    PLAYLIST_ID = get_playlist_for_schedule(key=hour)
        
    display_playlist_info(PLAYLIST_ID)


playlist_info = {
    "name": "",
    "owner": "",
    "image_url": ""
}
# Change playlist to selected time
def change_playlist():
    global playlist_info
    user_input = playlist_entry.get().strip()
    if user_input != "":
        current_time = selected_time.get().split("(")[0].rstrip(" ") 

        playlist_entry.delete(0, tk.END)
        PLAYLIST_ID = extract_playlist_id(user_input) if "open.spotify.com" in user_input else user_input

        if not PLAYLIST_ID:
            timestamped_print("Failed to extract playlist ID.")
            return
        playlist_info = {
            "name": _("The playlist has been changed but its data could not be retrieved."),
            "image_url": ""
        }
        
        schedule_playlists[current_time] = PLAYLIST_ID
        save_schedule_playlists()

        timestamped_print(f"Playlist for {current_time} updated to {PLAYLIST_ID}.")
        refresh_playlist_gui(current_time)
        spotify_main()
    else:
        timestamped_print(f"Playlist ID can't be blank.")

def remove_playlist(user_input=None):
    global schedule_playlists
    current_time = selected_time.get().split("(")[0].rstrip(" ")
    if user_input==None:
        user_input = current_time  # Selected time
    if user_input in schedule_playlists:
        del schedule_playlists[user_input]
        save_schedule_playlists()
        timestamped_print(f"Playlist for {user_input} has been removed.")

        refresh_playlist_gui(current_time)
        spotify_main()
    else:
        timestamped_print(f"No playlist found for {user_input}.")

# Add a dropdown list at the top
time_selection_frame = ttk.Frame(playlist_frame)
time_selection_frame.pack(fill="x", padx=10, pady=(5,0))

time_label = ttk.Label(time_selection_frame, text=_("Select time slot:"))
time_label.pack(side="left", padx=5)

time_dropdown = ttk.Combobox(time_selection_frame, textvariable=selected_time, state="readonly", values=schedule, width=50, height=20)
time_dropdown.pack(side="left")
time_dropdown.bind("<<ComboboxSelected>>", update_view_for_time)

# Set default as selected time
if schedule:
    selected_time.set(schedule[0])

def get_spotify_playlist(id=None):
    if not id:
        return None
    
    # Spotipy doesn't log 404 errors as an exception, so temporarily disable logging.
    logger = logging.getLogger("spotipy.client")
    original_level = logger.level
    logger.setLevel(logging.CRITICAL)

    try:
        return sp_anon.playlist(id)
    except Exception:
        return sp.playlist(id)
    finally:
        logger.setLevel(original_level) # Bring back original logging
    

def get_playlist_info(id=None):
    playlist_info = {
        "name": "",
        "owner": "",
        "image_url": ""
    }
    if id:
        try:
            playlist_info = {
                "name": _("failed_to_fetch_data"),
                "owner": _("failed_to_fetch_data"),
                "image_url": ""
            }
            playlist = get_spotify_playlist(id)
            if playlist["name"]:
                playlist_info["name"] = playlist["name"]
            if playlist["owner"]['display_name']:
                playlist_info["owner"] = playlist["owner"]['display_name']


            # Get playlist image url
            images = playlist.get("images", [])
            if images:
                playlist_info["image_url"] = images[0]["url"]

        except Exception as e:
            timestamped_print(f"Failed to retrieve playlist {id} data: {error(e)}")

    return playlist_info


# Playlist container
playlist_info_frame = ttk.Frame(playlist_frame)
playlist_info_frame.pack(fill="x", padx=10, pady=10)

# img
playlist_image_label = ttk.Label(playlist_info_frame)
playlist_image_label.grid(row=0, column=0, rowspan=3, sticky="nw")

# name
playlist_label = ttk.Label(playlist_info_frame, text=_("Playlist")+":")
playlist_label.grid(row=0, column=1, padx=5, pady=2, sticky="nw")

# id/url
playlist_entry_label = ttk.Label(playlist_info_frame, text=_("Playlist ID or link:"))
playlist_entry_label.grid(row=1, column=1, padx=5, pady=2, sticky="w")

playlist_entry = ttk.Entry(playlist_info_frame, width=75)
playlist_entry.grid(row=1, column=1, padx=125, pady=2)

# Container for buttons
buttons_frame = ttk.Frame(playlist_info_frame)
buttons_frame.grid(row=2, column=1, columnspan=2, pady=10)

# Set Playlist button
change_playlist_btn = ttk.Button(buttons_frame, text=_("Set Playlist"), command=change_playlist)
change_playlist_btn.pack(side="left", padx=5)

# Remove Playlist button
remove_playlist_btn = ttk.Button(buttons_frame, text=_("Remove Playlist"), command=remove_playlist)
remove_playlist_btn.pack(side="left", padx=5)









def extract_playlist_id(url):
    try:
        pattern = r"playlist/(\w+)"
        return re.search(pattern, url).group(1)
    except AttributeError:
        return None



# Container for table and scrollbar
table_frame = ttk.Frame(playlist_frame)
table_frame.pack(fill="both", expand=True, padx=10, pady=5)

# Playlist table
columns = ("name", "id")
playlist_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
playlist_table.heading("name", text=_("Name"))
playlist_table.heading("id", text="ID")
playlist_table.pack(side="left", fill="both", expand=True)

# Scrollbar
scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=playlist_table.yview)
playlist_table.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")


def fetch_user_playlists():
    try:
        playlists = sp.current_user_playlists()
        playlist_table.delete(*playlist_table.get_children())  
        for playlist in playlists['items']:
            if playlist: 
                playlist_name = playlist['name']
                playlist_id = playlist['id']
                playlist_table.insert("", "end", values=(playlist_name, playlist_id))
    except Exception as e:
        timestamped_print(f"Error downloading user playlists: {error(e)}")

# Select playlist from list
def select_playlist(event):
    try:
        selected_item = playlist_table.focus()  # selected item
        if not selected_item:
            return
        playlist_values = playlist_table.item(selected_item, "values")
        playlist_id = playlist_values[1]  # column with id
        playlist_entry.delete(0, tk.END)  # clear input
        playlist_entry.insert(0, playlist_id)  # put id into input
    except Exception as e:
        timestamped_print(f"Error selecting playlist: {error(e)}")

# bind click
playlist_table.bind("<ButtonRelease-1>", select_playlist)

# load playlist button
load_playlists_btn = ttk.Button(playlist_frame, text=_("Refresh Playlists"), command=fetch_user_playlists)
load_playlists_btn.pack(side='left', pady=10, padx=10)



def display_playlist_info(id):
    playlist_info = get_playlist_info(id)

    playlist_label.config(text=f"{_('Playlist')}: {playlist_info['name']}\n{_('Owner')}: {playlist_info['owner']}")

    if playlist_info["image_url"]:
        response = requests.get(playlist_info["image_url"])
        if response.status_code == 200:
            img_data = BytesIO(response.content)
            img = Image.open(img_data)
        else:
            img = Image.new("RGB", (150, 150), "lightgrey")
    else:
        img = Image.new("RGB", (150, 150), "lightgrey")

    img = img.resize((150, 150))
    playlist_img = ImageTk.PhotoImage(img)

    playlist_image_label.config(image=playlist_img)
    playlist_image_label.image = playlist_img



# now playing label
now_playing_label = ttk.Label(now_playing_frame, text="", font=("Arial", 12))
now_playing_label.pack(padx=10, pady=10)

# cover photo
now_playing_image_label = ttk.Label(now_playing_frame)
now_playing_image_label.pack(padx=10, pady=10)

def checklist():
    global global_devices
    if not spstatus:
        checklistvar.set(_("failed_to_fetch_data_console"))
        return
    try:
        #limit spotify api calls
        if global_devices:
            devices = global_devices
        else:
            devices = sp.devices()
        found_device = _("Device Not Found")
        volume = _("Check Manually")
        proces = ''

        if devices["devices"]:
            for device in devices["devices"]:
                if DEVICE_NAME in device["name"].upper():
                    found_device = _("Device Found", device_name=device['name'])
                    volume=device['volume_percent']
                    if volume>10:
                        volume = _("Volume OK", volume=volume)
                    else:
                        volume = _("Volume Increase", volume=volume)
                    break
        PLAYLIST_ID=get_playlist_for_schedule("default")
        if PLAYLIST_ID:
            playlist = _("Playlist Set")
        else:
            playlist = _("Playlist Missing")
        if os.name == 'nt':
            proces = (_("Spotify Is Turned Off")+"\n")
            for proc in psutil.process_iter():
                if PROCNAME.lower() in proc.name().lower():
                    if (proc.pid!=current_pid) or (proc.pid!=parent_pid):
                        proces = (_("Spotify Running")+"\n")
        
        checklistvar.set(_("Checklist", process=proces, device=found_device, volume=volume, playlist=playlist))

    except Exception as ex:
        timestamped_print(f"Checklist error: {error(ex)}")
        checklistvar.set(_("failed_to_fetch_data_console"))


    


lastfetch=None
lastresponse=None
lasttype=None
playlist_info_str=None
lastalbum=None
def update_now_playing_info():
    global lastfetch, playlist_name, lastresponse, playlist_info_str, lasttype, lastalbum
    
    try:
        # LIMIT SPOTIFY API CALLS
        if global_playback:
            current_playback = global_playback
        else:
            current_playback = sp.current_playback()

        if global_devices:
            devices = global_devices
        else:
            devices = sp.devices()

        # Get active device
        target_device_name = _("No device")
        device_list=''
        if devices and "devices" in devices:
            for device in devices["devices"]:
                name = device.get("name", _("Unknown device"))
                device_list+=(f"• {name} ")
                if device.get("is_active"):
                    target_device_name = name
                    break
        devices_string=f"{_('Detected devices')}:\n{device_list}"
        devices_list.set(devices_string)

        if current_playback and "item" in current_playback and current_playback["item"]:
            track = current_playback["item"]
            artist = track["artists"][0]["name"]
            title = track["name"]

            is_playing = current_playback.get("is_playing", False)
            playback_state = _("Playing") if is_playing else _("Paused")

            playing_playlist = None
            failed=True
            try:
                context = current_playback.get("context", {})
                playing_playlist = context.get("uri", "").split(":")[-1]
            except Exception:
                pass
            current_track = current_playback['item']
            album = current_track['album']

            forcefetch=False
            if album['name']!=lastalbum and lasttype=="album":
                forcefetch=True

            if lastfetch != playing_playlist or forcefetch:
                if playing_playlist:
                    try:
                        lastfetch = playing_playlist
                        playlist_details = get_spotify_playlist(playing_playlist)
                        if playlist_details:
                            lasttype="playlist"
                            playlist_name = playlist_details.get("name", "-")
                            failed=False
                    except Exception as e:
                        playlist_name = _("failed_to_fetch_data")
                    playlist_info_str = f"{_('Playlist')}: {playlist_name}"
                if failed:
                    lasttype="album"
                    lastalbum=album['name']
                    playlist_info_str = f"{_('Album')}: {album['name']}"
            
            if not playlist_info_str:
                playlist_info_str=_("failed_to_fetch_data")
            # Now playing text
            now_playing_label.config(
                text=(
            f"{_('Title')}: {title}\n"
            f"{_('Artist')}: {artist}\n"
            f"{playlist_info_str}\n"
            f"{_('Device')}: {target_device_name}\n\n"
            f"{_('State')}: {playback_state}\n"
            f"{_('Time slot')}: {last_schedule.strip()}")
            )

            # Get and display cover photo
            if lastresponse!=track["album"]:
                album_images = track["album"].get("images", [])
                if album_images:
                    response = requests.get(album_images[0]["url"])
                    if response.status_code == 200:
                        img_data = BytesIO(response.content)
                        img = Image.open(img_data)
                        img = img.resize((200, 200))
                        now_playing_img = ImageTk.PhotoImage(img)
                        lastresponse=track["album"]

                        now_playing_image_label.config(image=now_playing_img)
                        now_playing_image_label.image = now_playing_img 

        else:
            now_playing_label.config(text=_("no_playback"))
            now_playing_image_label.image=None

    except Exception as e:
        timestamped_print(f"Error during updating now playing info: {error(e)}")
        now_playing_label.config(text=_("failed_to_fetch_data"))

    checklist()

# Pause music and stop automation button
pause_play_btn = ttk.Button(now_playing_frame, text=_("Pause music and stop automation"), command=pauseandauto)
pause_play_btn.pack(padx=10, pady=10)

checklistvar = tk.StringVar()
checklistvar.set("")

# Checklist label
checklist_label = ttk.Label(now_playing_frame, textvariable=checklistvar, font=("Arial", 10))
checklist_label.pack(padx=10, pady=5)


# Spotipy main functions
def killswitch(reason=None):
    if KILLSWITCH_ON:
        processes=0
        for proc in psutil.process_iter():
            if PROCNAME.lower() in proc.name().lower():
                if (proc.pid!=current_pid) and (proc.pid!=parent_pid):
                    try:
                        proc.kill()
                        processes+=1
                        status.set(_("Killed Spotify process"))
                    except Exception:
                        pass
        if processes>0:
            timestamped_print(f"Killed {processes} Spotify process(es). Reason: {reason}")

last_endtime=None
def is_within_schedule(schedule_file=schedule_file):
    match=False
    global last_schedule, WEEKDAYS_ONLY, last_endtime
    last_schedule=''
    try:
        with open(schedule_file, "r+") as file:
            lines = file.readlines()
            now = datetime.now().time()
            for line in lines:
                if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?-([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$", line.strip()):
                    start_str, end_str = line.strip().split("-")
                    start_time = datetime.strptime(start_str, "%H:%M:%S" if ":" in start_str and start_str.count(":") == 2 else "%H:%M").time()
                    end_time = datetime.strptime(end_str, "%H:%M:%S" if ":" in end_str and end_str.count(":") == 2 else "%H:%M").time()
                    if start_time <= now <= end_time:
                        weekno = datetime.today().weekday()
                        if not WEEKDAYS_ONLY:
                            weekno = 0
                        if weekno < 5:
                            last_schedule=line
                            last_endtime=datetime.combine(datetime.now(), end_time)
                            match=True
    except FileNotFoundError:
        timestamped_print(f"The file schedule.txt does not exist, it will be created now from default.")
        replace_schedule_with_default()
    except Exception as e:
        timestamped_print(f"Error during reading schedule: {error(e)}")
    return match

last_playlist=''
def play_music():
    global last_playlist, global_devices, last_spotify_run
    try:
        if global_devices:
            devices = global_devices
        else:
            devices = sp.devices()

        if not devices["devices"]:
            status.set(_( "no_active_device"))
            if spotify_button_check() and AUTO_SPOTIFY and not last_spotify_run:
                timestamped_print("Trying to run spotify.")
                run_spotify()
                last_spotify_run = True
            return

        target_device = None
        for device in devices["devices"]:
            if DEVICE_NAME in device["name"].upper():
                target_device = device["id"]
                break

        if target_device:
            PLAYLIST_ID=get_playlist_for_schedule()
            if PLAYLIST_ID:
                sp.start_playback(device_id=target_device, context_uri=f"spotify:playlist:{PLAYLIST_ID}")
                last_playlist=PLAYLIST_ID
                playlist_info=get_playlist_info(PLAYLIST_ID)
                string=""
                if playlist_info:
                    string=f"Playlist: {playlist_info['name']}, Owner: {playlist_info['owner']}"
                timestamped_print(f"Music playing on {device['name']}. {string}")
                last_spotify_run=False
        else:
            status.set(_( "no_active_device"))
            if spotify_button_check() and AUTO_SPOTIFY and not last_spotify_run:
                timestamped_print("Trying to run spotify.")
                run_spotify()
                last_spotify_run = True


    except Exception as ex:
        timestamped_print(f"Error while playing: {error(ex)}")

last_spotify_run=False
def pause_music(retries=3, delay=2):
    global last_endtime, global_playback, last_spotify_run
    last_spotify_run = False

    if not spstatus:
        killswitch("Pausing music - Spotipy not initialized.")
        return
    
    attempt = 0
    while attempt < retries:
        try:
            took_time=datetime.now()
            current_playback = sp.current_playback()
            global_playback = current_playback

            if current_playback and current_playback["is_playing"]:
                sp.pause_playback()
                delay=""
                if last_endtime:
                    delay=f"(Delay: {round(((datetime.now()-last_endtime).total_seconds()),2)}s)"
                timestamped_print(f"Playback has been paused. {delay}")
            status.set(_("out_of_schedule_paused"))
            return  # Zakończ funkcję, jeśli się udało
        except Exception as e:
            if ("token" in str(e)) or ("Expecting value" in str(e)):
                delete_spotify_cache(str(e))
                killswitch("Pausing music - Killed after deleting cache.")
                return
            attempt += 1
            timestamped_print(f"Error occurred, retrying... ({attempt}/{retries}, took {round(((datetime.now()-took_time).total_seconds()),2)}s) {error(e)}")
            t.sleep(delay)
    timestamped_print("Failed to pause playback after multiple attempts.")
    killswitch("Pausing music - Failed to pause music.")

global_playback = None
global_devices = None
def spotify_main():
    global last_playlist, global_playback, global_devices
    if not is_paused:
        if not sp or not spstatus:
            initialize_sp()
        if is_within_schedule():
            try:
                current_playback = sp.current_playback()
                global_playback = current_playback

                devices=None
                try:
                    devices = sp.devices()
                    global_devices = devices
                except Exception:
                    pass

                target_device = None
                active_device = None
                if devices and "devices" in devices:
                    for device in devices["devices"]:
                        if DEVICE_NAME in device["name"].upper():
                            target_device = device["id"]
                        if device.get("is_active"):
                            active_device = device["id"]
                    
                PLAYLIST_ID=get_playlist_for_schedule()
                if (not current_playback) or (not current_playback["is_playing"]) or (not last_playlist==PLAYLIST_ID) or (target_device!=active_device):
                    if PLAYLIST_ID:
                        play_music()
                    else:
                        status.set(_("Playlist not set"))
                else:
                    status.set(_("Music is currently playing."))
            except Exception as ex:
                timestamped_print(f"Error getting playback status: {error(ex)}")
                if ("token" in str(ex)) or ("Expecting value" in str(ex)):
                    delete_spotify_cache(str(ex))
        else:
            status.set(_("out_of_schedule"))
            pause_music()
            try:
                global_devices = sp.devices()
            except Exception:
                pass
    update_now_playing_info()

def main():
    global CLIENT_ID, CLIENT_SECRET, config, newupdate, sp
    if(not CLIENT_ID or not CLIENT_SECRET):
        print(f"Create an app here (instructions are in README on Github):\nhttps://developer.spotify.com/dashboard (it should open automatically)")
        t.sleep(1.5)
        open_link("https://developer.spotify.com/dashboard")
        CLIENT_ID = input("Enter CLIENT_ID: ")
        CLIENT_SECRET = input("Enter CLIENT_SECRET: ")
        while not validate_client_credentials():
            print("Credentials are not valid.")
            CLIENT_ID = input("Enter CLIENT_ID: ")
            CLIENT_SECRET = input("Enter CLIENT_SECRET: ")

    try:
        with open(config_file, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {}

    config['CLIENT_ID'] = CLIENT_ID
    config['CLIENT_SECRET'] = CLIENT_SECRET

    # Save to config.json
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)

    print("# Spotify Scheduler made by Szymon Andrzejewski (https://szymonandrzejewski.pl)")
    print("# Github repository: https://github.com/sandrzejewskipl/spotify-scheduler/")
    print(_( "check_schedule"))
    try:
        with open(schedule_file, 'r') as file:
            lines = file.readlines()
            for line in lines:
                if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?-([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$", line.strip()):
                    print(f'{line.strip()}')
    except FileNotFoundError:
        replace_schedule_with_default()
        with open(schedule_file, 'r') as file:
            lines = file.readlines()
            for line in lines:
                if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?-([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$", line.strip()):
                    print(f'{line.strip()}')
    except Exception as e:
        timestamped_print(f"Error during reading schedule: {error(e)}")     
    print('') # newline
    t.sleep(5)   
    refresh_settings()
    sp=None
    initialize_sp()
    load_schedule_to_table()
        
    if os.name == 'nt':
        root.iconbitmap(bundle_path("icon.ico"))
        try:
            from ctypes import windll
            kernel32 = windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 128)
        except Exception as e:
            timestamped_print(f'Cannot disable QuickEdit mode: {error(e)}')
            
    
    def loop():
        try:
            spotify_main()
        except Exception as e:
            timestamped_print(f"Exception during looping Spotify main function. {error(e)}")
            pause_music()
        root.after(2500, loop)  # Loop

    def fetching_loop():
        fetch_user_playlists()
        root.after(60000, fetching_loop)
    
    def title_loop(lastdate=None):
        try:
            global newupdate
            now = datetime.now().strftime("%H:%M:%S")
            if lastdate!=now: #update title only when time changes
                lastdate=now
                root.title(f"Spotify Scheduler v{version} | {now} {newupdate}")
        except Exception:
            pass

        root.after(100, title_loop, lastdate)

    def updatechecker_loop():
        global newupdate
        newupdate=""
        try:
            response = requests.get("https://api.github.com/repos/sandrzejewskipl/spotify-scheduler/releases/latest")
            if response:
                if response.json()["tag_name"]:
                    if response.json()["tag_name"]>version:
                        newupdate=(f"| {_('A new update is available for download')}!")
                        timestamped_print(f"A new update is available for download at https://github.com/sandrzejewskipl/spotify-scheduler/releases/latest (latest {response.json()['tag_name']} vs current {version})")
        except Exception:
            pass
        
        root.after(600000, updatechecker_loop)

    loop()
    fetching_loop()
    updatechecker_loop()
    title_loop()


if __name__ == "__main__":
    root.after(0, main)
    root.mainloop()
