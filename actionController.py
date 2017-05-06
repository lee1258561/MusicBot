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
    parser.add_argument('--genre_map',default='./data/genre_map.json',type=str,help='genre_map.json path')
    parser.add_argument('-v',dest='verbose',default=False,action='store_true',help='verbose')
    args = parser.parse_args()
    return args

class Controller():
    def __init__(self,data_dir,train_dir,genre_map,verbose=False):
        self.DB = databaseAPI.Database(genre_map,verbose=verbose)
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
        sent = ''
        if len(slot) > 0:
            if 'search' in self.in_intent:
                _, sent = self.DB.search(slot)
            elif 'recommend' in self.in_intent:
                _, sent = self.DB.recommend(slot)
            elif 'info' in self.in_intent:
                _, sent = self.DB.recommend(slot)
            elif 'neutral' in self.in_intent:
                sent = (u'麻煩說得更清楚一些喔')
            else:
                sent = ('Not supported yet...')
            print (sent)


def main():
    args = optParser()
    AC = Controller(args.data , args.model, args.genre_map, verbose=args.verbose)

    while True:
        print('(SpotiBot): 想聽什麼歌?')
        print(':',end='')
        sentence = sys.stdin.readline()
        if AC.input(sentence):
            AC.action()
        
if __name__ == '__main__':
    main()
        
