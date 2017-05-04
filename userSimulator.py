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
        self.data = self._load_data(template_dir, data_path, genre_path)
        self.intents = intents[:3]
        self.dialogue_end = True
        self.cur_intent = ''
        self.cur_slot = {}
        self.cur_slots_all = set()

    def set_user_goal(self, intent=None, artist=None, track=None, genre=None, random=False):
        ''' set the current user goal. manually init each slot or random init
        '''
        self.cur_intent = intent
        self.cur_slot['artist'] = artist
        self.cur_slot['track'] = track
        self.cur_slot['genre'] = None
        if self.cur_intent == 'recomment': # only recommend would have genre slot
            self.cur_slot['genre'] = genre

        ### if random init
        if random:
            self.cur_intent = self._rand(self.intents)
            self.cur_slot['track'] = self._rand(self.data['tracks'])
            self.cur_slot['artist'] =  self.data['track_artist_map'][self.cur_slot['track']]
            ### TODO: random init genre as well

        ### all the possible slots set based on current intent
        self.cur_slots_all = set([s for s in self.cur_slot if self.cur_slot[s] is not None]) 
        self.cur_templates = self.data['intent_template_map'][self.cur_intent] # use the current intent template

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
        slots_asked = set([])
        intent_asked = ''

        if dst_msg is None and not self.dialogue_end:
            ### NOTE: should not happen
            print '[ERROR] Need DST message...'
        
        if dst_msg['action'] == 'confirm':
            if 'slot' in dst_msg:
                for key in dst_msg['slot']:
                    slots_asked.add(key)
                if not self.cur_slots_all >= slots_asked: # if DTW ask slots not included in current intent
                    sent = self._neg_response(None)
                else:
                    slots_asked.clear() # clear all the elements
                    for key in dst_msg['slot']: # check if each slot DTW returned is correct
                        ### add incorrect slots to slots_asked, then generate neg_response
                        if self.cur_slot[key] != dst_msg['slot'][key]:
                            slots_asked.add(key)
                    if len(slots_asked) > 0:
                        sent = self._neg_response(slot=slots_asked,strict=False)
            if 'intent' in dst_msg:
                if self.cur_intent != dst_msg['intent']: # check if the DTW intent correct
                    sent = self._neg_response()
            if len(sent) == 0:
                sent = self._pos_response()

        elif dst_msg['action'] == 'question':
            if 'slot' in dst_msg:
                for key in dst_msg['slot']:
                    slots_asked.add(key)
            if 'intent' in dst_msg:
                intent_asked = dst_msg['intent']

            ### check correctness
            if not self.cur_slots_all >= slots_asked: # if DTW ask slots not included in current intent
                sent = self._neg_response(None)
            else:
                sent = self.sentence_generate(slots_asked)

        elif dst_msg['action'] == 'response':
            self.dialogue_end = True
        elif dst_msg['action'] == 'inform':
            self.dialogue_end = True

        return sent

    def sentence_generate(self, slots_asked=set([]), strict=True):
        '''strict: use the template contain all the slots_asked
        '''
        #intent_asked = intent_asked if len(intent_asked) > 0 else self.cur_intent
        shuffle(self.cur_templates)
        slots_all = set(slots)
        for t in self.cur_templates:
            t = t.decode('utf-8')
            ### if no slots asked, use the any template which contains any currrent slot and 
            ### doesn't contain any other slots
            if len(slots_asked) is 0 and any(slot_token_map[s] in t for s in self.cur_slots_all)\
                    and all(slot_token_map[s] not in t for s in slots_all - self.cur_slots_all):
                sent = self._fill_slot(t)
                break
            ### else if the template contains the slot asked and doesn't contain any other slots
            if strict:
                if all(slot_token_map[s] in t for s in slots_asked) and\
                        all(slot_token_map[s] not in t for s in slots_all - slots_asked):
                    sent = self._fill_slot(t)
                    break
            else:
                if any(slot_token_map[s] in t for s in slots_asked) and\
                        all(slot_token_map[s] not in t for s in slots_all - slots_asked):
                    sent = self._fill_slot(t)
                    break
        return sent

    def _fill_slot(self, template):
        #new_temp = io_utils.naive_seg(template)
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

    def _neg_response(self,slot=set([]),strict=True):
        # TODO
        responses = [u'不是 ',u'錯了 ', u'不對 ']
        sent = ''
        if slot is not None: # if all the slot are valid
            sent = self.sentence_generate(slots_asked=slot,strict=strict)
        sent = responses[randrange(len(responses))] + sent
        #print 'No! Fuck U!'
        #print sent
        return sent

    def _pos_response(self):
        # TODO
        responses = [u'是的',u'對', u'恩',u'對阿',u'沒錯']
        sent = responses[randrange(len(responses))]
        #print 'Yes! U Asshole!'
        #print sent
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
                data: dict
                    'artists': list of artists
                    'tracks': list of tracks
                    'track_artist_map': track_artist_map {'t1':'a1','t2':'a2']}
                    'genres': list of genres
                    'intent_template_map': intent to template dictionary
        '''
        ### load file and init
        with open(data_path,'r') as f:
            data_artist = json.load(f)
        with open(genre_path,'r') as f:
            genres=json.load(f)

        artists = [s for s in data_artist]
        tracks = []
        track_artist_map = {}
        for s in data_artist:
            for a in data_artist[s]:
                for t in data_artist[s][a]:
                    track_artist_map[t] = s
                    tracks.append(t)
        intent_template_map = {}
        for i in intents:
            intent_template_map[i] = []
            f = join(template_dir, i+'.csv')
            data_sent = pd.read_csv(f)
            data_sent = data_sent[data_sent.columns[0]].unique()
            intent_template_map[i] = data_sent

        return {'artist':artists, 'tracks':tracks, 'track_artist_map':track_artist_map,\
                'genres':genres, 'intent_template_map':intent_template_map}

def main(args):
    simulator = Simulator(args.template_dir, args.data, args.genre, intents)
    simulator.set_user_goal(intent='search',artist=u'郭靖', track=u'分手看看', random=True)
    simulator.print_cur_user_goal()
    sent = simulator.user_response({'action':'confirm','intent':'search','slot':{'track':u'分手看看2','artist':'fuck'}})
    print sent

if __name__ == '__main__':
    args = opt_parse()
    main(args)
