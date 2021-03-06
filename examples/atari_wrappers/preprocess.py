
import gym
import numpy as np
from PIL import Image


'''
Atari gaming screen preprocessor
'''
class Preprocessor(gym.Wrapper):
    """
    A wrapper for frame preprocessing.
    Will convert input image to grayscale and resize to 'shape'.
    """

    metadata = {'render.modes': ['human', 'wrapped', 'rgb_array']}

    '''
    Arguments for the constructor:
        env:    Game environment to be preprocessed.
        shape:  Tuple of 2 integers (height, width).
    '''
    def __init__(self, env, shape=(84, 84)):
        super().__init__(env)
        assert(isinstance(env.observation_space, gym.spaces.Box))
        assert(len(env.observation_space.shape) == 3)
        self.observation_space = gym.spaces.Box(low=0, high=255, shape=shape,
                                                dtype=np.uint8)
        self.viewer = None
        height, width = shape
        self.resize = width, height

    def step(self, action):
        obs, reward, done, info = self.env.step(action)
        self.preprocessed_obs = self.preprocess(obs)
        return self.preprocessed_obs, reward, done, info

    def reset(self):
        self.preprocessed_obs = self.preprocess(self.env.reset())
        return self.preprocessed_obs

    def render(self, mode='human'):
        if mode == 'rgb_array':
            return self.preprocessed_obs
        elif mode == 'human':
            self.env.render(mode='human')
        elif mode == 'wrapped':
            from gym.envs.classic_control import rendering
            if self.viewer is None:
                self.viewer = rendering.SimpleImageViewer()
            img = np.stack([self.preprocessed_obs] * 3, axis=-1)
            self.viewer.imshow(img)

    def close(self):
        self.unwrapped.close()
        if self.viewer is not None:
            self.viewer.close()
            self.viewer = None

    def preprocess(self, obs):
        img = Image.fromarray(obs)
        img = img.convert('L')
        img = img.resize(self.resize)
        return np.asarray(img)


