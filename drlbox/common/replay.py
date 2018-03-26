
import random
import pickle


FILL_PERCENT = 0.1

'''
Ring-buffer uniformly sampled replay memory.
Both 'append' and 'sample' are O(1)
'''
class Replay:

    def __init__(self, maxlen, minlen=None):
        self.maxlen = maxlen
        if minlen is None:
            self.minlen = FILL_PERCENT * self.maxlen
        else:
            self.minlen = minlen
        self.ring_buffer = [None] * self.maxlen
        self.index = 0
        self.length = 0

    def append(self, transition):
        self.ring_buffer[self.index] = transition
        self.index = (self.index + 1) % self.maxlen
        self.length = min(self.length + 1, self.maxlen)

    def extend(self, batch):
        for transition in batch:
            self.append(transition)

    def sample(self, batch_size):
        batch_idx = [random.randrange(len(self)) for _ in range(batch_size)]
        batch = [self.ring_buffer[i] for i in batch_idx]
        return batch, batch_idx, [None] * batch_size

    def __len__(self):
        return self.length

    def usable(self):
        return len(self) >= self.minlen

    def save(self, filepath):
        with open(filepath, 'wb') as save:
            pickle.dump(self, save, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def load(filepath):
        with open(filepath, 'rb') as save:
            replay = pickle.load(save)
        return replay


'''
Proportional prioritization with ring-buffer and sum-tree indexing.
'''
class PriorityReplay(Replay):

    error_eps = 1e-2

    def __init__(self, maxlen, minlen=None, evict_rule='oldest',
                 alpha=0.6, beta=0.4, beta_delta=1e-8):
        super().__init__(maxlen, minlen)
        size_sum_tree = 2 * self.maxlen - 1
        self.sum_tree = [0.0] * size_sum_tree
        self.evict_rule = evict_rule
        if evict_rule == 'sample':
            self.sum_tree_evict = [0.0] * size_sum_tree
        self.alpha = alpha
        self.beta = beta
        self.beta_delta = beta_delta
        self.max_priority = 1.0         # max priority we've ever seen so far

    def append(self, transition, error=None):
        priority = self.compute_priority(error)
        if len(self) < self.maxlen or self.evict_rule == 'oldest':
            self.update_idx(self.index, priority)
            super().append(transition)
        elif self.evict_rule == 'sample':
            _, evict_idx, _ = self.sample_sum_tree(1, self.sum_tree_evict)
            evict_idx = evict_idx[0]
            self.update_idx(evict_idx, priority)
            self.ring_buffer[evict_idx] = transition
        else:
            raise TypeError('evict rule {} invalid'.format(self.evict_rule))

    def extend(self, batch, batch_error=None):
        if batch_error is None:
            batch_error = [None] * len(batch)
        for transition, error in zip(batch, batch_error):
            self.append(transition, error)

    def sample(self, batch_size):
        batch_result = self.sample_sum_tree(batch_size, self.sum_tree)
        self.beta = min(1.0, self.beta + self.beta_delta)
        return batch_result

    def sample_sum_tree(self, batch_size, sum_tree):
        len_seg = sum_tree[0] / batch_size
        rand_list = [(random.random() + i) * len_seg for i in range(batch_size)]
        batch, batch_idx, batch_weights = [], [], []
        for rand in rand_list:
            ring_idx, priority, transition = self.get_leaf(rand, sum_tree)
            batch.append(transition)
            batch_idx.append(ring_idx)
            weight = (priority / sum_tree[0])**(-self.beta)
            batch_weights.append(weight)
        max_weight = max(batch_weights)
        batch_weights = [w / max_weight for w in batch_weights]
        return batch, batch_idx, batch_weights

    def update_priority(self, batch_idx, batch_error):
        for ring_idx, error in zip(batch_idx, batch_error):
            priority = self.compute_priority(error)
            self.update_idx(ring_idx, priority)

    def compute_priority(self, error):
        if error is None:
            return self.max_priority
        else:
            priority = abs(error) + self.error_eps
            priority **= self.alpha
            self.max_priority = max(self.max_priority, priority)
            return priority

    def get_leaf(self, value, sum_tree):
        """
        Tree structure and array storage:
        Tree index:
             0         -> storing priority sum
            / \
          1     2
         / \   / \
        3   4 5   6    -> storing priority for transitions
        Array type for storing:
        [0, 1, 2, 3, 4, 5, 6]
        """
        parent = 0
        while True:
            left = 2 * parent + 1
            right = left + 1
            if left >= len(sum_tree):  # reach bottom, end search
                leaf_idx = parent
                break
            else:
                if value <= sum_tree[left]:
                    parent = left
                else:
                    value -= sum_tree[left]
                    parent = right
        ring_idx = leaf_idx - (self.maxlen - 1)
        return ring_idx, sum_tree[leaf_idx], self.ring_buffer[ring_idx]

    def update_idx(self, ring_idx, priority):
        self.update_sum_tree(ring_idx, priority, self.sum_tree)
        if self.evict_rule == 'sample':
            self.update_sum_tree(ring_idx, 1.0 / priority, self.sum_tree_evict)

    def update_sum_tree(self, ring_idx, priority, sum_tree):
        leaf_idx = ring_idx + (self.maxlen - 1)
        change = priority - sum_tree[leaf_idx]
        sum_tree[leaf_idx] = priority
        while leaf_idx:
            leaf_idx = (leaf_idx - 1) // 2
            sum_tree[leaf_idx] += change


