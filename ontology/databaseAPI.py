# -*- coding: utf-8 -*-
import spotipy
import argparse
import pprint

from operator import itemgetter

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

    def given(self, slots):
        query = ""
        filters = ['artist', 'album', 'track']
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
            results = sp.next(results)
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
        if pos[n] == 'a':
            slot_content['album'] = slot_content['album'] + w
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

    db.given(slots)
    




