database = {}

def store_song(song_name, hashes):
    for h, t in hashes:
        if h not in database:
            database[h] = []
        database[h].append((song_name, t))

def get_matches(hashes):
    matches = []

    for h, t in hashes:
        if h in database:
            matches.extend(database[h])

    return matches