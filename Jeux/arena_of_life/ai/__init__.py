"""
AI package for Arena of Life.
"""
from .neural_network import MultiHeadDQN as DQN
from .replay_memory import ReplayMemory
from .trainer import Trainer

__all__ = ['DQN', 'ReplayMemory', 'Trainer']
