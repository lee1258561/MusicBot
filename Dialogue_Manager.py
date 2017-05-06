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
    parser.add_argument('--nlu_data', default='./hahaha2/nlu_data/',type=str, help='data dir')
    parser.add_argument('--model',default='./hahaha2/model_tmp/',type=str,help='model dir')
    parser.add_argument('--template_dir',default='./data/template/',\
            help='sentence template directory')
    parser.add_argument('--data',default='./data/chinese_artist.json',\
            help='artist-album-track json data')
    parser.add_argument('--genre',default='./data/genres.json',\
            help='genres')
    parser.add_argument('--random',action='store_true',help='whether to random user goal')
    parser.add_argument('-v',dest='verbose',default=False,action='store_true',help='verbose')
    args = parser.parse_args()
    return args


class Manager():
    def __init__(self,data_dir,train_dir,verbose=False):
        self.DB = databaseAPI.Database(verbose=verbose)
        self.NLUModel = test_multi_task_rnn.test_model(data_dir,train_dir)
        self.in_sent = ''
        self.in_sent_seg = []

        #slot to fill for each action
        self.intent_slot_dict = {'search':['artist','track'],'recommend':['artist','track','genre'],'info':['track','artist']}
        self.slot_prob_map = ['PAD','UNK',None,'track','artist','genre']
        self.positive_response = [u'是的',u'對',u'對啊',u'恩',u'沒錯']
        self.negative_response = [u'不是',u'錯了',u'不對']
        #action threshold:
        self.intent_upper_threshold = 1.9
        self.intent_lower_threshold = 0.95
        self.slot_uppser_threshold = 1.9
        self.slot_lower_threshold = 0.95

        #if cycle_num > max_cycle_num, end the dialogue
        self.max_cycle_num = 10

        self.state_init()
        

    def get_input(self,sentence):
        self.in_sent = sentence

        sentence = re.sub(u'就這樣|是的|對啊|對|恩|沒錯|不是|錯了|不對| ','',sentence)
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
        self.action_maker()

        return self.action_history[-1]

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
            self.turn_end = True
        """ make action when the current turn ended
            API response should be wrote here
        """
        if self.turn_end:
            if self.confirmed_state['intent']=='search':
                cur_action['action'] = 'response'
            elif self.confirmed_state['intent']=='info':
                cur_action['action'] = 'info'
            elif self.confirmed_state['intent']=='recommend':
                cur_action['action'] = 'response'
            self.action_history.append(cur_action)
            return cur_action

        self.action_history.append(cur_action)

        return cur_action




    def state_init(self):
        """ initialize state: state is depending on state and action and turn_end
            state_intent:
        """
        self.state = {'intent':{'search':0.0,'recommend':0.0,'info':0.0},'slot':{'track':{},'artist':{},'genre':{}},'turn':0}
        #'slot' = {'slot_name':{'slot_value':[prob]}}
        self.confirmed_state = {'intent':None,'slot':{'artist':None,'track':None,'genre':None}}
        self.action_history = []
        self.turn_end = False
        self.cycle_num = 0 


    def state_tracking(self):
        """ Update current state given response
            Based on this state, action maker will make appropriate action!!
            State is depending on state and action and turr_end
        """
        last_action = self.action_history[-1] if len(self.action_history)>0 else None

        #if system have confirm intent value
        if self.confirmed_state['intent']:
            if last_action['action'] == 'question' and (u'不是' or u'錯了' or u'不對') in self.in_sent:
                for slot_name in last_action['slot']:
                    self.confirmed_state['slot'][slot_name][last_action['slot'][slot_name]] = -1.0


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
            self.turn_end = True
        self.cycle_num += 1
    

    def print_current_state(self):
        print('uncertained state:')
        print('uncertained intent: ',end='')
        for e in self.state['intent']:
            print(' ',end='')
            print(e,end='')
            print(': ',self.state['intent'][e],end='')
        print()
        print('uncertained slot: ',end='')
        for e in self.state['slot']:
            if len(self.state['slot'][e])!=0:
                print(e,end='')
                for e2 in self.state['slot'][e]:
                    print(' ',end='')
                    print(e2,end='')
                    print(': ',e2,end='')
        print('\n')
        print('confirmed state:')
        print('confirmed intent:',self.confirmed_state['intent'])
        print('confirmed slots:',end='')
        for e in self.confirmed_state['slot']:
            print(e,': ',end='')
            print(self.confirmed_state['slot'][e],end='')
        print('\n')
        print('action:',end='')
        print(self.action_history[-1]['action'])
        if 'intent' in self.action_history[-1]:
            print('intent:',self.action_history[-1]['intent'],end='')
        if 'slot' in self.action_history[-1]:
            print(' slot:',end='')
            for e in self.action_history[-1]['slot']:
                print(' '+e,end='')
                print(self.action_history[-1]['slot'][e],end='')

        print('\nturn_end!!\n\n')



def main():
    args = optParser()
    DM = Manager(args.nlu_data , args.model, verbose=args.verbose)

    #initialize user simulator:
    simulator = Simulator(args.template_dir, args.data, args.genre)
    simulator.set_user_goal(intent='recommend',artist=u'林俊傑',track=u'她說',genre=u'搖滾')
    simulator.print_cur_user_goal()
    sentence = simulator.user_response({'action':'question'})
    
    while True:
        action = DM.get_input(sentence)
        DM.print_current_state()
        """
        print('state:',DM.state)
        print('confirmed_state:',DM.confirmed_state)
        print('action:',action,'\n\n')
        """
        sentence = simulator.user_response(action)
        if DM.turn_end:
            print('Congratulation!!! You have ended dialogue successfully')
            break


        
if __name__ == '__main__':
    main()
