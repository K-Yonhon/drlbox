
import tensorflow as tf
from ..common.rlnet import RLNet


class QNet(RLNet):

    def __init__(self, model):
        self.weights = model.weights
        self.ph_state, = model.inputs
        self.tf_values, = model.outputs

    def set_loss(self, loss_function):
        tf_values = self.tf_values
        batch_size, num_actions = tf_values.shape
        ph_target = tf.placeholder(tf.float32, [batch_size, num_actions])
        ph_weight = tf.placeholder(tf.float32, [batch_size])
        weight_tile = tf.tile(tf.expand_dims(ph_weight, 1), [1, num_actions])
        weighted_ph_target = weight_tile * ph_target
        weighted_tf_values = weight_tile * tf_values
        self.tf_loss = loss_function(weighted_ph_target, weighted_tf_values)
        self.ph_target = ph_target
        self.ph_sample_weight = ph_weight

    def action_values(self, state):
        return self.sess.run(self.tf_values, feed_dict={self.ph_state: state})

    def train_on_batch(self, state, target, sample_weight=None):
        if sample_weight is None:
            sample_weight = [1.0] * len(state)
        feed_dict = {self.ph_state:         state,
                     self.ph_target:        target,
                     self.ph_sample_weight: sample_weight}
        self.sess.run(self.op_train, feed_dict=feed_dict)

