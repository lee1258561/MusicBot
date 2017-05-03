# -*- coding: utf-8 -*-
import sys
import json
import argparse
import random
import os
import pandas as pd
import numpy as np
import io_utils

def opt_parse():
    parser = argparse.ArgumentParser(description=\
            'Split dataset into train,valid,test',\
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('data_dir',help='directory of original Train_')
    parser.add_argument('-v',default=0.05,type=float,help='valid proportion')
    parser.add_argument('-t',default=0.05,type=float,help='test proportion')
    parser.add_argument('-o','--output',default='./',help='output dir')
    args = parser.parse_args()
    return args

def split_data(args):
    X = io_utils.load_X(args.data_dir+'Train_X')
    POS = io_utils.load_POS(args.data_dir+'Train_POS')
    Intent = io_utils.load_Intent(args.data_dir+'Train_Intent')
    data_len = len(X)

    ### shuffle data
    index_shuff = range(data_len)
    random.shuffle(index_shuff)

    X_shuff = [ X[index_shuff[i]] for i in index_shuff]
    POS_shuff = [ POS[index_shuff[i]] for i in index_shuff]
    Intent_shuff = [ Intent[index_shuff[i]] for i in index_shuff]


    ### dump train
    directory = os.path.join(args.output,'train')
    if not os.path.exists(directory):
            os.makedirs(directory)
    amount = int(data_len*(1. - args.v - args.t))
    io_utils.dump_to_file(X_shuff[:amount],POS_shuff[:amount],Intent_shuff[:amount],\
            directory+'/train_' )

    ### dump valid
    directory = os.path.join(args.output,'valid')
    if not os.path.exists(directory):
            os.makedirs(directory)
    amount_v = int(data_len*(1. - args.t))
    io_utils.dump_to_file(X_shuff[amount:amount_v],POS_shuff[amount:amount_v],\
            Intent_shuff[amount:amount_v],directory+'/valid_' )

    ### dump test
    directory = os.path.join(args.output,'test')
    if not os.path.exists(directory):
            os.makedirs(directory)
    io_utils.dump_to_file(X_shuff[amount_v:],POS_shuff[amount_v:],Intent_shuff[amount_v:]\
            ,directory+'/test_' )

if __name__ == '__main__':
    args = opt_parse()
    split_data(args)
