# Spotify Scheduler
This Python script allows you to schedule playing a Spotify playlist within a specified time range in `schedule.txt` (e.g., 8:00-8:15).

It was created as a school project, so it contains some Polish log messages. The script features a Killswitch, which terminates Spotify processes if there is an issue with stopping the music, ensuring that music does not play outside the scheduled timeframe.

## Usage
<b>Clone the repository</b>

`git clone https://github.com/sandrzejewskipl/spotify-scheduler.git`<br>

<b>Install dependencies:</b><br>
Make sure you have Python installed. Then, download the required packages by running:

`pip install -r requirements.txt`<br>

<b>Configure environment files:</b><br>
Remove the .example suffix from the following files:

`.env.example` → `.env`

`schedule.txt.example` → `schedule.txt`

<b>Set up Spotify App:</b>

- Go to https://developer.spotify.com/dashboard and create a new app.<br>
- Set the Redirect URI to: http://localhost:8080.<br>
- Select Web API and Web Playback SDK.<br>
- In your app settings, copy the Client ID and Client Secret, and paste them into your .env file.<br>


### .env Configuration
```
CLIENT_ID=your_client_id # Replace with your client id  
CLIENT_SECRET=your_client_secret # Replace with your client secret
PLAYLIST_ID=your_playlist_id # Replace with your playlist ID that will be played
DEVICE_NAME=DESKTOP # Replace with your Spotify device name (if unsure, run the script to display connected devices)
KILLSWITCH=true # true or false - If the script can't pause music (e.g., due to losing internet access), it will kill Spotify to prevent playback outside the schedule
```

Modify your schedule file `schedule.txt`, example below.
```
8:45-8:55
9:40-9:45
10:30-10:45
11:30-11:35
12:20-12:25
13:10-13:25
14:10-14:15
```



## Run
`python main.py`

- On the first run, an OAuth window for Spotify should appear.
- There is no need to restart the script when changing the schedule.
- However, you must rerun the script if you modify the .env file.
