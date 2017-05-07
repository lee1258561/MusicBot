    # -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import sys
import re
from ontology import databaseAPI
from rnn_nlu import data_utils, test_multi_task_rnn
from userSimulator import Simulator
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
    parser.add_argument('--random',action='store_true',help='whether to random user goal')
    parser.add_argument('--stdin',default=False,action='store_true',help='stdin test, enter sentence')
    parser.add_argument('--auto_test',default=False,action='store_true',help='auto test, enter user goal')
    parser.add_argument('-v',dest='verbose',default=False,action='store_true',help='verbose')
    args = parser.parse_args()
    return args


class Manager():
    def __init__(self,data_dir,train_dir, genre_map, verbose=False):
        self.DB = databaseAPI.Database(genre_map, verbose=verbose)
        self.NLUModel = test_multi_task_rnn.test_model(data_dir,train_dir)
        self.in_sent = ''
        self.in_sent_seg = []

        #slot to fill for each action
        self.intent_slot_dict = {'search':['artist','track'],'recommend':['artist','track','genre'],'info':['track','artist']}
        self.slot_prob_map = ['PAD','UNK',None,'track','artist','genre']
        self.positive_response = [u'是的',u'對',u'對啊',u'恩',u'沒錯',u'是啊',u'就是這樣',u'你真聰明',u'是']
        self.negative_response = [u'不是',u'錯了',u'不對',u'不用',u'沒有',u'算了',u'不需要',u'不 ',u'否',u'錯']
        #action threshold:
        self.intent_upper_threshold = 1.9
        self.intent_lower_threshold = 0.95
        self.slot_uppser_threshold = 1.9
        self.slot_lower_threshold = 0.95

        #if cycle_num > max_cycle_num, end the dialogue
        self.max_cycle_num = 12

        self.dialogue_end_sentence = ''
        self.state_init()
        

    def get_input(self,sentence):
        self.in_sent = sentence

        sentence = re.sub(u'就這樣|是的|對啊|對|恩|沒錯|不是|錯了|不對','',sentence)
        print("CURRENT TURN START!!!!!!")
        print('input:',self.in_sent)
        print('NLU_input:',sentence)
        """
        self.in_sent_seg = data_utils.naive_seg(sentence)
        if len(self.in_sent_seg) == 0:
            return False
        """

        if len(sentence)>3:
            self.NLU_result = self.NLUModel.feed_sentence(sentence)
        else:
            self.NLU_result = None
        print('NLU_RESULT:',self.NLU_result)

        self.state_tracking()
        action = self.action_maker()

        return action

    def api_action(self):
        # TODO add rule-based if else
        slot = databaseAPI.build_slot(self.in_sent_seg, self.in_pos)
        if 'search' in self.in_intent and len(slot) > 0:
            self.DB.given(slot)
        else:
            print ('Not supported yet...')

    def update_state_with_NLU(self,target=None,last_action_delete=None):
        """ Use the NLU result to update current state
            if target is provided, 
        """
        if target=='intent':
            self.state['intent'][last_action_delete['intent']] = 0.0
        elif target=='slot':
            for slot_name in last_action_delete['slot']:
                self.state['slot'][slot_name][last_action_delete['slot'][slot_name]] = 0.0

        if not self.NLU_result:
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
            for intent in self.NLU_result['intent']:
                if intent in self.intent_slot_dict:
                    if intent in self.state['intent']:
                        self.state['intent'][intent] += self.NLU_result['intent'][intent]
                    else:
                        self.state['intent'][intent] = self.NLU_result['intent'][intent]
        


    def action_maker(self):
        #based on state, make action
        cur_action = {}
        """
        do confirm if there is any prob > lower_threshold else do question to ask missing slot
        """
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
            self.tdialogue_end = True
        """ make action when the current turn ended
            API response should be wrote here
        """
        if self.dialogue_end:
            cur_action = {'intent':'','slot':{}}
            s = {}
            for slot_name in self.confirmed_state['slot']:
                if self.confirmed_state['slot'][slot_name] != None and self.confirmed_state['slot'][slot_name] != -1:
                    s[slot_name] = self.confirmed_state['slot'][slot_name]
            if self.confirmed_state['intent']=='search':
                cur_action['action'] = 'response'
                _,sentence = self.DB.search(s)
            elif self.confirmed_state['intent']=='info':
                cur_action['action'] = 'info'
                _,sentence = self.DB.info(s)
            elif self.confirmed_state['intent']=='recommend':
                cur_action['action'] = 'info'
                _,sentence = self.DB.recommend(s)
            self.dialogue_end_sentence = sentence
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




    def state_init(self):
        """ initialize state: state is depending on state and action and dialogue_end
            state_intent:
        """
        self.state = {'intent':{'search':0.0,'recommend':0.0,'info':0.0},'slot':{'track':{},'artist':{},'genre':{}},'turn':0}
        #'slot' = {'slot_name':{'slot_value':[prob]}}
        self.confirmed_state = {'intent':None,'slot':{'artist':None,'track':None,'genre':None}}
        self.action_history = []
        self.dialogue_end = False
        self.cycle_num = 0 


    def state_tracking(self):
        """ Update current state given response
            Based on this state, action maker will make appropriate action!!
            State is depending on state and action and turr_end
        """
        last_action = self.action_history[-1] if len(self.action_history)>0 else None

        #if system have confirm intent value
        if self.confirmed_state['intent']:
            if last_action['action'] == 'question' and any(e in self.in_sent for e in self.negative_response):
                for slot_name in last_action['slot']:
                    self.confirmed_state['slot'][slot_name] = -1.0


            elif last_action['action'] == 'confirm':
                if any(e in self.in_sent for e in self.negative_response):
                    self.update_state_with_NLU('slot',last_action)
                elif any(e in self.in_sent for e in self.positive_response):
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
                if any(e in self.in_sent for e in self.negative_response):
                    self.update_state_with_NLU('intent',last_action)
                elif any(e in self.in_sent for e in self.positive_response):
                    self.confirmed_state['intent'] = last_action['intent']
                else:
                    self.update_state_with_NLU()

            elif last_action['action'] == 'question':
                if any(e in self.in_sent for e in self.negative_response):
                    self.state['intent'][last_action['intent']] = -100.0
                else:
                    self.update_state_with_NLU()


        self.max_intent_prob = 0.0
        self.max_intent = ''
        self.max_slot_prob =''
        #put it to max slot if it's not confirmed(state_confirm!=-1 or prob<upper) if all confirmed end_turn=True 
        self.max_slot ={'track':None,'artist':None,'genre':None}

        if not self.confirmed_state['intent']:
            for e in self.state['intent']:
                if self.state['intent'][e] > self.max_intent_prob:
                    self.max_intent_prob = self.state['intent'][e]
                    self.max_intent = e

            if self.max_intent_prob>self.intent_upper_threshold:
                self.confirmed_state['intent'] = self.max_intent            

        all_slot_filled = True
        if self.confirmed_state['intent']:
            for slot_name in self.intent_slot_dict[self.confirmed_state['intent']]:
                if not self.confirmed_state['slot'][slot_name] and len(self.state['slot'][slot_name])>0:
                    max_prob = 0.0
                    max_slot = ''
                    for s in self.state['slot'][slot_name]:
                        if self.state['slot'][slot_name][s]>max_prob:
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
        print(self.action_history[-1]['action'])
        if 'intent' in self.action_history[-1]:
            print('action intent:',self.action_history[-1]['intent'],end=' \n')
        if 'slot' in self.action_history[-1]:
            print('action slot:',end='')
            for e in self.action_history[-1]['slot']:
                print(' '+e+':',end='')
                print(self.action_history[-1]['slot'][e],end='')
        print('\n\n\n')



def test(args):
    
    DM = Manager(args.nlu_data , args.model, args.genre_map, verbose=args.verbose)
    #initialize user simulator:
    simulator = Simulator(args.template_dir, args.data, args.genre)
    simulator.set_user_goal(intent='search',artist=u'林俊傑',track=u'她說')
    simulator.print_cur_user_goal()
    sentence = simulator.user_response({'action':'question'})
    
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
    simulator = Simulator(args.template_dir, args.data, args.genre)
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

    DM = Manager(args.nlu_data , args.model, args.genre_map, verbose=args.verbose)

    while True:
        print('\n>',end='')
        sentence = sys.stdin.readline()
        sentence = sentence.decode('utf-8').strip()
        action = DM.get_input(sentence)
        DM.print_current_state()
        if DM.dialogue_end:
            print("Dialogue System final response:",end=' ')
            print(DM.dialogue_end_sentence)
            print('\nCongratulation!!! You have ended one dialogue successfully\n')
            DM.state_init()
        
if __name__ == '__main__':
    args = optParser()
    if args.stdin:
        stdin_test(args)
    elif args.auto_test:
        auto_test(args)
    else:
        test(args)
