# -*- coding: utf-8 -*-
import pandas as pd
import sys
import json
import argparse
import numpy as np
from os.path import splitext, basename
from random import randrange, shuffle

import io_utils


'''
Sentence generation based on sentence template from google form
and the artists, tracks, albums, genres data crawled from Spotify
'''


INTENTS = ['search', 'recommend','info','neutral', 'playlistCreate', 'playlistAdd', 'playlistPlay',
           'playlistShow', 'playlistTrack','playlistSpotify']

def opt_parse():
    parser = argparse.ArgumentParser(description=\
            'Slot & intent data generate')
    parser.add_argument('template',help='sentence template')
    parser.add_argument('data',help='artist-album-track json data')
    parser.add_argument('data_english', help='english artist-album-track json data')
    parser.add_argument('genre',help='genres')
    parser.add_argument('playlist_names',help='playlist names')
    parser.add_argument('-output',default='Train',help='output filename prefix')
    parser.add_argument('--nb_per_template',default=100,type=int,\
            help='use 1 template sentences generate n times')
    args = parser.parse_args()
    return args


def slot_sample(s=None,a=None,t=None,g=None,p=None):
    slot = {'[s]':s,'[a]':a,'[t]':t,'[g]':g,'[p]':p}
    return slot


def fill_slot(X,POS,Intent,intent,template,s=None,a=None,t=None,g=None,p=None):
    slot_map = slot_sample(s,a,t,g,p)
    new_temp = io_utils.naive_seg(template)
    pos = [0 for i in range(len(new_temp))]

    for key in slot_map:
        offset = 0
        if key in new_temp and slot_map[key] != None:
            offset = new_temp.index(key)
            slot_content = io_utils.naive_seg(slot_map[key])
            pos = pos[:offset] + [key[1]]*len(slot_content) + pos[offset+1:]
            new_temp = new_temp[:offset] + slot_content + new_temp[offset+1:]


    X.append(new_temp)
    POS.append(pos)
    Intent.append(intent)
    return


def fill_template(data_artist,data_sent,genres, playlist_names, args_output, intent,nb_per_template=100):
    '''
        fill the given [...] slot of template sentences
        then store to file with prefix of args_output
    '''
    ### init
    data_sent = data_sent[data_sent.columns[0]].unique()
    playlist_names = playlist_names[playlist_names.columns[0]].unique()
    X = [] # [[],[],...]
    POS = [] # [[],[],...]
    Intent = [] # []
    
    artists = [s for s in data_artist]
    tracks = []
    for s in data_artist:
        for a in data_artist[s]:
            for t in data_artist[s][a]:
                tracks.append(t)

    genres = [key for key in genres]

    for n,sent in enumerate(data_sent):
        #intent = sent[0].decode('utf-8')
        template = sent.decode('utf-8')
        #print n,intent,template
        if intent in INTENTS:
            for _ in range(nb_per_template):
                t = tracks[randrange(0,len(tracks))] if '[t]' in template else None
                s = artists[randrange(0,len(artists))] if '[s]' in template else None
                g = genres[randrange(0,len(genres))] if '[g]' in template else None
                p = playlist_names[randrange(0,len(playlist_names))] if '[p]' in template else None
                fill_slot(X,POS,Intent,intent, template,t=t,s=s,g=g, p=p)



        #elif 'List' not in intent and 'list' not in intent:
        #    fill_slot(X,POS,Intent,intent,template)
    io_utils.dump_to_file(X,POS,Intent,args_output, mode='a')


def sent_gen(args):
    with open(args.data,'r') as f:
        data_artist = json.load(f)
    with open(args.data_english,'r') as f:
        data_artist_english = json.load(f)
    for artist in  data_artist_english:
        if artist not in data_artist:
            data_artist[artist] = data_artist_english[artist]

    with open(args.genre,'r') as f:
        genre_list=json.load(f)
    data_sent = pd.read_csv(args.template)
    intent = splitext(basename(args.template))[0]

    playlist_names = pd.read_csv(args.playlist_names)
    print intent
    
    #data_sent = data_sent[data_sent.columns[0]] # remove timestamp column
    #print data_sent

    ### select Intent: Given [singer | album | date | track | genre ] find songs
    ### given_row =  data_sent[data_sent.columns[0]] == 'Given'
    fill_template(data_artist,data_sent,genre_list, playlist_names, args.output, intent,nb_per_template=args.nb_per_template)

if __name__ == '__main__':
    args = opt_parse()
    sent_gen(args)
