import tensorflow as tf
import random
import os
import numpy as np

class policy_network():

    def __init__(self,model_dir,action_num=10):
        self.memory = []
        self.memory_size = 1000
        self.batch_size = 64
        self.action_num = action_num
        self.model_dir = model_dir
        self.load_model = False
        if not os.path.exists(self.model_dir):
            os.mkdir(self.model_dir)

        self.__build_model()
        self.step = 0


    def __build_model(self):
        self.graph = tf.Graph()
        with self.graph.as_default() as g:
            with g.name_scope( "policy_graph" ) as scope:
                self.input_vec = tf.placeholder(dtype=tf.float32, shape=(None,10))
                self.reward = tf.placeholder(dtype=tf.float32,shape=(None))
                self.sampled_action = tf.placeholder(dtype=tf.float32,shape=(None,self.action_num))
                with tf.variable_scope("policy_linear0") as scope:
                    hidden = tf.contrib.layers.linear(self.input_vec, 50, scope=scope, activation_fn=tf.nn.relu)
                with tf.variable_scope("policy_output") as scope:
                    output = tf.contrib.layers.linear(hidden, self.action_num, scope=scope, activation_fn=tf.nn.softmax)
                self.action_distribution = output

                self.loss = tf.reduce_mean(-self.reward*tf.log(tf.reduce_max(self.sampled_action*output,axis=-1)))
                self.train_op = self.train_generator_op = tf.train.RMSPropOptimizer(0.001).minimize(self.loss)
            self.saver = tf.train.Saver(max_to_keep=2)
            self.sess = tf.Session(graph = self.graph)
            if self.load_model:
                self.saver.restore(self.sess, tf.train.latest_checkpoint(self.model_dir))
            else:
                self.sess.run(tf.global_variables_initializer())
        tf.reset_default_graph()


    def update(self,num_batch=10):
        self.step += 1
        total_loss = 0.0
        random.shuffle(self.memory)
        input_vec = [self.memory[i][0] for i in range(self.batch_size)]
        sampled_action = [self.memory[i][1] for i in range(self.batch_size)]
        reward = [self.memory[i][2] for i in range(self.batch_size)]
        feed_dict = {
            self.input_vec:np.array(input_vec),
            self.sampled_action:np.array(sampled_action),
            self.reward:np.array(reward)
        }
        loss,_ = self.sess.run([self.loss,self.train_op],feed_dict=feed_dict)
        total_loss += loss
        self.memory = []
        return total_loss/num_batch


    def get_action_distribution(self,input_vec):
        feed_dict = {self.input_vec:input_vec}
        return self.sess.run([self.action_distribution],feed_dict=feed_dict)[0]


    def add_memory(self,one_data):
        self.memory.append(one_data)



    def save_model(self):
        path = self.model_dir + 'ckeckpoint'
        self.saver.save(self.sess, path, global_step=self.step)


    def load_model(self):
        self.saver.restore(self.sess, tf.train.latest_checkpoint(self.model_dir))
