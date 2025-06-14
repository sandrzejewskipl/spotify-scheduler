import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime, timezone, timedelta
import time as t
import psutil
import sys
import tkinter as tk
from tkinter import ttk, font
from tkinter import filedialog, messagebox
import base64
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
import logging
from packaging import version
import locale
from platformdirs import PlatformDirs
from tkinter.messagebox import askyesno
import random

VER="1.13.0"
CONFIG_FILE="config.json"
SCHEDULE_FILE="schedule.txt"
DEFAULT_SCHEDULE_FILE='default-schedule.txt'
LOG_FILE="output.log"
SCHEDULE_PLAYLISTS_FILE = "schedule_playlists.json"
DATA_DIRECTORY = PlatformDirs(appname="spotify-scheduler", appauthor=False, ensure_exists=True).user_data_dir

try:
    current_pid = os.getpid()
    parent_pid = psutil.Process(current_pid).parent().pid
except Exception:
    parent_pid = None

def timestamped_print(message):
    current_time = datetime.now().isoformat(sep=" ", timespec="seconds")
    print(f"{current_time} | {message}")
 
def error(e):
    e = "Spotify Premium subscription is required" if "PREMIUM_REQUIRED" in str(e) else e
    string=f'\n\033[91m{e}\033[0m'
    return string

try:
    if os.name == 'nt':
        if sys.__stdout__:
            os.system('title Spotify Scheduler Console')
except Exception:
    pass

os.chdir(DATA_DIRECTORY)

# Check if schedule playlists file exists and contains "randomqueue". Fix for upgrading to v1.11.0 and later
if os.path.exists(SCHEDULE_PLAYLISTS_FILE):
    try:
        with open(SCHEDULE_PLAYLISTS_FILE, "r") as file:
            data = json.load(file)
            if not any("randomqueue" in entry for entry in data.values()):
                with open(SCHEDULE_PLAYLISTS_FILE, "w") as file:
                    json.dump({}, file, indent=4)
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
        "AUTO_SPOTIFY": True,
        "SKIP_EXPLICIT": False
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
        response = requests.post(url, headers=headers, data=data, timeout=5)
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
    global sp, spstatus, last_spotify_run
    sp=None
    REDIRECT_URI = "http://127.0.0.1:23918"
    SCOPE = "user-modify-playback-state user-read-playback-state playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative user-read-playback-position user-top-read user-read-recently-played user-read-email ugc-image-upload user-read-currently-playing app-remote-control streaming user-library-read user-library-modify user-follow-read user-follow-modify user-read-private"
    
    if config['CLIENT_ID']!="" and config['CLIENT_SECRET']!="":
        try:
            if validate_client_credentials():
                sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=config['CLIENT_ID'],client_secret=config['CLIENT_SECRET'],redirect_uri=REDIRECT_URI,scope=SCOPE, requests_timeout=5), retries=0, requests_timeout=5)
                spstatus=True
                fetch_user_playlists()
                timestamped_print("Spotipy initialized properly.")
                last_spotify_run=False
            else:
                sp = fake_sp()
                spstatus=False
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
        config['SKIP_EXPLICIT'] = setting_vars['SKIP_EXPLICIT'].get()

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

last_played_frame = ttk.Frame(notebook)
notebook.add(last_played_frame, text=_("Recently Played"))


frame_with_padding = ttk.Frame(last_played_frame)
frame_with_padding.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")


columns = ("played_at", "track_name", "artist_name")
last_played_table = ttk.Treeview(frame_with_padding, columns=columns, show="headings")
last_played_table.heading("played_at", text=_("Time"))
last_played_table.heading("track_name", text=_("Title"))
last_played_table.heading("artist_name", text=_("Artist"))


scrollbar = ttk.Scrollbar(frame_with_padding, orient="vertical", command=last_played_table.yview)
last_played_table.configure(yscrollcommand=scrollbar.set)


last_played_table.grid(row=0, column=0, sticky="nsew")
scrollbar.grid(row=0, column=1, sticky="ns")


frame_with_padding.grid_rowconfigure(0, weight=1)
frame_with_padding.grid_columnconfigure(0, weight=1)

def fetch_last_played_songs():
    try:
        results = sp.current_user_recently_played(limit=50)
        last_played_table.delete(*last_played_table.get_children())
        for item in results['items']:
            played_at = (str(item['played_at']).split('.')[0]).replace("Z","")
            utc_time = datetime.strptime(played_at, "%Y-%m-%dT%H:%M:%S")
                       
            local_now = datetime.now()
            local_tz = local_now.astimezone().tzinfo

            utc_time = utc_time.replace(tzinfo=timezone.utc)
            local_time = utc_time.astimezone(local_tz)
            
            track_name = item['track']['name']
            artist_name = item['track']['artists'][0]['name']
            last_played_table.insert("", "end", values=(local_time.strftime("%Y-%m-%d %H:%M:%S"), track_name, artist_name))
        lastplayedvar.set(_("Last refreshed at", date=datetime.now().strftime("%H:%M:%S")))

    except Exception as e:
        lastplayedvar.set(_("Error fetching recently played songs.", date=datetime.now().strftime("%H:%M:%S")))
        timestamped_print(f"Error fetching recently played songs: {error(e)}")


button_frame = ttk.Frame(last_played_frame)
button_frame.grid(row=1, column=0, sticky="sw", padx=10, pady=10)


last_played_frame.grid_rowconfigure(0, weight=1)
last_played_frame.grid_columnconfigure(0, weight=1)

fetch_last_played_btn = ttk.Button(button_frame, text=_("Refresh recently played"), command=fetch_last_played_songs)
fetch_last_played_btn.grid(row=0, column=0, sticky="w")

lastplayedvar = tk.StringVar()
lastplayedvar.set("sdf")

lastplayed_label = ttk.Label(button_frame, textvariable=lastplayedvar, font=("Arial", 10))
lastplayed_label.grid(row=0, column=1, padx=5, sticky="w")

import_export_frame = ttk.Frame(notebook)
notebook.add(import_export_frame, text=_("Import/Export"))

settings_frame = ttk.Frame(notebook)
notebook.add(settings_frame, text=_("Settings"))

console_frame = ttk.Frame(notebook)
notebook.add(console_frame, text=_("Console"))

info_frame = ttk.Frame(notebook)
notebook.add(info_frame, text=_("About"))

def export_playlist():
    try:
        # Ask user to select a playlist from the list or enter a URL/ID
        def do_export(playlist_input):
            playlist_id = playlist_input
            if "open.spotify.com" in playlist_input:
                playlist_id = extract_playlist_id(playlist_input)
            if "37i9dQ" in playlist_id:
                messagebox.showerror(_("Export Playlist"), _("You cannot export Spotify's curated playlists due to API limitations."))
                return
            if not playlist_id:
                messagebox.showerror(_("Export Playlist"), _("No playlist selected."))
                return
            
            tracks = []
            limit = 100
            offset = 0

            while True:
                results = sp.playlist_items(
                    playlist_id, 
                    fields="items(track(uri, name, artists(name))),total",
                    additional_types=['track'],
                    limit=limit, 
                    offset=offset
                )
                for item in results['items']:
                    track = item['track']
                    if track:
                        tracks.append({
                            "uri": track['uri'],
                            "name": track['name'],
                            "artists": [artist['name'] for artist in track['artists']]
                        })
                offset += limit
                if len(results['items']) < limit:
                    break
            track_uris = [track for track in tracks if ":local:" not in track.get("uri", "")] # remove local tracks
            # Get playlist name for metadata and default filename
            playlist_name = ""
            try:
                playlist_data = sp.playlist(playlist_id)
                playlist_name = playlist_data.get("name", "")
                total_tracks = playlist_data.get("tracks", {}).get("total", 0)
            except Exception:
                playlist_name = playlist_id
                total_tracks = 0

            # Sanitize playlist name for filename
            safe_name = re.sub(r'[\\/*?:"<>|]', "_", playlist_name) or "playlist"
            date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            default_filename = f"{safe_name}_{date_str}.json"

            export_file = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")],
                title=_("Export Playlist As"),
                initialfile=default_filename
            )
            if export_file:
                image_b64 = None
                try:
                    if playlist_data.get("images"):
                        image_url = playlist_data["images"][0].get("url")
                        if image_url:
                            response = requests.get(image_url, timeout=5)
                            if response.status_code == 200:
                                image_b64 = base64.b64encode(response.content).decode("utf-8")
                except Exception as e:
                    image_b64 = None

                export_data = {
                    "metadata": {
                        "original_name": playlist_name,
                        "exported_by": "Spotify Scheduler",
                        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "image_b64": image_b64
                    },
                    "tracks": track_uris
                }
                with open(export_file, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                messagebox.showinfo(
                    _("Export Playlist"),
                    _("Playlist exported successfully.") + f"\n{_('Tracks exported')}: {len(track_uris)}/{total_tracks}\n{_('File saved at')}: {export_file}"
                )
                timestamped_print(f"Exported playlist {playlist_id} to {export_file}")

        def on_select():
            user_input = playlist_var.get().strip()
            select_win.destroy()
            do_export(user_input)

        def on_entry_enter(event):
            on_select()

        # Fetch user playlists for selection
        playlists = []
        offset = 0
        limit = 50
        while True:
            try:
                response = sp.current_user_playlists(limit=limit, offset=offset)
                playlists.extend(response['items'])
                if len(response['items']) < limit:
                    break
                offset += limit
            except Exception:
                break

        select_win = tk.Toplevel(root)
        select_win.title(_("Select Playlist to Export"))
        select_win.geometry("600x400")
        select_win.resizable(False, False)
        # Set window icon if available
        try:
            if os.name == 'nt':
                select_win.iconbitmap(bundle_path("icon.ico"))
        except Exception:
            pass
        # Center the window relative to the root window
        select_win.update_idletasks()
        root.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - select_win.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - select_win.winfo_height()) // 2
        select_win.geometry(f"+{x}+{y}")

        ttk.Label(select_win, text=_("Choose from your playlists:")).pack(pady=10)

        playlist_var = tk.StringVar()
        # Frame for listbox and scrollbar
        listbox_frame = ttk.Frame(select_win)
        listbox_frame.pack(pady=5, padx=10, fill="both", expand=True)

        # Listbox with custom font and highlight
        custom_font = font.Font(family="Arial", size=10)
        playlist_listbox = tk.Listbox(
            listbox_frame,
            width=60,
            height=12,
            font=custom_font,
            selectbackground="#8BEBAD",
            selectforeground="black",
            activestyle="none",
            relief="flat",
            borderwidth=2,
            highlightthickness=1,
        )
        playlist_id_map = {}

        for idx, playlist in enumerate(playlists):
            display = f"{playlist['name']} ({playlist['id']})"
            playlist_listbox.insert(tk.END, display)
            playlist_id_map[idx] = playlist['id']
            # Set background color for even rows
            if idx % 2 == 0:
                playlist_listbox.itemconfig(idx, background="#e6e6e6")  # light gray for even

        # Add a scrollbar
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=playlist_listbox.yview)
        playlist_listbox.config(yscrollcommand=scrollbar.set)
        playlist_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Entry for manual input
        entry_frame = ttk.Frame(select_win)
        entry_frame.pack(pady=5)
        ttk.Label(entry_frame, text=_("Or enter playlist URL/ID:")).pack(side="left")
        entry = ttk.Entry(entry_frame, textvariable=playlist_var, width=35)
        entry.pack(side="left", padx=5)
        entry.bind('<Return>', on_entry_enter)

        def on_listbox_select(event):
            selection = playlist_listbox.curselection()
            if selection:
                idx = selection[0]
                playlist_var.set(playlist_id_map[idx])

        playlist_listbox.bind('<<ListboxSelect>>', on_listbox_select)

        ttk.Button(select_win, text=_("Export"), command=on_select).pack(pady=10)
        entry.focus_set()
        select_win.transient(root)
        select_win.grab_set()
        root.wait_window(select_win)

        # If user closed the window without selection, do nothing

    except Exception as e:
        messagebox.showerror(_("Export Playlist"), _("Failed to export playlist: ") + str(e))
        timestamped_print(f"Failed to export playlist: {error(e)}")

def import_playlist():
    try:
        import_file = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title=_("Import Playlist From")
        )
        if not import_file:
            return
        with open(import_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Check if file has Spotify Scheduler metadata
        if isinstance(data, dict) and "metadata" in data and "tracks" in data and "Spotify Scheduler" in data["metadata"].get("exported_by"):
            tracks = data["tracks"]
            original_name = data["metadata"].get("original_name", "")
            exported_at = data["metadata"].get("exported_at", "")
        else:
            messagebox.showerror(_("Import Playlist"), _("This file was not exported by Spotify Scheduler."))
            return

        if not tracks:
            messagebox.showerror(_("Import Playlist"), _("No tracks found in the imported file."))
            return

        # Show a dialog listing all tracks and count before proceeding
        def show_tracks_and_confirm():
            preview_win = tk.Toplevel(root)
            preview_win.title(_("Preview Imported Tracks"))
            preview_win.geometry("500x450")
            preview_win.resizable(False, False)
            # Set window icon if available
            try:
                if os.name == 'nt':
                    preview_win.iconbitmap(bundle_path("icon.ico"))
            except Exception:
                pass
            # Center the window relative to the root window
            preview_win.update_idletasks()
            root.update_idletasks()
            x = root.winfo_x() + (root.winfo_width() - preview_win.winfo_width()) // 2
            y = root.winfo_y() + (root.winfo_height() - preview_win.winfo_height()) // 2
            preview_win.geometry(f"+{x}+{y}")

            # If image_b64 is present, display image on the left, label_text on the right
            if data["metadata"].get("image_b64"):
                try:
                    img_bytes = base64.b64decode(data["metadata"]["image_b64"])
                    img = Image.open(BytesIO(img_bytes))
                    img = img.resize((100, 100))
                    img_tk = ImageTk.PhotoImage(img)
                except Exception:
                    img_tk = None
                frame = ttk.Frame(preview_win)
                frame.pack(pady=(10, 5))
                if img_tk:
                    img_label = ttk.Label(frame, image=img_tk)
                    img_label.image = img_tk
                    img_label.pack(side="left", padx=(0, 10))
                label_text = f"{original_name}\n"
                label_text += f"{_('Tracks')}: {len(tracks)}\n"
                label_text += f"\n{_('Exported at')}: {exported_at}"
                label = ttk.Label(frame, text=label_text,
                                 font=("Arial", 11, "bold"), justify="left")
                label.pack(side="left", anchor="n")
            else:
                label_text = f"{original_name}\n"
                label_text += f"{_('Tracks')}: {len(tracks)}\n"
                label_text += f"\n{_('Exported at')}: {exported_at}"
                ttk.Label(preview_win, text=label_text, font=("Arial", 11, "bold")).pack(pady=(10, 5))

            # Frame for listbox and scrollbar
            listbox_frame = ttk.Frame(preview_win)
            listbox_frame.pack(padx=10, pady=5, fill="both", expand=True)

            # Listbox for track names
            listbox = tk.Listbox(listbox_frame, width=65, height=15)
            listbox.pack(side="left", fill="both", expand=True)

            # Scrollbar for the listbox
            scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
            scrollbar.pack(side="right", fill="y")
            listbox.config(yscrollcommand=scrollbar.set)

            for idx, track in enumerate(tracks, 1):
                name = track.get("name", "Unknown")
                artists = ", ".join(track.get("artists", []))
                listbox.insert(tk.END, f"{idx}. {name} - {artists}")

            # Continue button
            def proceed():
                preview_win.destroy()
                ask_for_name_and_import()

            ttk.Button(preview_win, text=_("Continue Import"), command=proceed).pack(pady=10)
            preview_win.transient(root)
            preview_win.grab_set()
            root.wait_window(preview_win)

        # Ask for playlist name and import
        def ask_for_name_and_import():
            def on_create():
                name = name_var.get().strip()
                if not name:
                    name_label.config(foreground="red")
                    return
                import_win.destroy()
                # Create playlist and add tracks
                try:
                    if not user_id:
                        uid = sp.me()['id']
                    else:
                        uid = user_id
                    new_playlist = sp.user_playlist_create(user=uid, name=name, public=False, description=f"📥 Imported by Spotify Scheduler v{VER} on {datetime.now()}")
                    uris = [track['uri'] for track in tracks if 'uri' in track]
                    # Spotify API: max 100 tracks per request
                    for i in range(0, len(uris), 100):
                        sp.playlist_add_items(new_playlist['id'], uris[i:i+100])
                    # Set playlist image if available in import file
                    image_b64 = data["metadata"].get("image_b64")
                    # Check if image_b64 is a valid Base64-encoded JPEG image string and <= 256 KB
                    if image_b64:
                        try:
                            img_bytes = base64.b64decode(image_b64)
                            if len(img_bytes) <= 256 * 1024:
                                img = Image.open(BytesIO(img_bytes))
                                if img.format == "JPEG":
                                    sp.playlist_upload_cover_image(new_playlist['id'], str(image_b64))
                                else:
                                    timestamped_print("Imported image is not a JPEG. Skipping cover upload.")
                            else:
                                timestamped_print("Imported image exceeds 256 KB. Skipping cover upload.")
                        except Exception as e:
                            timestamped_print(f"Failed to set playlist image: {error(e)}")
                    timestamped_print(f"Imported {import_file} to new playlist {new_playlist['id']}")
                    messagebox.showinfo(_("Import Playlist"), _("Playlist imported successfully."))
                    fetch_user_playlists()
                except Exception as e:
                    timestamped_print(f"Failed to import playlist: {error(e)}")
                    messagebox.showerror(_("Import Playlist"), _("Failed to import playlist: ") + str(e))

            import_win = tk.Toplevel(root)
            import_win.title(_("Import Playlist"))
            import_win.geometry("350x150")
            import_win.resizable(False, False)
            # Set window icon if available
            try:
                if os.name == 'nt':
                    import_win.iconbitmap(bundle_path("icon.ico"))
            except Exception:
                pass
            # Center the window relative to the root window
            import_win.update_idletasks()
            root.update_idletasks()
            x = root.winfo_x() + (root.winfo_width() - import_win.winfo_width()) // 2
            y = root.winfo_y() + (root.winfo_height() - import_win.winfo_height()) // 2
            import_win.geometry(f"+{x}+{y}")

            ttk.Label(import_win, text=_("Playlist name:")).pack(pady=(10, 0))
            default_name = original_name if original_name else _("Imported Playlist")
            name_var = tk.StringVar(value=default_name)
            name_entry = ttk.Entry(import_win, textvariable=name_var, width=40)
            name_entry.pack(pady=5)
            name_label = ttk.Label(import_win, text="")
            name_label.pack()
            ttk.Button(import_win, text=_("Create Playlist"), command=on_create).pack(pady=10)
            import_win.transient(root)
            import_win.grab_set()
            root.wait_window(import_win)

        show_tracks_and_confirm()

    except Exception as e:
        timestamped_print(f"Failed to import playlist: {error(e)}")
        messagebox.showerror(_("Import Playlist"), _("Failed to import playlist: ") + str(e))


# Centered container with padding
container = ttk.Frame(import_export_frame)
container.pack(expand=True, fill="both", padx=0, pady=0)

# Title label
title_label = ttk.Label(container, text=_("Import/Export Playlists"), font=("Arial", 16, "bold"))
title_label.pack(pady=(30, 10))

# Description
desc_label = ttk.Label(
    container,
    text=_("Easily import or export your playlists as JSON files. Exported playlists can be shared or backed up. Imported playlists will be created in your Spotify account."),
    wraplength=600,
    font=("Arial", 11)
)
desc_label.pack(pady=(0, 20))

# Buttons frame
btns_frame = ttk.Frame(container)
btns_frame.pack(pady=10)

import_btn = ttk.Button(btns_frame, text=_("Import Playlist (from file)"), command=import_playlist)
import_btn.grid(row=0, column=0, padx=15, ipadx=10, ipady=5)

export_btn = ttk.Button(btns_frame, text=_("Export Playlist (to file)"), command=export_playlist)
export_btn.grid(row=0, column=1, padx=15, ipadx=10, ipady=5)

# Info box
info_box = ttk.LabelFrame(container, text=_("How it works"), padding=(15, 10))
info_box.pack(pady=(30, 10), padx=40, fill="x")

info_text = (
    f"• {_('Export Playlist')}: {_('Select a playlist from your account or paste a playlist link/ID. The playlist will be saved as a JSON file.')}\n"
    f"• {_('Import Playlist')}: {_('Choose a previously exported JSON file. The playlist will be created in your Spotify account.')}\n"
    f"• {_('Note')}: {_('Only playlists exported by Spotify Scheduler can be imported.')}"
)
info_label = ttk.Label(info_box, text=info_text, wraplength=550, font=("Arial", 10))
info_label.pack()

# Add some spacing at the bottom
container.pack_propagate(False)
container.configure(height=350)

LOG_FILE = open(LOG_FILE, "a", encoding="utf-8")

console_text = tk.Text(console_frame, wrap="word", height=20, width=100, font=("Arial", 10))
console_text.pack(side="left", expand=True, fill="both", padx=10, pady=10)

console_scrollbar = ttk.Scrollbar(console_frame, orient="vertical", command=console_text.yview)
console_scrollbar.pack(side="right", fill="y")

console_text.configure(yscrollcommand=console_scrollbar.set)

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

info_text.insert("insert", f"\n{_('github_star')}\n\nMIT License - © 2025 Szymon Andrzejewski")

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

# Button to set input to device name
def set_device_name():
    setting_entries['DEVICE_NAME'].delete(0, tk.END)
    setting_entries['DEVICE_NAME'].insert(0, platform.node())
    on_settings_change()

if hasattr(platform, "node"):
    set_device_btn = ttk.Button(settings_frame, text=_("This device"), command=set_device_name)
    set_device_btn.grid(row=3, column=2, padx=5, pady=5)

# SWITCHES
setting_vars['KILLSWITCH_ON'] = tk.BooleanVar(value=config.get('KILLSWITCH_ON', False))
ttk.Checkbutton(settings_frame, text=_("Killswitch"), variable=setting_vars['KILLSWITCH_ON']).grid(row=5, columnspan=2, pady=5,padx=5)

setting_vars['WEEKDAYS_ONLY'] = tk.BooleanVar(value=config.get('WEEKDAYS_ONLY', False))
ttk.Checkbutton(settings_frame, text=_("Weekdays Only"), variable=setting_vars['WEEKDAYS_ONLY']).grid(row=4, columnspan=2, pady=5,padx=5)

setting_vars['AUTO_SPOTIFY'] = tk.BooleanVar(value=config.get('AUTO_SPOTIFY', False))
ttk.Checkbutton(settings_frame, text=_("Auto Spotify"), variable=setting_vars['AUTO_SPOTIFY']).grid(row=6, columnspan=2, pady=5,padx=5)

setting_vars['SKIP_EXPLICIT'] = tk.BooleanVar(value=config.get('SKIP_EXPLICIT', False))
ttk.Checkbutton(settings_frame, text=_("Skip explicit tracks"), variable=setting_vars['SKIP_EXPLICIT']).grid(row=7, columnspan=2, pady=5,padx=5)

buttons_frame = ttk.Frame(settings_frame)
buttons_frame.grid(row=8, column=0, columnspan=2, pady=10)

save_btn = ttk.Button(buttons_frame, text=_("Save Settings"), command=save_settings)
save_btn.pack(side="left", padx=5)

deletecache_btn = ttk.Button(buttons_frame, text=_("Delete cache (logout)"), command=delete_spotify_cache)
deletecache_btn.pack(side="left", padx=5)

settingsstatus_text = tk.StringVar()
settingsstatus_text.set("")

settingsstatus = ttk.Label(settings_frame, textvariable=settingsstatus_text, wraplength=500, anchor="w")
settingsstatus.grid(row=9, columnspan=2, padx=10)

def on_settings_change(*args):
    # Check if any setting differs from config
    unsaved = False
    # Check language
    if language_var.get() != config.get('LANG', 'en'):
        unsaved = True
    # Check entries
    for key, entry in setting_entries.items():
        if entry.get() != str(config.get(key, "")):
            unsaved = True
    # Check checkboxes
    for key, var in setting_vars.items():
        if var.get() != config.get(key, False):
            unsaved = True
    if unsaved:
        settingsstatus_text.set(_("Unsaved changes"))
    else:
        settingsstatus_text.set("")

# Bind changes for language
language_var.trace_add("write", on_settings_change)
# Bind changes for entries
for entry in setting_entries.values():
    entry.bind("<KeyRelease>", lambda e: on_settings_change())
# Bind changes for checkboxes
for var in setting_vars.values():
    var.trace_add("write", on_settings_change)

devices_list = tk.StringVar()
devices_list.set("")

devices_label = ttk.Label(settings_frame, textvariable=devices_list, wraplength=500, anchor="w")
devices_label.grid(row=10, columnspan=2, pady=10, padx=10, sticky='w')

last_loaded_schedule=""
def load_schedule_to_table(printstatus=True):
    global last_loaded_schedule
    try:
        with open(SCHEDULE_FILE, "r") as file:
            lines = file.readlines()
            last_loaded_schedule=lines
            schedule_table.delete(*schedule_table.get_children())
            try:
                default_font = font.nametofont("TkDefaultFont").copy()
                default_font.configure(weight="bold")
                schedule_table.tag_configure("blue", foreground="blue", font=default_font)
            except Exception:
                pass
            for line in lines:
                if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?-([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$", line.strip()):
                    start_time, end_time = line.strip().split("-")
                    start_time_formatted = datetime.strptime(start_time, "%H:%M:%S" if ":" in start_time and start_time.count(":") == 2 else "%H:%M").time()
                    end_time_formatted = datetime.strptime(end_time, "%H:%M:%S" if ":" in end_time and end_time.count(":") == 2 else "%H:%M").time()
                    if start_time_formatted > end_time_formatted:
                        schedule_table.insert("", "end", values=(start_time, end_time), tags=("blue",))
                    else:
                        schedule_table.insert("", "end", values=(start_time, end_time))
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
                    new_data={"default": data["default"]}
                json_file.seek(0)
                json_file.truncate()
                json.dump(new_data, json_file, indent=4)
        else:
            with open(SCHEDULE_PLAYLISTS_FILE, "w") as json_file:
                json.dump(new_data, json_file, indent=4)
    except Exception as e:
        timestamped_print(f"Error during saving playlists file: {error(e)}")
def get_value_for_schedule(key=None,value="playlist"): #value should be playlist or randomqueue
    global last_schedule, SCHEDULE_PLAYLISTS_FILE
    if key==None:
        key=is_within_schedule()
    if key:
        try:
            with open(SCHEDULE_PLAYLISTS_FILE, "r") as file:
                data = json.load(file)
                key = key.strip()
                if key in data and value in data[key]:
                    return data[key][value]

                elif "default" in data and value in data["default"]:
                    return data["default"][value]
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

    if start_dt==end_dt:
        schedulevar.set(_("Error: Start and end time cannot be the same."))
        timestamped_print("Start and end time cannot be the same.")
        return
    
    # if end_dt <= start_dt:
    #     schedulevar.set(_("Error: End time must be later than start time."))
    #     timestamped_print("Error: End time must be later than start time.")
    #     return

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
start_time_label.pack(side="left")
start_time_entry = ttk.Entry(entry_frame, width=10)
start_time_entry.pack(side="left", padx=5)
start_time_entry.bind('<Return>', add_entry)

end_time_label = ttk.Label(entry_frame, text=_("END_LABEL"))
end_time_label.pack(side="left", padx=(10,0))
end_time_entry = ttk.Entry(entry_frame, width=10)
end_time_entry.pack(side="left", padx=5)
end_time_entry.bind('<Return>', add_entry)

delete_button = ttk.Button(entry_frame, text=_("Delete Selected"), command=delete_selected_entry)
delete_button.pack(side="right")

add_button = ttk.Button(entry_frame, text=_("Add Entry"), command=add_entry)
add_button.pack(side="right", padx=5)



schedulevar = tk.StringVar()
schedulevar.set("")

# Checklist label
schedule_label = ttk.Label(schedule_frame, textvariable=schedulevar, font=("Arial", 10))
schedule_label.pack(fill="x", padx=10)

# Buttons
button_frame = ttk.Frame(schedule_frame)
button_frame.pack(fill="x", padx=5, pady=10)

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
        return {"default": {"playlist": "", "randomqueue": False}} 
    
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
    try:
        global schedule, schedule_playlists
        schedule = playlist_read_schedule_file()
        schedule_playlists = load_schedule_playlists()

        schedule_with_ids = []
        for hour in schedule:
            playlist_id = get_playlist_gui_string(hour)
            if playlist_id==_("same as default"):
                schedule_with_ids.append(f"{hour} ({_("same as default")})")
            else:
                randomqueue_status = f"" 
                if checkifrandomqueue(hour) and "37i9dQ" not in playlist_id:
                    randomqueue_status = f", {_('Random queue')}" 
                schedule_with_ids.append(f"{hour} ({_('Playlist')}: {playlist_id}{randomqueue_status})")
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
    except Exception as e:
        timestamped_print(f"Failed to refresh playlist gui: {error(e)}")


def get_playlist_gui_string(hour):
    default_text={"playlist": _("same as default"), "randomqueue": False}

    if hour=="default":
        default_text={"playlist": _("No ID set"), "randomqueue": False}

    if schedule_playlists.get(hour) and not "playlist" in schedule_playlists.get(hour):
        return _("same as default")
    else:
        if schedule_playlists.get(hour, default_text)["playlist"]:
            return schedule_playlists.get(hour, default_text)["playlist"]
        else:
            if hour=="default":
                return _("No ID set")
            return ("same as default")

def checkifrandomqueue(key):
    if not (schedule_playlists.get(key) and "playlist" in schedule_playlists.get(key)):
        key="default"
    if schedule_playlists.get(key) and "randomqueue" in schedule_playlists.get(key):
        return schedule_playlists.get(key)["randomqueue"]
    else:
        return False

# Function to update the view based on the selected time
def update_view_for_time(*args):
    current_time = selected_time.get()

    hour = current_time.split("(")[0].rstrip(" ")
    PLAYLIST_ID = get_value_for_schedule(key=hour,value="playlist")
    
    randomqueue_var.set(checkifrandomqueue(hour))
    randomqueue_checkbox.config(text=_("Random queue"))
    if("37i9dQ" in PLAYLIST_ID):
        randomqueue_checkbox.config(state="disabled")
        randomqueue_var.set(False)
        randomqueue_checkbox.config(text=_("Random queue"))
    elif(schedule_playlists.get(hour) and "playlist" in schedule_playlists.get(hour)):
        randomqueue_checkbox.config(state="enabled")
    else:
        randomqueue_checkbox.config(state="disabled")

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
        playlist_table.selection_remove(playlist_table.selection())
        PLAYLIST_ID = extract_playlist_id(user_input) if "open.spotify.com" in user_input else user_input

        if not PLAYLIST_ID:
            timestamped_print("Failed to extract playlist ID.")
            return
        playlist_info = {
            "name": _("The playlist has been changed but its data could not be retrieved."),
            "image_url": ""
        }
        schedule_playlists.setdefault(current_time, {})
        schedule_playlists[current_time]["playlist"] = PLAYLIST_ID
        if not "randomqueue" in schedule_playlists[current_time]:
            schedule_playlists[current_time]["randomqueue"] = False
        save_schedule_playlists()
        playliststatus_text.set(_(""))
        timestamped_print(f"Playlist for {current_time} updated to {PLAYLIST_ID}.")
        refresh_playlist_gui(current_time)
        spotify_main()
    else:
        playliststatus_text.set(_("Playlist ID can't be blank."))
        timestamped_print(f"Playlist ID can't be blank.")

def change_randomqueue():
    global playlist_info
    current_time = selected_time.get().split("(")[0].rstrip(" ") 

    schedule_playlists.setdefault(current_time, {})
    schedule_playlists[current_time]["randomqueue"] = randomqueue_var.get() 
    save_schedule_playlists()
    playliststatus_text.set(_(""))
    randomqueue_status = 'Enabled' if schedule_playlists[current_time]["randomqueue"] else 'Disabled'
    timestamped_print(f"Random queue for {current_time} changed to {randomqueue_status}")
    refresh_playlist_gui(current_time)
    spotify_main()

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

time_dropdown = ttk.Combobox(time_selection_frame, textvariable=selected_time, state="readonly", values=schedule, width=80, height=20)
time_dropdown.pack(side="left")
time_dropdown.bind("<<ComboboxSelected>>", update_view_for_time)

# Set default as selected time
if schedule:
    selected_time.set(schedule[0])

def get_spotify_playlist(id=None):
    if not id:
        return None
    
    if("37i9dQ" in id):
        return {"name": f"{_("Unknown")}", "owner": {"display_name": f"Spotify"}, "scheduler_warning": True, "images": []}
    return sp.playlist(id)

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
            if "scheduler_warning" in playlist:
                playlist_info["scheduler_warning"] = playlist["scheduler_warning"]


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

# Random queue checkbox
randomqueue_var = tk.BooleanVar()
randomqueue_checkbox = ttk.Checkbutton(buttons_frame, text=_("Random queue"), variable=randomqueue_var, command=change_randomqueue, state="disabled")
randomqueue_checkbox.pack(side="left", padx=5)

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
user_id=None
def fetch_user_playlists():
    global username, user_id
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
        display_name=""
        email=""
        if "display_name" in user:
            display_name=user['display_name']
        if "email" in user:
            email=f"({user['email']})"
        if "id" in user:
            user_id=user['id']
        if display_name or email:
            username=(f"{_('Logged in as')}: {display_name} {email}")
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
            playlistsvar.set(f"{_('fetched_playlists', length=len(playlists), total=total, date=datetime.now().strftime('%H:%M:%S'))}")
    except Exception as e:
        playlistsvar.set(f"{_('Error fetching playlists.', date=datetime.now().strftime('%H:%M:%S'))}")
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
    warning=""
    if "scheduler_warning" in playlist_info:
        warning=f"\n\n{_("Title & Random Queue not available due to API limitations for Spotify's curated playlists.")}"

    playlist_label.config(text=f"{_('Playlist')}: {playlist_info['name']}\n{_('Owner')}: {playlist_info['owner']}{warning}")

    if playlist_info["image_url"]:
        response = requests.get(playlist_info["image_url"], timeout=5)
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
    try:
        devices = cached_spotify_data("devices")
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
        PLAYLIST_ID=get_value_for_schedule(key="default",value="playlist")
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

def char_limit(s):
    return s[:50] + ("..." if len(s) > 50 else "")
    
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
        current_playback = cached_spotify_data("current_playback")
        devices = cached_spotify_data("devices")

        # Get active device
        target_device_name = _("No device")
        device_list=''
        webplayer=""
        if devices and "devices" in devices:
            for device in devices["devices"]:
                name = device.get("name", _("Unknown device"))
                if "web player" not in name.lower():
                    device_list+=(f"• {name} ")
                else:
                    webplayer="\n"+_("Web players were detected but are not supported.")+"\n"
                if device.get("is_active"):
                    target_device_name = name
        devices_string=f"{username}\n\n{_('Detected devices')}:\n{device_list}\n{webplayer}"
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
                    playlist_info_str = f"{_('Playlist')}: {char_limit(playlist_name)}"
                if failed:
                    lasttype="album"
                    lastalbum=album['name']
                    playlist_info_str = f"{_('Album')}: {char_limit(album['name'])}"
            
            if not playlist_info_str:
                playlist_info_str=_("failed_to_fetch_data")
            # Now playing text
            now_playing_label.config(
                text=(
            f"{_('Title')}: {char_limit(title)}\n"
            f"{_('Artist')}: {char_limit(artist)}\n"
            f"{playlist_info_str}\n"
            f"{_('Device')}: {target_device_name}\n\n"
            f"{_('State')}: {playback_state}\n"
            f"{_('Time slot')}: {last_schedule.strip()}")
            )

            # Get and display cover photo
            if lastresponse!=track["album"]:
                album_images = track["album"].get("images", [])
                if album_images:
                    response = requests.get(album_images[0]["url"], timeout=5)
                    if response.status_code == 200:
                        img_data = BytesIO(response.content)
                        img = Image.open(img_data)
                        lastresponse=track["album"]
                    else:
                        img = Image.new("RGB", (200, 200), "lightgrey")
                else:
                    img = Image.new("RGB", (200, 200), "lightgrey")

                img = img.resize((200, 200))
                now_playing_img = ImageTk.PhotoImage(img)
                now_playing_image_label.config(image=now_playing_img)
                now_playing_image_label.image = now_playing_img 
        else:
            now_playing_label.config(text=_("no_playback"))
            now_playing_image_label.image=None

    except Exception as e:
        timestamped_print(f"Error during updating now playing info: {error(e)}")
        now_playing_label.config(text=_("failed_to_fetch_data"))
        now_playing_image_label.config(image="")
        now_playing_image_label.image = None

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
last_delay=None
closest_start_time=None
earliest_start_time=None
empty_schedule=None
def is_within_schedule():
    match=False
    global last_schedule, last_endtime, closest_start_time, last_delay, empty_schedule, earliest_start_time, last_loaded_schedule
    last_schedule=''
    try:
        with open(SCHEDULE_FILE, "r+") as file:
            lines = file.readlines()
            now = datetime.now().time()
            closest_start_time = None
            earliest_start_time=None
            last_endtime=None
            empty_schedule=True
            for line in lines:
                if re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?-([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$", line.strip()):
                    empty_schedule=False
                    start_str, end_str = line.strip().split("-")
                    start_time = datetime.strptime(start_str, "%H:%M:%S" if ":" in start_str and start_str.count(":") == 2 else "%H:%M").time()
                    end_time = datetime.strptime(end_str, "%H:%M:%S" if ":" in end_str and end_str.count(":") == 2 else "%H:%M").time()
                    if start_time <= end_time:
                        if start_time <= now <= end_time and (not config['WEEKDAYS_ONLY'] or datetime.today().weekday() < 5):
                            last_schedule=line
                            match=line.strip()
                            if last_endtime is None or last_endtime<datetime.combine(datetime.now(), end_time):
                                last_endtime=datetime.combine(datetime.now(), end_time)
                    else:  # Handle overnight schedules
                        if (start_time <= now or now <= end_time) and (not config['WEEKDAYS_ONLY'] or datetime.today().weekday() < 5):
                            last_schedule=line
                            match = line.strip()
                            if last_endtime is None or last_endtime < datetime.combine(datetime.now(), end_time):
                                if start_time < now:
                                    last_endtime = datetime.combine(datetime.now(), end_time) + timedelta(days=1)
                                else:
                                    last_endtime = datetime.combine(datetime.now(), end_time)

                    if start_time > now and (closest_start_time is None or start_time < closest_start_time):
                        closest_start_time = start_time
                    if earliest_start_time is None or start_time < earliest_start_time:
                        earliest_start_time = start_time
            if last_endtime:
                last_delay=last_endtime
            if match:
                closest_start_time=None
            if not closest_start_time:
                closest_start_time=earliest_start_time
            if last_loaded_schedule!=lines:
                try:
                    load_schedule_to_table(False)
                except Exception:
                    pass
    except FileNotFoundError:
        timestamped_print(f"Schedule file does not exist, it will be created now from default.")
        replace_schedule_with_default()
    except Exception as e:
        timestamped_print(f"Error during reading schedule: {error(e)}")
    return match

last_playlist=''
last_randomqueue=None
def play_music():
    global last_playlist, last_spotify_run, closest_start_time, last_randomqueue, user_id
    try:
        if target_device:
            PLAYLIST_ID=get_value_for_schedule(value="playlist")
            if PLAYLIST_ID:
                closest_start_time=None
                randomqueue=get_value_for_schedule(value="randomqueue")
                playlist_info=get_playlist_info(PLAYLIST_ID)
                if (randomqueue and "37i9dQ" not in PLAYLIST_ID):
                    name=playlist_info['name']
                    tracks = []
                    limit = 100
                    offset = 0

                    while True:
                        results = sp.playlist_items(
                            PLAYLIST_ID, 
                            fields="items(track(uri)),total", 
                            additional_types=['track'], 
                            limit=limit, 
                            offset=offset
                        )
                        tracks.extend([item['track']['uri'] for item in results['items']])
                        offset += limit
                        if len(results['items']) < limit:
                            break
                    track_uris = [track for track in tracks if ":local:" not in track] # remove local tracks
                    if not track_uris:
                        status.set(_("No tracks found in playlist"))
                        return
                    random.shuffle(track_uris)
                    if not user_id:
                        user_id = sp.me()['id']
                    temp_playlist = sp.user_playlist_create(user=user_id, name=f"{name} ({_("Random queue")})", description=f"🔀 Generated by Spotify Scheduler v{VER} on {datetime.now()}", public=False)
                    sp.current_user_unfollow_playlist(temp_playlist['id'])
                    sp.playlist_add_items(temp_playlist['id'], track_uris[:100])
                    sp.start_playback(device_id=target_device["id"], context_uri=f"spotify:playlist:{temp_playlist['id']}")
                else:
                    sp.start_playback(device_id=target_device["id"], context_uri=f"spotify:playlist:{PLAYLIST_ID}")

                last_playlist=PLAYLIST_ID
                last_randomqueue=randomqueue
                randomqueue_status = 'Enabled' if (randomqueue and "37i9dQ" not in PLAYLIST_ID) else 'Disabled'
                string=""
                if playlist_info:
                    string=f"Playlist: {playlist_info['name']}, Owner: {playlist_info['owner']}"
                timestamped_print(f"Music playing on {target_device['name']}. Random queue: {randomqueue_status}. {string}")
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
    global last_delay, last_spotify_run
    last_spotify_run = False

    if not spstatus:
        killswitch("Pausing music - Spotipy not initialized.")
        return
    
    attempt = 0
    while attempt < retries:
        try:
            took_time=datetime.now()

            current_playback = cached_spotify_data("current_playback", True)

            if current_playback and "is_playing" in current_playback:
                if current_playback["is_playing"]:
                    sp.pause_playback()
                    delay=""
                    if last_delay:
                        delay=f"(Delay: {round(((datetime.now()-last_delay).total_seconds()),2)}s)"
                        last_delay=None
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

def spotify_main():
    global last_playlist, target_device
    if not is_paused:
        if not sp or not spstatus:
            initialize_sp()
        if is_within_schedule():
            try:
                current_playback = cached_spotify_data("current_playback")
                devices = cached_spotify_data("devices")

                target_device = None
                active_device = None
                if devices and "devices" in devices:
                    for device in devices["devices"]:
                        if config['DEVICE_NAME'].lower() in device["name"].lower():
                            target_device = device
                        if device.get("is_active"):
                            active_device = device
                    
                PLAYLIST_ID=get_value_for_schedule(value="playlist")
                randomqueue=get_value_for_schedule(value="randomqueue")
                if (not current_playback) or (not current_playback["is_playing"]) or (not last_playlist==PLAYLIST_ID) or (target_device["id"]!=active_device["id"]) or (last_randomqueue!=randomqueue):
                    if PLAYLIST_ID:
                        play_music()
                    else:
                        status.set(_("Playlist not set"))
                else:
                    status.set(_("Music is currently playing."))
                    try:
                        if config['SKIP_EXPLICIT'] and current_playback and current_playback["item"].get("explicit"):
                            sp.next_track(device_id=target_device["id"])
                            status.set(_("Skipped explicit song"))
                            timestamped_print(f"Skipped explicit song: {current_playback['item']['artists'][0]['name']} - {current_playback['item']['name']} ")
                    except Exception as e:
                        timestamped_print(f"Error skipping explicit song: {error(e)}")

            except Exception as ex:
                timestamped_print(f"Error getting playback status: {error(ex)}")
                if ("token" in str(ex)) or ("Expecting value" in str(ex)):
                    delete_spotify_cache(str(ex))
        else:
            status.set(_("out_of_schedule"))
            pause_music()
    else:
        status.set(_("Automation is paused"))
    update_now_playing_info()

cache = {
    "current_playback": {"data": None, "timestamp": 0},
    "devices": {"data": None, "timestamp": 0}
}
def cached_spotify_data(data_type, force=False):
    """
    data_type: "current_playback" or "devices"
    """
    if data_type not in cache:
        raise ValueError("Invalid data_type. Use 'current_playback' or 'devices'.")
    if (t.time() - cache[data_type]["timestamp"] < 2.5) and not force:
        return cache[data_type]["data"]
    cache[data_type]["timestamp"] = t.time()
    if data_type == "current_playback":
        data = sp.current_playback()
    elif data_type == "devices":
        data = sp.devices()
    cache[data_type]["timestamp"] = t.time() 
    cache[data_type]["data"] = data
    return data

def main():
    global config, newupdate, sp
    print(f"\n! MIT License - © 2025 Szymon Andrzejewski (https://github.com/sandrzejewskipl/spotify-scheduler/blob/main/LICENSE) !\n")
    print(f"# Spotify Scheduler v{VER} made by Szymon Andrzejewski (https://szymonandrzejewski.pl)")
    print("# Github repository: https://github.com/sandrzejewskipl/spotify-scheduler/") 
    print(f"# Data is stored in {DATA_DIRECTORY}\n") 

    set_up()
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

    def fetch_playlists_loop():
        fetch_user_playlists()
        root.after(90000, fetch_playlists_loop)

    def fetch_played_loop():
        fetch_last_played_songs()
        root.after(300000, fetch_played_loop)
    
    def title_loop(lastdate=None):
        try:
            global newupdate, closest_start_time, last_endtime, empty_schedule
            now = datetime.now().strftime("%H:%M:%S")
            if lastdate!=now: #update title only when time changes
                lastdate=now
                nextplay=""
                if not is_paused:
                    try:
                        if not config['WEEKDAYS_ONLY'] or (config['WEEKDAYS_ONLY'] and datetime.today().weekday() < 5):
                            if empty_schedule:
                                nextplay=f" | {_('Schedule is empty')}"
                            elif last_endtime:
                                if last_endtime > datetime.now():
                                    closest_time_str = last_endtime - datetime.now()
                                    closest_time_str = str(closest_time_str).split('.')[0]
                                    nextplay=f" | {_('Stops in ')}{closest_time_str}"
                            elif closest_start_time:
                                if closest_start_time >= datetime.now().time():
                                    closest_time_str = datetime.combine(datetime.today(), closest_start_time) - datetime.now()
                                    closest_time_str = str(closest_time_str).split('.')[0]
                                    nextplay=f" | {_('Plays in ')}{closest_time_str}"
                                elif closest_start_time >= (datetime.now() - timedelta(seconds=2.5)).time():
                                    nextplay=f" | {_('Playing soon')}"
                                else:
                                    if not config['WEEKDAYS_ONLY'] or (config['WEEKDAYS_ONLY'] and (datetime.today() + timedelta(days=1)).weekday() < 5):
                                        closest_time_str = datetime.combine(datetime.today() + timedelta(days=1), closest_start_time) - datetime.now()
                                        closest_time_str = str(closest_time_str).split('.')[0]
                                        nextplay=f" | {_('Plays in ')}{closest_time_str}"
                                    else:
                                        nextplay=f" | {_('Weekend!')}"
                        else:
                            nextplay=f" | Weekend!"
                    except Exception:
                        pass
                else:
                    nextplay=f" | {_('Automation is paused')}"
                root.title(f"Spotify Scheduler v{VER} | {now}{nextplay} {newupdate}")
        except Exception:
            pass

        root.after(100, title_loop, lastdate)

    def is_canonical(version):
        return re.match(r'^([1-9][0-9]*!)?(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*((a|b|rc)(0|[1-9][0-9]*))?(\.post(0|[1-9][0-9]*))?(\.dev(0|[1-9][0-9]*))?$', version) is not None

    def updatechecker_loop():
        global newupdate
        newupdate=""
        try:
            response = requests.get("https://api.github.com/repos/sandrzejewskipl/spotify-scheduler/releases/latest", timeout=5)
            if response:
                if response.json()["tag_name"]:
                    if is_canonical(VER) and is_canonical(response.json()["tag_name"]):
                        if version.parse(response.json()["tag_name"])>version.parse(VER):
                            newupdate=(f"| {_('A new update is available for download')}!")
                            timestamped_print(f"A new update is available for download at https://github.com/sandrzejewskipl/spotify-scheduler/releases/latest (latest {response.json()['tag_name']} vs current {VER})")
        except Exception:
            pass
        
        root.after(600000, updatechecker_loop)

    # Check for Spotify Premium subscription
    try:
        user_profile = sp.me()
        if user_profile.get("product").lower() != "premium":
            # Show error and auto-close after 10 seconds
            error_win = tk.Toplevel(root)
            error_win.title(_("Spotify Premium Required"))
            error_win.geometry("450x250")
            error_win.resizable(False, False)
            # Center the window relative to the root window
            error_win.update_idletasks()
            root.update_idletasks()
            x = root.winfo_x() + (root.winfo_width() - error_win.winfo_width()) // 2
            y = root.winfo_y() + (root.winfo_height() - error_win.winfo_height()) // 2
            error_win.geometry(f"+{x}+{y}")
            # Set window icon if available
            try:
                if os.name == 'nt':
                    error_win.iconbitmap(bundle_path("icon.ico"))
            except Exception:
                pass
            frame = ttk.Frame(error_win, padding=20)
            frame.pack(expand=True, fill="both")
            ttk.Label(
                frame,
                text=_("You are not using Spotify Premium!"),
                wraplength=380,
                font=("Arial", 12, "bold"),
                anchor="center",
                justify="center"
            ).pack(pady=(0, 10))
            text=f"{_('A Spotify Premium subscription is required.\nWithout subscription, this application will not function properly, due to Spotify API limitations.')}\n\n{_('Current product type:')} {str(user_profile.get('product')).title()}\n{_("Account")}: {user_profile.get('email')}\n\n{_('This warning will close in 15 seconds.')}"
            ttk.Label(
                frame,
                text=text,
                wraplength=350,
                font=("Arial", 10),
                anchor="center",
                justify="center"
            ).pack(pady=(0, 15))
            ttk.Button(
                frame,
                text=_("> I understand <"),
                command=error_win.destroy
            ).pack(pady=(0, 5))
            def close_error_win():
                if error_win.winfo_exists():
                    error_win.destroy()
            error_win.after(15000, close_error_win)
            error_win.transient(root)
            error_win.grab_set()
            error_win.focus_set()
            timestamped_print("Spotify Premium subscription is required to use this application.")
    except Exception as e:
        timestamped_print(f"Failed to check Spotify subscription: {error(e)}")

    loop()
    fetch_playlists_loop()
    fetch_played_loop()
    updatechecker_loop()
    title_loop()

    def close_confirm():
        ans = askyesno("Spotify Scheduler", _("Are you sure you want to exit?"))
        if ans:
            root.destroy()

    root.wm_protocol ("WM_DELETE_WINDOW", close_confirm)
    
def set_up():
    global config
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

        set_up_box_1=tk.Text(credentials_window, wrap="word", height=3, width=60, font=("Arial", 10))
        set_up_box_1.pack(pady=10)
        set_up_box_1.insert(tk.END, _("set_up_box1"))
        set_up_box_1.config(state="disabled")
        set_up_box_1.tag_configure("center", justify='center')
        set_up_box_1.tag_add("center", 1.0, "end")
        def open_spotify_developers():
            open_link("https://developer.spotify.com/dashboard")

        open_button = ttk.Button(credentials_window, text=_("Open Spotify for Developers"), command=open_spotify_developers)
        open_button.pack()

        set_up_box_2=tk.Text(credentials_window, wrap="word", height=6, width=60, font=("Arial", 10))
        set_up_box_2.pack(pady=10)
        set_up_box_2.insert(tk.END, _("set_up_box2"))
        set_up_box_2.config(state="disabled")
        set_up_box_2.tag_configure("center", justify='center')
        set_up_box_2.tag_add("center", 1.0, "end")
        

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

if __name__ == "__main__":
    root.after(0, main)
    root.mainloop()
