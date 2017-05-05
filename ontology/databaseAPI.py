# -*- coding: utf-8 -*-
import spotipy
import argparse
import pprint

from operator import itemgetter
from spotipy.oauth2 import SpotifyClientCredentials

class Database():
    def __init__(self,verbose=False):
        self.__sp = spotipy.Spotify()
        self.__sp.trace = verbose #NOTE dubug

    def get_artist(self, artist_name):
        results = self.__sp.search(q='artist:' + artist_name, type='artist')
        items = results['artists']['items']
        return items

    def get_album(self, album_name):
        results = self.__sp.search(q='album:' + album_name, type='album')
        items = results['albums']['items']
        return items
    def get_track(self, track_name):
        results = self.__sp.search(q='track:' + track_name, type='track')
        items = results['tracks']['items']
        return items

    def search(self, slots):
        query = ""
        filters = ['artist', 'track']
        for f in filters:
            if f in slots.keys():
                query += '%s:%s ' % (f, slots[f])

        results = self.__sp.search(q=query, type='track')
        items = results['tracks']['items']
        if len(items) > 0:
            items = sorted(items,key=itemgetter('popularity'),reverse=True)
            sentence = (u'幫你播 ' + items[0]['artists'][0]['name'] + u' 的 ' + items[0]['name'])
        else:
            sentence = (u'Sorry Not Found...')
        print(sentence)
        return items, sentence

    def info(self, slots):
        ### TODO list more songs
        if 'artist' in slots:
            items = self.get_artist(slots['artist'])
            if len(items) > 0:
                artist = items[0]
                album = self.get_artist_albums(artist)[0]
                tracks = self.show_album_tracks(album)
                tracks = [tracks[i]['name'] for i in range(len(tracks))]
                ### NOTE currently only return newest album's songs
                return {'artist':artist['name'],'genre':artist['genres'],\
                        'album':album['name'], 'track':tracks}

        if 'track' in slots:
            items = self.get_track(slots['track'])
            tracks = items[0]
            return {'artist':tracks['artists'][0]['name'], 'album':tracks['album']['name'],\
                    'track':tracks['name']}

    def recommend(self, slots):
        client_credentials_manager = SpotifyClientCredentials()
        self.__sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

        seed_artists = None
        seed_tracks = None
        seed_genres = None
        ### TODO: use artist & track lists
        if 'track' in slots:
            seed_tracks = [self.get_track(slots['track'])[0]['id']]
        if 'artist' in slots:
            seed_artists = [self.get_artist(slots['artist'])[0]['id']]
        if 'genre' in slots:
            seed_genres = [slots['genre']]

        items = self.__sp.recommendations(seed_tracks=seed_tracks, seed_artists=seed_artists,
                seed_genres=seed_genres, limit=6)['tracks']
        tracks = [items[i]['name'] for i in range(len(items))]
        return tracks


    def show_album_tracks(self, album):
        tracks = []
        results = self.__sp.album_tracks(album['id'])
        tracks.extend(results['items'])
        while results['next']:
            results = sp.next(results)
            tracks.extend(results['items'])
        
        return tracks

    def get_artist_albums(self, artist):
        albums = []
        results = self.__sp.artist_albums(artist['id'], album_type='album')
        albums.extend(results['items'])
        while results['next']:
            results = self.__sp.next(results)
            albums.extend(results['items'])
        print('Total albums:', len(albums))
        
        return albums

    def show_artist(self, artist):
        print('====', artist['name'], '====')
        print('Popularity: ', artist['popularity'])
        if len(artist['genres']) > 0:
            print('Genres: ', ','.join(artist['genres']))

def build_slot(sentence,pos):
    '''
        sentence: [你,的,English,真,的,是,very,good,的,呢]
    '''
    slot_content = {'artist':'','album':'','track':''}
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

    db = Database()
    slots = {
        'artist': args.artist,
        #'album': args.album,
        #'track': args.track
    }
    print db.recommend({'track':'superhero'})
    db.search(slots)
    

