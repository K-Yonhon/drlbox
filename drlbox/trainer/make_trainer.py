
from .a3c_trainer import A3CTrainer
from .acktr_trainer import ACKTRTrainer
from .acer_trainer import ACERTrainer
from .dqn_trainer import DQNTrainer
from .noisynet_a3c_trainer import NoisyNetA3CTrainer
from .noisynet_acer_trainer import NoisyNetACERTrainer
from .noisynet_dqn_trainer import NoisyNetDQNTrainer


TRAINER_CLS_DICT = {'a3c':              A3CTrainer,
                    'acktr':            ACKTRTrainer,
                    'acer':             ACERTrainer,
                    'noisynet-a3c':     NoisyNetA3CTrainer,
                    'noisynet-acer':    NoisyNetACERTrainer,
                    'dqn':              DQNTrainer,
                    'noisynet-dqn':     NoisyNetDQNTrainer,}

def make_trainer(algorithm, **kwargs):
    algorithm = algorithm.lower()
    if algorithm not in TRAINER_CLS_DICT:
        raise ValueError('Algorithm "{}" not valid'.format(algorithm))
    return TRAINER_CLS_DICT[algorithm](**kwargs)

