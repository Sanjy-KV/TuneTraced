from audio_utils import load_audio, generate_spectrogram
from fingerprint import find_peaks, generate_hashes
from database import store_song, get_matches

# 🎵 SONG 1 (store in DB)
y1, sr1 = load_audio("../data/song.mp3")
spec1 = generate_spectrogram(y1, sr1)
peaks1 = find_peaks(spec1)
hashes1 = generate_hashes(peaks1)

store_song("Song 1", hashes1)

# 🎵 SONG 2 (store in DB)
y2, sr2 = load_audio("../data/song2.mp3")
spec2 = generate_spectrogram(y2, sr2)
peaks2 = find_peaks(spec2)
hashes2 = generate_hashes(peaks2)

store_song("Song 2", hashes2)

# 🔍 QUERY SONG (test recognition)
yq, srq = load_audio("../data/song.mp3")  # try changing later
specq = generate_spectrogram(yq, srq)
peaksq = find_peaks(specq)
hashesq = generate_hashes(peaksq)

matches = get_matches(hashesq)

# 🎯 Count matches per song
match_count = {}

for song_name, _ in matches:
    match_count[song_name] = match_count.get(song_name, 0) + 1

# 🎉 Find best match
best_match = max(match_count, key=match_count.get)

print("\n🎵 Detected Song:", best_match)
print("Match Scores:", match_count)