import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime
from dotenv import load_dotenv
import time as t
import psutil
import sys
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
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

version="1.2.4"
config_file="config.json"
schedule_file="schedule.txt"
log_file="output.log"

current_pid = os.getpid()
parent_pid = psutil.Process(current_pid).parent().pid

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

def load_config():
    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        default = """{
    "LANG": "en",
    "CLIENT_ID": "",
    "CLIENT_SECRET": "",
    "PLAYLIST_ID": "",
    "DEVICE_NAME": "DESKTOP",
    "KILLSWITCH_ON": true,
    "WEEKDAYS_ONLY": true
}"""
        with open(config_file, "w") as schedule_file:
            schedule_file.write(default)
load_config()

# Load config
config = load_config()

CLIENT_ID = config['CLIENT_ID']
CLIENT_SECRET = config['CLIENT_SECRET']
PLAYLIST_ID = config['PLAYLIST_ID']
DEVICE_NAME = config['DEVICE_NAME']
KILLSWITCH_ON = config['KILLSWITCH_ON']
WEEKDAYS_ONLY = config['WEEKDAYS_ONLY']
LANG = config['LANG']

REDIRECT_URI = "http://localhost:8080"
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

def initialize_sp():
    global sp
    sp=None
    if CLIENT_ID!="" and CLIENT_SECRET!="":

        try:
            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID,client_secret=CLIENT_SECRET,redirect_uri=REDIRECT_URI,scope=SCOPE))
        except Exception as e:
            timestamped_print(f"Error during spotipy initalization: {e}")

def save_settings():
    global config, CLIENT_ID, CLIENT_SECRET, KILLSWITCH_ON, WEEKDAYS_ONLY, PLAYLIST_ID, DEVICE_NAME, LANG, setting_entries
    config['CLIENT_ID'] = setting_entries['CLIENT_ID'].get()
    config['CLIENT_SECRET'] = setting_entries['CLIENT_SECRET'].get()
    config['DEVICE_NAME'] = setting_entries['DEVICE_NAME'].get()
    config['LANG'] = language_var.get()
    config['KILLSWITCH_ON'] = setting_vars['KILLSWITCH_ON'].get()
    config['WEEKDAYS_ONLY'] = setting_vars['WEEKDAYS_ONLY'].get() 


    save_config(config)
    refresh_settings()
    config = load_config()
    CLIENT_ID = config['CLIENT_ID']
    CLIENT_SECRET = config['CLIENT_SECRET']
    PLAYLIST_ID = config['PLAYLIST_ID']
    DEVICE_NAME = config['DEVICE_NAME']
    KILLSWITCH_ON = config['KILLSWITCH_ON']
    WEEKDAYS_ONLY = config['WEEKDAYS_ONLY']
    LANG = config['LANG']
    initialize_sp()



    


# Creating a GUI window
root = tk.Tk()
root.title(f"Spotify Scheduler {version} | by @sandrzejewskipl")
root.geometry("800x600")


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
    import webbrowser
    webbrowser.open(url)
try:
    icon_image = Image.open(bundle_path("icon.ico"))
    icon_photo = ImageTk.PhotoImage(icon_image)
    icon_label = tk.Label(info_frame, image=icon_photo)
    icon_label.image = icon_photo  # Zachowaj referencję, aby zapobiec usunięciu przez Garbage Collector
    icon_label.pack(pady=10)
except Exception as e:
    print(f"Failed to load icon: {e}")    

info_text = tk.Text(info_frame, wrap="word", height=10, width=70, font=("Arial", 12))
info_text.pack(expand=True, pady=20, padx=20)

info_text.insert("insert", _( "Spotify Scheduler") + "\n", "header")
info_text.insert("insert", f"{_('Version')}: {version}\n")
info_text.insert("insert", f"{_('Author')}: ")
info_text.insert("insert", f"Szymon Andrzejewski\n", "link1")

info_text.insert("insert", f"{_('GitHub')}: ")
info_text.insert("insert", "https://github.com/sandrzejewskipl/Spotify-Scheduler\n", "link2")

info_text.insert("insert", f"\n{_('Made_with')}\n{_('Greetings')}")

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

# KILLSWITCH_ON and WEEKDAYS_ONLY
setting_vars['KILLSWITCH_ON'] = tk.BooleanVar(value=config.get('KILLSWITCH_ON', False))
ttk.Checkbutton(settings_frame, text=_("Killswitch"), variable=setting_vars['KILLSWITCH_ON']).grid(row=4, columnspan=2, pady=5)

setting_vars['WEEKDAYS_ONLY'] = tk.BooleanVar(value=config.get('WEEKDAYS_ONLY', False))
ttk.Checkbutton(settings_frame, text=_("Weekdays Only"), variable=setting_vars['WEEKDAYS_ONLY']).grid(row=5, columnspan=2, pady=5)

save_btn = ttk.Button(settings_frame, text=_("Save Settings"), command=save_settings)
save_btn.grid(row=6, columnspan=2, pady=20)

text_label = ttk.Label(settings_frame, text="EN: After changing the language, restart the application to apply the changes. \nPL: Po zmianie języka zrestartuj aplikację, aby zastosować zmiany.", foreground="green")
text_label.grid(row=7, columnspan=2, pady=10)

devices_list = tk.StringVar()
devices_list.set("")

devices_label = ttk.Label(settings_frame, textvariable=devices_list, wraplength=500, anchor="w")
devices_label.place(x=10, y=300)



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

def timestamped_print(message):
    current_time = datetime.now().isoformat(sep=" ", timespec="seconds")
    print(f"{current_time} | {message}")

def load_schedule_to_table():
    try:
        with open(schedule_file, "r") as file:
            lines = file.readlines()
            schedule_table.delete(*schedule_table.get_children())
            for line in lines:
                start_time, end_time = line.strip().split("-")
                schedule_table.insert("", "end", values=(start_time, end_time))
        timestamped_print("Schedule loaded into table.")
    except FileNotFoundError:
        timestamped_print("The file schedule.txt does not exist.")
    except Exception as e:
        timestamped_print(f"Error loading schedule: {e}")
        
def replace_schedule_with_default():
    try:
        default_data = """8:45-8:55
9:40-9:45
10:30-10:45
11:30-11:35
12:20-12:25
13:10-13:25
14:10-14:15"""
        with open(schedule_file, "w") as file:
            file.write(default_data)
        timestamped_print("Setting schedule to default.")
        load_schedule_to_table()

    except Exception as e:
        timestamped_print(f"Error while changing schedule: {e}")


def save_schedule_from_table():
    try:
        # Get all entries from table
        rows = []
        for row in schedule_table.get_children():
            start_time, end_time = schedule_table.item(row, "values")
            rows.append((start_time, end_time))

        # Sort entries by start time
        rows.sort(key=lambda x: datetime.strptime(x[0], "%H:%M"))

        # Save sorted entries to file
        with open(schedule_file, "w") as file:
            for start_time, end_time in rows:
                file.write(f"{start_time}-{end_time}\n")

        timestamped_print("The schedule has been saved.")
        load_schedule_to_table()
    except Exception as e:
        timestamped_print(f"Error during saving schedule: {e}")


def is_valid_time_format(time_str):
    time_pattern = r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"  # Hours: 00-23, Minutes: 00-59
    return re.match(time_pattern, time_str) is not None

def add_entry():
    start_time = (start_time_entry.get()).replace(';',':')
    end_time = (end_time_entry.get()).replace(';',':')

    if not is_valid_time_format(start_time):
        timestamped_print(f"Incorrect time format: {start_time}. Use HH:MM.")
        return

    if not is_valid_time_format(end_time):
        timestamped_print(f"Incorrect time format: {end_time}. Use HH:MM.")
        return

    start_dt = datetime.strptime(start_time, "%H:%M")
    end_dt = datetime.strptime(end_time, "%H:%M")

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
            schedule_table.delete(item)
        timestamped_print("The selected entry has been deleted.")
        save_schedule_from_table()
    else:
        timestamped_print("No entries have been marked for deletion.")

# dont know if it's doing something, 'dont want to break things xD
for widget in schedule_frame.winfo_children():
    widget.destroy()

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

end_time_label = ttk.Label(entry_frame, text=_("END_LABEL"))
end_time_label.pack(side="left", padx=5)
end_time_entry = ttk.Entry(entry_frame, width=10)
end_time_entry.pack(side="left", padx=5)

add_button = ttk.Button(entry_frame, text=_("Add Entry"), command=add_entry)
add_button.pack(side="left", padx=5)

delete_button = ttk.Button(entry_frame, text=_("Delete Selected"), command=delete_selected_entry)
delete_button.pack(side="left", padx=5)

# Buttons
button_frame = ttk.Frame(schedule_frame)
button_frame.pack(fill="x", padx=10, pady=10)

load_button = ttk.Button(button_frame, text=_("Reload Schedule"), command=load_schedule_to_table)
load_button.pack(side="left", padx=5)

save_button = ttk.Button(button_frame, text=_("Save Schedule"), command=save_schedule_from_table)
save_button.pack(side="right", padx=5)

is_paused = False

def toggle_pause():
    global is_paused
    is_paused = not is_paused
    status = _( "Paused") if is_paused else _( "Running")
    timestamped_print(f"App state: {status}")
    pause_button.config(text=_("Resume Automation") if is_paused else _("Pause Automation"))
    if not is_paused:
        pause_play_btn.config(text=_("Pause music and stop automation"))

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
    subprocess.run(["spotify"])

# Spotify button
spotify_button = ttk.Button(control_frame, text=_("Run Spotify"), command=run_spotify)
spotify_button.pack(side="left",)

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

# Restore default
replace_button = ttk.Button(button_frame, text=_("Restore default"), command=replace_schedule_with_default)
replace_button.pack(side="left", padx=5)

playlist_info = {
    "name": _("failed_to_fetch_data"),
    "owner": _("failed_to_fetch_data"),
    "image_url": ""
}

def get_playlist_info():
    global PLAYLIST_ID
    if PLAYLIST_ID!="":
        try:
            playlist = sp.playlist(PLAYLIST_ID)
            if playlist["name"]:
                playlist_info["name"] = playlist["name"]
            if playlist["owner"]:
                playlist_info["owner"] = playlist["owner"]['display_name']


            # Get playlist image url
            images = playlist.get("images", [])
            if images:
                playlist_info["image_url"] = images[0]["url"]
            else:
                playlist_info["image_url"] = ""

            timestamped_print(f"Playlist: {playlist_info['name']} Owner: {playlist_info['owner']}")
        except Exception as e:
            timestamped_print(f"Failed to retrieve playlist data: {e}")

def change_playlist():
    global PLAYLIST_ID
    global playlist_info
    user_input = playlist_entry.get().strip()
    if user_input!='':
        playlist_entry.delete(0, tk.END)
        # check if id/url
        PLAYLIST_ID = extract_playlist_id(user_input) if "open.spotify.com" in user_input else user_input
        if not PLAYLIST_ID:
            timestamped_print("Failed to extract playlist ID.")
            return
        playlist_info = {
            "name": _("The playlist has been changed but its data could not be retrieved."),
            "image_url": ""
        }
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}

        config['PLAYLIST_ID'] = PLAYLIST_ID

        # Save to config.json
        with open(config_file, "w") as f:
            json.dump(config, f, indent=4)
        display_playlist_info()
        pause_music()
    else:
        timestamped_print(f"Playlist ID can't be blank.")

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

# button
change_playlist_btn = ttk.Button(playlist_info_frame, text=_("Set Playlist"), command=change_playlist)
change_playlist_btn.grid(row=2, column=1, columnspan=2, pady=10)








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
        timestamped_print("User's playlist downloaded.")
    except Exception as e:
        timestamped_print(f"Error downloading user playlists: {e}")

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
        timestamped_print(f"Error selecting playlist: {e}")

# bind click
playlist_table.bind("<ButtonRelease-1>", select_playlist)

# load playlist button
load_playlists_btn = ttk.Button(playlist_frame, text=_("Refresh Playlists"), command=fetch_user_playlists)
load_playlists_btn.pack(side='left', pady=10, padx=10)




def display_playlist_info():
    get_playlist_info()

    playlist_label.config(text=f"{_('Playlist')}: {playlist_info['name']}\n{_('Owner')}: {playlist_info['owner']}")

    if playlist_info["image_url"]:
        response = requests.get(playlist_info["image_url"])
        if response.status_code == 200:
            img_data = BytesIO(response.content)
            img = Image.open(img_data)
            img = img.resize((150, 150))
            playlist_img = ImageTk.PhotoImage(img)

            playlist_image_label.config(image=playlist_img)
            playlist_image_label.image = playlist_img 
        else:
            playlist_image_label.config(text=_("Image not found"))
    else:
        playlist_image_label.image=""


# now playing label
now_playing_label = ttk.Label(now_playing_frame, text="", font=("Arial", 12))
now_playing_label.pack(padx=10, pady=10)

# cover photo
now_playing_image_label = ttk.Label(now_playing_frame)
now_playing_image_label.pack(padx=10, pady=10)

def checklist():
    try:
        devices = sp.devices()
        found_device = _("Device Not Found")
        volume = _("Check Manually")
        proces = _("Spotify Is Turned Off")
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
        
        if PLAYLIST_ID:
            playlist = _("Playlist Set", playlist_id=PLAYLIST_ID)
        else:
            playlist = _("Playlist Missing")

        for proc in psutil.process_iter():
            if PROCNAME.lower() in proc.name().lower():
                if (proc.pid!=current_pid) or (proc.pid!=parent_pid):
                    proces = _("Spotify Running")

        checklistvar.set(_("Checklist", process=proces, device=found_device, volume=volume, playlist=playlist))

    except Exception as ex:
        checklistvar.set(f"Problem z pobraniem danych: {ex}")


    


lastfetch=''

def update_now_playing_info():
    global lastfetch, playlist_name
    
    try:
        current_playback = sp.current_playback()
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

            playing_playlist = ''
            try:
                context = current_playback.get("context", {})
                playing_playlist = context.get("uri", "").split(":")[-1]
            except Exception as e:
                playing_playlist = _("no_playing_playlist")
            if lastfetch != playing_playlist:
                try:
                    lastfetch = playing_playlist
                    playlist_details = sp.playlist(playing_playlist)
                    if playlist_details:
                        playlist_name = playlist_details.get("name", "-")
                except Exception as e:
                    playlist_name = _("failed_to_fetch_data")
                
            playlist_info_str = f"{_('Playlist')}: {playlist_name}"
            
            # Now playing text
            now_playing_label.config(
                text=(
            f"{_('Title')}: {title}\n"
            f"{_('Artist')}: {artist}\n"
            f"{playlist_info_str}\n"
            f"{_('Device')}: {target_device_name}\n\n"
            f"{_('State')}: {playback_state}\n"
            f"{_('Schedule')}: {last_schedule.strip()}")
            )

            # Get and display cover photo
            album_images = track["album"].get("images", [])
            if album_images:
                response = requests.get(album_images[0]["url"])
                if response.status_code == 200:
                    img_data = BytesIO(response.content)
                    img = Image.open(img_data)
                    img = img.resize((200, 200))
                    now_playing_img = ImageTk.PhotoImage(img)

                    now_playing_image_label.config(image=now_playing_img)
                    now_playing_image_label.image = now_playing_img 

        else:
            now_playing_label.config(text=_("no_playback"))

    except Exception as e:
        now_playing_label.config(text=f"Error: {str(e)}")

    checklist()

    root.after(5000, update_now_playing_info)  # Refresh every 5 seconds

# Pause music and stop automation button
pause_play_btn = ttk.Button(now_playing_frame, text=_("Pause music and stop automation"), command=pauseandauto)
pause_play_btn.pack(padx=10, pady=10)

checklistvar = tk.StringVar()
checklistvar.set("")

# Checklist label
checklist_label = ttk.Label(now_playing_frame, textvariable=checklistvar, font=("Arial", 10))
checklist_label.pack(padx=10, pady=5)


# Spotipy main functions
def killswitch():
    if KILLSWITCH_ON:
        for proc in psutil.process_iter():
            if PROCNAME.lower() in proc.name().lower():
                if (proc.pid!=current_pid) or (proc.pid!=parent_pid):
                    proc.kill()
                    timestamped_print("Killed Spotify process")
                    status.set(_("Killed Spotify process"))

last_schedule=''
def is_within_schedule(schedule_file=schedule_file):
    global last_schedule
    try:
        with open(schedule_file, "r+") as file:
            lines = file.readlines()
            now = datetime.now().time()
            for line in lines:
                start_str, end_str = line.strip().split("-")
                start_time = datetime.strptime(start_str, "%H:%M").time()
                end_time = datetime.strptime(end_str, "%H:%M").time()
                if start_time <= now <= end_time:
                    weekno = datetime.today().weekday()
                    if WEEKDAYS_ONLY == "false":
                        weekno = 0
                    if weekno < 5:
                        last_schedule=line
                        return True
    except FileNotFoundError:
        timestamped_print(f"The file schedule.txt does not exist, it will be created now from default.")
        replace_schedule_with_default()
    except Exception as e:
        timestamped_print(f"Error during reading schedule: {e}")
    return False

def play_music():
    try:
        devices = sp.devices()
        if not devices["devices"]:
            status.set(_( "no_active_devices"))
            return

        target_device = None
        for device in devices["devices"]:
            if DEVICE_NAME in device["name"].upper():
                target_device = device["id"]
                timestamped_print(f"Found device: {device['name']}")
                break

        if target_device:
            sp.start_playback(device_id=target_device, context_uri=f"spotify:playlist:{PLAYLIST_ID}")
            timestamped_print(f"Music playing on device {target_device}.")
        else:
            timestamped_print(f"No device found with name {DEVICE_NAME}.")

    except Exception as ex:
        timestamped_print(f"Error while playing: {ex}")

def pause_music(retries=3, delay=2):
    attempt = 0
    while attempt < retries:
        try:
            current_playback = sp.current_playback()
            if current_playback and current_playback["is_playing"]:
                sp.pause_playback()
                timestamped_print("Playback has been paused.")
            status.set(_("out_of_schedule_paused"))
            return  # Zakończ funkcję, jeśli się udało
        except Exception as e:
            attempt += 1
            timestamped_print(f"Error occurred, retrying... ({attempt}/{retries}) {e}")
            t.sleep(delay)
    timestamped_print("Failed to pause playback after multiple attempts.")
    killswitch()


def main():
    global CLIENT_ID, CLIENT_SECRET, config
    
    if(not CLIENT_ID):
        print("Create an app here: https://developer.spotify.com/dashboard")
        CLIENT_ID = input("Enter CLIENT_ID: ")

    if(not CLIENT_SECRET):
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
            content = file.read() 
            print(f'{content}\n')
    except FileNotFoundError:
        replace_schedule_with_default()
        with open(schedule_file, 'r') as file:
            content = file.read() 
            print(f'{content}\n')
    except Exception as e:
        timestamped_print(f"Error during reading schedule: {e}")            
    t.sleep(5)   
    if os.name == 'nt':
        root.iconbitmap(bundle_path("icon.ico"))
    refresh_settings()
    initialize_sp()
    update_now_playing_info()
    load_schedule_to_table()
    display_playlist_info()
    fetch_user_playlists()
    pause_music()
    
    
    def loop():
        if not is_paused: 
            if is_within_schedule():
                try:
                    current_playback = sp.current_playback()
                    if not current_playback or not current_playback["is_playing"]:
                        if PLAYLIST_ID!='':
                            play_music()
                        else:
                            status.set(_("Playlist not set"))
                    else:
                        status.set(_("Music is currently playing."))
                except Exception as ex:
                    timestamped_print(f"Error getting playback status: {ex}")
            else:
                status.set(_("out_of_schedule"))
                pause_music()
                
        
        root.after(5000, loop)  # Loop every 5 seconds

    loop()

if __name__ == "__main__":
    root.after(0, main)
    root.mainloop()
