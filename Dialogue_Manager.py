# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import sys
import re
from ontology import databaseAPI
from rnn_nlu import data_utils, test_multi_task_rnn
from rule_based_NLU import *
from userSimulator import Simulator
from policy_network import policy_network
from nlg import rule_based

import numpy as np

def optParser():
    parser = argparse.ArgumentParser(description='Vanilla action controller')
    parser.add_argument('--nlu_data', default='./data/nlu_data/',type=str, help='data dir')
    parser.add_argument('--model',default='./model_tmp/',type=str,help='model dir')
    parser.add_argument('--template_dir',default='./data/template/',\
            help='sentence template directory')
    parser.add_argument('--data',default='./data/chinese_artist.json',\
            help='artist-album-track json data')
    parser.add_argument('--genre',default='./data/genres.json',\
            help='genres')
    parser.add_argument('--genre_map',default='./data/genre_map.json',\
            type=str,help='genre_map.json path')
    parser.add_argument('--spotify_playlist',default='./data/spotify_playlist.json',\
            type=str,help='spotify_playlist.json path')
    parser.add_argument('spotify_account', help='your spotify account')
    parser.add_argument('--random',action='store_true',help='whether to random user goal')
    parser.add_argument('--stdin',default=False,action='store_true',help='stdin test, enter sentence')
    parser.add_argument('--auto_test',default=False,action='store_true',help='auto test, enter user goal')
    parser.add_argument('--train_policy',default=False,action='store_true',help='train policy network')
    parser.add_argument('-v',dest='verbose',default=False,action='store_true',help='verbose')
    args = parser.parse_args()
    return args


class Manager():
    def __init__(self,data_dir,train_dir, genre_map,spotify_playlist, spotify_account, verbose=False,user_name='default_user'):
        self.DB = databaseAPI.Database(genre_map,spotify_playlist, spotify_account,verbose=verbose)
        self.NLUModel = test_multi_task_rnn.test_model(data_dir,train_dir)
        self.RULENLU = rule_based_NLU()
        self.NLG = rule_based.NLG('./nlg/NLG.txt')
        self.in_sent = ''
        self.in_sent_seg = []
        self.user_name = user_name

        #slot to fill for each action
        self.intent_slot_dict = {'search':['artist','track'],
                                 'recommend':['artist','track','genre'],
                                 'info':['track','artist'],
                                 'playlistCreate':['playlist'],
                                 'playlistAdd':['track','artist',
                                 'playlist'],'playlistPlay':['playlist'],
                                 'playlistShow':[],
                                 'playlistTrack':['playlist'],
                                 'all':['artist','track','genre','playlist','spotify_playlist'],
                                 None:[],'empty':[]}
        self.slot_prob_map = ['PAD','UNK',None,'track','playlist','artist','genre']
        self.positive_response = [u'是的',u'對',u'對啊',u'恩',u'沒錯',u'是啊',u'就是這樣',u'你真聰明',u'是',u'有',u'好啊']
        self.negative_response = [u'不是',u'錯了',u'不對',u'不用',u'沒有',u'算了',u'不需要',u'不',u'不要',u'否',u'不知道']
        self.recommend_keyword = [u'相似',u'類似',u'推薦',u'像是',u'相關',u'風格']
        self.last_track_keyword = [u'剛剛',u'上一首',u'正在',u'上首',u'剛才',u'再播']
        #action threshold:
        self.intent_upper_threshold = 0.85
        self.intent_lower_threshold = 0.8
        self.slot_uppser_threshold = 1.15
        self.slot_lower_threshold = 0.9

        #if cycle_num > max_cycle_num, end the dialogue
        self.max_cycle_num = 10

        self.dialogue_end_track_url = ''
        self.dialogue_end_type = ''
        self.dialogue_end_sentence = ''
        self.state_init()



    def get_input(self,sentence,rule_based_action=True):
        self.in_sent = sentence

        sentence = re.sub(u'就這樣|是的|對啊|對|恩|沒錯|不是|錯了|不對|不要|不知道','',sentence[:3]) + sentence[3:]
        """
        print("CURRENT TURN START!!!!!!")
        print('input:',self.in_sent)
        print('NLU_input:',sentence)
        """

        self.NLU_result = self.NLUModel.feed_sentence(sentence)
        self.RULE_result = self.RULENLU.feed_sentence(sentence)
        print('NLU_RESULT:',self.NLU_result)
        print('RULE_RESULT:',self.RULE_result)


        self.state_tracking()
        action = self.action_maker()
        return action



    def update_state_with_NLU(self,target=None,last_action_delete=None):
        """ Use the NLU result to update current state
            if target is provided, 
        """
        if target=='intent':
            if 'intent' in last_action_delete:
                self.state['intent'][last_action_delete['intent']] = 0.0
        elif target=='slot':
            for slot_name in last_action_delete['slot']:
                #self.state['slot'][slot_name][last_action_delete['slot'][slot_name]] = 0.0
                if 'slot' in last_action_delete:
                    self.state['slot'][slot_name][last_action_delete['slot'][slot_name]] = 0.0

        if self.NLU_result is None:
            return

        for e in self.NLU_result['slot']:
            max_prob = 0.0
            slot_name = ''
            for i,p in enumerate(self.NLU_result['slot'][e]):
                if i>=3 and p>max_prob:
                    slot_name = self.slot_prob_map[i]
                    max_prob = p
            if e in self.state['slot'][slot_name]:
                self.state['slot'][slot_name][e] += max_prob
            else:
                self.state['slot'][slot_name][e] = max_prob

        total_intent_prob = 0.0
        for intent in self.NLU_result['intent']:
            if intent in self.intent_slot_dict:
                total_intent_prob += self.NLU_result['intent'][intent]
                if intent in self.state['intent']:
                    self.state['intent'][intent] += self.NLU_result['intent'][intent]
                else:
                    self.state['intent'][intent] = self.NLU_result['intent'][intent]
        
        for slot_name in self.RULE_result:
            if slot_name=='track' and total_intent_prob<0.9 and self.confirmed_state['intent'] is None:
                continue
            for e in self.RULE_result[slot_name]:
                for slot_name2 in self.state['slot']:
                    if slot_name != slot_name2:
                        for slot_value in self.state['slot'][slot_name2]:
                            if slot_value == e:
                                self.state['slot'][slot_name2][slot_value] = -1.0
                if e in self.state['slot'][slot_name]:
                    self.state['slot'][slot_name][e] += self.RULE_result[slot_name][e]
                else:
                    self.state['slot'][slot_name][e] = self.RULE_result[slot_name][e]
        if len(self.state['slot']['spotify_playlist'])>0:
            self.confirmed_state['intent'] = 'empty'



    def action_maker(self):
        #based on state, make action
        cur_action = {}
        """
        do confirm if there is any prob > lower_threshold else do question to ask missing slot
        """
        if self.confirmed_state['intent'] is not None and \
           'playlist' in self.confirmed_state['intent'] and \
           'Show' not in self.confirmed_state['intent'] and \
           self.confirmed_state['slot']['playlist'] is None:
            cur_action = {'action':'question','slot':{'playlist':''}}
            self.action_history.append(cur_action)
            return cur_action

        if self.confirmed_state['intent']:
            slot = {}
            for slot_name in self.intent_slot_dict[self.confirmed_state['intent']]:
                if self.max_slot[slot_name] and self.confirmed_state['slot'][slot_name] != -1:
                    if self.max_slot[slot_name][1] > self.slot_lower_threshold:
                        slot[slot_name] = self.max_slot[slot_name][0]

            if len(slot) == 0:
                for slot_name in self.intent_slot_dict[self.confirmed_state['intent']]:
                    if not self.confirmed_state['slot'][slot_name]:
                        cur_action = {'action':'question','slot':{slot_name:''}}
                        break

            else:
                cur_action = {'action':'confirm','slot':slot}
            
        else:
            if self.max_intent_prob > self.intent_lower_threshold:
                cur_action = {'action':'confirm','intent':self.max_intent}
            else:
                cur_action = {'action':'question','intent':''}

        if len(cur_action)==0:
            self.dialogue_end = True

        """ make action when the current turn ended
            API response should be wrote here
        """
        if self.dialogue_end:
            cur_action = {'intent':'','slot':{}}
            s = {}
            sentence = ''
            url = ''

            spotify_playlist = self.confirmed_state['slot']['spotify_playlist']
            playlist = self.confirmed_state['slot']['playlist']
            for slot_name in self.confirmed_state['slot']:
                if self.confirmed_state['slot'][slot_name] != None and self.confirmed_state['slot'][slot_name] != -1:
                    s[slot_name] = self.confirmed_state['slot'][slot_name]

            if spotify_playlist is not None and not self.rec_in_sent:
                cur_action['action'] = 'response'
                sentence,url = self.DB.playlistSpotify(spotify_playlist)
                self.confirmed_state['intent'] = 'playlistSpotify'
            elif self.confirmed_state['intent']=='playlistShow':
                cur_action['action']='playlistShow'
                sentence,playlistIDs = self.DB.playlistShow(self.user_name)
            elif self.confirmed_state['intent']=='playlistTrack':
                cur_action['action']='playlistTrack'
                sentence,url = self.DB.playlistTrack(self.user_name,playlist)
            elif self.confirmed_state['intent']=='playlistPlay':
                cur_action['action']='playlistPlay'
                sentence, url = self.DB.playlistPlay(self.user_name,playlist)
            elif self.confirmed_state['intent']=='playlistCreate':
                cur_action['action']='playlistCreate'
                sentence,url = self.DB.playlistCreate(self.user_name,playlist)
            elif self.confirmed_state['intent']=='playlistAdd':
                cur_action['action'] = 'playlistAdd'
                sentence,url = self.DB.playlistAdd(self.user_name,playlist,s)
            elif self.confirmed_state['intent']=='search':
                cur_action['action'] = 'response'
                _,sentence, url = self.DB.search(s)
                self.dialogue_end_track_url = url
            elif self.confirmed_state['intent']=='info':
                cur_action['action'] = 'info'
                _,sentence = self.DB.info(s)
            elif self.confirmed_state['intent']=='recommend':
                cur_action['action'] = 'info'
                _,sentence,url = self.DB.recommend(s)

            self.dialogue_end_track_url = url
            self.dialogue_end_sentence = sentence
            self.dialogue_end_type = self.confirmed_state['intent']
            cur_action['intent'] = self.confirmed_state['intent']
            for slot_name in self.confirmed_state['slot']:
                if self.confirmed_state['slot'][slot_name]!=-1:
                    cur_action['slot'][slot_name] = self.confirmed_state['slot'][slot_name]
                else:
                    cur_action['slot'][slot_name] = None
            self.action_history.append(cur_action)
            return cur_action

        self.action_history.append(cur_action)

        return cur_action


    def state_init(self,flag=0):
        """ initialize state: state is depending on state and action and dialogue_end
            state_intent:
        """
        self.last_track = None
        self.last_artist = None
        self.state = {'intent':{'search':0.0,'recommend':0.0,'info':0.0,'playlistCreate':0.0,
                                 'playlistAdd':0.0,'playlistPlay':0.0,'playlistShow':0.0,'playlistTrack':0.0},
                      'slot':{'track':{},'artist':{},'genre':{},'playlist':{},'spotify_playlist':{}}}
        if flag!=0 and self.confirmed_state['slot']['track'] is not None and self.confirmed_state['slot']['track'] != -1:
            self.last_track = self.confirmed_state['slot']['track']
            if self.confirmed_state['slot']['artist'] is not None:
                self.last_artist = self.confirmed_state['slot']['artist']


        #'slot' = {'slot_name':{'slot_value':[prob]}}
        self.confirmed_state = {'intent':None,'slot':{'artist':None,'track':None,'genre':None,'playlist':None,'spotify_playlist':None}}
        self.action_history = []
        self.dialogue_end = False
        self.cycle_num = 0
        self.rec_in_sent = False


    def state_tracking(self):
        """ Update current state given response
            Based on this state, action maker will make appropriate action!!
            State is depending on state and action and turr_end
        """
        last_action = self.action_history[-1] if len(self.action_history)>0 else None
        if any(e in self.in_sent for e in self.last_track_keyword):
            if self.last_track:
                self.confirmed_state['slot']['track'] = self.last_track
            if self.last_artist:
                self.confirmed_state['slot']['artist'] = self.last_artist
        #if system have confirm intent value
        if self.confirmed_state['intent'] is not None:
            if last_action['action'] == 'question' and 'playlist' in last_action['slot']:
                self.confirmed_state['slot']['playlist'] = self.in_sent.strip()
            elif last_action['action'] == 'question' and any(e in self.in_sent[:3] for e in self.negative_response):
                if 'slot' in last_action:
                    for slot_name in last_action['slot']:
                        self.confirmed_state['slot'][slot_name] = -1.0
                if 'slot' in last_action:
                    for slot_name in last_action['slot']:
                        self.confirmed_state['slot'][slot_name] = -1.0


            elif last_action['action'] == 'confirm':
                if any(e in self.in_sent[:3] for e in self.negative_response):
                    self.update_state_with_NLU('slot',last_action)
                elif any(e in self.in_sent[:3] for e in self.positive_response):
                    if 'slot' in last_action:
                        for slot_name in last_action['slot']:
                            self.confirmed_state['slot'][slot_name] = last_action['slot'][slot_name]
                else:
                    self.update_state_with_NLU()
            else:
                self.update_state_with_NLU()

        #if system not yet confirm intent value
        else:
            #the first response to user in one turn
            if not last_action:
                self.update_state_with_NLU()

            elif last_action['action'] == 'confirm':
                if any(e in self.in_sent[:3] for e in self.negative_response):
                    self.update_state_with_NLU('intent',last_action)
                elif any(e in self.in_sent[:3] for e in self.positive_response):
                    if 'intent' in last_action:
                        self.confirmed_state['intent'] = last_action['intent']
                else:
                    self.update_state_with_NLU()

            elif last_action['action'] == 'question':
                if any(e in self.in_sent[:3] for e in self.negative_response):
                    if 'intent' in last_action:
                        self.state['intent'][last_action['intent']] = -100.0
                else:
                    self.update_state_with_NLU()

        if any(e in self.in_sent for e in self.recommend_keyword):
            self.rec_in_sent = True

        self.max_intent_prob = 0.0
        self.max_intent = ''
        #put it to max slot if it's not confirmed(state_confirm!=-1 or prob<upper) if all confirmed end_turn=True 
        self.max_slot ={'track':None,'artist':None,'genre':None,'playlist':None}

        if self.confirmed_state['intent'] is None:
            for e in self.state['intent']:
                if self.state['intent'][e] > self.max_intent_prob:
                    self.max_intent_prob = self.state['intent'][e]
                    self.max_intent = e

            if self.max_intent_prob>self.intent_upper_threshold:
                self.confirmed_state['intent'] = self.max_intent            

        all_slot_filled = True
        for slot_name in self.intent_slot_dict['all']:
            if not self.confirmed_state['slot'][slot_name] and len(self.state['slot'][slot_name])>0:
                max_prob = 0.0
                max_slot = ''
                for s in self.state['slot'][slot_name]:
                    if self.state['slot'][slot_name][s]>max_prob:
                        check = 1
                        if slot_name=='artist':
                            check = self.DB.check_artist(s)
                        elif slot_name=='track':
                            check = self.DB.check_track(s)
                        if check == 0:
                            continue
                        max_prob = self.state['slot'][slot_name][s]
                        max_slot = s
                if max_prob>self.slot_uppser_threshold:
                    self.confirmed_state['slot'][slot_name] = max_slot
                else:
                    self.max_slot[slot_name] = [max_slot,max_prob]

            if not self.confirmed_state['slot'][slot_name]:
                all_slot_filled = False

        #print('max_slot:',self.max_slot)
        if self.confirmed_state['intent'] and all_slot_filled or self.cycle_num>=self.max_cycle_num:
            self.dialogue_end = True
        self.cycle_num += 1
    

    def print_current_state(self):
        print('distribution state:')
        print('distribution intent: ',end='')
        for e in self.state['intent']:
            print(' ',end='')
            print(e,end='')
            print(': ',self.state['intent'][e],end='')
        print()
        print('distribution slot: ',end='')
        for e in self.state['slot']:
            if len(self.state['slot'][e])!=0:
                print(e,end='')
                for e2 in self.state['slot'][e]:
                    print(' ',end='')
                    print(e2,end='')
                    print(':',self.state['slot'][e][e2],end='')
                    print(' ',end='')
        print('\n')
        print('confirmed state:')
        print('confirmed intent:',self.confirmed_state['intent'])
        print('confirmed slots:',end='')
        for e in self.confirmed_state['slot']:
            print(e+':',end='')
            print(self.confirmed_state['slot'][e],end='')
            print(' ',end='')
        print('\n')
        print('action:',end='')
        if len(self.action_history)>0:
            print(self.action_history[-1]['action'])
        if 'intent' in self.action_history[-1]:
            print('action intent:',self.action_history[-1]['intent'],end=' \n')
        if 'slot' in self.action_history[-1]:
            print('action slot:',end='')
            for e in self.action_history[-1]['slot']:
                print(' '+e+':',end='')
                print(self.action_history[-1]['slot'][e],end='')
        print('\n\n\n')

 
    def action_to_sentence(self,action):
        if action['action'] == 'question' and 'slot' in action and 'playlist' in action['slot']:
            sent = u'可以跟我說歌單的名稱嗎?(填歌單名稱就好)'
            return sent
        sent = self.NLG.decode(action)
        if sent != None:
            return sent
        
        intent_to_chinese = {'search':u'聽歌','recommend':u'推薦歌曲', 'info':u'詢問歌曲資訊',
                             'playlistCreate':u'建立歌單', 'playlistAdd':u'新增歌曲到歌單',
                             'playlistPlay':u'播放歌單','playlistShow':u'列出使用者歌單',
                             'playlistTrack':u'列出歌單中的歌曲'}
        slot_to_chinese = {'artist':u'歌手名稱','track':u'歌曲名稱','genre':u'曲風','playlist':u'歌單'}
        sent = ''
        if action['action']=='question':
            if 'intent' in action:
                return u'你好啊，請問你想要什麼服務? 我可以推薦歌曲，播放歌曲，詢問歌曲或歌手資訊'
            elif 'slot' in action:
                for slot_name in action['slot']:
                    return u'請問你要填入' + slot_to_chinese[slot_name] + u'嗎?'

        elif action['action'] == 'confirm':
            if 'intent' in action:
                return u'再確認一次 請問你是想' + intent_to_chinese[action['intent']] + u'嗎?'
            elif 'slot' in action:
                sent = u'再確認一次 請問你有填入'
                for slot_name in action['slot']:
                    sent = sent + slot_to_chinese[slot_name] + action['slot'][slot_name] + u'，'
                sent = sent + u'嗎?'
        return sent



    def get_API_input(self,sentence):

        sentence = sentence.decode('utf-8').strip()
        action = self.get_input(sentence)
        self.print_current_state()
        if self.dialogue_end:
            return ("Dialogue System final response:" + DM.dialogue_end_sentence + "\n")
            self.state_init()
        return self.action_to_sentence(action)



def test(args):
    
    DM = Manager(args.nlu_data , args.model, args.genre_map, verbose=args.verbose)
    #initialize user simulator:
    simulator = Simulator(args.template_dir, args.data, args.genre)
    simulator.set_user_goal(intent='search',artist=u'林俊傑',track=u'她說')
    simulator.print_cur_user_goal()
    sentence = simulator.user_response({'action':'question'})
    
    turn = 0
    while True:
        action = DM.get_input(sentence)
        DM.print_current_state()
        sentence = simulator.user_response(action)
        if DM.dialogue_end:
            simulator.print_cur_user_goal()
            print("Dialogue System final response:",end=' ')
            print(DM.dialogue_end_sentence)
            print('\nCongratulation!!! You have ended one dialogue successfully\n')
            turn += 1
            DM.state_init(flag=turn)
            break

def set_simulator_goal(simulator):
    intent_slot_dict = {'search':['artist','track'],'recommend':['artist','track','genre'],'info':['track','artist']}
    while(True):
        print('Please enter user intent "search" or "recommend" or "info"\n>',end='')
        intent = sys.stdin.readline()
        intent = intent.strip()
        if intent in intent_slot_dict:
            break
    slot_dict = {'artist':None,'genre':None,'track':None}
    for slot_name in intent_slot_dict[intent]:
        print('Please enter ' + slot_name + '\n>',end='')
        slot_value = sys.stdin.readline()
        slot_value = slot_value.strip().decode('utf-8')
        if len(slot_value) <= 1:
            slot_dict[slot_name]= None
        else:
            slot_dict[slot_name] = slot_value
    simulator.set_user_goal(intent=intent,artist=slot_dict['artist'],track=slot_dict['track'],genre=slot_dict['genre'])
    simulator.print_cur_user_goal()
    sentence = simulator.user_response({'action':'question'})
    return sentence

def auto_test(args):
    
    DM = Manager(args.nlu_data , args.model, args.genre_map, verbose=args.verbose)
    #initialize user simulator:
    simulator = Simulator(args.template_dir, args.data, args.genre,args.genre_map)
    sentence = set_simulator_goal(simulator)
    while True:
        action = DM.get_input(sentence)
        DM.print_current_state()
        sentence = simulator.user_response(action)
        if DM.dialogue_end:
            simulator.print_cur_user_goal()
            print("Dialogue System final response:",end=' ')
            print(DM.dialogue_end_sentence)
            print('\nCongratulation!!! You have ended one dialogue successfully\n')
            DM.state_init()
            sentence = set_simulator_goal(simulator)
            

def stdin_test(args):

    DM = Manager(args.nlu_data , args.model, args.genre_map, args.spotify_playlist,
                 args.spotify_account, verbose=args.verbose)

    turn = 0
    while True:
        print('\n>',end='')
        sentence = sys.stdin.readline()
        sentence = sentence.decode('utf-8').strip()
        action = DM.get_input(sentence)
        DM.print_current_state()
        print(DM.action_to_sentence(action))
        if DM.dialogue_end:
            print("Dialogue System final response:",end=' ')
            print(DM.dialogue_end_sentence)
            print('\nCongratulation!!! You have ended one dialogue successfully\n')
            turn += 1
            DM.state_init(turn)


if __name__ == '__main__':
    args = optParser()
    if args.stdin:
        stdin_test(args)
    elif args.auto_test:
        auto_test(args)
    else:
        test(args)
