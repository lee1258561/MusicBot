# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
import sys
from ontology import databaseAPI
from rnn_nlu import data_utils, test_multi_task_rnn

def optParser():
    parser = argparse.ArgumentParser(description='Vanilla action controller')
    parser.add_argument('--data', default='./data/nlu_data/',type=str, help='data dir')
    parser.add_argument('--model',default='./model_tmp',type=str,help='model dir')
    parser.add_argument('-v',dest='verbose',default=False,action='store_true',help='verbose')
    args = parser.parse_args()
    return args

class Controller():
    def __init__(self,data_dir,train_dir,verbose=False):
        self.DB = databaseAPI.Database(verbose=verbose)
        self.NLUModel = test_multi_task_rnn.test_model(data_dir,train_dir)
        self.in_sent = ''
        self.in_sent_seg = []
        

    def input(self,sentence):
        self.in_sent = sentence
        self.in_sent_seg = data_utils.naive_seg(sentence)
        if len(self.in_sent_seg) == 0:
            return False
        self.in_intent, self.in_pos = self.NLUModel.feed_sentence(sentence)
        print (self.in_intent,self.in_pos)

        return True

    def action(self):
        # TODO add rule-based if else
        slot = databaseAPI.build_slot(self.in_sent_seg, self.in_pos)
        if 'given' in self.in_intent and len(slot) > 0:
            self.DB.given(slot)
        else:
            print ('Not supported yet...')


def main():
    args = optParser()
    AC = Controller(args.data , args.model, verbose=args.verbose)

    while True:
        print('(SpotiBot): 想聽什麼歌?')
        print(':',end='')
        sentence = sys.stdin.readline()
        if AC.input(sentence):
            AC.action()
        
if __name__ == '__main__':
    main()
        
