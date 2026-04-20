🎵 MusicFinder — AI Music Recognition App
A full-stack music recognition web app inspired by Shazam. Simply upload an audio file or record live audio — the app automatically identifies the song and displays full details in seconds.
✨ Features

🎤 Live Recording — auto-identifies every 10 seconds, no button needed
📂 File Upload — supports MP3, WAV, WebM and more
🎯 Real-time Recognition — powered by ACRCloud's audio fingerprinting
📀 Full Song Details — title, artist, album, label, genre, release date, duration
🔗 Streaming Links — direct links to Spotify, YouTube & Apple Music
🌙☀️ Dark / Light Theme — toggle between themes
🎨 Animated UI — Shazam-style recording animation with sound wave visualizer

🛠 Tech Stack

Frontend — React.js
Backend — Python Flask
Recognition API — ACRCloud
Metadata APIs — iTunes Search API, MusicBrainz
Audio Processing — Librosa, SoundFile, FFmpeg

⚙️ How It Works

Audio is captured or uploaded
A 10-second snippet is extracted and sent to ACRCloud
Song metadata is enriched via iTunes and MusicBrainz APIs in parallel
Result is displayed instantly with album art and streaming links