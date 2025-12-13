# Changelog

## 2.0.0
### Added:
- new "Schedule" tab with a calendar which allows for setting different schedules for different days
- device picker in "Settings" tab

### Fixed:
- fixed minor bugs

## 1.13.2
### Fixed:
- fixed an error "argument of type 'NoneType' is not iterable" during a playlist GUI refresh, when a playlist is not set

## 1.13.1
### Added:
- hotfix for spotify client not playing random queue; cause: when spotify's api has problems, client doesn't see any tracks in playlist unless manually clicked; fix requires killing and autorunning spotify enabled

## 1.13.0
### Added:
- import/export playlists feature
- warning when not using Spotify Premium

## Changed
- using more API scopes (you might need to reauthorize an app after update)

## Removed:
- metadata and randomqueue support for Spotify curated playlists (due to API changes)

## 1.12.0
### Added:
- scrollbar in console tab
- unsaved changes notice, set to default device name in settings tab
- skip explicit tracks option
- warning for web players

### Changed:
- better caching of api requests
- updated dependencies
- display no image when unable to fetch now playing
- changed about tab

### Fixed:
- Spotify's playlist weren't played when Random queue was enabled

## 1.11.4
### Added:
- requests timeout to prevent freezing

### Changed:
- display only first 50 characters of title, author or playlist/album name

## 1.11.3
### Fixed
- fixed "time data does not match format '%Y-%m-%dT%H:%M:%S.%fZ'

## 1.11.2
### Changed
- redirect URI changed to 127.0.0.1 from localhost - <b>you need to update it in Spotify for Developers to `http://127.0.0.1:23918`</b> ([that's why](https://developer.spotify.com/blog/2025-02-12-increasing-the-security-requirements-for-integrating-with-spotify))

## 1.11.1
### Added:
- auto refresh schedule table on file change

### Changed:
- code refactor

### Removed
- console log when loading schedule into table

## 1.11.0
### Added:
- <b>random queue feature</b> - when enabled for a specific time slot, Spotify Scheduler will make new, temporary playlist with a random tracks from selected playlist and play it. It was added because Spotify's shuffle feature sucks.
- different app title when automation is paused

### Changed:
- removed "Killswitch" name from settings

## 1.10.1
### Fixed:
- translation ("Schedule is empty")

## 1.10.0
### Added:
- overnight schedules (e.g. 23:00-1:00)
- placeholder img on now playing tab
- exit popup
- empty schedule info
- "plays in" on next day
- changelog

### Fixed:
- duplicate API requests when nothing is playing

### Changed:
- delay for fetching user's playlists is now 90 seconds
- delay for fetching recently played is now 5 minutes

## 1.9.1
added plays in/stops in time in title bar, spacing fixes, display user's email

## 1.9.0
renamed main script to spotifyscheduler.py, changed requirements, stability fixes (dont retry on rate limit), **added recently played tab**, display date on refresh playlists

## 1.8.2
data are now being stored in user data dir, please backup your data on update.

## 1.8.1
build changes (back to building with pyinstaller)

## 1.8.0
app runs in windowed mode without console (now builded using nuitka), displaying errors added to gui, added credentials prompt gui on first run, code refactor and improvements, no more delay on startup, auto set default language, improved stability and reliability...

... and fixed **a lot** of bugs.

## 1.7.4
"delete cache" button fix

## 1.7.3
run and auto-launch spotify, checklist and killswitch now works with Linux, fixed issue with device name detection

## 1.7.2
stability fixes

## 1.7.1
added **validating client credentials**, changed default settings for Killswitch and Auto-launch spotify, improved stability, bug fixes

## 1.7.0
changes on getting playlist info, **added support for time format with seconds in schedule**, current time and new update status displayed in title, fixed behavior on expired and not refreshed access token...

...and fixed **a lot** of bugs.

## 1.6.2:
fixes on getting playlist data, added placeholder image in playlist tab, added delay before opening spotify developers page

## 1.6.1:
fixes on quickedit disable feature

## 1.6.0
Added anonymous fetching from API for Spotify-owned playlists, different color for errors in console, displaying album name when playlist can't be fetched, removed showing playlist id on checklist, playing music on selected device if different device is active, fetching users playlist every minute, console output changes, MIT license...

...and fixed **a lot** of bugs.

## 1.5.2
changed loop to 2.5s from 5s

## 1.5.1
missing keys config fix, auto-launch spotify feature, massively reduced API calls

## 1.5.0
This update changed previous redirect uri from http://localhost:8080 to http://localhost:23918. Before running new version, go to https://developer.spotify.com/dashboard and change redirect uri.

Fixes on non-windows systems

## 1.4.2
render run spotify button only when spotify installation is detected

## 1.4.1
fixed exception on getting playlist

## 1.4.0
fixes

## 1.3.3
fix defender

## 1.3.2
fix open link

## 1.3.1
quickedit fix and other fixes

## 1.3.0
Added scheduling playlists for certain hours.
Fixed bugs.

## 1.2.4
fixes

## 1.2.3
linux fixes

## 1.2.2
icon on about page, fixes

## 1.2.1
killswitch fix

## 1.2.0
first release

