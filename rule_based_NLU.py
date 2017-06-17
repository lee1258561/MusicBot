import json
import re

class rule_based_NLU():
    def __init__(self):
        chinese_data = json.load(open('data/chinese_artist.json'))
        englist_data = json.load(open('data/english_artist.json'))
        
        self.artists_list = chinese_data.keys()
        
        tracks_list = []
        for artist in chinese_data:
            for album in chinese_data[artist]:
                for track_name in chinese_data[artist][album]:
                    tracks_list.append(track_name)
        self.tracks_list = [self._filt(e) for e in tracks_list]

        self.genres_list = json.load(open('data/genre_map.json')).keys()


    def _filt(self,track):
        track = re.sub('\'|\.|\=|\-|\/','',track)
        if not track.isalpha():
            track = track.split()[0]
            track = track.split('(')[0]
        return track


    def feed_sentence(self,input_sent):
        cur_artists = []
        cur_tracks = []
        cur_genres = []
        result = {}

        for artist in self.artists_list:
            if artist in input_sent:
                cur_artists.append(artist)
        if len(cur_artists)>0:
            result['artist'] = {}
            for a in cur_artists:
                result['artist'][a] = 1.1 / (1 + 0.15*(len(cur_artists)-1.0))

        for track in self.tracks_list:
            if track in input_sent:
                if len(track)>1:
                    cur_tracks.append(track)
        if len(cur_tracks)>0:
            result['track'] = {}
            for t in cur_tracks:
                result['track'][t] = 1.1 / (1 + 0.15*(len(cur_tracks)-1.0))

        for genre in self.genres_list:
            if genre in input_sent:
                cur_genres.append(genre)
        if len(cur_genres)>0:
            result['genre'] = {}
            for g in cur_genres:
                result['genre'][g] = 2.0

        return result