import numpy as np
from scipy.ndimage import maximum_filter
import hashlib

# Step 3: Find peaks
def find_peaks(spectrogram, amp_min=10):
    local_max = maximum_filter(spectrogram, size=20) == spectrogram
    peaks = np.where(local_max & (spectrogram > amp_min))
    return list(zip(peaks[0], peaks[1]))

# Step 4: Generate hashes (fingerprints)
def generate_hashes(peaks, fan_value=5):
    hashes = []

    for i in range(len(peaks)):
        for j in range(1, fan_value):
            if i + j < len(peaks):
                freq1, time1 = peaks[i]
                freq2, time2 = peaks[i + j]

                t_delta = time2 - time1

                if 0 < t_delta <= 200:
                    hash_input = f"{freq1}|{freq2}|{t_delta}"
                    h = hashlib.sha1(hash_input.encode()).hexdigest()
                    hashes.append((h, time1))

    return hashes