import json
import os 
import pandas as pd
import argparse

from copy import copy
sys_intent = ['question', 'confirm']
intents = ['search', 'recommend', 'info']
intent_to_chinese = {'search':u'搜尋', 'recommend':u'推薦', 'info':u'查相關資訊'}
slots = ['artist','track', 'genre']
tokens = ['[s]','[t]','[g]']
slot_token_map = {'artist':'[s]', 'track':'[t]', 'genre':'[g]'}
token_slot_map = {'[i]': 'intent','[s]':'artist', '[t]':'track', '[g]':'genre'}
input_dims = ['action', 'intent', 'artist','track', 'genre']
input_default = ['none', 'none', 'none', 'none', 'none']


def load_data(data_path, genre_path):
    '''
        Load templates and all the slot data
        Arguments: 
            template_dir: path to the template dir
            data_path: path to the chinese_artist.json
            genre_path: path to the genre.json
        Return: 
            data: dict
                'artists': list of artists
                'tracks': list of tracks
                'track_artist_map': track_artist_map {'t1':'a1','t2':'a2']}
                'genres': list of genres
                'intent_template_map': intent to template dictionary
    '''
    ### load file and init
    with open(data_path,'r') as f:
        data_artist = json.load(f)
    with open(genre_path,'r') as f:
        genres=json.load(f)

    artists = [s for s in data_artist]
    tracks = []
    track_artist_map = {}
    for s in data_artist:
        for a in data_artist[s]:
            for t in data_artist[s][a]:
                track_artist_map[t] = s
                tracks.append(t)
    '''
    intent_template_map = {}
    for i in intents:
        intent_template_map[i] = []
        f = os.path.join(template_dir, i+'.csv')
        data_sent = pd.read_csv(f)
        data_sent = data_sent[data_sent.columns[0]].unique()
        intent_template_map[i] = data_sent
        '''

    return {'artist':artists, 'tracks':tracks, 'track_artist_map':track_artist_map,\
            'genres':genres, 'intent_template_map':intent_template_map}

def generate_input(frame):
    print (frame)
    input_sentence = copy(input_default)
    input_sentence[0] = frame[0]
    if len(frame) <= 1:
        return ' '.join(input_sentence)
    slot = frame[1:]
    if frame[1] in intents:
        input_sentence[input_dims.index('intent')] = frame[1]
        slot = frame[2:]

    for s in slot:
        if s in slots:
            input_sentence[input_dims.index(s)] = 'True'

    return ' '.join(input_sentence)





def generate_sentence(data, template_path, data_dir):
    frame_templates_pairs = [] 
    with open(template_path, 'r') as f:
        for line in f:
            frame = line.split()
            templates = []
            for line in f:
                if line == '\n':
                    break
                templates.append(line.strip())

            frame_templates_pairs.append((frame, templates))

    seq_pairs = []
    for frame, templates in frame_templates_pairs:
        if 'intent' in frame:
            for i in intents:
                tmp_frame = copy(frame)
                tmp_frame[tmp_frame.index('intent')] = i
                input_sentence = generate_input(tmp_frame)

                template_num = 0
                for t in templates:
                    t = t.replace('[i]', intent_to_chinese[i])
                    t = t.replace('[a]', 'a')
                    t = t.replace('[t]', 't')
                    t = t.replace('[g]', 'g')

                    seq_pairs.append((input_sentence + ' ' + str(template_num), ' '.join(t)))
                    template_num += 1
                    
        else:
            input_sentence = generate_input(frame)
            template_num = 0
            for t in templates:
                t = t.replace('[a]', 'a')
                t = t.replace('[t]', 't')
                t = t.replace('[g]', 'g')
                seq_pairs.append((input_sentence + ' ' + str(template_num), ' '.join(t)))
                template_num += 1

    if not os.path.exists(data_dir):
        os.mkdir(data_dir)

    with open(os.path.join(data_dir, 'train.en'), 'w') as f_en, open(os.path.join(data_dir, 'train.fr'), 'w') as f_fr:
        for p in seq_pairs:
            f_en.write(p[0] + '\n')
            f_fr.write(p[1] + '\n')

    with open(os.path.join(data_dir, 'valid.en'), 'w') as f_en, open(os.path.join(data_dir, 'valid.fr'), 'w') as f_fr:
        pass
    for p in seq_pairs:
        print(p)


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--template_path', type=str, help="Path to template file")
    parser.add_argument('--data_dir', type=str, help="Path to data directory")

    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = get_args()
    #data = load_data('../data/template', '../data/chinese_artist.json', '../data/genres.json')
    generate_sentence([], args.template_path, args.data_dir)




