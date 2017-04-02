# -*- coding: utf-8 -*-
import pandas as pd
import sys
import json
import argparse
import numpy as np


'''
Sentence generation based on sentence template from google form
and the artists, tracks, albums, genres data crawled from Spotify
'''


def opt_parse():
    parser = argparse.ArgumentParser(description=\
            'Slot & intent data generate')
    parser.add_argument('template',help='sentence template')
    parser.add_argument('data',help='artist-album-track json data')
    parser.add_argument('genre',help='genres')
    parser.add_argument('-output',default='Train_',help='output filename prefix')
    args = parser.parse_args()
    return args

def fill_slot(X,POS,Intent,intent,template,s=None,a=None,t=None,g=None,l=None):
    pos = '0'*len(template)
    new_temp = template
    offset_s = new_temp.find('[s]')
    if offset_s != -1 and s != None:
        pos = pos[:offset_s]+'s'*len(s)+pos[offset_s+3:]
        new_temp = new_temp.replace('[s]',s)

    offset_a = new_temp.find('[a]')
    if offset_a != -1 and a != None:
        pos = pos[:offset_a]+'a'*len(a)+pos[offset_a+3:]
        new_temp = new_temp.replace('[a]',a)

    offset_t = new_temp.find('[t]')
    if offset_t != -1 and t != None:
        pos = pos[:offset_t]+'t'*len(t)+pos[offset_t+3:]
        new_temp = new_temp.replace('[t]',t)

    offset_g = new_temp.find('[g]')
    if offset_g != -1 and g!= None:
        pos = pos[:offset_g]+'g'*len(g)+pos[offset_g+3:]
        new_temp = new_temp.replace('[g]',g)

    offset_l = new_temp.find('[l]')
    if offset_l != -1 and l!=None:
        pos = pos[:offset_l]+'l'*len(l)+pos[offset_l+3:]
        new_temp = new_temp.replace('[l]',l)

    #print new_temp
    #print pos

    X.append(new_temp)
    POS.append(pos)
    Intent.append(intent)
    return


def fill_template(data_artist,data_sent,genre_list,args_output):
    '''
        fill the given [...] slot of template sentences
        then store to file with prefix of args_output
    '''
    ### init
    intent_list = data_sent[data_sent.columns[0]].unique()
    print intent_list
    X = []
    POS = []
    Intent = []
    
    data_sent = data_sent.values
    for n,sent in enumerate(data_sent):
        intent = sent[0].decode('utf-8')
        template = sent[1].decode('utf-8')
        #print n,intent,template
        
        if intent == 'given':
            if '[d]' in template: # skip date info
                continue
            if '[t]' in template:
                for s in data_artist:
                    for a in data_artist[s]:
                        for t in data_artist[s][a]:
                            fill_slot(X,POS,Intent,intent,template,s,a,t)
            elif '[a]' in template:
                for s in data_artist:
                    for a in data_artist[s]:
                        if '[g]' in template:
                            for g in genre_list:
                                fill_slot(X,POS,Intent,intent,template,s,a,t,g)
                        else:
                            fill_slot(X,POS,Intent,intent,template,s,a,t)
            elif '[s]' in template:
                for s in data_artist:
                    if '[g]' in template:
                        for g in genre_list:
                            fill_slot(X,POS,Intent,intent,template,s,a,t,g)
                    else:
                        fill_slot(X,POS,Intent,intent,template,s,a,t)

        elif intent =='recommend':
            for g in genre_list:
                fill_slot(X,POS,Intent,intent,template,g=g)
                print g,intent
        elif 'List' not in intent and 'list' not in intent:
            fill_slot(X,POS,Intent,intent,template)


    dump_to_file(X,POS,Intent,args_output)

def dump_to_file(X,POS,Intent,args_output):
    f_X = open(args_output+'X','w')
    f_POS = open(args_output+'POS','w')
    f_Intent = open(args_output+'Intent','w')

    for n in range(len(X)):
        f_X.write(u'{}\n'.format(X[n]).encode('utf-8'))
        f_POS.write(u'{}\n'.format(POS[n]).encode('utf-8'))
        f_Intent.write(u'{}\n'.format(Intent[n]).encode('utf-8'))


def sent_gen(args):
    with open(args.data,'r') as f:
        data_artist = json.load(f)
    with open(args.genre,'r') as f:
        genre_list=json.load(f)
    data_sent = pd.read_csv(args.template)

    data_sent = data_sent[data_sent.columns[1:]] # remove timestamp column
    #print data_sent

    # select Intent: Given [singer | album | date | track | genre ] find songs
    # given_row =  data_sent[data_sent.columns[0]] == 'Given'
    fill_template(data_artist,data_sent,genre_list,args.output)



if __name__ == '__main__':
    args = opt_parse()
    sent_gen(args)
