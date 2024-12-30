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
from packaging import version
import locale

VER="1.8.1"
CONFIG_FILE="config.json"
SCHEDULE_FILE="schedule.txt"
DEFAULT_SCHEDULE_FILE='default-schedule.txt'
LOG_FILE="output.log"
SCHEDULE_PLAYLISTS_FILE = "schedule_playlists.json"

try:
    current_pid = os.getpid()
    parent_pid = psutil.Process(current_pid).parent().pid
except Exception:
    parent_pid = None

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
try:
    if os.name == 'nt':
        if sys.__stdout__:
            os.system('title Spotify Scheduler Console')
except Exception:
    pass

def bundle_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    # try:
    #     # PyInstaller creates a temp folder and stores path in _MEIPASS
    #     base_path = sys._MEIPASS
    # except Exception:
    #     base_path = os.path.abspath("..")

    # return os.path.join(base_path, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

def get_default_language():
    try:
        locale.setlocale(locale.LC_TIME, '')
        system_language = locale.getlocale()[0]
        if system_language.startswith('Polish'):
            return 'pl'
    except Exception:
        pass
    return 'en'
    
def load_config():
    default_config = {
        "LANG": get_default_language(),
        "CLIENT_ID": "",
        "CLIENT_SECRET": "",
        "DEVICE_NAME": platform.node() if hasattr(platform, "node") else "",
        "KILLSWITCH_ON": True,
        "WEEKDAYS_ONLY": False,
        "AUTO_SPOTIFY": True
    }

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = default_config.copy()

    for key, default_value in default_config.items():
        if key not in config:
            config[key] = default_value
            timestamped_print(f"Missing key '{key}' set to default value.")

    with open(CONFIG_FILE, "w") as file:
        json.dump(config, file, indent=4)

    return config

# Load config
config = load_config()

def _(key, **kwargs):
    text = translations.get(config['LANG'], {}).get(key, key)
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
    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    if not (client and secret):
        client=config['CLIENT_ID']
        secret=config['CLIENT_SECRET']

    data = {
        "grant_type": "client_credentials",
        "client_id": client,
        "client_secret": secret
    }
    try:
        response = requests.post(url, headers=headers, data=data)
    except Exception as e:
        timestamped_print(f"Failed validating client credentials: {error(e)}")
        return False
    if response.status_code!=200:
        timestamped_print(f"Credentials are not valid: {error((response.status_code))} {error((response.text)).strip()}")
        return False
    return True

fakesplastprint=t.time()
class fake_sp:
    def __call__(self, *args, **kwargs):
        global fakesplastprint
        if t.time()-fakesplastprint>=1:
            timestamped_print(f"Spotipy can't be initialized. Change CLIENT_ID and CLIENT_SECRET or fix internet connection.")
            status.set(_("failed_to_fetch_data_console"))
            fakesplastprint=t.time()

    def __getattr__(self, name):
        return self


def initialize_sp():
    global sp, sp_anon, spstatus, last_spotify_run
    sp=None
    sp_anon=None
    REDIRECT_URI = "http://localhost:23918"
    SCOPE = "user-modify-playback-state user-read-playback-state playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative"
    
    if config['CLIENT_ID']!="" and config['CLIENT_SECRET']!="":
        try:
            if validate_client_credentials():
                sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=config['CLIENT_ID'],client_secret=config['CLIENT_SECRET'],redirect_uri=REDIRECT_URI,scope=SCOPE))
                spstatus=True
                fetch_user_playlists()
                timestamped_print("Spotipy initialized properly.")
                last_spotify_run=False
            else:
                sp = fake_sp()
                spstatus=False
            sp_anon = spotipy.Spotify(auth_manager=SpotifyAnon())
        except Exception as e:
            timestamped_print(f"Error during spotipy initalization: {error(e)}")

def save_settings():
    global config, setting_entries

    for key, entry in setting_entries.items():
        value = setting_entries[key].get()
        if not value.strip():
            timestamped_print(f"Settings not saved. Complete all fields.")
            string=_("Couldn't save. Complete all fields.")
            settingsstatus_text.set(string)
            return
    if validate_client_credentials(setting_entries['CLIENT_ID'].get(),setting_entries['CLIENT_SECRET'].get()):
        config['CLIENT_ID'] = setting_entries['CLIENT_ID'].get()
        config['CLIENT_SECRET'] = setting_entries['CLIENT_SECRET'].get()
        config['DEVICE_NAME'] = setting_entries['DEVICE_NAME'].get()
        langstring=""
        lastlang = config['LANG']
        if config['LANG']!=language_var.get():
            config['LANG'] = language_var.get()
            langstring=f" {_('Restart the app to apply the language change.')} "
        config['KILLSWITCH_ON'] = setting_vars['KILLSWITCH_ON'].get()
        config['WEEKDAYS_ONLY'] = setting_vars['WEEKDAYS_ONLY'].get() 
        config['AUTO_SPOTIFY'] = setting_vars['AUTO_SPOTIFY'].get() 

        save_config(config)
        config = load_config()
        refresh_settings()
        string=_("Settings saved.")
        config['LANG'] = lastlang #set current language to previous, because otherwise it looks bad - some elements are in previous language, some are in current
        settingsstatus_text.set(string+langstring)
        initialize_sp()
    else:
        timestamped_print(f"Settings not saved.")
        string=_("Couldn't save. Credentials are not valid.")
        settingsstatus_text.set(string)



    


# Creating a GUI window
root = tk.Tk()
root.title(f"Spotify Scheduler v{VER}")
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

console_frame = ttk.Frame(notebook)
notebook.add(console_frame, text=_("Console"))

info_frame = ttk.Frame(notebook)
notebook.add(info_frame, text=_("About"))

LOG_FILE = open(LOG_FILE, "a", encoding="utf-8")

console_text = tk.Text(console_frame, wrap="word", height=20, width=100, font=("Arial", 10))
console_text.pack(expand=True, fill="both", padx=10, pady=10)

# Redirecting stdout to console and file
class Logger:
    ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def __init__(self, file, terminal, text_widget):
        self.file = file
        self.terminal = terminal
        self.text_widget = text_widget

    def write(self, message):
        clean_message = self.ANSI_ESCAPE.sub('', message)
        self.file.write(message)
        if self.terminal:
            self.terminal.write(message)
        self.text_widget.insert(tk.END, clean_message)
        self.text_widget.see(tk.END)
        self.flush()

    def flush(self):
        self.file.flush()
        if self.terminal:
            self.terminal.flush()

sys.stdout = Logger(LOG_FILE, sys.__stdout__, console_text)
sys.stderr = Logger(LOG_FILE, sys.__stderr__, console_text)

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
info_text.insert("insert", f"{_('Version')}: {VER}\n")
info_text.insert("insert", f"{_('Author')}: ")
info_text.insert("insert", f"Szymon Andrzejewski\n", "link1")

info_text.insert("insert", f"{_('GitHub')}: ")
info_text.insert("insert", "https://github.com/sandrzejewskipl/Spotify-Scheduler\n", "link2")

info_text.insert("insert", f"\n{_('Made_with')}\n{_('Greetings')}\n\nMIT License - © 2024 Szymon Andrzejewski")

info_text.tag_config("header", font=("Arial", 14, "bold"), justify="center")
info_text.tag_config("link1", foreground="#1DB954", underline=True)
info_text.tag_config("link2", foreground="#1DB954", underline=True)

info_text.tag_bind("link1", "<Button-1>", lambda e: open_link("https://szymonandrzejewski.pl"))
info_text.tag_bind("link2", "<Button-1>", lambda e: open_link("https://github.com/sandrzejewskipl/Spotify-Scheduler"))

info_text.config(state="disabled")

# Function to save configuration
def save_config(config, CONFIG_FILE=CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
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

def delete_spotify_cache(ex=""):
    if validate_client_credentials():
        if "access" in ex:
            try:
                with open('.cache', 'r') as file:
                    data = json.load(file)

                data["expires_at"] = 0

                with open('.cache', 'w') as file:
                    json.dump(data, file, indent=4)
                timestamped_print("Forced access token to renew.")
                initialize_sp()
                return True
            except Exception:
                pass
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
    initialize_sp()
    return False

setting_entries = {}
setting_vars = {}

# Language selection 
ttk.Label(settings_frame, text=_("Language:")).grid(row=0, column=0, padx=10, pady=5, sticky=tk.E)
language_var = tk.StringVar(value=config.get('LANG', 'en'))

language_combobox = ttk.Combobox(settings_frame, textvariable=language_var, state="readonly", width=47)
language_combobox['values'] = ('en', 'pl')
language_combobox.grid(row=0, column=1, pady=5)

# CLIENT ID
ttk.Label(settings_frame, text="Client ID:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.E)
setting_entries['CLIENT_ID'] = ttk.Entry(settings_frame, width=50)
setting_entries['CLIENT_ID'].grid(row=1, column=1, pady=5)

# CLIENT SECRET
ttk.Label(settings_frame, text="Client secret:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.E)
setting_entries['CLIENT_SECRET'] = ttk.Entry(settings_frame, show="*", width=50)
setting_entries['CLIENT_SECRET'].grid(row=2, column=1, pady=5)

# DEVICE NAME
ttk.Label(settings_frame, text=_("Device name:")).grid(row=3, column=0, padx=10, pady=5, sticky=tk.E)
setting_entries['DEVICE_NAME'] = ttk.Entry(settings_frame, width=50)
setting_entries['DEVICE_NAME'].grid(row=3, column=1, pady=5)

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
settingsstatus.grid(row=8, columnspan=2, padx=10)

text_label = ttk.Label(settings_frame, text="EN: After changing the language, restart the application to apply the changes. \nPL: Po zmianie języka zrestartuj aplikację, aby zastosować zmiany.", foreground="green")
text_label.grid(row=9, columnspan=2, padx=10, sticky='w', pady=5)

devices_list = tk.StringVar()
devices_list.set("")

devices_label = ttk.Label(settings_frame, textvariable=devices_list, wraplength=500, anchor="w")
devices_label.grid(row=10, columnspan=2, pady=10, padx=10, sticky='w')

def load_schedule_to_table(printstatus=True):
    try:
        with open(SCHEDULE_FILE, "r") as file:
            lines = file.readlines()
            schedule_table.delete(*schedule_table.get_children())
            for line in lines:
                if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?-([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$", line.strip()):
                    start_time, end_time = line.strip().split("-")
                    schedule_table.insert("", "end", values=(start_time, end_time))
        timestamped_print("Schedule loaded into table.")
        if printstatus:
            schedulevar.set(_("Schedule has been reloaded."))
        refresh_playlist_gui()
    except FileNotFoundError:
        timestamped_print(f"Schedule file does not exist, it will be created now from default.")
        replace_schedule_with_default()
    except Exception as e:
        timestamped_print(f"Error during loading schedule: {error(e)}")
def save_default_schedule():
    try:
        shutil.copy(SCHEDULE_FILE, DEFAULT_SCHEDULE_FILE)
        load_schedule_to_table()
        schedulevar.set(_("Default schedule has been saved."))
        timestamped_print("Schedule loaded into table.")
    except Exception as e:
        timestamped_print(f"Error during saving schedule: {error(e)}")
        
def replace_schedule_with_default():
    try:
        shutil.copy(DEFAULT_SCHEDULE_FILE, SCHEDULE_FILE)
        timestamped_print("Setting schedule to default.")
        load_schedule_to_table()
        generate_schedule_playlists()
        refresh_playlist_gui()
        schedulevar.set(_("Default schedule has been loaded."))

    except Exception as e:
        timestamped_print(f"Error while changing schedule: {error(e)}")

# Create default schedule
def generate_default(force=True):
    global DEFAULT_SCHEDULE_FILE, default_schedule
    if (not os.path.exists(DEFAULT_SCHEDULE_FILE)) or force==True:
        with open(DEFAULT_SCHEDULE_FILE, "w") as file:
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
        with open(SCHEDULE_FILE, "w") as file:
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
        if os.path.exists(SCHEDULE_PLAYLISTS_FILE):
            with open(SCHEDULE_PLAYLISTS_FILE, "r+") as json_file:
                data = json.load(json_file)
                if "default" in data:
                    default_key=data["default"]
                    new_data={"default": default_key}
                json_file.seek(0)
                json_file.truncate()
                json.dump(new_data, json_file, indent=4)
        else:
            with open(SCHEDULE_PLAYLISTS_FILE, "w") as json_file:
                json.dump(new_data, json_file, indent=4)
    except Exception as e:
        timestamped_print(f"Error during saving playlists file: {error(e)}")
def get_playlist_for_schedule(key=None):
    global last_schedule, SCHEDULE_PLAYLISTS_FILE
    if key==None:
        key=is_within_schedule()
    if key:
        try:
            with open(SCHEDULE_PLAYLISTS_FILE, "r") as file:
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
    return False

def is_valid_time_format(time_str):
    time_pattern = r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$"  # Hours: 00-23, Minutes: 00-59
    return re.match(time_pattern, time_str) is not None

def add_entry(event=None):
    start_time = (start_time_entry.get()).replace(';',':')
    end_time = (end_time_entry.get()).replace(';',':')

    if not is_valid_time_format(start_time):
        schedulevar.set(_("Error: Incorrect time format."))
        timestamped_print(f"Incorrect time format: {start_time}. Use HH:MM or HH:MM:SS.")
        return

    if not is_valid_time_format(end_time):
        schedulevar.set(_("Error: Incorrect time format."))
        timestamped_print(f"Incorrect time format: {end_time}. Use HH:MM or HH:MM:SS.")
        return

    start_dt = datetime.strptime(start_time, "%H:%M:%S" if ":" in start_time and start_time.count(":") == 2 else "%H:%M")
    end_dt = datetime.strptime(end_time, "%H:%M:%S" if ":" in end_time and end_time.count(":") == 2 else "%H:%M")

    if end_dt <= start_dt:
        schedulevar.set(_("Error: End time must be later than start time."))
        timestamped_print("Error: End time must be later than start time.")
        return

    if start_time and end_time:
        schedule_table.insert("", "end", values=(start_time, end_time))
        start_time_entry.delete(0, tk.END)
        end_time_entry.delete(0, tk.END)
        schedulevar.set(f"{_('Added to schedule:')}: {start_time} - {end_time}")
        timestamped_print(f"Added to schedule: {start_time} - {end_time}")
        save_schedule_from_table() 
    else:
        schedulevar.set(_("Error: Cannot add an empty entry."))
        timestamped_print("Cannot add an empty entry.")



def delete_selected_entry():
    selected_item = schedule_table.selection()
    if selected_item:
        for item in selected_item:
            start_time, end_time = schedule_table.item(item, "values")
            remove_playlist(f"{start_time}-{end_time}")
            schedule_table.delete(item)
        schedulevar.set(f"{_('Removed from schedule:')}: {start_time} - {end_time}")
        timestamped_print("The selected entry has been deleted.")
        save_schedule_from_table()
    else:
        schedulevar.set(_("No entry selected."))
        timestamped_print("No entries have been marked for deletion.")

def regenerate():
    generate_default()
    replace_schedule_with_default()
    schedulevar.set(_("Default schedule has been restored."))

# Schedule table
columns = ("start", "end")
schedule_table = ttk.Treeview(schedule_frame, columns=columns, show="headings")
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

schedulevar = tk.StringVar()
schedulevar.set("")

# Checklist label
schedule_label = ttk.Label(schedule_frame, textvariable=schedulevar, font=("Arial", 10))
schedule_label.pack(fill="x", padx=15)

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
            if shutil.which('spotify'):
                subprocess.run(["spotify"])
            else:
                userdir = os.path.join(os.environ['USERPROFILE'], 'AppData\\Roaming\\Spotify\\Spotify.exe')
                if os.path.exists(userdir):
                    subprocess.Popen([userdir], shell=True)
                else:
                    timestamped_print("Spotify not found.")
        except Exception as e:
            timestamped_print(f"Error during launching Spotify: {error(e)}")
    if os.name == 'posix':
        try:
            if shutil.which('spotify'):
                devnull = open(os.devnull, "w")
                process = subprocess.Popen(["spotify"], stdout=devnull, stderr=devnull)
                devnull.close()
        except Exception:
            timestamped_print(f"Error during launching Spotify: {error(e)}")
            
def spotify_button_check():
    if os.name == 'nt':
        try:
            if shutil.which('spotify'):
                return True
            else:
                userdir = os.path.join(os.environ['USERPROFILE'], 'AppData\\Roaming\\Spotify\\Spotify.exe')
                if os.path.exists(userdir):
                    return True
        except Exception:
            pass
    if os.name == 'posix':
        try:
            if shutil.which('spotify'):
                return True
        except Exception:
            pass
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
        with open(SCHEDULE_PLAYLISTS_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"default": ""} 
    
# Save playlist scheduling
def save_schedule_playlists():
    try:
        with open(SCHEDULE_PLAYLISTS_FILE, "w") as file:
            json.dump(schedule_playlists, file, indent=4)
        timestamped_print("Schedule playlists saved successfully.")
    except Exception as e:
        timestamped_print(f"Error saving schedule playlists: {error(e)}")

# Load default scheduled playlists
schedule_playlists = load_schedule_playlists()

# Read schedule file for playlists
def playlist_read_schedule_file():
    try:
        with open(SCHEDULE_FILE, "r") as file:
            lines = [line.strip() for line in file.readlines()]
            # Check each line against the regex
            valid_lines = [
                line for line in lines if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?-([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$", line)
            ]
            return ["default"] + valid_lines
    except FileNotFoundError:
        return ["default"]

schedule = playlist_read_schedule_file()
selected_time = tk.StringVar()

def refresh_playlist_gui(last=None):
    global schedule, schedule_playlists

    schedule = playlist_read_schedule_file()
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
        playliststatus_text.set(_(""))
        timestamped_print(f"Playlist for {current_time} updated to {PLAYLIST_ID}.")
        refresh_playlist_gui(current_time)
        spotify_main()
    else:
        playliststatus_text.set(_("Playlist ID can't be blank."))
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
playlist_label.grid(row=0, column=1, padx=5, sticky="nw")

# id/url
playlist_entry_label = ttk.Label(playlist_info_frame, text=_("Playlist ID or link:"))
playlist_entry_label.grid(row=1, column=1, padx=5, sticky="w")

playlist_entry = ttk.Entry(playlist_info_frame, width=75)
playlist_entry.grid(row=1, column=1, padx=125)

playliststatus_text = tk.StringVar()
playliststatus_text.set("")

settingsstatus = ttk.Label(playlist_info_frame, textvariable=playliststatus_text, wraplength=500, anchor="w")
settingsstatus.grid(row=3, column=1, columnspan=2)

# Container for buttons
buttons_frame = ttk.Frame(playlist_info_frame)
buttons_frame.grid(row=2, column=1, columnspan=2)

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

username=""
def fetch_user_playlists():
    global username
    playlists = []
    offset = 0
    limit = 50
    
    while True:
        try:
            response = sp.current_user_playlists(limit=limit, offset=offset)
            total=response['total']
            playlists.extend(response['items'])
            if len(response['items']) < limit:
                break
            offset += limit
        except Exception:
            break
    try:
        user = sp.current_user()
        username=(f"{_('Logged in as')}: {user['display_name']}\n\n")
    except Exception as e:
        pass
    try:
        playlist_table.delete(*playlist_table.get_children())  
        if playlists:
            for playlist in playlists:
                if playlist: 
                    playlist_name = playlist['name']
                    playlist_id = playlist['id']
                    playlist_table.insert("", "end", values=(playlist_name, playlist_id))
            playlistsvar.set(f"{_('fetched_playlists', length=len(playlists), total=total)}")
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
load_playlists_btn.pack(side='left', pady=10, padx=(10,5))

playlistsvar = tk.StringVar()
playlistsvar.set("")

# Checklist label
playlists_label = ttk.Label(playlist_frame, textvariable=playlistsvar, font=("Arial", 10))
playlists_label.pack(side='left', pady=10)

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
    try:
        #limit spotify api calls
        if global_devices:
            devices = global_devices
        else:
            devices = sp.devices()
        found_device = _("Device Not Found")
        volume = _("Check Manually")
        proces = ''

        if devices and "devices" in devices:
            for device in devices["devices"]:
                if config['DEVICE_NAME'].lower() in device["name"].lower():
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
        if spotify_button_check():
            if os.name == 'nt':
                proces = (_("Spotify Is Turned Off")+"\n")
                for proc in psutil.process_iter():
                    try:
                        if "spotify.exe"==proc.name().lower():
                            if (proc.pid!=current_pid) or (proc.pid!=parent_pid):
                                proces = (_("Spotify Running")+"\n")
                    except Exception:
                        pass
            if os.name == 'posix':
                proces = (_("Spotify Is Turned Off")+"\n")
                for proc in psutil.process_iter():
                    try:
                        if proc.name().lower()=="spotify":
                            if (proc.pid!=current_pid) or (proc.pid!=parent_pid):
                                proces = (_("Spotify Running")+"\n")
                    except Exception:
                        pass
        
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
    if not spstatus:
        now_playing_label.config(text=(_("Spotify credentials are not valid.\nChange CLIENT ID and CLIENT SECRET or fix internet connection.")))
        checklistvar.set(_("Spotify credentials are not valid.\nChange CLIENT ID and CLIENT SECRET or fix internet connection."))
        return
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
        devices_string=f"{username}{_('Detected devices')}:\n{device_list}"
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
            if album['name']!=lastalbum and lasttype!="playlist":
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
    if config['KILLSWITCH_ON']:
        processes=0
        if os.name=='nt':
            try:
                for proc in psutil.process_iter():
                    try:
                        if "spotify.exe"==proc.name().lower():
                            if (proc.pid!=current_pid) and (proc.pid!=parent_pid):
                                    proc.kill()
                                    processes+=1
                                    status.set(_("Killed Spotify process"))
                    except Exception:
                        pass
            except Exception as e:
                timestamped_print(f"Kilswitch failed: {error(e)}")
        if os.name=='posix':
            try:
                for proc in psutil.process_iter():
                    try:
                        if proc.name().lower()=="spotify":
                            if (proc.pid!=current_pid) and (proc.pid!=parent_pid):
                                    proc.kill()
                                    processes+=1
                                    status.set(_("Killed Spotify process"))
                    except Exception:
                        pass
            except Exception as e:
                timestamped_print(f"Kilswitch failed: {error(e)}")
        if processes>0:
            timestamped_print(f"Killed {processes} Spotify process(es). Reason: {reason}")

last_endtime=None
def is_within_schedule():
    match=False
    global last_schedule, last_endtime
    last_schedule=''
    try:
        with open(SCHEDULE_FILE, "r+") as file:
            lines = file.readlines()
            now = datetime.now().time()
            for line in lines:
                if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?-([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$", line.strip()):
                    start_str, end_str = line.strip().split("-")
                    start_time = datetime.strptime(start_str, "%H:%M:%S" if ":" in start_str and start_str.count(":") == 2 else "%H:%M").time()
                    end_time = datetime.strptime(end_str, "%H:%M:%S" if ":" in end_str and end_str.count(":") == 2 else "%H:%M").time()
                    if start_time <= now <= end_time and (not config['WEEKDAYS_ONLY'] or datetime.today().weekday() < 5):
                        last_schedule=line
                        last_endtime=datetime.combine(datetime.now(), end_time)
                        match=line.strip()
    except FileNotFoundError:
        timestamped_print(f"Schedule file does not exist, it will be created now from default.")
        replace_schedule_with_default()
    except Exception as e:
        timestamped_print(f"Error during reading schedule: {error(e)}")
    return match

last_playlist=''
def play_music():
    global last_playlist, global_devices, last_spotify_run
    try:
        if target_device:
            PLAYLIST_ID=get_playlist_for_schedule()
            if PLAYLIST_ID:
                sp.start_playback(device_id=target_device["id"], context_uri=f"spotify:playlist:{PLAYLIST_ID}")
                last_playlist=PLAYLIST_ID
                playlist_info=get_playlist_info(PLAYLIST_ID)
                string=""
                if playlist_info:
                    string=f"Playlist: {playlist_info['name']}, Owner: {playlist_info['owner']}"
                timestamped_print(f"Music playing on {target_device['name']}. {string}")
                last_spotify_run=False
        else:
            status.set(_( "no_active_device"))
            if spotify_button_check() and config['AUTO_SPOTIFY'] and not last_spotify_run:
                timestamped_print("Trying to run spotify.")
                run_spotify()
                last_spotify_run = True
            return

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

            if current_playback and "is_playing" in current_playback:
                if current_playback["is_playing"]:
                    sp.pause_playback()
                    delay=""
                    if last_endtime:
                        delay=f"(Delay: {round(((datetime.now()-last_endtime).total_seconds()),2)}s)"
                    timestamped_print(f"Playback has been paused. {delay}")
            status.set(_("out_of_schedule_paused"))
            return
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
    global last_playlist, global_playback, global_devices, target_device
    if not is_paused:
        if not sp or not spstatus:
            initialize_sp()
        if is_within_schedule():
            try:
                current_playback = sp.current_playback()
                global_playback = current_playback

                devices = sp.devices()
                global_devices = devices

                target_device = None
                active_device = None
                if devices and "devices" in devices:
                    for device in devices["devices"]:
                        if config['DEVICE_NAME'].lower() in device["name"].lower():
                            target_device = device
                        if device.get("is_active"):
                            active_device = device
                    
                PLAYLIST_ID=get_playlist_for_schedule()
                if (not current_playback) or (not current_playback["is_playing"]) or (not last_playlist==PLAYLIST_ID) or (target_device["id"]!=active_device["id"]):
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
    else:
        status.set(_("Automation is paused"))
    update_now_playing_info()

def main():
    global config, newupdate, sp
    print(f"\n! MIT License - © 2024 Szymon Andrzejewski (https://github.com/sandrzejewskipl/spotify-scheduler/blob/main/LICENSE) !\n")
    print(f"# Spotify Scheduler v{VER} made by Szymon Andrzejewski (https://szymonandrzejewski.pl)")
    print("# Github repository: https://github.com/sandrzejewskipl/spotify-scheduler/\n")  
    if(not config['CLIENT_ID'] or not config['CLIENT_SECRET']):
        print(f"Create an app on Spotify for Developers (instructions are in README on Github):\nhttps://developer.spotify.com/dashboard")
        def save_credentials():
            if validate_client_credentials(client_id_entry.get(), client_secret_entry.get()):
                config['CLIENT_ID'] = client_id_entry.get()
                config['CLIENT_SECRET'] = client_secret_entry.get()
                credentials_window.destroy()
            else:
                error_label.config(text=_("Couldn't save. Credentials are not valid."))

        credentials_window = tk.Toplevel(root)
        credentials_window.title(_("Enter Spotify Credentials"))
        credentials_window.geometry("450x430")
        credentials_window.resizable(False, False)
        # Update geometry to get accurate dimensions
        credentials_window.update_idletasks()
        root.update_idletasks()
        
        # Calculate position to center the window
        x = root.winfo_x() + (root.winfo_width() - credentials_window.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - credentials_window.winfo_height()) // 2
        
        # Set the new geometry with updated position
        credentials_window.geometry(f"+{x}+{y}")

        tk.Label(credentials_window, text=_("set_up_box1")).pack(pady=5)
        def open_spotify_developers():
            open_link("https://developer.spotify.com/dashboard")

        open_button = ttk.Button(credentials_window, text=_("Open Spotify for Developers"), command=open_spotify_developers)
        open_button.pack()
        tk.Label(credentials_window, text=_("set_up_box2")).pack(pady=10)

        tk.Label(credentials_window, text="Client ID:").pack(pady=(5,0))
        client_id_entry = ttk.Entry(credentials_window, width=50)
        client_id_entry.pack(pady=(0,5))

        tk.Label(credentials_window, text="Client Secret:").pack(pady=(5,0))
        client_secret_entry = ttk.Entry(credentials_window, width=50)
        client_secret_entry.pack(pady=(0,5))

        save_button = ttk.Button(credentials_window, text=_("Save Settings"), command=save_credentials)
        save_button.pack(pady=(10,5))

        error_label = tk.Label(credentials_window, text="", fg="red")
        error_label.pack()

        credentials_window.transient(root)
        credentials_window.grab_set()

        if os.name == 'nt':
            root.iconbitmap(bundle_path("icon.ico"))
            credentials_window.iconbitmap(bundle_path("icon.ico"))

        root.wait_window(credentials_window)

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    if(not config['CLIENT_ID'] or not config['CLIENT_SECRET']):
        timestamped_print("No credentials provided. Exiting.")
        sys.exit()
  
    refresh_settings()
    initialize_sp()
    load_schedule_to_table(False)
        
    if os.name == 'nt':
        root.iconbitmap(bundle_path("icon.ico"))
            
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
                root.title(f"Spotify Scheduler v{VER} | {now} {newupdate}")
        except Exception:
            pass

        root.after(100, title_loop, lastdate)

    def is_canonical(version):
        return re.match(r'^([1-9][0-9]*!)?(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*((a|b|rc)(0|[1-9][0-9]*))?(\.post(0|[1-9][0-9]*))?(\.dev(0|[1-9][0-9]*))?$', version) is not None

    def updatechecker_loop():
        global newupdate
        newupdate=""
        try:
            response = requests.get("https://api.github.com/repos/sandrzejewskipl/spotify-scheduler/releases/latest")
            if response:
                if response.json()["tag_name"]:
                    if is_canonical(VER) and is_canonical(response.json()["tag_name"]):
                        if version.parse(response.json()["tag_name"])>version.parse(VER):
                            newupdate=(f"| {_('A new update is available for download')}!")
                            timestamped_print(f"A new update is available for download at https://github.com/sandrzejewskipl/spotify-scheduler/releases/latest (latest {response.json()['tag_name']} vs current {VER})")
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
