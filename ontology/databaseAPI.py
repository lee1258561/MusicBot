# -*- coding: utf-8 -*-
import spotipy
import spotipy.util
import argparse
import pprint
import json

from random import randrange
from operator import itemgetter
from spotipy.oauth2 import SpotifyClientCredentials

SCOPE = ('playlist-modify-private playlist-read-private playlist-modify-public '
         'playlist-read-collaborative')
SPOTIFY_EMBED_PREFIX = 'https://open.spotify.com/embed?uri='

class Database():
    def __init__(self, genre_map_path, spotify_playlist_map_path, spotify_id,verbose=False):
        client_credentials_manager = SpotifyClientCredentials()
        self.__sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        token = spotipy.util.prompt_for_user_token(spotify_id, SCOPE)
        self.__sp = spotipy.Spotify(auth=token)
        
        self.spotify_id = spotify_id
        self.__sp.trace = verbose #NOTE dubug

        with open(genre_map_path,'r') as f:
            self.genre_map = json.load(f)
        with open(spotify_playlist_map_path) as f:
            self.spotifyPL2uri = json.load(f)

    def __get_artist(self, artist_name):
        results = self.__sp.search(q='artist:' + artist_name, type='artist', limit=50)
        items = results['artists']['items']
        return items

    def __get_album(self, album_name):
        results = self.__sp.search(q='album:' + album_name, type='album')
        items = results['albums']['items']
        return items

    def __get_track(self, track_name):
        results = self.__sp.search(q='track:' + track_name, type='track', limit=50)
        items = results['tracks']['items']
        return items

    def check_track(self, track_name):
        ''' Return number of track search results '''
        items = self.__get_track(track_name)
        n = 0
        for item in items:
            if item['name'].lower() == track_name.lower():
                n += 1
        return n

    def check_artist(self, artist_name):
        ''' Return number of artist search results '''
        items = self.__get_artist(artist_name)
        n = 0
        for item in items:
            if item['name'].lower() == artist_name.lower():
                n += 1
        return n

    def search(self, slots):
        query = ""
        filters = ['artist', 'track']
        url = ''
        for f in filters:
            if f in slots.keys():
                query += '%s:%s ' % (f, slots[f])
        if 'track' in slots.keys(): # if search for track
            results = self.__sp.search(q=query, type='track')
            items = results['tracks']['items']
            if len(items) > 0:
                #items = sorted(items,key=itemgetter('popularity'),reverse=True)
                sentence = (u'幫你播 ' + items[0]['artists'][0]['name'] + u' 的 ' + items[0]['name'])
                url = SPOTIFY_EMBED_PREFIX + items[0]['uri']
            else:
                sentence = (u'Sorry Not Found...')

        else: # else search for artist
            results = self.__sp.search(q=query, type='artist')
            items = results['artists']['items']
            if len(items) > 0: # found something
                sentence = (u'幫你播 ' + items[0]['name'] + u' 的歌')
                url = SPOTIFY_EMBED_PREFIX + items[0]['uri']
            else:
                sentence = (u'Sorry Not Found...')
        #print(sentence)
        return items, sentence, url

    def info(self, slots):
        ### TODO list more songs
        if 'artist' in slots:
            items = self.__get_artist(slots['artist'])
            if len(items) > 0:
                artist = items[0]
                album = self.____get_artist_albums(artist)[0]
                tracks = self.__show_album_tracks(album)
                tracks = [tracks[i]['name'] for i in range(len(tracks))]

                ### NOTE currently only return newest album's songs
                infos = {'artist':artist['name'],'genre':artist['genres'],\
                        'album':album['name'], 'track':tracks}

                ### build sentence
                sentence = (u''+infos['artist'])
                sentence += u' 曲風:'
                for g in artist['genres']:
                    sentence += g + ', '
                sentence = sentence[:-2] + u' 最熱門的歌曲:'

                top_songs = self.__sp.artist_top_tracks(artist['uri'])['tracks']
                for i,s in enumerate(top_songs):
                    sentence += u' ' + s['name']
                    if i >=2:
                        break
                #sentence += u'專輯:'+ album['name']+u'歌曲:'+tracks[0]
                print(sentence)
            else:
                sentence = (u'Sorry Not Found...')
                infos = {}

        elif 'track' in slots:
            items = self.__get_track(slots['track'])
            if len(items) > 0:
                tracks = items[0]
                infos = {'artist':tracks['artists'][0]['name'],\
                        'album':tracks['album']['name'], 'track':tracks['name']}
                sentence = (u'這是'+infos['artist']+u'的歌曲 專輯:'+ infos['album']+u' 歌曲:'+infos['track'])
            else:
                sentence = (u'Sorry Not Found...')
                infos = {}

        return infos, sentence

    def recommend(self, slots):

        seed_artists = None
        seed_tracks = None
        seed_genres = None
        ### TODO: use artist & track lists
        if 'track' in slots:
            tracks_get = self.__get_track(slots['track'])
            if len(tracks_get) > 0:
                seed_tracks = [tracks_get[0]['id']]
        if 'artist' in slots:
            artists_get = self.__get_artist(slots['artist'])
            if len(artists_get) > 0:
               seed_artists = [artists_get[0]['id']]
        if 'genre' in slots:
            if slots['genre'] in self.genre_map:
                seed_genres = [self.genre_map[slots['genre']]]

        try:
            items = self.__sp.recommendations(seed_tracks=seed_tracks, seed_artists=seed_artists,
                    seed_genres=seed_genres, limit=6)['tracks']
        except spotipy.client.SpotifyException:
            items = []
            print (u'All seeds are None')

        urls = []
        if len(items) > 0:  # if items found
            sentence = u'為你推薦 '
            tracks = []
            for i,track in enumerate(items):
                sentence += u'' + track['artists'][0]['name'] + u'的' + track['name'] + u','
                url = SPOTIFY_EMBED_PREFIX + track['uri']
                urls.append(url)
                tracks.append(track['name'])
                if i >=3:
                    break
            sentence = sentence[:-1]
        else:
            tracks = []
            sentence = (u'No recommended songs...')
        #print(sentence)
        return tracks, sentence, urls


    def playlistCreate(self, username, playlist_name):
        url = ''
        sentence = ''
        
        token = spotipy.util.prompt_for_user_token(self.spotify_id, SCOPE)
        self.__sp = spotipy.Spotify(auth=token)

        playlist_name_db = self.__playlist_name2dbname(username, playlist_name)
        playlists = self.__sp.user_playlist_create(self.spotify_id, playlist_name_db, public=False)
        sentence = u'為您新增播放清單 '+ playlist_name
        url = SPOTIFY_EMBED_PREFIX + playlists['uri']

        return sentence, url


    def playlistAdd(self, username, playlist_name, slots):
        sentence = ''
        url = ''

        token = spotipy.util.prompt_for_user_token(self.spotify_id, SCOPE)
        self.__sp = spotipy.Spotify(auth=token)
        playlist_id = self.__get_playlist_id(username, playlist_name)

        # handle no track slot bulshit
        if 'track' not in slots:
            sentence = u'請填入歌曲名稱'
            return sentence, url

        items, _, _ = self.search(slots)
        if len(items) > 0 and len(playlist_id) > 0:
            tracks = [ items[0]['id'] ]
            self.__sp.user_playlist_add_tracks(self.spotify_id, playlist_id, tracks)
            sentence = u'為您將 ' + items[0]['artists'][0]['name']+ u' 的 ' + items[0]['name'] + u' 加入清單 ' + playlist_name
            uri = self.__playlist_id2uri(username, playlist_id)
            url = SPOTIFY_EMBED_PREFIX + uri
        
        # error handling
        if len(items) == 0: # if no track found
            sentence += u'很抱歉找不到此歌曲 '
        if len(playlist_id) == 0: # if no playlist found
            sentence += u'沒有播放清單 ' + playlist_name

        return sentence, url

    def playlistPlay(self, username, playlist_name):
        url = ''
        sentence = ''
        token = spotipy.util.prompt_for_user_token(self.spotify_id, SCOPE)
        self.__sp = spotipy.Spotify(auth=token)
        playlist_id = self.__get_playlist_id(username, playlist_name)
        if len(playlist_id) > 0: # if found this playlist
            sentence = u'為您播放清單 ' + playlist_name
            uri = self.__playlist_id2uri(username, playlist_id)
            url = SPOTIFY_EMBED_PREFIX + uri
        else: # if no playlist found
            sentence = u'沒有播放清單 ' + playlist_name

        return sentence, url

    def playlistSpotify(self, playlist_name):
        ''' play spotify playlist  '''
        url = ''
        sentence = ''
        if playlist_name in self.spotifyPL2uri:
            uri = self.__rand(self.spotifyPL2uri[playlist_name])
            url = SPOTIFY_EMBED_PREFIX + uri
            sentence = u'為您播放Spotify播放清單 ' + playlist_name
        return sentence, url


    def playlistShow(self, username):
        ''' Show all of the user's playlist '''
        sentence = ' '
        playlists = self.__get_all_playlists(username)
        playlist_ids = [p['id'] for p in playlists]
        for p in playlists:
            if p['name'] is not None: # handle if no playlist
                sentence += ' ' + self.__playlist_prefix_remove(username, p['name']) + ','
        sentence = sentence[:-1]
        if len(sentence) > 0: # if playlist found
            sentence = u'您的播放清單有: ' + sentence
        else:
            sentence = u'您目前沒有任何播放清單'
        return sentence, playlist_ids

    def playlistTrack(self, username, playlist_name):
        ''' Show all the tracks in this playlist '''
        sentence = ''
        url = ''

        token = spotipy.util.prompt_for_user_token(self.spotify_id, SCOPE)
        self.__sp = spotipy.Spotify(auth=token)

        playlist_id = self.__get_playlist_id(username, playlist_name)
        if len(playlist_id) > 0: # if playlist found
            track_items = self.__sp.user_playlist(self.spotify_id, playlist_id)['tracks']['items']
            tracks = [ t['track']['name'] for t in track_items]
            for t in tracks:
                sentence += ' ' +t + ','
            sentence = sentence[:-1]
            if len(sentence) == 0:
                sentence = u'播放清單 ' + playlist_name + u' 目前沒有任何歌曲'
            else:
                sentence = u'播放清單 ' + playlist_name + u' 有歌曲: ' + sentence
    
            uri = self.__playlist_id2uri(username,playlist_id)
            url = SPOTIFY_EMBED_PREFIX + uri
        else: # no this playlist
            sentence = u'沒有播放清單 ' + playlist_name

        return sentence, url


    def __get_all_playlists(self, username):
        offset = 0
        playlists = []
        if self.__check_user_exist(username):
            token = spotipy.util.prompt_for_user_token(self.spotify_id, SCOPE)
            self.__sp = spotipy.Spotify(auth=token)
            while True:
                playlists_cur = self.__sp.user_playlists(self.spotify_id,
                                offset=offset, limit=50)['items']
                playlists_cur = [p for p in playlists_cur
                                 if self.__playlist_prefix_user_check(username, p['name'])]
                playlists += playlists_cur
                if len(playlists_cur) < 50:
                    break
                offset += 50
        return playlists


    def __get_playlist_id(self, username, playlist_name):
        playlists = self.__get_all_playlists(username)
        playlist_name_db = self.__playlist_name2dbname(username, playlist_name)
        playlist_id = ''
        for p in playlists:
            if p['name'] == playlist_name_db:
                playlist_id = p['id']
                break
        return playlist_id
    

    def __playlist_name2dbname(self, username, playlist_name):
        return username + '@' + playlist_name

    def __playlist_prefix_user_check(self, username, playlist_name):
        return (username + '@') == playlist_name[:len(username+'@')]

    def __playlist_prefix_remove(self, username, playlist_name):
        return playlist_name[len(username+'@'):]

    def __playlist_id2uri(self, username, playlist_id):
        return 'spotify:user:' + username + ':playlist:' + playlist_id

    def __show_album_tracks(self, album):
        tracks = []
        results = self.__sp.album_tracks(album['id'])
        tracks.extend(results['items'])
        while results['next']:
            results = self.__sp.next(results)
            tracks.extend(results['items'])
        
        return tracks

    def __get_artist_albums(self, artist):
        albums = []
        results = self.__sp.artist_albums(artist['id'], album_type='album')
        albums.extend(results['items'])
        while results['next']:
            results = self.__sp.next(results)
            albums.extend(results['items'])
        print('Total albums:', len(albums))
        
        return albums

    def __show_artist(self, artist):
        print('====', artist['name'], '====')
        print('Popularity: ', artist['popularity'])
        if len(artist['genres']) > 0:
            print('Genres: ', ','.join(artist['genres']))

    def __check_user_exist(self, username):
        try:
            self.__sp.user(username)
            return True
        except spotipy.client.SpotifyException:
            print ('No such user: '+username)
            return False

    def __rand(self, item_list):
        return item_list[randrange(len(item_list))]

def build_slot(sentence,pos):
    '''
        sentence: [你,的,English,真,的,是,very,good,的,呢]
    '''
    slot_content = {'artist':'','genre':'','track':''}
    for n in range(len(sentence)):
        w = ''.join(sentence[n])
        if not u'\u4e00' <= w[0] <= u'\u9fff': # check if chinese
            w+=' '

        if pos[n] == 's':
            slot_content['artist'] = slot_content['artist'] + w
        if pos[n] == 'g':
            slot_content['genre'] = slot_content['genre'] + w
        if pos[n] == 't':
            slot_content['track'] = slot_content['track'] + w
    key_list = [s for s in slot_content]
    for s in key_list:
        if len(slot_content[s] ) == 0:
            del slot_content[s]

    return slot_content

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--artist', type=str, help="Artist to query.")
    parser.add_argument('--album', type=str, help="Album to query.")
    parser.add_argument('--track', type=str, help="Track to query.")
    args = parser.parse_args()

    db = Database('../data/genre_map.json', '../data/spotify_playlist.json', 'seq2seq')
    slots = {
        'artist': args.artist,
        #'album': args.album,
        #'track': args.track
    }
    _, sent, url =  db.search({'artist':u'owl city','track':'fireflies'})
    #print sent, url
    #print db.check_artist(u'red hot chili peppers')
    #print db.playlistCreate('asdf','test2')[0]
    #print db.playlistAdd('asdf','test2', {'artist':u'林正','track':u'我不是他'})[0]
    #print (db.playlistPlay('asdf','test2'))[0]
    #print (db.playlistSpotify('taiwan_popular'))[0]
    #print (db.playlistShow('asdf'))[0]
    #print (db.playlistTrack('asdf', 'test2'))[0]


