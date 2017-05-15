# -*- coding: utf-8 -*-
import fbchat

from Dialogue_Manager import Manager, optParser

class fbBot(fbchat.Client):
    def __init__(self, email, password, args, debug=True, user_agent=None):
        fbchat.Client.__init__(self,email, password, debug, user_agent)

        #print('NLU initializing...')
        #self.NLU = run_multi_task_rnn.NLU_test()

        #print('database initializing...')
        #self.db = databaseAPI.Database('./data/genre_map.json')

        print('Dialogue_Manager initializing...')
        self.DM = Manager(args.nlu_data, args.model, args.genre_map, verbose=args.verbose)

    def on_message(self, mid, author_id, author_name, message, metadata):
        self.markAsDelivered(author_id, mid) #mark delivered
        self.markAsRead(author_id) #mark read
        print('======metadata======')
        #print(metadata)

        print("%s said: %s"%(author_id, message))
        ID = None
        if 'delta' in metadata and 'messageMetadata' in metadata['delta'] and 'threadKey' in metadata['delta']['messageMetadata'] and 'threadFbId' in metadata['delta']['messageMetadata']['threadKey']:
            ID = metadata['delta']['messageMetadata']['threadKey']['threadFbId']
        #if you are not the author, echo
        if str(author_id) != str(self.uid) and ID == None:
            try:
                message = message.decode('utf-8')
            except UnicodeError:
                pass

            '''
            intent, pos = self.NLU.feed_sentence(message)
            print(intent, pos)
            slot = databaseAPI.build_slot(data_utils.naive_seg(message), pos)
            print(slot)
            if 'search' in intent:
                _, sentence = self.db.search(slot)
            elif 'recommend' in intent:
                tracks, sentence = self.db.recommend(slot)
            elif 'info' in intent:
                info, sentence = self.db.info(slot)
            elif 'neutral' in intent:
                sentence = (u'可以說清楚些嗎？')
            '''
            sentence = self.DM.get_API_input(message)
            print("=============")
            print("system response: %s" % sentence)
            print("=============")
            self.send(author_id,sentence)

if __name__ == '__main__':
    args = optParser()
    bot = fbBot("cotapocil@1rentcar.top", "silencefarmer", args)
    bot.listen()
