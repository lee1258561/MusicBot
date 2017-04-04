# -*- coding: utf-8 -*-
import numpy as np
import sys

def naive_seg(sentence):
    ''' Seqment the sentence into words seperated by space
        Return segment list
        Input sentence should be utf-8 encoding
        e.g.
            你的English真的是very good的呢
            ->[你,的,English,真,的,是,very,good,的,呢]
    '''
    #sentence = sentence.decode('utf-8')
    sentence = sentence.split()
    sentence_seg = []
    for w in sentence:
        tmp_w = ''
        for c in w:
            if u'\u4e00' <= c <= u'\u9fff':
                if len(tmp_w) > 0:
                    sentence_seg.append(tmp_w)
                sentence_seg.append(c)
                tmp_w = ''
            else:
                tmp_w += c
        if len(tmp_w) > 0:
            sentence_seg.append(tmp_w)
    return sentence_seg


if __name__ == '__main__':
    naive_seg('我想聽[s]的')
