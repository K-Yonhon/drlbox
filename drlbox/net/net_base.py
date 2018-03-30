
import tensorflow as tf
from drlbox.layer.noisy_dense import NoisyDenseIG, NoisyDenseFG


class RLNet:

    op_sync = None
    kfac_loss_list = []

    # net constructed by set_model only can predict but cannot be trained
    def set_model(self, model):
        raise NotImplementedError

    def set_session(self, sess):
        self.sess = sess

    def set_sync_weights(self, sync_weights):
        zip_weights = zip(self.weights, sync_weights)
        self.op_sync = tf.group(*[wt.assign(swt) for wt, swt in zip_weights])

    def set_loss(self, *args, **kwargs):
        raise NotImplementedError

    def set_optimizer(self, optimizer, clip_norm=None, train_weights=None):
        self.ph_batch_weight = tf.placeholder(tf.float32, [None])
        batch_loss = tf.reduce_sum(self.tf_loss * self.ph_batch_weight)
        grads_and_vars = optimizer.compute_gradients(batch_loss, self.weights)
        grads = [g for g, v in grads_and_vars]
        if clip_norm is not None:
            grads, _ = tf.clip_by_global_norm(grads, clip_norm)
        if train_weights is None:
            train_weights = self.weights
        op_grad = optimizer.apply_gradients(zip(grads, train_weights))
        self.op_train = [op_grad]
        self.op_result = [batch_loss, self.tf_error]
        self.op_periodic = []
        self.periodic_interval = None
        self.periodic_counter = 0

    def set_kfac(self, kfac, inv_upd_interval, train_weights=None):
        # kfac has a builtin trust-region scheme and so there is no clip_norm
        self.set_optimizer(kfac, train_weights=train_weights)
        self.op_train.append(kfac.cov_update_op)
        self.op_periodic = kfac.inv_update_op
        self.periodic_interval = inv_upd_interval

    def action_values(self, state):
        raise NotImplementedError

    def train_on_batch(self, *args, batch_weight=None):
        if batch_weight is None:
            batch_weight = [1.0] * len(args[0])     # trick to get batch size
        feed_dict = {ph: arg for ph, arg in zip(self.ph_train_list, args)}
        feed_dict[self.ph_batch_weight] = batch_weight

        # run training and loss/error separately for correct running order
        self.sess.run(self.op_train, feed_dict=feed_dict)
        loss, error = self.sess.run(self.op_result, feed_dict=feed_dict)
        if self.periodic_interval is not None:
            if self.periodic_counter >= self.periodic_interval:
                self.sess.run(self.op_periodic)
                self.periodic_counter = 0
            self.periodic_counter += 1
        return loss, error

    def state_value(self, *args, **kwargs):
        raise NotImplementedError

    def sync(self):
        self.sess.run(self.op_sync)

    def set_noise_list(self):
        self.noise_list = []
        for layer in self.model.layers:
            if type(layer) in {NoisyDenseIG, NoisyDenseFG}:
                self.noise_list.extend(layer.noise_list)

    def sample_noise(self):
        for noise in self.noise_list:
            self.sess.run(noise.initializer)

    def save_model(self, filename):
        self.model.save(filename)

