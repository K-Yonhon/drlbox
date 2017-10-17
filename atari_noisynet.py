
import tensorflow.contrib.keras.api.keras.layers as kl
import tensorflow.contrib.keras.api.keras.activations as ka
from tensorflow.contrib.keras.api.keras import backend as K
import tensorflow.contrib.keras.api.keras.initializers as ki
from tensorflow.contrib.keras.api.keras.models import Model
from tensorflow.contrib.keras.python.keras.engine.topology import Layer


'''
Note: NoisyNet currently supports only fully connected net

Input arguments:
    input_shape: Tuple of the format (height, width, num_frames);
    num_actions: Number of actions in the environment; integer;
    net_size:    Number of neurons in the first non-convolutional layer.
'''
def atari_acnet(input_shape, num_actions, net_size):
    state, feature = _atari_state_feature(input_shape)
    hid = NoisyDense(net_size, activation='relu')(feature)
    near_zeros = ki.RandomNormal(stddev=1e-3)
    logits = NoisyDense(num_actions, kernel_initializer=near_zeros)(hid)
    value = NoisyDense(1)(hid)

    # build model
    return Model(inputs=state, outputs=[value, logits])


def _atari_state_feature(input_shape):
    # input state
    state = kl.Input(shape=input_shape)

    # convolutional layers
    conv1_32 = kl.Conv2D(32, (8, 8), strides=(4, 4), activation='relu')
    conv2_64 = kl.Conv2D(64, (4, 4), strides=(2, 2), activation='relu')
    conv3_64 = kl.Conv2D(64, (3, 3), strides=(1, 1), activation='relu')

    # extract features with convolutional layers
    conv1 = conv1_32(state)
    conv2 = conv2_64(conv1)
    convf = conv3_64(conv2)
    feature = kl.Flatten()(convf)

    return state, feature


class NoisyDense(Layer):

    def __init__(self, output_dim, activation=None,
                 kernel_initializer='glorot_uniform', bias_initializer='zeros',
                 **kwargs):
        self.output_dim = output_dim
        self.activation = ka.get(activation)
        self.kernel_initializer = ki.get(kernel_initializer)
        self.bias_initializer = ki.get(bias_initializer)
        super().__init__(**kwargs)

    def build(self, input_shape):
        # Create a trainable weight variable for this layer.
        kernel_shape = int(input_shape[1]), self.output_dim
        bias_shape = self.output_dim,
        self.kernel = self.add_weight(name='kernel',
                                      shape=kernel_shape,
                                      initializer=self.kernel_initializer,
                                      trainable=True)
        self.bias = self.add_weight(name='bias',
                                    shape=bias_shape,
                                    initializer=self.bias_initializer,
                                    trainable=True)
        self.scale_k = self.add_weight(name='noise_k',
                                       shape=kernel_shape,
                                       initializer=ki.Constant(value=0.017),
                                       trainable=True)
        self.scale_b = self.add_weight(name='noise_b',
                                       shape=bias_shape,
                                       initializer=ki.Constant(value=0.017),
                                       trainable=True)
        self.noise_k = K.random_normal(kernel_shape, mean=0.0, stddev=1.0)
        self.noise_b = K.random_normal(bias_shape, mean=0.0, stddev=1.0)
        self.noisynet_kernel = self.kernel + self.scale_k * self.noise_k
        self.noisynet_bias = self.bias + self.scale_b * self.noise_b
        super().build(input_shape)  # Be sure to call this somewhere!

    def call(self, x):
        output = K.dot(x, self.noisynet_kernel)
        output = K.bias_add(output, self.noisynet_bias)
        output = self.activation(output)
        return output

    def compute_output_shape(self, input_shape):
        return (input_shape[0], self.output_dim)


import numpy as np

state = np.ones([1, 80, 60, 4])
num_actions = 6
net_size = 256

model = atari_acnet(state.shape[1:], num_actions, net_size)
model.summary()
