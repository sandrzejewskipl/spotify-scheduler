<p align="center">
<img src="icon.ico" width='150'>
</p>

# Spotify Scheduler
This Python script application with GUI allows you to schedule a Spotify playlist to play at specific times (e.g. 8:00-8:15).

![Now playing tab](img/now_playing.png)

Easily plan and schedule music for any time of day! Modify your schedule, choose a playlist from the user's playlist library, or directly add a playlist using its ID or link. Perfect for managing music playback effortlessly, whether you're creating a radio station for your school to play music during breaks or events, setting up a music schedule for your workplace, or planning playlists for specific times at venues.

![Schedule](img/schedule.png)
![Playlist](img/playlist.png)


## Running on Windows
Download an `.exe` file from the latest release <a href="https://github.com/sandrzejewskipl/spotify-scheduler/releases">here</a>. 

A `spotify-scheduler_data` folder will be automatically created. This folder contains configuration files and needs to remain in the same directory as your .exe.

On the first run, you will be asked for CLIENT_ID and CLIENT_SECRET from Spotify in a console. Then OAuth popup should open. You <b>need</b> to keep the console running; otherwise, closing it will cause the program to stop.
## Running on Linux or MacOS
<b>Clone the repository (by the command below, or download it)</b>

`git clone https://github.com/sandrzejewskipl/spotify-scheduler.git`<br>

<b>Install dependencies:</b><br>
Make sure you have Python installed. Then, download the required packages by running:

`pip install -r requirements.txt`<br>

<b>Set up Spotify App:</b>

- Go to https://developer.spotify.com/dashboard and create a new app.<br>
- Set the Redirect URI to: `http://localhost:8080`.<br>
- Select Web API and Web Playback SDK.<br>

Run this command from the command line in the same directory.<br>
`python main.py`

On the first run, you will be asked for CLIENT_ID and CLIENT_SECRET from Spotify. Then OAuth popup should open.

## Settings
![Settings](img/settings.png)

You can fully configure your settings and set your schedule using the GUI. If you are unable to display the GUI, you can customize the files in the `spotify-scheduler_data` folder and restart the app to apply the changes.

### Supported languages:
- English (en)
- Polish (pl)

<b>DEVICE NAME</b> - name (or part of it) of the device in Spotify API that will play music. It defaults to "DESKTOP", because default windows computer name starts with "DESKTOP-" and Spotify sets device name of Windows app to it.

<b>Killswitch</b> - feature that kills the Spotify process(es) when an error with API occurs. It prevents playback when it shouldn't be played but API call somehow didn't worked.

<b>Play music only on weekdays</b> - You can play music only on Monday to Friday

## After changing the language, run the script again.
