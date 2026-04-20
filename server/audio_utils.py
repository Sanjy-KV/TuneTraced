import librosa
import numpy as np
import subprocess
import os
import shutil

def get_ffmpeg_path():
    """
    Finds ffmpeg automatically:
    - On Render/Linux: uses system ffmpeg
    - On Windows: checks common install locations
    """
    # First check if ffmpeg is in system PATH (works on Render/Linux)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg

    # Windows fallback paths
    windows_paths = [
        r"C:\Users\Admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    for path in windows_paths:
        if os.path.exists(path):
            return path

    raise RuntimeError("ffmpeg not found. Install ffmpeg and add it to PATH.")


def convert_to_wav(input_path):
    """Convert any audio format to wav using ffmpeg"""
    output_path = input_path.rsplit(".", 1)[0] + "_converted.wav"
    ffmpeg = get_ffmpeg_path()
    try:
        subprocess.run([
            ffmpeg, "-y",
            "-i", input_path,
            "-ac", "1",
            "-ar", "44100",
            "-sample_fmt", "s16",
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