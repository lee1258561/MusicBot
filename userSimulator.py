# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import argparse
import json

from utils import io_utils
from random import randrange, shuffle
from os.path import join


intents = ['search', 'recommend', 'info', 'neutral']
slots = ['artist','track', 'genre']
tokens = ['[s]','[t]','[g]']
slot_token_map = {'artist':'[s]', 'track':'[t]', 'genre':'[g]'}
token_slot_map = {'[s]':'artist', '[t]':'track', '[g]':'genre'}

def opt_parse():
    parser = argparse.ArgumentParser(description=\
            'Slot & intent data generate')
    parser.add_argument('--template_dir',default='./data/template/',\
            help='sentence template directory')
    parser.add_argument('--data',default='./data/chinese_artist.json',\
            help='artist-album-track json data')
    parser.add_argument('--genre',default='./data/genres.json',\
            help='genres')
    args = parser.parse_args()
    return args

class Simulator():
    def __init__(self, template_dir, data_path, genre_path, intents=intents):
        data = self._load_data(template_dir, data_path, genre_path)

        self.intents = intents
        self.artists = data[0]
        self.tracks = data[1]
        self.genres = data[2]
        self.intent_template_map = data[3]
        self.dialogue_end = True
        self.cur_intent = ''
        self.cur_slot = {}

    def set_user_goal(self, intent=None, artist=None, track=None, genre=None):
        ''' set the current user goal. if not given intent, artist, track or genre,
            it would randomly set
        '''
        self.cur_intent = intent if intent != None else self._rand(self.intents)
        self.cur_slot['artist'] = artist if artist != None else self._rand(self.artists)
        self.cur_slot['track'] = track if track != None else self._rand(self.tracks)
        self.cur_slot['genre'] = genre if genre != None else self._rand(self.genres)

    def user_response(self, dst_msg=None):
        ''' Given DST message, return user response
            Arguments:
                dst_msg: DST message. {'action':'confirm|question|response|inform',\
                            'intent':'', 'slot':{'slot_name':'value'}}
            Return:
                sent: string, user response
        '''
        self.dialogue_end = False
        sent=''

        if dst_msg is None and not self.dialogue_end:
            ### NOTE: should not happen
            print '[ERROR] Need DST message...'
        
        if dst_msg['action'] == 'confirm':
            if 'slot' in dst_msg:
                for key in dst_msg['slot']:
                    if self.cur_slot[key] != dst_msg['slot'][key]:
                        sent = self._neg_response(slot=set([key]))
                    else:
                        sent =self._pos_response()
            elif 'intent' in dst_msg:
                if self.cur_intent == dst_msg['intent']:
                    sent = self._neg_response(intent=self.cur_intent)
                else:
                    sent = self._pos_response()

        elif dst_msg['action'] == 'question':
            slots_asked = set([])
            intent_asked = ''
            if 'slot' in dst_msg:
                for key in dst_msg['slot']:
                    slots_asked.add(key)
            if 'intent' in dst_msg:
                intent_asked = dst_msg['intent']

            sent = self.sentence_generate(intent_asked, slots_asked)
            print sent

        elif dst_msg['action'] == 'response':
            self.dialogue_end = True
        elif dst_msg['action'] == 'inform':
            self.dialogue_end = True

        return sent

    def sentence_generate(self, intent_asked='', slots_asked=set([])):
        intent_asked = intent_asked if len(intent_asked) > 0 else self.cur_intent
        templates = self.intent_template_map[intent_asked]
        shuffle(templates)
        slots_all = set(slots)
        for t in templates:
            t = t.decode('utf-8')
            if len(slots_asked) is 0:
                sent = self._fill_slot(t)
                break
            else:
                if all(slot_token_map[s] in t for s in slots_asked) and\
                        all(slot_token_map[s] not in t for s in slots_all - slots_asked):
                    sent = self._fill_slot(t)
                    break
        return sent

    def _fill_slot(self, template):
        new_temp = io_utils.naive_seg(template)
        new_temp = template
        for key in tokens:
            if key in new_temp:
                #offset = new_temp.index(key)
                offset = new_temp.find(key)
                #slot_content = io_utils.naive_seg(self.cur_slot[token_slot_map[key]])
                slot_content= self.cur_slot[token_slot_map[key]]
                new_temp = new_temp[:offset] + slot_content + new_temp[offset+3:]
        return new_temp

    def print_cur_user_goal(self):
        # NOTE Debug
        print u'[DEBUG] intent:[{}], artist:[{}], track:[{}], genre:[{}]'.\
                format(self.cur_intent, self.cur_slot['artist'],\
                self.cur_slot['track'], self.cur_slot['genre'])

    def _neg_response(self,intent=None,slot=None):
        # TODO
        responses = [u'不是 ',u'錯了 ', u'不對 ']
        sent = self.sentence_generate(slots_asked=set(slot))
        sent = responses[randrange(len(responses))] + sent
        print 'No! Fuck U!'
        print sent
        return sent

    def _pos_response(self):
        # TODO
        responses = [u'是的',u'對', u'恩',u'對阿',u'沒錯']
        sent = responses[randrange(len(responses))]
        print 'Yes! U Asshole!'
        print sent
        return sent

    def _rand(self, data_lists):
        return data_lists[randrange(len(data_lists))]

    def _load_data(self,template_dir, data_path, genre_path):
        '''
            Load templates and all the slot data
            Arguments: 
                template_dir: path to the template dir
                data_path: path to the chinese_artist.json
                genre_path: path to the genre.json
            Return: 
                artists: list of artists
                tracks: list of tracks
                genres: list of genres
                intent_template_map: intent to template dictionary
        '''
        ### load file and init
        with open(data_path,'r') as f:
            data_artist = json.load(f)
        with open(genre_path,'r') as f:
            genres=json.load(f)

        artists = [s for s in data_artist]
        tracks = []
        for s in data_artist:
            for a in data_artist[s]:
                for t in data_artist[s][a]:
                    tracks.append(t)
        intent_template_map = {}
        for i in intents:
            intent_template_map[i] = []
            f = join(template_dir, i+'.csv')
            data_sent = pd.read_csv(f)
            data_sent = data_sent[data_sent.columns[0]].unique()
            intent_template_map[i] = data_sent
        return [artists, tracks, genres, intent_template_map]


def main(args):
    simulator = Simulator(args.template_dir, args.data, args.genre, intents)
    simulator.set_user_goal(intent='search', artist=u'五月天')
    simulator.print_cur_user_goal()
    simulator.user_response({'action':'question','intent':'search'})

if __name__ == '__main__':
    args = opt_parse()
    main(args)
