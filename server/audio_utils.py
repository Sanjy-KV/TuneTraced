import librosa
import numpy as np
import subprocess
import os

# Your exact ffmpeg path
FFMPEG_PATH = r"C:\Users\Admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe"

def convert_to_wav(input_path):
    """Convert any audio format to wav using ffmpeg"""
    output_path = input_path.rsplit(".", 1)[0] + "_converted.wav"
    try:
        subprocess.run([
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-ac", "1",
            "-ar", "22050",
            output_path
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg conversion failed: {e.stderr.decode()}")

def load_audio(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    converted_path = None

    # Convert non-standard formats (webm from browser recording, etc.)
    if ext not in [".wav", ".mp3", ".flac", ".ogg"]:
        converted_path = convert_to_wav(file_path)
        load_path = converted_path
    else:
        load_path = file_path

    try:
        y, sr = librosa.load(load_path, sr=None, mono=True)
    finally:
        if converted_path and os.path.exists(converted_path):
            os.remove(converted_path)

    return y, sr

def generate_spectrogram(y, sr):
    S = np.abs(librosa.stft(y))
    return S