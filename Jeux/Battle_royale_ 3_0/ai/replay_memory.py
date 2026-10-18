"""
Replay Memory for storing and sampling agent experiences.

Experience replay is a key technique in DQN training that breaks temporal
correlations in the training data by storing past experiences and sampling
random mini-batches for training.
"""
import random
from collections import deque
from typing import List
from config.constants import Transition


class ReplayMemory:
    """
    Fixed-size buffer to store experience tuples (state, action, reward, next_state).
    
    This circular buffer stores the agent's experiences and allows random sampling
    for training. When the buffer is full, old experiences are automatically discarded.
    
    Args:
        capacity (int): Maximum number of transitions to store
    """
    def __init__(self, capacity: int) -> None:
        self.memory: deque = deque(maxlen=capacity)

    def push(self, *args) -> None:
        """
        Save a transition to memory.
        
        Args:
            *args: Components of a Transition (state, action, reward, next_state)
        """
        self.memory.append(Transition(*args))

    def sample(self, batch_size: int) -> List[Transition]:
        """
        Sample a random batch of transitions for training.
        
        Args:
            batch_size (int): Number of transitions to sample
        
        Returns:
            List[Transition]: Random sample of transitions
        """
        return random.sample(self.memory, batch_size)

    def __len__(self) -> int:
        """Return the current size of the memory buffer."""
        return len(self.memory)

