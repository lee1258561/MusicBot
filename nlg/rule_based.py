import json
import os 
import pandas as pd
import argparse
import random

from math import ceil
from copy import copy

sys_intent = ['question', 'confirm']
intents = ['search', 'recommend', 'info']
intent_to_chinese = {'search':u'搜尋', 'recommend':u'推薦', 'info':u'查相關資訊'}
slots = ['artist','track', 'genre']
tokens = ['[a]','[t]','[g]']
slot_token_map = {'artist':'[a]', 'track':'[t]', 'genre':'[g]'}
token_slot_map = {'[i]': 'intent','[a]':'artist', '[t]':'track', '[g]':'genre'}
input_dims = ['action', 'intent', 'artist','track', 'genre']
input_default = ['none', 'none', 'none', 'none', 'none']

class NLG():
	def __init__(self, template_path):
		self.frame_templates_pairs = {}
		with open(template_path, 'r') as f:
			for line in f:
				frame = line.strip()
				templates = []
				for line in f:
					if line == '\n':
						break
					templates.append(line.strip())

				self.frame_templates_pairs[frame] = templates

		#print(self.frame_templates_pairs)

	def decode(self, frame):
		frame_s = [frame['action']]
		if 'intent' in frame:
			frame_s.append(frame['intent'])
		if frame['action'] == 'question' and 'intent' in frame:
			frame_s = ['Hello']

		slot_to_replace = []
		if 'slot' in frame:
			for s in slots:
				if s in frame['slot']:
					slot_to_replace.append(s)
					frame_s.append(s)
		frame_s = ' '.join(frame_s)
		print(frame_s)
		if frame_s not in self.frame_templates_pairs:
			print('Error: template not exist')
			return None
		template = random.choice(self.frame_templates_pairs[frame_s])

		for s in slot_to_replace:
			print(s)
			template = template.replace(slot_token_map[s], frame['slot'][s])

		return template

if __name__ == '__main__':
	nlg = NLG('./NLG.txt')
	frame = {'action': 'confirm', 'intent': 'search', 'slot': {'artist': 'Maroon5', 'track': 'Move like jagger'}}
	print(nlg.decode(frame))


    	






