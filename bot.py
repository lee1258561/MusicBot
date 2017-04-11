import fbchat
#subclass fbchat.Client and override required methods
class EchoBot(fbchat.Client):

    def __init__(self,email, password, debug=True, user_agent=None):
        fbchat.Client.__init__(self,email, password, debug, user_agent)

    def on_message(self, mid, author_id, author_name, message, metadata):
        self.markAsDelivered(author_id, mid) #mark delivered
        self.markAsRead(author_id) #mark read
        print('======metadata======')
        print(metadata)

        print("%s said: %s"%(author_id, message))
        ID = None
        if 'delta' in metadata and 'messageMetadata' in metadata['delta'] and 'threadKey' in metadata['delta']['messageMetadata'] and 'threadFbId' in metadata['delta']['messageMetadata']['threadKey']:
            ID = metadata['delta']['messageMetadata']['threadKey']['threadFbId']
        #if you are not the author, echo
        if str(author_id) != str(self.uid):
            self.send(author_id,message)

bot = EchoBot("email", "password")
bot.listen()
