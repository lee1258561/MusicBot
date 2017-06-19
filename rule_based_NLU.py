# -*- coding: utf-8 -*-
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

        self.playlist_map = {'sleep':[u'想睡覺',u'休息',u'睡眠',u'晚上',u'睡前'],
                             'taiwan_popular':[u'熱門',u'流行',u'火紅',u'最多人',u'都在聽',u'最近'],
                             'study':[u'讀書',u'考試',u'唸書',u'看書'],
                             'piano':[u'鋼琴'],
                             'relax':[u'放鬆',u'純音樂',u'抒壓'],
                             'japanese_popular':[u'日本'],
                             'korean_popular':[u'韓國'],
                             'global_popular':[u'全球',u'世界'],
                             'japanese_rock':[u'日本搖滾',u'日式搖滾'],
                             'jazz':[u'爵士'],
                             'classical':[u'古典']
                             }

        self.list_name = {u'清單',u'歌單'}
        self.list_crate = {u'創造'} 

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
                result['artist'][a] = 1.1 / (1 + 0.1*(len(cur_artists)-1.0))

        for track in self.tracks_list:
            if track in input_sent:
                if len(track)>1:
                    cur_tracks.append(track)
        if len(cur_tracks)>0:
            result['track'] = {}
            for t in cur_tracks:
                result['track'][t] = 1.1 / (1 + 0.1*(len(cur_tracks)-1.0))

        for genre in self.genres_list:
            if genre in input_sent:
                cur_genres.append(genre)
        if len(cur_genres)>0:
            result['genre'] = {}
            for g in cur_genres:
                result['genre'][g] = 2.0

        cur_num = 100
        cur_playlist = ''
        for playlist_name in self.playlist_map:
            for keyword in self.playlist_map[playlist_name]:
                if keyword in input_sent and len(self.playlist_map[playlist_name])<cur_num:
                    cur_playlist = playlist_name
                    cur_num = len(self.playlist_map[playlist_name])
        if cur_playlist!='':
            result['spotify_playlist'] = {}
            result['spotify_playlist'][cur_playlist] = 2.0

        return result