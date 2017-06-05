# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import sys
import os
import json
import re
from ontology import databaseAPI
from rnn_nlu import data_utils, test_multi_task_rnn
from userSimulator import Simulator
from policy_network import policy_network
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
    parser.add_argument('--train_policy',default=False,action='store_true',help='train policy network')
    parser.add_argument('-v',dest='verbose',default=False,action='store_true',help='verbose')
    args = parser.parse_args()
    return args


class Manager():
    def __init__(self,data_dir,train_dir, genre_map, verbose=False,
                 policy_network=None,load_policy_network=None,do_call_API=True):
        self.DB = databaseAPI.Database(genre_map, verbose=verbose)
        self.NLUModel = test_multi_task_rnn.test_model(data_dir,train_dir)
        self.policy_network = policy_network
        self.do_call_API = do_call_API
        self.in_sent = ''
        self.in_sent_seg = []

        #slot to fill for each action
        self.intent_slot_dict = {'search':['artist','track'],'recommend':['artist','track','genre'],'info':['track','artist'],None:[],'':[]}
        self.slot_prob_map = ['PAD','UNK',None,'track','artist','genre']
        self.valid_action = ['question_intent','question_slot_track','question_slot_artist','question_slot_genre',
                             'confirm_intent','confirm_slot_track','confirm_slot_artist','confirm_slot_genre',
                             'response','info']
        self.action_set = {'question_intent':0,'question_slot_track':1,'question_slot_artist':2,
                           'question_slot_genre':3,'confirm_intent':4,'confirm_slot_track':5,
                           'confirm_slot_artist':6,'confirm_slot_genre':7,'response':8,'info':9}
        self.positive_response = [u'是的',u'對',u'對啊',u'恩',u'沒錯',u'是啊',u'就是這樣',u'你真聰明',u'是',u'有',u'好啊']
        self.negative_response = [u'不是',u'錯了',u'不對',u'不用',u'沒有',u'算了',u'不需要',u'不 ',u'不要']
        #action threshold:
        self.intent_upper_threshold = 1.9
        self.intent_lower_threshold = 0.1
        self.slot_uppser_threshold = 1.9
        self.slot_lower_threshold = 0.1

        #if cycle_num > max_cycle_num, end the dialogue
        self.max_cycle_num = 12

        self.dialogue_end_sentence = ''
        self.state_init()

    def get_state_vec(self):
        """
        output vector is a 10 dim vector
            3:current state intent prob
            3:current state slot prob
            1:confirmed state intent(binary)
            3:confirmed state slot(binary)
        """
        state_vec = np.zeros(10)
        i = 0
        for intent_name in self.state['intent']:
            if self.confirmed_state['intent'] is None:
                state_vec[i] = self.state['intent'][intent_name]
            i += 1

        for slot_name in self.state['slot']:
            if len(self.state['slot'][slot_name])>0 and self.confirmed_state['slot'][slot_name] is None:
                state_vec[i] = self.max_slot[slot_name][1]
            i += 1

        if self.confirmed_state['intent'] is not None:
            state_vec[i] = 1.0
        i += 1

        for slot_name in self.state['slot']:
            if self.confirmed_state['slot'][slot_name] is not None:
                state_vec[i] = 1.0
            i += 1

        return state_vec.reshape([1,-1])


    def get_action_idx(self, action):
        action_name = action['action']
        if action_name != 'response' and action_name != 'info':
          if 'intent' in action:
            action_name += '_intent'
          elif 'slot' in action:
            action_name += '_slot_%s' % action['slot'].keys()[0]
        return self.action_set[action_name]
        raise Exception('action index not found')
        return None

    def get_input(self,sentence,agent):
        self.in_sent = sentence

        sentence = re.sub(u'就這樣|是的|對啊|對|恩|沒錯|不是|錯了|不對','',sentence[:4]) + sentence[4:]
        """
        print("CURRENT TURN START!!!!!!")
        print('input:',self.in_sent)
        print('NLU_input:',sentence)
        """

        self.NLU_result = self.NLUModel.feed_sentence(sentence)
        #print('NLU_RESULT:',self.NLU_result)

        self.state_tracking()
        if agent == 'rule-based':
            state_vec = self.get_state_vec()
            action = self.action_maker()
            sampled_action = np.zeros([len(self.valid_action)])
            sampled_action[self.get_action_idx(action)] = 1.0
            return action,state_vec.reshape([-1]),sampled_action
        else:
            state_vec = self.get_state_vec()
            action_distribution = self.policy_network.get_action_distribution(state_vec)
            #print('state_vec:',state_vec)
            action_distribution = action_distribution.reshape([-1])
            #print('action_distribution:',action_distribution.shape)
            action_id = np.random.choice(len(self.valid_action),1, p=action_distribution)[0]
            action = self.make_policy_action(action_id)
            sampled_action = np.zeros([len(self.valid_action)])
            sampled_action[action_id] = 1.0
            #print('action',action)
            return action,state_vec.reshape([-1]),sampled_action


    def make_policy_action(self,action_id):
        action_name = self.valid_action[action_id]
        cur_action = {'action':action_name.split('_')[0]}
        if 'intent' in action_name:
            cur_action['intent'] = self.max_intent
        elif 'slot' in action_name:
            slot = {}
            for slot_name in self.intent_slot_dict[self.confirmed_state['intent']]:
                if self.max_slot[slot_name] and self.confirmed_state['slot'][slot_name] != -1 and slot_name in action_name:
                    if self.max_slot[slot_name][1] > self.slot_lower_threshold:
                        slot[slot_name] = self.max_slot[slot_name][0]
            if len(slot)==0:
                slot['track'] = ''
            cur_action['slot'] = slot

        elif 'response' in action_name or 'info' in action_name:
            self.dialogue_end = True
            cur_action = {'action':action_name.split('_')[0],'intent':'','slot':{}}

            sentence = ''
            if self.do_call_API:
                s = {}
                for slot_name in self.confirmed_state['slot']:
                    if self.confirmed_state['slot'][slot_name] != None and self.confirmed_state['slot'][slot_name] != -1:
                        s[slot_name] = self.confirmed_state['slot'][slot_name]
                if self.confirmed_state['intent']=='search':
                    if self.do_call_API:
                        _,sentence = self.DB.search(s)
                elif self.confirmed_state['intent']=='info':
                    if self.do_call_API:
                        _,sentence = self.DB.info(s)
                elif self.confirmed_state['intent']=='recommend':
                    if self.do_call_API:
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
            self.dialogue_end = True
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
                if 'slot' in last_action:
                    for slot_name in last_action['slot']:
                        self.confirmed_state['slot'][slot_name] = -1.0
                if 'slot' in last_action:
                    for slot_name in last_action['slot']:
                        self.confirmed_state['slot'][slot_name] = -1.0


            elif last_action['action'] == 'confirm':
                if any(e in self.in_sent for e in self.negative_response):
                    self.update_state_with_NLU('slot',last_action)
                elif any(e in self.in_sent for e in self.positive_response):
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
                if any(e in self.in_sent for e in self.negative_response):
                    self.update_state_with_NLU('intent',last_action)
                elif any(e in self.in_sent for e in self.positive_response):
                    if 'intent' in last_action:
                        self.confirmed_state['intent'] = last_action['intent']
                else:
                    self.update_state_with_NLU()

            elif last_action['action'] == 'question':
                if any(e in self.in_sent for e in self.negative_response):
                    if 'intent' in last_action:
                        self.state['intent'][last_action['intent']] = -100.0
                else:
                    self.update_state_with_NLU()


        self.max_intent_prob = 0.0
        self.max_intent = ''
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
        for slot_name in self.intent_slot_dict['recommend']:
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


    def action_to_sentence(self,action):
        intent_to_chinese = {'search':u'聽歌','recommend':u'推薦歌曲', 'info':u'詢問歌曲資訊'}
        slot_to_chinese = {'artist':u'歌手名稱','track':u'歌曲名稱','genre':u'曲風'}
        if action['action']=='question':
            if 'intent' in action:
                return u'你好啊，請問你想要什麼服務'
            elif 'slot' in action:
                for slot_name in action['slot']:
                    return u'請問你是否要填入' + slot_to_chinese[slot_name] + u'嗎?'

        elif action['action'] == 'confirm':
            if 'intent' in action:
                return u'再確認一次 請問你是想' + intent_to_chinese[action['intent']] + u'嗎?'
            elif 'slot' in action:
                sent = u'再確認一次 請問你是否曾填入'
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

    DM = Manager(args.nlu_data , args.model, args.genre_map, verbose=args.verbose)

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
            DM.state_init()


def train_policy_network(args):
    performance_records = {}
    performance_records['success_rate'] = {}
    performance_records['ave_turns'] = {}
    performance_records['ave_reward'] = {}
    actor = policy_network('policy_network_model/')
    DM = Manager(args.nlu_data , args.model, args.genre_map,
                 verbose=args.verbose,policy_network=actor,
                 do_call_API=False)
    #initialize user simulator:
    simulator = Simulator(args.template_dir, args.data, args.genre,args.genre_map)
    _ = simulation(DM, actor, simulator, warm_start=True)
    episode_num = 0
    success_num = 0.0
    print('start training policy network')
    while(episode_num<=10000):
        episode_num += 1
        temp_memory = []
        simulator.set_user_goal(random_init=True)
        sentence = simulator.user_response({'action':'question'})
        while True:
            action,state_vec,sampled_action = DM.get_input(sentence, 'pg')
            temp_memory.append([state_vec,sampled_action])
            sentence = simulator.user_response(action)
            if DM.dialogue_end:
                reward = simulator.cur_reward
                if reward>0:
                    success_num += 1.0
                DM.state_init()
                for i in range(len(temp_memory)):
                    actor.add_memory([temp_memory[i][0],temp_memory[i][1],reward])
                break
        if episode_num%50==0:
            loss = actor.update()
            print(episode_num,':',loss,success_num/100.)
            result_file.write(str(episode_num)+':'+str(loss)+':'+str(success_num/100.)+'\n')
            success_num = 0.0

        if episode_num%5000==0:   
            actor.save_model(episode_num)

            simulation_res = simulation(DM, actor, simulator, warm_start=False)
            performance_records['success_rate'][episode_num] = simulation_res['success_rate']
            performance_records['ave_turns'][episode_num] = simulation_res['ave_turns']
            performance_records['ave_reward'][episode_num] = simulation_res['ave_reward']
            print('episode: %s, success_rate: %s, reward: %s'
                  % (episode_num, simulation_res['success_rate'], simulation_res['ave_reward']))
            if not os.path.exists('performance_record/'):
                os.mkdir('performance_record/')
            save_performance_records('performance_record/', episode_num, performance_records)
            actor.save_model()

def simulation(DM, actor, simulator, warm_start):
    successes = 0
    cumulative_reward = 0
    cumulative_turns = 0

    res = {}
    episode_num = 0
    if warm_start:
      agt = 'rule-based'
      epochs = 100
    else:
      agt = 'pg'
      epochs = 50
    print('start simulation')
    while(episode_num<=epochs):
        episode_num += 1
        temp_memory = []
        simulator.set_user_goal(random_init=True)
        sentence = simulator.user_response({'action':'question'})
        while True:
            action,state_vec,sampled_action = DM.get_input(sentence, agt)
            temp_memory.append([state_vec,sampled_action])
            sentence = simulator.user_response(action)
            if DM.dialogue_end:
                reward = simulator.cur_reward
                if reward > 0:
                  successes += 1
                cumulative_reward += reward
                cumulative_turns += DM.cycle_num
                DM.state_init()
                for i in range(len(temp_memory)):
                    actor.add_memory([temp_memory[i][0],temp_memory[i][1],reward])
                break
        if len(actor.memory) >= actor.memory_size:
            break
    res['success_rate'] = float(successes)/epochs
    res['ave_reward'] = float(cumulative_reward)/epochs
    res['ave_turns'] = float(cumulative_turns)/epochs
    print("Simulation %s epochs, success rate %s, ave_reward %s, ave_turns %s"
          % (epochs, res['success_rate'], res['ave_reward'], res['ave_turns']))
    print("Current experience replay buffer size % s" % (len(actor.memory)))
    return res

def save_performance_records(path, episode, records):
    filename = 'performance_records_%s.json' % episode
    filepath = os.path.join(path, filename)
    try:
        json.dump(records, open(filepath, "wb"))
        print('saved model in %s' % (filepath))
    except:
        print('Error: Writing model fails: %s' % (filepath))
>>>>>>> 07b71b567618d0f7acf227d24929cf6f9ebc808f

if __name__ == '__main__':
    args = optParser()
    if args.stdin:
        stdin_test(args)
    elif args.auto_test:
        auto_test(args)
    elif args.train_policy:
        train_policy_network(args)
    else:
        test(args)
