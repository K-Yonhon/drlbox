
import numpy as np
import tensorflow as tf
from drlbox.net import ACERNet
from drlbox.common.util import softmax_with_minprob
from drlbox.common.policy import SoftmaxPolicy
from .a3c_trainer import A3CTrainer


ACER_KWARGS = dict(
    acer_kl_weight=1e-1,
    acer_trunc_max=10.0,
    acer_soft_update_ratio=0.05,
    replay_type='uniform',
    )

class ACERTrainer(A3CTrainer):

    KWARGS = {**A3CTrainer.KWARGS, **ACER_KWARGS}
    net_cls = ACERNet
    softmax_minprob = 1e-6
    retrace_max = 1.0

    def setup_algorithm(self):
        super().setup_algorithm()
        assert self.action_mode == 'discrete'
        self.loss_kwargs = dict(entropy_weight=self.a3c_entropy_weight,
                                kl_weight=self.acer_kl_weight,
                                trunc_max=self.acer_trunc_max,
                                policy_type='softmax')
        self.model_kwargs['size_value'] = self.action_dim
        self.policy = SoftmaxPolicy()

    def setup_nets(self, worker_dev, rep_dev, env):
        super().setup_nets(worker_dev, rep_dev, env)
        with tf.device(rep_dev):
            self.average_net = self.build_net(env)
            self.average_net.set_sync_weights(self.global_net.weights)
            self.average_net.set_soft_update(self.global_net.weights,
                                             self.acer_soft_update_ratio)

    def set_session(self, sess):
        super().set_session(sess)
        self.average_net.set_session(sess)
        self.average_net.sync()

    def train_on_batch(self, batch):
        batch_loss = super().train_on_batch(batch)
        self.average_net.soft_update()
        return batch_loss

    def concat_bootstrap(self, cc_state, rl_slice):
        cc_logits, cc_boot_value = self.online_net.ac_values(cc_state)
        cc_avg_logits = self.average_net.action_values(cc_state)
        return cc_logits, cc_boot_value, cc_avg_logits

    def rollout_feed(self, rollout, r_logits, r_boot_value, r_avg_logits):
        r_action = np.array(rollout.action_list)

        # off-policy probabilities, length n
        r_off_logits = np.array(rollout.act_val_list)
        r_off_probs = softmax_with_minprob(r_off_logits, self.softmax_minprob)

        # on-policy probabilities and values, length n+1
        r_probs = softmax_with_minprob(r_logits, self.softmax_minprob)

        # likelihood ratio and retrace, length n
        r_lratio = r_probs[:-1] / r_off_probs
        r_retrace = np.minimum(self.retrace_max, r_lratio)

        # baseline, length n+1
        r_baseline = np.sum(r_probs * r_boot_value, axis=1)

        # return, length n
        reward_long = 0.0 if rollout.done else r_baseline[-1]
        r_sample_return = np.zeros(len(rollout))
        for idx in reversed(range(len(rollout))):
            reward_long *= self.discount
            reward_long += rollout.reward_list[idx]
            r_sample_return[idx] = reward_long
            act = r_action[idx]
            val = r_boot_value[idx, act]
            retrace = r_retrace[idx, act]
            reward_long = retrace * (reward_long - val) + r_baseline[idx]

        # logits from the average net, length n
        return (r_action, r_lratio, r_sample_return, r_boot_value[:-1],
                r_baseline[:-1], r_avg_logits[:-1])


