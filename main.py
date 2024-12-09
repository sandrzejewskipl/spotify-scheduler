# Made by @sandrzejewskipl and chatgpt <3

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime, time
from dotenv import load_dotenv
import os
import time as t
import psutil

# Ładowanie danych z pliku .env
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
PLAYLIST_ID = os.getenv("PLAYLIST_ID")
DEVICE_NAME = os.getenv("DEVICE_NAME")
KILLSWITCH_ON = os.getenv("KILLSWITCH")
REDIRECT_URI = "http://localhost:8080"
SCOPE = "user-modify-playback-state user-read-playback-state"
PROCNAME = "spotify"

def timestamped_print(message):
    current_time = datetime.now().strftime("[%H:%M:%S]")
    print(f"{current_time} {message}")
    
def killswitch():
    if KILLSWITCH_ON=='true':
        for proc in psutil.process_iter():
            # check whether the process name matches
            if PROCNAME.lower() in proc.name().lower():
                proc.kill()
                timestamped_print("Proces spotify został zabity ze względu na brak kontroli.")


# Inicjalizacja Spotipy
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID,
                                               client_secret=CLIENT_SECRET,
                                               redirect_uri=REDIRECT_URI,
                                               scope=SCOPE))


    
# Funkcja sprawdzająca, czy obecny czas mieści się w przedziałach
def is_within_schedule(schedule_file="schedule.txt"):
    try:
        with open(schedule_file, "r") as file:
            lines = file.readlines()
            now = datetime.now().time()
            for line in lines:
                start_str, end_str = line.strip().split('-')
                start_time = datetime.strptime(start_str, "%H:%M").time()
                end_time = datetime.strptime(end_str, "%H:%M").time()
                if start_time <= now <= end_time:
                    return True
    except FileNotFoundError:
        timestamped_print("Plik z harmonogramem nie istnieje.")
    except Exception as e:
        timestamped_print("Błąd:")
        print(f"Błąd podczas odczytu harmonogramu: {e}")
    return False

# Funkcja włączająca playlistę
def play_music():
    try:
        devices = sp.devices()
        if not devices['devices']:
            timestamped_print("Brak aktywnych urządzeń Spotify.")
            return

        # Szukaj urządzenia z nazwą zawierającą 'DEVICE'
        target_device = None
        
        for device in devices['devices']:
            print(device)
        for device in devices['devices']:
            if DEVICE_NAME in device['name'].upper():
                target_device = device['id']
                timestamped_print(f"Znaleziono urządzenie z nazwą zawierającą {DEVICE_NAME}: {device['name']}")
                break

        if target_device:
            sp.start_playback(device_id=target_device, context_uri=f"spotify:playlist:{PLAYLIST_ID}")
            timestamped_print(f"Muzyka odtwarzana na urządzeniu {target_device}.")
        else:
            timestamped_print(f"Nie znaleziono urządzenia z nazwą zawierającą {DEVICE_NAME}.")
        
    except spotipy.exceptions.SpotifyException as e:
        timestamped_print(f"Błąd podczas odtwarzania muzyki: {e}")
        print(f"Status kod błędu: {e.status}")
        print(f"Treść błędu: {e}")
        killswitch()
    except Exception as ex:
        timestamped_print(f"Nieoczekiwany błąd podczas odtwarzania: {ex}")
        killswitch()


# Funkcja pauzująca muzykę
def pause_music():
    try:
        # Pobierz aktualny stan odtwarzacza
        current_playback = sp.current_playback()
        
        if current_playback and current_playback['is_playing']:
            sp.pause_playback()
            timestamped_print("Muzyka zatrzymana.")
        else:
            timestamped_print("Muzyka już jest zatrzymana.")
    except spotipy.exceptions.SpotifyException as e:
        timestamped_print(f"Błąd podczas pauzowania muzyki: {e}")
        print(f"Status kod błędu: {e.status}")
        print(f"Treść błędu: {e}")
        killswitch()        
    except Exception as e:
        timestamped_print(f"Nieoczekiwany błąd podczas pauzowania muzyki: {e}")
        killswitch()

# Główna pętla programu
def main():
    print("!!! Sprawdź poniższy harmonogram na dziś i dostosuj go w razie potrzeby. !!!")
    with open('schedule.txt', 'r') as file:
        content = file.read() 
        print(content)
           
    while True:
        if is_within_schedule():
            timestamped_print("Obecny czas jest w harmonogramie. Sprawdzanie odtwarzania...")
            try:
                current_playback = sp.current_playback()
                
                if not current_playback or not current_playback['is_playing']:
                    play_music()
                else:
                    timestamped_print("Muzyka jest aktualnie odtwarzana.")
                    
            except (spotipy.exceptions.SpotifyException) as e:
                timestamped_print(f"Błąd podczas pobierania stanu odtwarzania: {e}")
                killswitch()

            except Exception as ex:
                timestamped_print(f"Nieoczekiwany błąd: {ex}")
                killswitch()
                

        else:
            timestamped_print("Obecny czas poza harmonogramem. Pauzowanie...")
            pause_music()
        t.sleep(10)  # Sprawdzenie co 30 sekund

if __name__ == "__main__":
    main()