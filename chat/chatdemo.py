#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import tornado.escape
import tornado.ioloop
import tornado.web
import os.path
import uuid

from tornado.concurrent import Future
from tornado import gen
from tornado.options import define, options, parse_command_line

define("port", default=8888, help="run on the given port", type=int)
define("debug", default=False, help="run in debug mode")

import sys
sys.path.append('../')
from userSimulator import Simulator
from Dialogue_Manager import Manager
import argparse

def optParser():
    parser = argparse.ArgumentParser(description='Vanilla action controller')
    parser.add_argument('--nlu_data', default='../data/nlu_data/',type=str, help='data dir')
    parser.add_argument('--model',default='../model_tmp/',type=str,help='model dir')
    parser.add_argument('--template_dir',default='../data/template/',\
            help='sentence template directory')
    parser.add_argument('--data',default='../data/chinese_artist.json',\
            help='artist-album-track json data')
    parser.add_argument('--genre',default='../data/genres.json',\
            help='genres')
    parser.add_argument('--genre_map',default='../data/genre_map.json',\
            type=str,help='genre_map.json path')
    parser.add_argument('--random',action='store_true',help='whether to random user goal')
    parser.add_argument('-v',dest='verbose',default=False,action='store_true',help='verbose')
    args = parser.parse_args()
    return args

class MessageBuffer(object):
    def __init__(self):
        self.waiters = set()
        self.cache = []
        self.cache_size = 200

    def wait_for_messages(self, cursor=None):
        # Construct a Future to return to our caller.  This allows
        # wait_for_messages to be yielded from a coroutine even though
        # it is not a coroutine itself.  We will set the result of the
        # Future when results are available.
        result_future = Future()
        if cursor:
            new_count = 0
            for msg in reversed(self.cache):
                if msg["id"] == cursor:
                    break
                new_count += 1
            if new_count:
                result_future.set_result(self.cache[-new_count:])
                return result_future
        self.waiters.add(result_future)
        return result_future

    def cancel_wait(self, future):
        self.waiters.remove(future)
        # Set an empty result to unblock any coroutines waiting.
        future.set_result([])

    def new_messages(self, messages):
        logging.info("Sending new message to %r listeners", len(self.waiters))
        for future in self.waiters:
            future.set_result(messages)
        self.waiters = set()
        self.cache.extend(messages)
        if len(self.cache) > self.cache_size:
            self.cache = self.cache[-self.cache_size:]


# Making this a non-singleton is left as an exercise for the reader.
global_message_buffer = MessageBuffer()
simulator = Simulator('../data/template/','../data/chinese_artist.json','../data/genres.json')
args = optParser()
DM = Manager(args.nlu_data , args.model, args.genre_map, verbose=args.verbose)

def build_msg(sentence):
    message = {
        "id": str(uuid.uuid4()),
        "body": sentence
    }
    return [message]


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", messages=global_message_buffer.cache)


class MessageNewHandler(tornado.web.RequestHandler):
    def post(self):
        message = {
            "id": str(uuid.uuid4()),
            "body": self.get_argument("body"),
        }
        # to_basestring is necessary for Python 3's json encoder,
        # which doesn't accept byte strings.
        print message
        message["html"] = tornado.escape.to_basestring(
            self.render_string("message.html", message=message))
        if self.get_argument("next", None):
            self.redirect(self.get_argument("next"))
        else:
            self.write(message)
        global_message_buffer.new_messages([message])


class SlotNewHandler(tornado.web.RequestHandler):
    def post(self):
        slot={}
        slot['intent'] = self.get_argument("intent")
        slot['artist'] = self.get_argument('artist')
        slot['track'] = self.get_argument('track')
        slot['genre'] = self.get_argument('genre')
        
        for key in slot:
            slot[key] = slot[key] if len(slot[key]) > 0 else None
        simulator.set_user_goal(intent=slot['intent'],artist=slot['artist'],track=slot['track'],\
                genre=slot['genre'])
        simulator.print_cur_user_goal()
        if self.get_argument("next", None):
            self.redirect(self.get_argument("next"))
        sent = simulator.user_response({'action':'question','intent':''})
        message = build_msg(sent)
        global_message_buffer.new_messages(message)
        while True:
            #print "sent = ", sent
            action = DM.get_input(sent)
            message = build_msg("(Music Bot)：State: " + str(DM.state))
            global_message_buffer.new_messages(message)
            message = build_msg("(Music Bot)：Confirmed State: " + str(DM.confirmed_state))
            global_message_buffer.new_messages(message)
            message = build_msg("(Music Bot)：Action History: " + str(DM.action_history))
            global_message_buffer.new_messages(message)
            sent = simulator.user_response(action)
            message = build_msg(sent)
            global_message_buffer.new_messages(message)
            if DM.dialogue_end:
                simulator.print_cur_user_goal()
                print('Congratulation!!! You have ended dialogue successfully')
                message = build_msg("(Music Bot)：想聽什麼歌？ (請輸入 intent 和 slot)")
                global_message_buffer.new_messages(message)
                DM.state_init()
                break


class MessageUpdatesHandler(tornado.web.RequestHandler):
    @gen.coroutine
    def post(self):
        cursor = self.get_argument("cursor", None)
        # Save the future returned by wait_for_messages so we can cancel
        # it in wait_for_messages
        self.future = global_message_buffer.wait_for_messages(cursor=cursor)
        messages = yield self.future
        if self.request.connection.stream.closed():
            return
        self.write(dict(messages=messages))

    def on_connection_close(self):
        global_message_buffer.cancel_wait(self.future)


def main():
    parse_command_line()
    global_message_buffer.new_messages([{"id": str(uuid.uuid4()), "body": "(Music Bot)：想聽什麼歌？ (請輸入 intent 和 slot)"}])
    app = tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/a/message/new", MessageNewHandler),
            (r"/a/message/updates", MessageUpdatesHandler),
            (r"/a/slots", SlotNewHandler),
            ],
        cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
        template_path=os.path.join(os.path.dirname(__file__), "templates"),
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        xsrf_cookies=False,
        debug=options.debug,
        )
    app.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
