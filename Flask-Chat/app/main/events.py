# -*- coding: utf-8 -*-
from flask import session
from flask_socketio import emit, join_room, leave_room
from .. import socketio
import time

import sys
sys.path.append('./')
from userSimulator import Simulator
from Dialogue_Manager import Manager
import argparse

def optParser():
    parser = argparse.ArgumentParser(description='Vanilla action controller')
    parser.add_argument('--nlu_data', default='./data/nlu_data_eng/',type=str, help='data dir')
    parser.add_argument('--model',default='./model_tmp_eng/',type=str,help='model dir')
    parser.add_argument('--template_dir',default='../data/template/',\
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
    parser.add_argument('-v',dest='verbose',default=False,action='store_true',help='verbose')
    args = parser.parse_args()
    return args

args = optParser()
simulator = Simulator('./data/template/','./data/chinese_artist.json','./data/genres.json', './data/genre_map.json')
DM = Manager(args.nlu_data, args.model, args.genre_map, args.spotify_playlist, args.spotify_account, verbose=args.verbose)
PLAY_TYPES = ['search', 'playlistPlay', 'playlistSpotify']

@socketio.on('joined', namespace='/chat')
def joined(message):
    """Sent by clients when they enter a room.
    A status message is broadcast to all people in the room."""
    room = session.get('room')
    join_room(room)
    DM.state_init()
    DM.user_name = session.get('name')
    emit('status', {'msg': session.get('name') + ' has entered the room.'}, room=room)
    emit('message', {'u_name':'Music Bot', 'msg': '你好，請問需要什麼服務？'}, room=room)
    emit('message', {'u_name':'Music Bot', 'msg': 'MusicBot提供的服務有：(1)聽歌：依據歌手及歌曲名稱找到你想要聽的歌 (2)推薦歌曲：依據歌手、歌曲名稱及曲風(古典、爵士、金屬、搖滾、吉他⋯⋯)推薦類似歌曲 (3)詢問歌手或歌曲資訊 (4)建立播放清單及新增歌曲 (5)播放自訂或公共播放清單'}, room=room)


@socketio.on('text', namespace='/chat')
def text(message):
    """Sent by a client when the user entered a new message.
    The message is sent to all people in the room."""
    room = session.get('room')
    name = session.get('name')
    sent = message['msg']
    emit('message', {'u_name':name,'msg':sent}, room=room)

    
    action = DM.get_input(sent)
    DM.print_current_state() # Debug

    DM_response = DM.action_to_sentence(action)
    if len(DM_response) > 0:
        emit('message', {'u_name':'Music Bot', 'msg': DM.action_to_sentence(action)}, room=room)
    if DM.dialogue_end:
        emit('message', {'u_name':'Music Bot', 'msg': DM.dialogue_end_sentence}, room=room)
        if DM.dialogue_end_type in PLAY_TYPES  :
            emit('message',{'u_name':'Music Bot', 'toPlay':1, 'url':DM.dialogue_end_track_url})
        if DM.dialogue_end_type == 'recommend':
            emit('message',{'u_name':'Music Bot', 'toPlay':1, 'url':DM.dialogue_end_track_url[0]})
            emit('message',{'u_name':'Music Bot', 'toPlay':1, 'url':DM.dialogue_end_track_url[1]})
            emit('message',{'u_name':'Music Bot', 'toPlay':1, 'url':DM.dialogue_end_track_url[2]})

        print('\nCongratulation!!! You have ended one dialogue successfully\n')
        DM.state_init()
    
    


@socketio.on('slot', namespace='/chat')
def slot(message):
    room = session.get('room')
    slot_dict = eval(message['slot'])
    for key in slot_dict:
        slot_dict[key] = slot_dict[key] if len(slot_dict[key]) > 0 else None
    simulator.set_user_goal(intent=slot_dict['intent'], artist=slot_dict['artist'], track=slot_dict['track'],\
            genre=slot_dict['genre'])
    simulator.print_cur_user_goal()
    sent = simulator.user_response({'action':'question'})
    emit('message', {'msg': session.get('name') + ': ' + sent}, room=room)
    
    
    while True:
        action = DM.get_input(sent)
        DM.print_current_state()
        DM_response = DM.action_to_sentence(action)
        if DM_response is not None:
            emit('message', {'msg': 'Music Bot: ' + DM_response}, room=room)
        sent = simulator.user_response(action)
        emit('message', {'msg': session.get('name') + ': ' + sent}, room=room)
        if DM.dialogue_end:
            emit('message', {'msg': 'Music Bot: Dialogue System final response: ' + DM.dialogue_end_sentence}, room=room)
            print('\nCongratulation!!! You have ended one dialogue successfully\n')
            DM.state_init()
            break
    
    
@socketio.on('left', namespace='/chat')
def left(message):
    """Sent by clients when they leave a room.
    A status message is broadcast to all people in the room."""
    room = session.get('room')
    leave_room(room)
    emit('status', {'msg': session.get('name') + ' has left the room.'}, room=room)
