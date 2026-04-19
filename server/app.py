import os
import time
import hmac
import hashlib
import base64
import requests
import numpy as np
import soundfile as sf
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# CORS - Allow all for debugging (restrict in production)
CORS(app, resources={r"/*": {"origins": "*", "supports_credentials": True}})

# ACRCloud Configuration
ACR_ACCESS_KEY = os.getenv("ACR_ACCESS_KEY")
ACR_ACCESS_SECRET = os.getenv("ACR_ACCESS_SECRET")
ACR_HOST = os.getenv("ACR_HOST")

# Validate environment variables
if not all([ACR_ACCESS_KEY, ACR_ACCESS_SECRET, ACR_HOST]):
    print("WARNING: Missing ACRCloud environment variables!")
    print(f"ACR_ACCESS_KEY: {'Set' if ACR_ACCESS_KEY else 'Missing'}")
    print(f"ACR_ACCESS_SECRET: {'Set' if ACR_ACCESS_SECRET else 'Missing'}")
    print(f"ACR_HOST: {'Set' if ACR_HOST else 'Missing'}")

ACR_URL = f"https://{ACR_HOST}/v1/identify" if ACR_HOST else None

# Constants
SNIPPET_SECONDS = 10
MIN_SCORE = 0.3

# Session with connection pooling
session = requests.Session()

def build_signature(timestamp):
    """Build HMAC signature for ACRCloud API."""
    if not ACR_ACCESS_SECRET:
        raise ValueError("ACR_ACCESS_SECRET not configured")
    
    string_to_sign = f"POST\n/v1/identify\n{ACR_ACCESS_KEY}\naudio\n1\n{timestamp}"
    return base64.b64encode(
        hmac.new(
            ACR_ACCESS_SECRET.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha1
        ).digest()
    ).decode("utf-8")


def recognize_with_acr(wav_path):
    """Send audio to ACRCloud for recognition."""
    if not all([ACR_ACCESS_KEY, ACR_ACCESS_SECRET, ACR_HOST]):
        return {"status": {"code": -1, "msg": "ACRCloud not configured"}}
    
    timestamp = str(int(time.time()))
    signature = build_signature(timestamp)
    
    with open(wav_path, "rb") as f:
        audio_data = f.read()
    
    files = {"sample": ("sample.wav", audio_data, "audio/wav")}
    data = {
        "access_key": ACR_ACCESS_KEY,
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
            "image": item.get("artworkUrl100", "").replace("100x100", "400x400"),
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
        
        rec = recordings[0]
        releases = rec.get("releases", [])
        
        label = release_date = album = ""
        if releases:
            rel = releases[0]
            album = rel.get("title", "")
            release_date = rel.get("date", "")
            label_info = rel.get("label-info", [])
            if label_info:
                label = label_info[0].get("label", {}).get("name", "")
        
        genres = [t["name"] for t in rec.get("tags", [])[:4]]
        duration_ms = rec.get("length", 0)
        duration = ""
        if duration_ms:
            secs = int(duration_ms) // 1000
            duration = f"{secs // 60}:{secs % 60:02d}"
        
        return {
            "genres": genres,
            "duration": duration,
            "label": label,
            "release_date": release_date,
            "album": album
        }
    except Exception as e:
        app.logger.error(f"[MusicBrainz ERROR] {e}")
        return {}


def load_audio(file_path):
    """
    Load audio file and convert to mono if needed.
    Returns: (audio_data, sample_rate)
    """
    try:
        # Read audio file
        data, samplerate = sf.read(file_path)
        
        # Convert to mono if stereo (2 channels)
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
    
    file_path = os.path.join(temp_dir, file.filename)
    wav_path = os.path.join(temp_dir, "processed.wav")
    
    try:
        # Save uploaded file
        file.save(file_path)
        app.logger.info(f"File saved: {file_path}")
        
        # Check file size (Render free tier has limits)
        file_size = os.path.getsize(file_path)
        app.logger.info(f"File size: {file_size} bytes")
        
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            return jsonify({"error": "File too large. Max 10MB allowed."}), 400
        
        # Load and process audio
        try:
            y, sr = load_audio(file_path)
        except Exception as e:
            app.logger.error(f"Audio load error: {e}")
            return jsonify({"error": f"Could not process audio file: {str(e)}"}), 400
        
        app.logger.info(f"Audio loaded: {len(y)} samples, {sr} Hz")
        
        # Resample to 44100 Hz for ACRCloud
        target_sr = 44100
        if sr != target_sr:
            try:
                import librosa
                y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
                sr = target_sr
                app.logger.info(f"Resampled to {sr} Hz")
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
        
        # Save processed audio
        sf.write(wav_path, y, sr, subtype="PCM_16")
        
        size_kb = os.path.getsize(wav_path) // 1024
        app.logger.info(f"[Audio] Snippet: {len(y)/sr:.1f}s | SR: {sr} | Size: {size_kb}KB")
        
        # ACRCloud recognition
        acr_result = recognize_with_acr(wav_path)
        app.logger.info(f"[ACRCloud Response] {acr_result}")
        
        status_code = acr_result.get("status", {}).get("code", -1)
        
        if status_code == 1001:
            return jsonify({"result": "No match found"})
        
        if status_code != 0:
            msg = acr_result.get("status", {}).get("msg", "Unknown error")
            return jsonify({"error": f"ACRCloud error: {msg}"}), 500
        
        metadata = acr_result.get("metadata", {})
        music_list = metadata.get("music") or metadata.get("humming") or []
        
        if not music_list:
            return jsonify({"result": "No match found"})
        
        # Get best match with confidence check
        music = sorted(music_list, key=lambda x: x.get("score", 0), reverse=True)[0]
        score = music.get("score", 0)
        
        if score < MIN_SCORE:
            app.logger.warning(f"[WARN] Low confidence score: {score} — rejecting")
            return jsonify({"result": "No match found"})
        
        title = music.get("title", "Unknown")
        artist = ", ".join(a.get("name", "") for a in music.get("artists", []))
        isrc = music.get("external_ids", {}).get("isrc", "")
        
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
            future_itunes = executor.submit(fetch_itunes, title, artist)
            future_mb = executor.submit(fetch_musicbrainz, title, artist)
            itunes = future_itunes.result()
            mb = future_mb.result()
        
        # Merge metadata
        image = itunes.get("image", "")
        album = itunes.get("album") or music.get("album", {}).get("name", "") or mb.get("album", "")
        release_date = itunes.get("release_date") or music.get("release_date", "") or mb.get("release_date", "")
        label = music.get("label", "") or mb.get("label", "")
        
        genres = mb.get("genres", [])
        if not genres and itunes.get("genre"):
            genres = [itunes["genre"]]
        
        apple_url = itunes.get("apple_url", "")
        
        duration = mb.get("duration", "")
        if not duration and itunes.get("duration_ms"):
            secs = int(itunes["duration_ms"]) // 1000
            duration = f"{secs // 60}:{secs % 60:02d}"
        
        # Build streaming links
        if spotify_track_id:
            spotify_url = f"https://open.spotify.com/track/{spotify_track_id}"
        else:
            spotify_url = f"https://open.spotify.com/search/{requests.utils.quote(title + ' ' + artist)}"
        
        youtube_url = f"https://www.youtube.com/results?search_query={requests.utils.quote(title + ' ' + artist)}"
        
        app.logger.info(f"[MATCH] {title} — {artist} (score: {score})")
        
        return jsonify({
            "song": title,
            "artist": artist,
            "album": album,
            "release_date": release_date,
            "label": label,
            "genres": genres,
            "score": score,
            "timecode": timecode,
            "duration": duration,
            "isrc": isrc,
            "image": image,
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
        for p in [file_path, wav_path]:
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