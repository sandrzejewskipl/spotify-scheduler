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

VER="2.0.1"
CONFIG_FILE="config.json"
NEWSCHEDULE="schedule.json"
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

def bundle_path(relative_path):
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

    for playlist in playlists:
        playlist_name = playlist['name']
        playlist_id = playlist['id']
        _playlist_name_cache[playlist_id] = (playlist_name, t.time())

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

def initialize_sp():
    global sp, spstatus, last_spotify_run, username, user_id
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
root.geometry("1000x600")
root.resizable(False, False) 

# Adding bookmarks
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

now_playing_frame = ttk.Frame(notebook)
notebook.add(now_playing_frame, text=_("Now Playing"))

schedulecombo_frame = ttk.Frame(notebook)
notebook.add(schedulecombo_frame, text=_("Schedule"))

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
    global username, user_id
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
                    uid = sp.me()['id']
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

info_text.insert("insert", f"{_('Donation')}: ")
info_text.insert("insert", "https://szymonandrzejewski.pl/donate/paypal\n", "link3")

info_text.insert("insert", f"\n{_('github_star')}\n\nMIT License - © 2025 Szymon Andrzejewski")

info_text.tag_config("header", font=("Arial", 14, "bold"), justify="center")
info_text.tag_config("link1", foreground="#1DB954", underline=True)
info_text.tag_config("link2", foreground="#1DB954", underline=True)
info_text.tag_config("link3", foreground="#1DB954", underline=True)

info_text.tag_bind("link1", "<Button-1>", lambda e: open_link("https://szymonandrzejewski.pl"))
info_text.tag_bind("link2", "<Button-1>", lambda e: open_link("https://github.com/sandrzejewskipl/Spotify-Scheduler"))
info_text.tag_bind("link3", "<Button-1>", lambda e: open_link("https://szymonandrzejewski.pl/donate/paypal"))

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

def choose_device_name():
    """Open a window to choose device name from Spotify devices"""
    try:
        # Fetch devices from Spotify
        devices_data = cached_spotify_data("devices")
        devices = []
        
        if devices_data and "devices" in devices_data:
            devices = devices_data["devices"]
        
        for device in devices:
            if "web player" in device.get("name", "").lower():
                devices.remove(devices)

        if not devices:
            messagebox.showwarning(_("Choose device"), _("No devices found. Please make sure Spotify is running on at least one device."))
            return
        
        # Create window
        device_select_win = tk.Toplevel(root)
        device_select_win.title(_("Choose device"))
        device_select_win.geometry("500x400")
        device_select_win.resizable(False, False)
        
        # Set window icon if available
        try:
            if os.name == 'nt':
                device_select_win.iconbitmap(bundle_path("icon.ico"))
        except Exception:
            pass
        
        # Center the window relative to the root window
        device_select_win.update_idletasks()
        root.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - device_select_win.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - device_select_win.winfo_height()) // 2
        device_select_win.geometry(f"+{x}+{y}")
        
        ttk.Label(device_select_win, text=_("Select a device:")).pack(pady=10)
        
        # Frame for listbox and scrollbar
        listbox_frame = ttk.Frame(device_select_win)
        listbox_frame.pack(pady=5, padx=10, fill="both", expand=True)
        
        # Listbox with custom font
        custom_font = font.Font(family="Arial", size=10)
        device_listbox = tk.Listbox(
            listbox_frame,
            width=50,
            height=12,
            font=custom_font,
            selectbackground="#8BEBAD",
            selectforeground="black",
            activestyle="none",
            relief="flat",
            borderwidth=2,
            highlightthickness=1,
        )
        
        device_name_map = {}
        listbox_idx = 0
        
        # Populate listbox with devices
        for device in devices:
            device_name = device.get("name", "Unknown Device")
            is_active = f" {_("(Active)")}" if device.get("is_active") else ""
            display = f"{device_name}{is_active}"
            device_listbox.insert(tk.END, display)
            device_name_map[listbox_idx] = device_name
            
            # Alternate row colors
            if listbox_idx % 2 == 0:
                device_listbox.itemconfig(listbox_idx, background="#e6e6e6")
            
            listbox_idx += 1
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=device_listbox.yview)
        device_listbox.config(yscrollcommand=scrollbar.set)
        device_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def on_select():
            selection = device_listbox.curselection()
            if selection:
                idx = selection[0]
                selected_device_name = device_name_map[idx]
                setting_entries['DEVICE_NAME'].delete(0, tk.END)
                setting_entries['DEVICE_NAME'].insert(0, selected_device_name)
                on_settings_change()
                device_select_win.destroy()
                timestamped_print(f"Device selected: {selected_device_name}")
            else:
                messagebox.showwarning(_("Choose Device"), _("Please select a device."))
        
        def on_listbox_select(event):
            on_select()
        
        # Bind double-click to select
        device_listbox.bind('<Double-Button-1>', on_listbox_select)
        
        # Button frame
        button_frame = ttk.Frame(device_select_win)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text=_("Select"), command=on_select).pack(side="left", padx=5)
        ttk.Button(button_frame, text=_("Cancel"), command=device_select_win.destroy).pack(side="left", padx=5)
        
        device_select_win.transient(root)
        device_select_win.grab_set()
        root.wait_window(device_select_win)
        
    except Exception as e:
        timestamped_print(f"Error opening device selection window: {error(e)}")
        messagebox.showerror(_("Choose Device"), _("Failed to fetch devices: ") + str(e))

set_device_btn = ttk.Button(settings_frame, text=_("Choose from list"), command=choose_device_name)
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

def get_value_for_schedule(day=None,hour=None,value="playlist"): #value should be playlist or randomqueue
    global last_schedule
    if hour==None:
        day=datetime.now().strftime("%Y-%m-%d")
        hour=is_within_schedule()
    if hour:
        try:
            with open(NEWSCHEDULE, "r") as file:
                data = json.load(file)
                hour = hour.strip()
                if day in data and hour in data[day] and value in data[day][hour]:
                    return data[day][hour][value]
                else:
                    return None
        except FileNotFoundError:
            initialize_new_schedule()
        except Exception as e:
            timestamped_print(f"Error during loading playlists file: {error(e)}")
    return False

def is_valid_time_format(time_str):
    time_pattern = r"^([01]?[0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$"  # Hours: 00-23, Minutes: 00-59
    return re.match(time_pattern, time_str) is not None

def initialize_new_schedule():
    """Initialize new schedule file if it doesn't exist"""
    if not os.path.exists(NEWSCHEDULE):
        with open(NEWSCHEDULE, "w") as f:
            json.dump({}, f, indent=4)
        timestamped_print("Initialized new schedule file.")
        refresh_schedule_display()

selected_date = tk.StringVar()
selected_date.set(datetime.now().strftime("%Y-%m-%d"))

# Main container for calendar and schedule table (side by side)
main_content_frame = ttk.Frame(schedulecombo_frame)
main_content_frame.pack(fill="both", expand=True, padx=10, pady=10)

calendar_left = ttk.Frame(main_content_frame)
calendar_left.pack(side="left", anchor="n", padx=(0,10))

def on_date_selected():
    date_obj = calendar.selection_get()
    date_string = date_obj.strftime("%Y-%m-%d")
    selected_date.set(date_string)
    refresh_schedule_display()

class CustomCalendar(ttk.Frame):
    def __init__(self, parent, year, month, day, on_select_callback=None):
        super().__init__(parent)
        self.on_select_callback = on_select_callback
        today = datetime.now().date()
        self.selected_date = today
        self.selected_day = today.day
        self.year = today.year
        self.month = today.month
        
        self.day_buttons = []
        self.create_widgets()
        self.update_calendar()
    
    def create_widgets(self):
        # Header with month/year and navigation
        header = ttk.Frame(self)
        header.pack(fill="x", padx=5, pady=5)
        
        ttk.Button(header, text="◀", width=3, command=self.prev_month).pack(side="left", padx=2)
        self.month_label = ttk.Label(header, text="", font=("Arial", 12, "bold"))
        self.month_label.pack(side="left", expand=True)
        ttk.Button(header, text="▶", width=3, command=self.next_month).pack(side="right", padx=2)
        
        # Calendar grid (includes day names header and days)
        self.calendar_frame = ttk.Frame(self)
        self.calendar_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        days_en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        days_pl = ["Pon", "Wto", "Śro", "Czw", "Pią", "Sob", "Nie"]

        days = days_pl if get_default_language() == "pl" else days_en

        for col, day_name in enumerate(days):
            ttk.Label(
                self.calendar_frame,
                text=day_name,
                font=("Arial", 9, "bold"),
                width=4,
                anchor="center"
            ).grid(row=0, column=col, padx=1, pady=1, sticky="nsew")
            self.calendar_frame.columnconfigure(col, weight=1)

    
    def update_calendar(self):
        for widget in self.calendar_frame.winfo_children():
            info = widget.grid_info()
            if info.get('row', 0) > 0:
                widget.destroy()
        self.day_buttons = []
        
        self.month_label.config(text=f"{datetime(self.year, self.month, 1).strftime('%B %Y')}")
        
        first_day = datetime(self.year, self.month, 1)
        num_days = (datetime(self.year, self.month, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        num_days = num_days.day
        
        start_weekday = first_day.weekday()
        
        today = datetime.now().date()
        day_counter = start_weekday
        
        for day in range(1, num_days + 1):
            row = (day_counter // 7) + 1  # +1 to account for header row
            col = day_counter % 7
            
            current_date = datetime(self.year, self.month, day).date()
            btn = tk.Button(
                self.calendar_frame,
                text=str(day),
                width=3,
                font=("Arial", 10),
                relief="raised",
                bd=1,
                bg="#FFFFFF" if current_date != today else "#BBDEFB",
                fg="#333333" if current_date != today else "#000000",
                activebackground="#bbdefb"
            )
            
            if current_date == self.selected_date:
                btn.config(bg="#4CAF50", fg="#FFFFFF")
         
            btn.grid(row=row, column=col, padx=1, pady=2)
            btn.config(command=lambda d=day: self.select_day(d))
            self.day_buttons.append((day, btn))
            day_counter += 1
        
        for i in range(start_weekday):
            row = (i // 7) + 1 
            col = i % 7
            ttk.Label(self.calendar_frame, text="", width=3).grid(row=row, column=col, padx=1, pady=2)

        # Color days with schedule entries
        try:
            with open(NEWSCHEDULE, "r") as f:
                schedule_data = json.load(f)
            
            for day, button in self.day_buttons:
                date_str = f"{self.year:04d}-{self.month:02d}-{day:02d}"
                today_str = datetime.now().strftime("%Y-%m-%d")
                
                if date_str in schedule_data and any(schedule_data[date_str].values()):
                    if self.selected_date and date_str == self.selected_date.strftime("%Y-%m-%d"):
                        continue  # skip selected day
                    if date_str == today_str:
                        continue  # skip today
                    button.config(bg="#FFECB3", fg="#333333")  # day with schedule

        except Exception:
            pass

    def select_day(self, day):
        self.selected_day = day
        self.selected_date = datetime(self.year, self.month, day).date()
        self.update_calendar()
        if self.on_select_callback:
            self.on_select_callback()
    
    def prev_month(self):
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self.update_calendar()
    
    def next_month(self):
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self.update_calendar()
    
    def selection_get(self):
        return self.selected_date if self.selected_date else datetime(self.year, self.month, self.selected_day).date()

calendar = CustomCalendar(calendar_left, datetime.now().year, datetime.now().month, datetime.now().day, on_select_callback=on_date_selected)
calendar.pack(fill="x")

# Copy button frame
copy_button_frame = ttk.Frame(calendar_left)
copy_button_frame.pack(fill="x", pady=5)

inner = ttk.Frame(copy_button_frame)
inner.pack(anchor="center")

def copy_schedule_dialog_days():
    try:
        current_date = calendar.selection_get()
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Load current schedule
        try:
            with open(NEWSCHEDULE, "r") as f:
                schedule_data = json.load(f)
        except FileNotFoundError:
            schedule_data = {}
        
        # Create dialog
        copy_dialog = tk.Toplevel(root)
        copy_dialog.title(_("Copy next X days"))
        copy_dialog.geometry("300x130")
        copy_dialog.resizable(False, False)
        try:
            if os.name == 'nt':
                copy_dialog.iconbitmap(bundle_path("icon.ico"))
        except Exception:
            pass
        
        # Center the window
        copy_dialog.update_idletasks()
        root.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - copy_dialog.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - copy_dialog.winfo_height()) // 2
        copy_dialog.geometry(f"+{x}+{y}")

        ttk.Label(copy_dialog, text=_("Copy schedule from") + f" {date_str}").pack(pady=(10,0))

        def update_preview(*args):
            val = days_var.get()

            if not val.strip():
                preview_label.config(text="")
                return

            try:
                days = int(val)
                if days <= 0:
                    preview_label.config(text="")
                    return
                
                end_date = current_date + timedelta(days=days)
                end_str = end_date.strftime("%Y-%m-%d")
                preview_label.config(text=f"{_('Copying will end on')}: {end_str}")
            except ValueError:
                preview_label.config(text="")

        days_var = tk.StringVar(value="")
        days_var.trace_add("write", update_preview)

        line = ttk.Frame(copy_dialog)
        line.pack(pady=5)

        def validate_digits(new_value):
            if new_value == "":
                return True
            if not new_value.isdigit():
                return False
            val = int(new_value)
            return 1 <= val <= 999

        vcmd = (copy_dialog.register(validate_digits), "%P")


        days_entry = ttk.Entry(
            line,
            textvariable=days_var,
            width=5,
            validate="key",
            validatecommand=vcmd
        )
        days_entry.pack(side="left", padx=(0, 5))


        ttk.Label(line, text=_("days ahead")).pack(side="left")

        preview_label = ttk.Label(copy_dialog, text="", foreground="gray")
        preview_label.pack(pady=2)

        
        def do_copy():
            try:
                if days_var.get().strip() == "":
                    preview_label.config(text=f"{_("Please enter a number of days.")}")
                    return
                
                days = int(days_var.get())
                   
                # Allow copying even if day doesn't exist or is empty
                if date_str not in schedule_data:
                    source_schedule = {}
                else:
                    source_schedule = schedule_data[date_str].copy()
                copied_count = 0
                
                # Copy to next X days
                for i in range(1, days + 1):
                    target_date = current_date + timedelta(days=i)
                    target_date_str = target_date.strftime("%Y-%m-%d")
                    
                    # Create new entry for target date or overwrite existing
                    schedule_data[target_date_str] = {}
                    for start_time, entry_data in source_schedule.items():
                        schedule_data[target_date_str][start_time] = entry_data.copy()
                    
                    copied_count += 1
                
                # Save
                with open(NEWSCHEDULE, "w") as f:
                    json.dump(schedule_data, f, indent=4)
                
                new_schedulecombo_status.set(f"{_("Schedule copied to")} {copied_count} {_("next days")}.")
                timestamped_print(f"Schedule from {date_str} copied to {copied_count} next days.")
                copy_dialog.destroy()
                refresh_schedule_display()
                calendar.update_calendar()
                
            except Exception as e:
                timestamped_print(f"Error copying schedule: {error(e)}")
        
        ttk.Button(copy_dialog, text=_("Copy"), command=do_copy).pack(pady=10)
        copy_dialog.transient(root)
        copy_dialog.grab_set()
        days_entry.focus_set()
        
    except Exception as e:
        new_schedulecombo_status.set(_("Error opening copy dialog."))
        timestamped_print(f"Error: {error(e)}")

def copy_schedule_dialog_weekdays():
    try:
        current_date = calendar.selection_get()
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Load current schedule
        try:
            with open(NEWSCHEDULE, "r") as f:
                schedule_data = json.load(f)
        except FileNotFoundError:
            schedule_data = {}
        
        copy_dialog = tk.Toplevel(root)
        copy_dialog.title(_("Copy next X weekdays"))
        copy_dialog.geometry("300x130")
        copy_dialog.resizable(False, False)
        try:
            if os.name == 'nt':
                copy_dialog.iconbitmap(bundle_path("icon.ico"))
        except Exception:
            pass
        
        # Center the window
        copy_dialog.update_idletasks()
        root.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - copy_dialog.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - copy_dialog.winfo_height()) // 2
        copy_dialog.geometry(f"+{x}+{y}")

        ttk.Label(copy_dialog, text=_("Copy schedule from") + f" {date_str}").pack(pady=(10,0))

        def update_preview(*args):
            val = days_var.get()
            if not val.strip():
                preview_label.config(text="")
                return
            try:
                count = int(val)
                if count <= 0:
                    preview_label.config(text="")
                    return
                preview_label.config(text=f"")
            except ValueError:
                preview_label.config(text="")

        days_var = tk.StringVar(value="")
        days_var.trace_add("write", update_preview)

        line = ttk.Frame(copy_dialog)
        line.pack(pady=5)

        def validate_digits(new_value):
            if new_value == "":
                return True
            if not new_value.isdigit():
                return False
            val = int(new_value)
            return 1 <= val <= 999

        vcmd = (copy_dialog.register(validate_digits), "%P")

        days_entry = ttk.Entry(line, textvariable=days_var, width=5, validate="key", validatecommand=vcmd)
        days_entry.pack(side="left", padx=(0, 5))
        ttk.Label(line, text=_("weekdays ahead")).pack(side="left")

        preview_label = ttk.Label(copy_dialog, text="", foreground="gray")
        preview_label.pack(pady=2)

        def do_copy():
            try:
                if days_var.get().strip() == "":
                    preview_label.config(text=f"{_("Please enter a number of weekdays.")}")
                    return
                count = int(days_var.get())
                if date_str not in schedule_data:
                    source_schedule = {}
                else:
                    source_schedule = schedule_data[date_str].copy()

                copied_count = 0
                weekday_to_copy = current_date.weekday()
                target_date = current_date

                while copied_count < count:
                    target_date += timedelta(days=1)
                    if target_date.weekday() == weekday_to_copy:
                        target_date_str = target_date.strftime("%Y-%m-%d")
                        schedule_data[target_date_str] = {}
                        for start_time, entry_data in source_schedule.items():
                            schedule_data[target_date_str][start_time] = entry_data.copy()
                        copied_count += 1

                with open(NEWSCHEDULE, "w") as f:
                    json.dump(schedule_data, f, indent=4)

                new_schedulecombo_status.set(f"{_("Schedule copied to")} {copied_count} {_("next weekdays")}.")
                timestamped_print(f"Schedule from {date_str} copied to {copied_count} next weekdays.")
                copy_dialog.destroy()
                refresh_schedule_display()
                calendar.update_calendar()
            except Exception as e:
                timestamped_print(f"Error copying schedule: {error(e)}")

        ttk.Button(copy_dialog, text=_("Copy"), command=do_copy).pack(pady=10)
        copy_dialog.transient(root)
        copy_dialog.grab_set()
        days_entry.focus_set()

    except Exception as e:
        new_schedulecombo_status.set(_("Error opening copy dialog."))
        timestamped_print(f"Error: {error(e)}")


btn_days = tk.Button(
    inner,
    text=_("Copy next X days"),
    command=copy_schedule_dialog_days,
    width=18,
    wraplength=130,
    justify="center",
    bg="#FCFCFC"
)
btn_days.pack(side="left", padx=5)

btn_weekdays = tk.Button(
    inner,
    text=_("Copy next X weekdays"),
    command=copy_schedule_dialog_weekdays,
    width=18,
    wraplength=130,
    justify="center",
    bg="#FCFCFC"
)
btn_weekdays.pack(side="left", padx=5)


# Table container on the right with checkboxes
table_container = ttk.Frame(main_content_frame)
table_container.pack(side="right", fill="both", expand=True)


# Column widths
COL_START_WIDTH = 8
COL_END_WIDTH = 8
COL_RANDOM_WIDTH = 12

header_frame = ttk.Frame(table_container)
header_frame.pack(fill="x", padx=0, pady=5)

# Start
ttk.Label(
    header_frame,
    text=_("Start"),
    font=("Arial", 9, "bold"),
    width=COL_START_WIDTH,
    anchor="w"
).pack(side="left", padx=(5,0))

# End
ttk.Label(
    header_frame,
    text=_("End"),
    font=("Arial", 9, "bold"),
    width=COL_END_WIDTH,
    anchor="w"
).pack(side="left")

# Playlist
ttk.Label(
    header_frame,
    text=_("Playlist"),
    font=("Arial", 9, "bold"),
    anchor="w"
).pack(side="left", padx=(200,0), fill="x", expand=True)

# Random queue
ttk.Label(
    header_frame,
    text=_("Random\nqueue"),
    font=("Arial", 9, "bold"),
    width=COL_RANDOM_WIDTH,
    anchor="center",
    justify="center"
).pack(side="left", padx=8)

# Delete column
ttk.Label(
    header_frame,
    text="",
    width=2,
    anchor="center"
).pack(side="left", padx=2)

# Create scrollable frame for entries
entries_frame = ttk.Frame(table_container)
entries_frame.pack(fill="both", expand=True, padx=0, pady=5)

# Canvas with scrollbar for entries
canvas = tk.Canvas(entries_frame, bg="white", highlightthickness=0)
scrollbar = ttk.Scrollbar(entries_frame, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas, bg="white")

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

# Update canvas window width when canvas is resized
def on_canvas_size_change(event):
    canvas.itemconfig(canvas_window, width=event.width)

canvas.bind("<Configure>", on_canvas_size_change)

# Bind mouse wheel for scrolling
def _on_mousewheel(event):
    if scrollable_frame.winfo_reqheight() > canvas.winfo_height():
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

canvas.bind_all("<MouseWheel>", _on_mousewheel)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Dictionary to store entry rows with checkbutton variables
schedule_entry_widgets = {}

# Function to refresh entries display
def refresh_schedule_display():
    global schedule_entry_widgets
    
    # Clear previous entries
    for widget_dict in schedule_entry_widgets.values():
        if 'frame' in widget_dict:
            widget_dict['frame'].destroy()
    schedule_entry_widgets = {}
    
    try:
        date_str = selected_date.get()
        with open(NEWSCHEDULE, "r") as f:
            schedule_data = json.load(f)
        
        if date_str in schedule_data:
            # Sort entries by start time
            def parse_time_str(tstr):
                fmt = "%H:%M:%S" if tstr.count(":") == 2 else "%H:%M"
                return datetime.strptime(tstr, fmt).time()

            sorted_entries = sorted(
                schedule_data[date_str].items(),
                key=lambda x: parse_time_str(x[0].split("-")[0])
            )
            
            for time_range, entry_data in sorted_entries:
                try:
                    playlist_id = entry_data.get("playlist", "")
                    randomqueue = entry_data.get("randomqueue", False)
                    playlist_name = get_playlist_name_for_display(playlist_id)
                    
                    start_time, end_time = time_range.split("-")
                    
                    entry_row = ttk.Frame(scrollable_frame)
                    entry_row.pack(fill="both", expand=True, pady=2, padx=0)
                    
                    ttk.Label(entry_row, text=start_time, width=COL_START_WIDTH, anchor="w").pack(side="left", padx=5, fill="x", expand=False)
                    ttk.Label(entry_row, text=end_time, width=COL_END_WIDTH, anchor="w").pack(side="left", padx=5, fill="x", expand=False)
                    
                    def on_edit_entry(tr=time_range, pid=playlist_id, pn=playlist_name):
                        edit_schedule_entry(tr, pid, pn)
                    
                    btn = ttk.Button(entry_row, text=f"{playlist_name[:100]}", command=on_edit_entry)
                    btn.pack(side="left", padx=5, fill="both", expand=True)
                    
                    rq_var = tk.BooleanVar(value=randomqueue)
                    def on_rq_change(tr=time_range, var=rq_var):
                        schedule_entry_widgets[tr]['rq_var'] = var
                        save_new_schedule()
                    
                    chk = tk.Checkbutton(entry_row, variable=rq_var, command=on_rq_change, width=2, anchor="center")
                    if("37i9dQ" in playlist_id):
                        chk.config(state="disabled")
                        rq_var.set(False)
                    chk.pack(side="left", padx=5, fill="none", expand=False)
                    
                    def on_delete_entry(tr=time_range):
                        try:
                            date_str_del = selected_date.get()
                            with open(NEWSCHEDULE, "r") as f:
                                schedule_data = json.load(f)
                            
                            if date_str_del in schedule_data and tr in schedule_data[date_str_del]:
                                del schedule_data[date_str_del][tr]
                                with open(NEWSCHEDULE, "w") as f:
                                    json.dump(schedule_data, f, indent=4)
                                
                                new_schedulecombo_status.set(_("Entry removed"))
                                timestamped_print(f"Removed schedule entry for {tr}")
                                refresh_schedule_display()
                        except Exception as e:
                            new_schedulecombo_status.set(_("Error during removing entry"))
                            timestamped_print(f"Error removing schedule entry: {error(e)}")
                    
                    del_btn = ttk.Button(entry_row, text="✕", command=on_delete_entry, width=2)
                    del_btn.pack(side="left", padx=2)
                    
                    schedule_entry_widgets[time_range] = {
                        'frame': entry_row,
                        'rq_var': rq_var,
                        'rq_checkbox': chk,
                        'playlist_id': playlist_id,
                        'playlist_name': playlist_name
                    }
                except Exception as e:
                    timestamped_print(f"Error creating entry widget: {error(e)}")
        
        new_schedulecombo_status.set("")
        
        scrollable_frame.update_idletasks()
        canvas_height = canvas.winfo_height()
        frame_height = scrollable_frame.winfo_reqheight()
        min_height = max(frame_height, canvas_height)
        canvas.config(scrollregion=(0, 0, scrollable_frame.winfo_width(), min_height))
    
    except Exception as e:
        new_schedulecombo_status.set(_("Error during loading schedule."))
        timestamped_print(f"Error loading schedule: {error(e)}")

def edit_schedule_entry(time_range, current_playlist, current_playlist_name):
    try:
        def on_playlist_select_callback():
            user_input = edit_playlist_var.get().strip()
            edit_select_win.destroy()
            playlist_id = user_input
            if "open.spotify.com" in user_input:
                playlist_id = extract_playlist_id(user_input)
            
            # Update in JSON
            date_str = selected_date.get()
            with open(NEWSCHEDULE, "r") as f:
                schedule_data = json.load(f)
            
            if date_str in schedule_data and time_range in schedule_data[date_str]:
                schedule_data[date_str][time_range]["playlist"] = playlist_id
                if "37i9dQ" in playlist_id:
                    schedule_data[date_str][time_range]["randomqueue"] = False
                with open(NEWSCHEDULE, "w") as f:
                    json.dump(schedule_data, f, indent=4)
                
                timestamped_print(f"Playlist for {time_range} updated to {playlist_id}.")
                refresh_schedule_display()
                save_new_schedule()
        
        # Load playlists
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
        
        # Create window
        edit_select_win = tk.Toplevel(root)
        edit_select_win.withdraw()
        edit_select_win.title(_("Select playlist"))
        edit_select_win.geometry("600x400")
        edit_select_win.resizable(False, False)
        try:
            if os.name == 'nt':
                edit_select_win.iconbitmap(bundle_path("icon.ico"))
        except Exception:
            pass
        
        ttk.Label(edit_select_win, text=_("Choose from your playlists:")).pack(pady=10)
        
        edit_playlist_var = tk.StringVar(value=current_playlist)
        listbox_frame = ttk.Frame(edit_select_win)
        listbox_frame.pack(pady=5, padx=10, fill="both", expand=True)
        
        custom_font = font.Font(family="Arial", size=10)
        edit_playlist_listbox = tk.Listbox(
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
            edit_playlist_listbox.insert(tk.END, display)
            playlist_id_map[idx] = playlist['id']
            if idx % 2 == 0:
                edit_playlist_listbox.itemconfig(idx, background="#e6e6e6")
        
        scrollbar_dialog = ttk.Scrollbar(listbox_frame, orient="vertical", command=edit_playlist_listbox.yview)
        edit_playlist_listbox.config(yscrollcommand=scrollbar_dialog.set)
        edit_playlist_listbox.pack(side="left", fill="both", expand=True)
        scrollbar_dialog.pack(side="right", fill="y")
        
        entry_frame = ttk.Frame(edit_select_win)
        entry_frame.pack(pady=5)
        ttk.Label(entry_frame, text=_("Or enter playlist URL/ID:")).pack(side="left")
        entry = ttk.Entry(entry_frame, textvariable=edit_playlist_var, width=35)
        entry.pack(side="left", padx=5)
        entry.bind('<Return>', lambda evt: on_playlist_select_callback())
        
        def on_listbox_select(evt):
            selection = edit_playlist_listbox.curselection()
            if selection:
                selected_idx = selection[0]
                if selected_idx in playlist_id_map:
                    edit_playlist_var.set(playlist_id_map[selected_idx])
        
        edit_playlist_listbox.bind('<<ListboxSelect>>', on_listbox_select)
        
        ttk.Button(edit_select_win, text=_("Select"), command=on_playlist_select_callback).pack(pady=10)
        
        edit_select_win.update_idletasks()
        root.update_idletasks()
        x = root.winfo_x() + (root.winfo_width() - edit_select_win.winfo_width()) // 2
        y = root.winfo_y() + (root.winfo_height() - edit_select_win.winfo_height()) // 2
        edit_select_win.geometry(f"+{x}+{y}")
        edit_select_win.deiconify()
        
        entry.focus_set()
        edit_select_win.transient(root)
        edit_select_win.grab_set()
        root.wait_window(edit_select_win)
        
    except Exception as e:
        new_schedulecombo_status.set(_("Error during editing entry."))
        timestamped_print(f"Error editing entry: {error(e)}")

# Input frame
input_frame = ttk.Frame(table_container)
input_frame.pack(fill="x", padx=0, pady=5)

ttk.Label(input_frame, text=_("START_LABEL")).pack(side="left")
new_start_time_entry = ttk.Entry(input_frame, width=10)
new_start_time_entry.pack(side="left", padx=5)

ttk.Label(input_frame, text=_("END_LABEL")).pack(side="left", padx=(5, 0))
new_end_time_entry = ttk.Entry(input_frame, width=10)
new_end_time_entry.pack(side="left", padx=5)

def on_enter(event):
    add_new_schedule_entry()

# Bind dla obu pól
new_start_time_entry.bind("<Return>", on_enter)
new_end_time_entry.bind("<Return>", on_enter)

_playlist_name_cache = {}

def get_playlist_name_for_display(playlist_id):
    try:
        if not playlist_id or playlist_id.strip() == "":
            name=_("--- Click to set playlist ---")
            return name
        
        # check cache
        if playlist_id in _playlist_name_cache:
            cached_data, timestamp = _playlist_name_cache[playlist_id]
            if t.time() - timestamp < 300:
                return cached_data
        if "37i9dQ" in playlist_id:
            name = _("Spotify's playlist")
        else:
            playlist = sp.playlist(playlist_id)
            name = playlist.get("name", "")
        
        # cache result
        _playlist_name_cache[playlist_id] = (name, t.time())
        
        return name
    except Exception as e:
        name=_("--- Unknown Playlist ---")
        timestamped_print("Error fetching playlist name: " + error(e))
        return ""

def add_new_schedule_entry():
    try:
        start_time = (new_start_time_entry.get()).replace(';', ':')
        end_time = (new_end_time_entry.get()).replace(';', ':')

        if not is_valid_time_format(start_time):
            new_schedulecombo_status.set(_("Error: Incorrect time format."))
            return

        if not is_valid_time_format(end_time):
            new_schedulecombo_status.set(_("Error: Incorrect time format."))
            return

        def parse_time_str(tstr):
            fmt = "%H:%M:%S" if tstr.count(":") == 2 else "%H:%M"
            return datetime.strptime(tstr, fmt).time()
            
        if parse_time_str(end_time) <= parse_time_str(start_time):
            new_schedulecombo_status.set(_("Error: End time must be later than start time."))
            return
                
        try:
            with open(NEWSCHEDULE, "r") as f:
                schedule_data = json.load(f)
        except FileNotFoundError:
            schedule_data = {}
        
        date_str = selected_date.get()
        if date_str not in schedule_data:
            schedule_data[date_str] = {}

        time_range_key = f"{start_time}-{end_time}"
        if time_range_key in schedule_data[date_str]:
            new_schedulecombo_status.set(_("Error: Entry already exists."))
            return

        schedule_data[date_str][time_range_key] = {
            "playlist": "",
            "randomqueue": False
        }

        def parse_start(time_range):
            start_str = time_range.split("-")[0]
            fmt = "%H:%M:%S" if start_str.count(":") == 2 else "%H:%M"
            return datetime.strptime(start_str, fmt).time()

        schedule_data[date_str] = dict(sorted(schedule_data[date_str].items(), key=lambda x: parse_start(x[0])))

        with open(NEWSCHEDULE, "w") as f:
            json.dump(schedule_data, f, indent=4)
        
        new_start_time_entry.delete(0, tk.END)
        new_end_time_entry.delete(0, tk.END)
        new_schedulecombo_status.set(_("Entry added"))
        timestamped_print(f"Added schedule entry for {date_str}: {time_range_key}")
        refresh_schedule_display()
    except Exception as e:
        new_schedulecombo_status.set(_("Error during adding entry."))
        timestamped_print(f"Error adding schedule entry: {error(e)}")

def save_new_schedule():
    try:
        date_str = selected_date.get()
        schedule_entries = {}

        for time_range, widget_dict in schedule_entry_widgets.items():
            rq_var = widget_dict.get('rq_var')
            playlist_id = widget_dict.get('playlist_id', '')
            randomqueue = rq_var.get() if rq_var else False
            
            schedule_entries[time_range] = {
                "playlist": playlist_id,
                "randomqueue": randomqueue
            }

        def parse_start(time_range):
            start_str = time_range.split("-")[0]
            fmt = "%H:%M:%S" if start_str.count(":") == 2 else "%H:%M"
            return datetime.strptime(start_str, fmt).time()

        sorted_entries = dict(sorted(schedule_entries.items(), key=lambda x: parse_start(x[0])))

        with open(NEWSCHEDULE, "r") as f:
            schedule_data = json.load(f)

        schedule_data[date_str] = sorted_entries

        with open(NEWSCHEDULE, "w") as f:
            json.dump(schedule_data, f, indent=4)

        new_schedulecombo_status.set(_("Schedule saved for") + f" {date_str}")
        timestamped_print(f"Schedule saved for {date_str}: {len(sorted_entries)} entries.")
        spotify_main()
    except Exception as e:
        new_schedulecombo_status.set(_("Error during saving schedule."))
        timestamped_print(f"Error saving schedule: {error(e)}")




add_btn = ttk.Button(input_frame, text=_("Add Entry"), command=add_new_schedule_entry)
add_btn.pack(side="left", padx=5)

new_schedulecombo_status = tk.StringVar()
new_schedulecombo_status.set("")

status_label = ttk.Label(schedulecombo_frame, textvariable=new_schedulecombo_status, wraplength=500, anchor="w")
status_label.pack(fill="x", padx=10, pady=(0,5))

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
    timestamped_print("Trying to run spotify.")
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

def extract_playlist_id(url):
    try:
        pattern = r"playlist/(\w+)"
        return re.search(pattern, url).group(1)
    except AttributeError:
        return None

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
        
        checklistvar.set(_("Checklist", process=proces, device=found_device, volume=volume))

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

last_endtime = None
last_delay = None
closest_start_time = None
earliest_start_time = None
empty_schedule = None

def is_within_schedule():
    global last_schedule, last_endtime, closest_start_time, last_delay, empty_schedule, earliest_start_time
    last_schedule = ''
    match = False
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().time()
        closest_start_time = None
        earliest_start_time = None
        last_endtime = None
        empty_schedule = True

        with open(NEWSCHEDULE, "r") as f:
            schedule_data = json.load(f)

        day_schedule = schedule_data.get(today_str, {})

        def parse_start(time_range):
            start_str = time_range.split("-")[0]
            fmt = "%H:%M:%S" if start_str.count(":") == 2 else "%H:%M"
            return datetime.strptime(start_str, fmt).time()

        sorted_entries = sorted(day_schedule.items(), key=lambda x: parse_start(x[0]))

        for time_range, entry_data in sorted_entries:
            empty_schedule = False
            start_str, end_str = time_range.split("-")
            start_time = datetime.strptime(start_str, "%H:%M:%S" if start_str.count(":") == 2 else "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M:%S" if end_str.count(":") == 2 else "%H:%M").time()

            if start_time <= end_time:
                if start_time <= now <= end_time and (not config.get('WEEKDAYS_ONLY', False) or datetime.today().weekday() < 5):
                    last_schedule = time_range
                    match = time_range
                    end_dt = datetime.combine(datetime.now(), end_time)
                    if last_endtime is None or last_endtime < end_dt:
                        last_endtime = end_dt
            # else:  # Overnight
            #     if (start_time <= now or now <= end_time) and (not config.get('WEEKDAYS_ONLY', False) or datetime.today().weekday() < 5):
            #         last_schedule = time_range
            #         match = time_range
            #         if start_time < now:
            #             last_endtime = datetime.combine(datetime.now(), end_time) + timedelta(days=1)
            #         else:
            #             last_endtime = datetime.combine(datetime.now(), end_time)

            # Closest start time
            if start_time > now and (closest_start_time is None or start_time < closest_start_time):
                closest_start_time = start_time
            # Earliest start time of the day
            if earliest_start_time is None or start_time < earliest_start_time:
                earliest_start_time = start_time

        if last_endtime:
            last_delay = last_endtime
        if match:
            closest_start_time = None

        return match

    except FileNotFoundError:
        initialize_new_schedule()
        
    except Exception as e:
        timestamped_print(f"Error during reading schedule: {error(e)}")
        return False

last_playlist=''
last_randomqueue=None
randomqueuefix_playlist=None
randomqueuefix_run=False
def play_music():
    global last_playlist, last_spotify_run, closest_start_time, last_randomqueue, user_id, randomqueuefix_playlist, randomqueuefix_run
    try:
        if target_device:
            PLAYLIST_ID=get_value_for_schedule(value="playlist")
            if PLAYLIST_ID:
                closest_start_time=None
                randomqueue=get_value_for_schedule(value="randomqueue")
                playlist_info=get_playlist_info(PLAYLIST_ID)
                if (randomqueue and "37i9dQ" not in PLAYLIST_ID):
                    if (last_playlist==PLAYLIST_ID and randomqueuefix_playlist) and (spotify_button_check() and config['AUTO_SPOTIFY'] and config['KILLSWITCH_ON']): # hotfix for spotify client not playing random queue; cause: when spotify's api has problems, client doesn't see any tracks in playlist unless manually clicked; fix requires killing and autorunning spotify enabled; fix doesn't work when different playlist was playing before without any pause - spotify's api reports that music is playing, but actually it's not
                        if not randomqueuefix_run: #restart only once
                            killswitch("Spotify not playing random queue, restarting client.")
                            run_spotify()
                            randomqueuefix_run=True
                            timestamped_print("Spotify client restarted, waiting 5 seconds...")
                            t.sleep(5)
                        sp.start_playback(device_id=target_device["id"], context_uri=f"spotify:playlist:{randomqueuefix_playlist}")
                        t.sleep(2.5) # give spotify some time to start playback, specially when api is slow
                    else:
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
                        randomqueuefix_playlist=temp_playlist['id']
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
    global last_playlist, target_device, randomqueuefix_playlist, randomqueuefix_run
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
                if (not current_playback) or (not current_playback["is_playing"]) or (not last_playlist==PLAYLIST_ID) or (target_device and target_device["id"]!=active_device["id"]) or (last_randomqueue!=randomqueue):
                    if PLAYLIST_ID:
                        play_music()
                    else:
                        status.set(_("Playlist not set"))
                else:
                    status.set(_("Music is currently playing."))
                    randomqueuefix_playlist=None
                    randomqueuefix_run=False
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
    print("# Donation: https://szymonandrzejewski.pl/donate/paypal")
    print(f"# Data is stored in {DATA_DIRECTORY}\n") 

    set_up()
    refresh_settings()
    initialize_sp()
        
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
        root.after(240000, fetch_playlists_loop)

    initialize_new_schedule()
    refresh_schedule_display()

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
                                nextplay=f" | {_("That's all for today!")}"

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
