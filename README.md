# Spotify Scheduler
This python script allows to schedule playing spotify playlist at time range specifed in `schedule.txt` (e.g. 8:00-8:15)

## Usage
Clone this repository (`git clone https://github.com/sandrzejewskipl/spotify-scheduler.git`) <br>

Make sure you got python installed. Download requirements by typing `pip install -r requirements.txt`<br>

Remove `.example` from file names of `.env.example` and `schedule.txt.example`

Next, go to https://developer.spotify.com/dashboard and create an app. Set redirect URI to `http://localhost:8080` and select Web API and Web Playback SDK. Then, go to your app settings and copy Client ID and Client secret and paste them in .env file.

### .env
```
CLIENT_ID=your_client_id # Replace with your client id  
CLIENT_SECRET=your_client_secret # Replace with your client secret
PLAYLIST_ID=your_playlist_id # Replace with your playlist ID that will be played
DEVICE_NAME=DESKTOP # Replace with spotify device name (if you don't know, you can run script without changing it and it will print devices connected to your account)
```
Modify your schedule file `schedule.txt`, example below
```
8:45-8:55
9:40-9:45
10:30-10:45
11:30-11:35
12:20-12:25
13:10-13:25
14:10-14:15
16:12-16:38
```



## Run
`python main.py`

On first run, OAuth from spotify should pop up.
