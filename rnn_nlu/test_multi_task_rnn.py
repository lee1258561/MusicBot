# -*- coding: utf-8 -*-
"""
Created on Sun Feb 28 16:23:37 2016

@author: Bing Liu (liubing@cmu.edu)
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import math
import os
import sys
import time

import numpy as np
from six.moves import xrange  # pylint: disable=redefined-builtin
import tensorflow as tf

from . import data_utils
from . import multi_task_model

import subprocess
import stat
from ontology import databaseAPI

#tf.app.flags.DEFINE_float("learning_rate", 0.1, "Learning rate.")
#tf.app.flags.DEFINE_float("learning_rate_decay_factor", 0.9,
#                          "Learning rate decays by this much.")
tf.app.flags.DEFINE_float("max_gradient_norm", 5.0,
                          "Clip gradients to this norm.")
tf.app.flags.DEFINE_integer("batch_size", 16,
                            "Batch size to use during training.")
tf.app.flags.DEFINE_integer("size", 128, "Size of each model layer.")
tf.app.flags.DEFINE_integer("word_embedding_size", 128, "Size of the word embedding")
tf.app.flags.DEFINE_integer("num_layers", 1, "Number of layers in the model.")
tf.app.flags.DEFINE_integer("in_vocab_size", 12000, "max vocab Size.")
tf.app.flags.DEFINE_integer("out_vocab_size", 12000, "max tag vocab Size.")
tf.app.flags.DEFINE_string("data_dir", "/tmp", "Data directory")
tf.app.flags.DEFINE_string("train_dir", "/tmp", "Training directory.")
tf.app.flags.DEFINE_integer("max_train_data_size", 0,
                            "Limit on the size of training data (0: no limit).")
tf.app.flags.DEFINE_integer("steps_per_checkpoint", 300,
                            "How many training steps to do per checkpoint.")
tf.app.flags.DEFINE_integer("max_training_steps", 10000,
                            "Max training steps.")
tf.app.flags.DEFINE_integer("max_test_data_size", 0,
                            "Max size of test set.")
tf.app.flags.DEFINE_boolean("use_attention", True,
                            "Use attention based RNN")
tf.app.flags.DEFINE_integer("max_sequence_length", 130,
                            "Max sequence length.")
tf.app.flags.DEFINE_float("dropout_keep_prob", 0.5,
                          "dropout keep cell input and output prob.")
tf.app.flags.DEFINE_boolean("bidirectional_rnn", True,
                            "Use birectional RNN")
tf.app.flags.DEFINE_string("task", 'joint', "Options: joint; intent; tagging")
tf.app.flags.DEFINE_string("mode", "train", "Options: train; test(default: train)")
FLAGS = tf.app.flags.FLAGS

if FLAGS.max_sequence_length == 0:
    print ('Please indicate max sequence length. Exit')
    sys.exit(1)

if FLAGS.task is None:
    print ('Please indicate task to run. Available options: intent; tagging; joint')
    sys.exit(1)

task = dict({'intent':0, 'tagging':0, 'joint':0})
if FLAGS.task == 'intent':
    task['intent'] = 1
elif FLAGS.task == 'tagging':
    task['tagging'] = 1
elif FLAGS.task == 'joint':
    task['intent'] = 1
    task['tagging'] = 1
    task['joint'] = 1

_buckets = [(FLAGS.max_sequence_length, FLAGS.max_sequence_length)]
#_buckets = [(3, 10), (10, 25)]

# metrics function using conlleval.pl
def conlleval(p, g, w, filename):
    '''
    INPUT:
    p :: predictions
    g :: groundtruth
    w :: corresponding words

    OUTPUT:
    filename :: name of the file where the predictions
    are written. it will be the input of conlleval.pl script
    for computing the performance in terms of precision
    recall and f1 score
    '''
    out = ''
    for sl, sp, sw in zip(g, p, w):
        out += 'BOS O O\n'
        for wl, wp, w in zip(sl, sp, sw):
            out += w + ' ' + wl + ' ' + wp + '\n'
        out += 'EOS O O\n\n'

    f = open(filename, 'w')
    f.writelines(out[:-1]) # remove the ending \n on last line
    f.close()

    return get_perf(filename)

def get_perf(filename):
    ''' run conlleval.pl perl script to obtain
    precision/recall and F1 score '''
    _conlleval = os.path.dirname(os.path.realpath(__file__)) + '/conlleval.pl'
    os.chmod(_conlleval, stat.S_IRWXU)  # give the execute permissions

    proc = subprocess.Popen(["perl",
                            _conlleval],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)

    stdout, _ = proc.communicate(b''.join(open(filename, 'rb').readlines()))
    stdout = stdout.decode()
    for line in stdout.split('\n'):
        if 'accuracy' in line:
            out = line.split()
            break

    precision = float(out[6][:-2])
    recall = float(out[8][:-2])
    f1score = float(out[10])

    return {'p': precision, 'r': recall, 'f1': f1score}


def read_data(source_path, target_path, label_path, max_size=None):
  """Read data from source and target files and put into buckets.

  Args:
    source_path: path to the files with token-ids for the source input - word sequence.
    target_path: path to the file with token-ids for the target output - tag sequence;
      it must be aligned with the source file: n-th line contains the desired
      output for n-th line from the source_path.
    label_path: path to the file with token-ids for the sequence classification label
    max_size: maximum number of lines to read, all other will be ignored;
      if 0 or None, data files will be read completely (no limit).

  Returns:
    data_set: a list of length len(_buckets); data_set[n] contains a list of
      (source, target, label) tuple read from the provided data files that fit
      into the n-th bucket, i.e., such that len(source) < _buckets[n][0] and
      len(target) < _buckets[n][1]; source,  target, and label are lists of token-ids.
  """
  data_set = [[] for _ in _buckets]
  with tf.gfile.GFile(source_path, mode="r") as source_file:
    with tf.gfile.GFile(target_path, mode="r") as target_file:
      with tf.gfile.GFile(label_path, mode="r") as label_file:
        source, target, label = source_file.readline(), target_file.readline(), label_file.readline()
        counter = 0
        while source and target and label and (not max_size or counter < max_size):
          counter += 1
          if counter % 100000 == 0:
            print("  reading data line %d" % counter)
            sys.stdout.flush()
          source_ids = [int(x) for x in source.split()]
          target_ids = [int(x) for x in target.split()]
          label_ids = [int(x) for x in label.split()]
#          target_ids.append(data_utils.EOS_ID)
          for bucket_id, (source_size, target_size) in enumerate(_buckets):
            if len(source_ids) < source_size and len(target_ids) < target_size:
              data_set[bucket_id].append([source_ids, target_ids, label_ids])
              break
          source, target, label = source_file.readline(), target_file.readline(), label_file.readline()
  return data_set # 3 outputs in each unit: source_ids, target_ids, label_ids

def create_model(session, source_vocab_size, target_vocab_size, label_vocab_size):
  """Create model and initialize or load parameters in session."""
  with tf.variable_scope("model", reuse=None):
    model_train = multi_task_model.MultiTaskModel(
          source_vocab_size, target_vocab_size, label_vocab_size, _buckets,
          FLAGS.word_embedding_size, FLAGS.size, FLAGS.num_layers, FLAGS.max_gradient_norm, FLAGS.batch_size,
          dropout_keep_prob=FLAGS.dropout_keep_prob, use_lstm=True,
          forward_only=False,
          use_attention=FLAGS.use_attention,
          bidirectional_rnn=FLAGS.bidirectional_rnn,
          task=task)
  with tf.variable_scope("model", reuse=True):
    model_test = multi_task_model.MultiTaskModel(
          source_vocab_size, target_vocab_size, label_vocab_size, _buckets,
          FLAGS.word_embedding_size, FLAGS.size, FLAGS.num_layers, FLAGS.max_gradient_norm, FLAGS.batch_size,
          dropout_keep_prob=FLAGS.dropout_keep_prob, use_lstm=True,
          forward_only=True,
          use_attention=FLAGS.use_attention,
          bidirectional_rnn=FLAGS.bidirectional_rnn,
          task=task)

  ckpt = tf.train.get_checkpoint_state(FLAGS.train_dir)
  if ckpt:
    print("Reading model parameters from %s" % ckpt.model_checkpoint_path)
    model_train.saver.restore(session, ckpt.model_checkpoint_path)
  else:
    print("Created model with fresh parameters.")
    session.run(tf.global_variables_initializer())
  return model_train, model_test


class test_model():
  def __init__(self,data_dir,train_dir,max_sequence_length=130,task='joint'):
    FLAGS.data_dir = data_dir
    FLAGS.train_dir = train_dir
    FLAGS.max_sequence_length = max_sequence_length
    FLAGS.task = task
    FLAGS.mode = 'test'

    print ('Applying Parameters:')
    for k,v in FLAGS.__dict__['__flags'].items():
      print ('%s: %s' % (k, str(v)))
    print("Preparing data in %s" % FLAGS.data_dir)
    vocab_path = ''
    tag_vocab_path = ''
    label_vocab_path = ''
    in_seq_train, out_seq_train, label_train, in_seq_dev, out_seq_dev, label_dev, in_seq_test, out_seq_test, label_test, vocab_path, tag_vocab_path, label_vocab_path = data_utils.prepare_multi_task_data(
      FLAGS.data_dir, FLAGS.in_vocab_size, FLAGS.out_vocab_size)

    vocab, rev_vocab = data_utils.initialize_vocabulary(vocab_path)
    self.tag_vocab, self.rev_tag_vocab = data_utils.initialize_vocabulary(tag_vocab_path)
    self.label_vocab, self.rev_label_vocab = data_utils.initialize_vocabulary(label_vocab_path)

    # vocab to unicode
    self.vocab = {}
    for w in vocab:
        self.vocab[w.decode('utf-8')] = vocab[w]
    self.rev_vocab = rev_vocab

    self.sess =  tf.Session()
    self.model, self.model_test = create_model(self.sess, len(self.vocab), len(self.tag_vocab), len(self.label_vocab))

  def softmax(self, x):
    return np.exp(x) / np.sum(np.exp(x), axis=0)

  def feed_sentence(self,sentence):
    data_set = [[]]
    token_ids = data_utils.prepare_one_data(sentence, self.vocab)
    print(token_ids) # NOTE debug

    slot_ids = [0 for i in range(len(token_ids))]
    data_set[0].append([token_ids, slot_ids, [0]])
    encoder_inputs, tags, tag_weights, sequence_length, labels = self.model_test.get_one(
        data_set, 0, 0)
    if task['joint'] == 1:
      _, step_loss, tagging_logits, classification_logits = self.model_test.joint_step(
          self.sess, encoder_inputs, tags, tag_weights, labels,
          sequence_length, 0, True)
    elif task['tagging'] == 1:
      _, step_loss, tagging_logits = self.model_test.tagging_step(
          self.sess, encoder_inputs, tags, tag_weights,
          sequence_length, 0, True)
    elif task['intent'] == 1:
      _, step_loss, classification_logits = self.model_test.classification_step(
          self.sess, encoder_inputs, labels,
          sequence_length, 0, True)

    tagging_probs = [self.softmax(tagging_logit.flatten())
                     for tagging_logit in tagging_logits[:sequence_length[0]]]
    tagging = [np.argmax(tagging_prob) for tagging_prob in tagging_probs]
    classification_probs = self.softmax(classification_logits[0])
    classification_dict = {}
    for i, c in enumerate(classification_probs):
        classification_dict[self.rev_label_vocab[i]] = c
    tagging_word = [self.rev_tag_vocab[t] for t in tagging]
    print(tagging_word)
    tag_tmp = '0'
    begin = True
    tag_dict = {}
    for i, tag in enumerate(tagging_word):
        if tag == '0' and tag_tmp == '0':
            continue
        else:
            if tag != tag_tmp:
                if begin:
                    start_i = i
                    prob_tmp = tagging_probs[i]
                    begin = False
                else:
                    key = "".join(self.rev_vocab[ids] for ids in token_ids[start_i:i])
                    geo_avg = prob_tmp ** (1/(i-start_i))
                    tag_dict[key.decode('utf-8')] = geo_avg / np.sum(geo_avg)
                    begin = True
            else:
                if i == len(tagging_word)-1:
                    key = "".join(self.rev_vocab[ids] for ids in token_ids[start_i:])
                    geo_avg = prob_tmp ** (1/(i+1-start_i))
                    tag_dict[key.decode('utf-8')] = geo_avg / np.sum(geo_avg)
                    continue
                prob_tmp *= tagging_probs[i]
        tag_tmp = tag
    return {'intent': classification_dict, 'slot': tag_dict}

def main(_):
  test = test_model(FLAGS.data_dir, FLAGS.train_dir)
  sys.stdout.write('>')
  sys.stdout.flush()
  sentence = sys.stdin.readline()
  while sentence:
    prob_dict = test.feed_sentence(sentence)
    print(prob_dict)
    '''
    slot = databaseAPI.build_slot(data_utils.naive_seg(sentence), pos)
    print(slot)
    db = databaseAPI.Database()
    db.given(slot)
    '''
    sys.stdout.write('>')
    sys.stdout.flush()
    sentence = sys.stdin.readline()


if __name__ == "__main__":
  tf.app.run()


