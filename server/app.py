import os
import time
import hmac
import hashlib
import base64
import requests
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import subprocess

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "supports_credentials": True}})

# ACRCloud Configuration
ACR_ACCESS_KEY = os.getenv("ACR_ACCESS_KEY")
ACR_ACCESS_SECRET = os.getenv("ACR_ACCESS_SECRET")
ACR_HOST = os.getenv("ACR_HOST")

if not all([ACR_ACCESS_KEY, ACR_ACCESS_SECRET, ACR_HOST]):
    print("WARNING: Missing ACRCloud environment variables!")

ACR_URL = f"https://{ACR_HOST}/v1/identify" if ACR_HOST else None

# Constants
SNIPPET_SECONDS = 10
MIN_SCORE = 0.3

session = requests.Session()


def build_signature(timestamp):
    """Build HMAC signature for ACRCloud API."""
    string_to_sign = f"POST\n/v1/identify\n{ACR_ACCESS_KEY}\naudio\n1\n{timestamp}"
    return base64.b64encode(
        hmac.new(
            os.getenv("ACR_ACCESS_SECRET").encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha1
        ).digest()
    ).decode("utf-8")


def recognize_with_acr(wav_path):
    """Send audio to ACRCloud for recognition."""
    timestamp = str(int(time.time()))
    signature = build_signature(timestamp)
    
    with open(wav_path, "rb") as f:
        audio_data = f.read()
    
    files = {"sample": ("sample.wav", audio_data, "audio/wav")}
    data = {
        "access_key": os.getenv("ACR_ACCESS_KEY"),
        "sample_bytes": str(len(audio_data)),
        "timestamp": timestamp,
        "signature": signature,
        "data_type": "audio",
        "signature_version": "1",
    }
    
    return session.post(ACR_URL, files=files, data=data, timeout=20).json()


def fetch_itunes(title, artist):
    """Fetch metadata from iTunes API."""
    try:
        r = session.get(
            "https://itunes.apple.com/search",
            params={
                "term": f"{title} {artist}",
                "media": "music",
                "limit": 1,
                "entity": "song"
            },
            timeout=5
        )
        results = r.json().get("results", [])
        if not results:
            return {}
        
        item = results[0]
        return {
            "Image": item.get("artworkUrl100", "").replace("100x100", "400x400"),
            "album": item.get("collectionName", ""),
            "release_date": item.get("releaseDate", "")[:10],
            "genre": item.get("primaryGenreName", ""),
            "duration_ms": item.get("trackTimeMillis", 0),
            "apple_url": item.get("trackViewUrl", ""),
        }
    except Exception as e:
        app.logger.error(f"[iTunes ERROR] {e}")
        return {}


def fetch_musicbrainz(title, artist):
    """Fetch metadata from MusicBrainz API."""
    try:
        r = session.get(
            "https://musicbrainz.org/ws/2/recording",
            params={
                "query": f'recording:"{title}" AND artist:"{artist}"',
                "fmt": "json",
                "limit": 1,
                "inc": "releases+tags",
            },
            headers={"User-Agent": "MusicRecognizerApp/1.0 (student-project)"},
            timeout=5
        )
        recordings = r.json().get("recordings", [])
        if not recordings:
            return {}
        
        Rec = recordings[0]
        releases = Rec.get("releases", [])
        
        label = release_date = album = ""
        if releases:
            rel = releases[0]
            album = rel.get("title", "")
            release_date = rel.get("date", "")
            label_info = rel.get("label-info", [])
            if label_info:
                Label = label_info[0].get("label", {}).get("name", "")
        
        Genres = [t["name"] for t in Rec.get("tags", [])[:4]]
        duration_ms = Rec.get("length", 0)
        Duration = ""
        if duration_ms:
            secs = int(duration_ms) // 1000
            Duration = f"{secs // 60}:{secs % 60:02d}"
        
        return {
            "genres": Genres,
            "duration": Duration,
            "label": Label,
            "release_date": release_date,
            "album": album
        }
    except Exception as e:
        app.logger.error(f"[MusicBrainz ERROR] {e}")
        return {}


def convert_webm_to_wav(webm_path, wav_path):
    """
    Convert WebM audio to WAV format using ffmpeg.
    Render has ffmpeg pre-installed.
    """
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", webm_path,
            "-ar", "44100", "-ac", "1",
            "-sample_fmt", "s16",
            wav_path
        ], check=True, capture_output=True)
        return True
    except Exception as e:
        raise Exception(f"FFmpeg conversion failed: {e}")


def load_audio(file_path):
    """
    Load audio file - supports WAV, FLAC, OGG but NOT WebM.
    Returns: (audio_data, sample_rate)
    """
    import soundfile as sf
    try:
        data, samplerate = sf.read(file_path)
        
        # Convert to mono if stereo
        if len(data.shape) > 1:
            data = data.mean(axis=1)
        
        return data, samplerate
    
    except Exception as e:
        raise Exception(f"Failed to load audio: {str(e)}")


@app.route("/recognize", methods=["POST"])
def recognize():
    """Main recognition endpoint."""
    app.logger.info("Recognize endpoint called")
    
    # Check if ACRCloud is configured
    if not all([ACR_ACCESS_KEY, ACR_ACCESS_SECRET, ACR_HOST]):
        return jsonify({"error": "Server configuration error: ACRCloud not configured"}), 500
    
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    
    # Use /tmp for Render's ephemeral filesystem
    temp_dir = "/tmp"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Get file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    app.logger.info(f"Received file: {file.filename} (type: {file_ext})")
    
    # Save uploaded file
    file_path = os.path.join(temp_dir, file.filename)
    file.save(file_path)
    
    # If WebM, convert to WAV first
    wav_path = os.path.join(temp_dir, "processed.wav")
    
    if file_ext == ".webm":
        try:
            convert_webm_to_wav(file_path, wav_path)
            file_path = wav_path  # Use converted file for processing
        else:
        # Copy/rename to .wav if not already
        wav_path = file_path
    
    try:
        # Load and process audio (now in WAV format)
        y, sr = load_audio(wav_path)
        
        # Resample to 44100 Hz for ACRCloud
        target_sr = 44100
        if sr != target_sr:
            try:
                import librosa
                y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
                sr = target_sr
            except Exception as e:
                app.logger.error(f"Resample error: {e}")
                return jsonify({"error": f"Audio resampling failed: {str(e)}"}), 500
        
        # Extract 10s snippet from 20% into the song
        total_samples = len(y)
        snippet_samples = int(SNIPPET_SECONDS * sr)
        
        if total_samples > snippet_samples:
            start = int(total_samples * 0.20)
            start = min(start, total_samples - snippet_samples)
            y = y[start:start + snippet_samples]
        
        # Save processed audio as WAV for ACRCloud
        final_wav = os.path.join(temp_dir, "final.wav")
        import soundfile as sf
        sf.write(final_wav, y, sr, subtype="PCM_16")
        
        size_kb = os.path.getsize(final_wav) // 1024
        app.logger.info(f"[Audio] Snippet: {len(y)/sr:.1f}s | SR: {sr} | Size: {size_kb}KB")
        
        # ACRCloud recognition
        acr_result = recognize_with_acr(final_wav)
        app.logger.info(f"[ACRCloud Response] {acr_result}")
        
        status_code = acr_result.get("status", {}).get("code", -1)
        
        if status_code == 1001:
            return jsonify({"result": "No match found"})
        
        if status_code != 0:
            msg = acr_result.get("status", {}).get("msg", "Unknown error")
            return jsonify({"error": f"ACRCloud error: {msg}"}), 500
        
        metadata = acr_result.get("metadata", {})
        Music_list = metadata.get("music") or metadata.get("humming") or []
        
        if not Music_list:
            return jsonify({"result": "No match found"})
        
        # Get best match with confidence check
        music = sorted(Music_list, key=lambda x: x.get("score", 0), reverse=True)[0]
        score = music.get("score", 0)
        
        if score < MIN_SCORE:
            app.logger.warning(f"[WARN] Low confidence score: {score} — rejecting")
            return jsonify({"result": "No match found"})
        
        Title = music.get("title", "Unknown")
        Artist = ", ".join(a.get("name", "") for a in music.get("artists", []))
        ISRC = music.get("external_ids", {}).get("isrc", "")
        
        # Calculate timecode
        timecode = ""
        offset_ms = music.get("play_offset_ms")
        if offset_ms:
            secs = int(offset_ms) // 1000
            timecode = f"{secs // 60}:{secs % 60:02d}"
        
        # Get Spotify track ID
        spotify_track_id = music.get("external_metadata", {}).get("spotify", {}).get("track", {}).get("id", "")
        
        # Fetch metadata in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_itunes = executor.submit(fetch_itunes, Title, Artist)
            future_mb = executor.submit(fetch_musicbrainz, Title, Artist)
            itunes = future_itunes.result()
            mb = future_mb.result()
        
        # Merge metadata
        Image = itunes.get("Image", "")
        album = itunes.get("album") or music.get("album", {}).get("name", "") or mb.get("album", "")
        release_date = itunes.get("release_date") or music.get("release_date", "") or mb.get("release_date", "")
        label = music.get("label", "") or mb.get("label", "")
        
        Genres = mb.get("genres", [])
        if not Genres and itunes.get("genre"):
            Genres = [itunes["genre"]]
        
        apple_url = itunes.get("apple_url", "")
        
        Duration = mb.get("duration", "")
        if not Duration and itunes.get("duration_ms"):
            secs = int(itunes["duration_ms") // 1000
            Duration = f"{secs // 60}:{secs % 60:02d}"
        
        # Build streaming links
        if spotify_track_id:
            spotify_url = f"https://open.spotify.com/track/{spotify_track_id}"
        else:
            spotify_url = f"https://open.spotify.com/search/{requests.utils.quote(Title + ' ' + Artist)}"
        
        youtube_url = f"https://www.youtube.com/results?search_query={requests.utils.quote(Title + ' ' + Artist)}"
        
        app.logger.info(f"[MATCH] {Title} — {Artist} (score: {score})")
        
        return jsonify({
            "song": Title,
            "artist": Artist,
            "album": album,
            "release_date": release_date,
            "label": Label,
            "genres": Genres,
            "score": score,
            "timecode": timecode,
            "duration": Duration,
            "isRC": ISRC,
            "Image": Image,
            "apple_url": apple_url,
            "spotify_url": spotify_url,
            "youtube_url": youtube_url,
        })
    
    except Exception as e:
        app.logger.error(f"[ERROR] {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500
    
    finally:
        # Cleanup temp files
        for p in [file_path, wav_path if file_ext == ".webm" else None, final_wav]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception as e:
                app.logger.warning(f"[Cleanup ERROR] {e}")


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": int(time.time()),
        "acr_configured": all([ACR_ACCESS_KEY, ACR_ACCESS_SECRET, ACR_HOST]),
        "acr_host": ACR_HOST
    })


@app.route("/")
def home():
    """Root endpoint."""
    return jsonify({
        "message": "Music Recognition API",
        "endpoints": {
            "recognize": "/recognize (POST)",
            "health": "/health (GET)"
        }
    })


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))