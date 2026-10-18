"""
AI Trainer for optimizing the neural network.

This module implements the training logic for the DQN, including the
epsilon-greedy exploration strategy, experience replay, and mixed precision
training for performance optimization.
"""
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from typing import Optional
from config.constants import (
    BATCH_SIZE, GAMMA, EPS_START, EPS_END, EPS_DECAY,
    LR, device, Transition
)


class Trainer:
    """
    Handles training of the DQN network using experience replay and epsilon-greedy policy.
    
    This trainer implements the core DQN algorithm:
    1. Epsilon-greedy action selection (exploration vs exploitation)
    2. Experience replay from memory buffer
    3. Target network for stable Q-value estimation
    4. Mixed precision training for GPU performance
    
    Args:
        policy_net (DQN): The main network being trained
        target_net (DQN): The target network for stable Q-value computation
        memory (ReplayMemory): Experience replay buffer
    """
    def __init__(self, policy_net, target_net, memory) -> None:
        self.policy_net = policy_net
        self.target_net = target_net
        self.memory = memory
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=LR)
        self.scaler = torch.amp.GradScaler('cuda')  # Mixed precision for faster training
        self.steps_done = 0  # Total training steps (used for epsilon decay)

    def get_epsilon(self) -> float:
        """
        Calculate current epsilon for epsilon-greedy policy.
        
        Epsilon decays exponentially from EPS_START to EPS_END over EPS_DECAY steps.
        Higher epsilon means more random exploration, lower means more exploitation
        of learned policy.
        
        Returns:
            float: Current epsilon value in range [EPS_END, EPS_START]
        """
        return self.get_epsilon_at_step(self.steps_done)

    def get_epsilon_at_step(self, steps: int) -> float:
        """
        Calculate epsilon at a specific step count.
        
        Args:
            steps (int): The number of steps to calculate epsilon for.
            
        Returns:
            float: Epsilon value at the given step.
        """
        eps_threshold = EPS_END + (EPS_START - EPS_END) * \
            np.exp(-1. * steps / EPS_DECAY)
        return eps_threshold

    def optimize_model(self) -> Optional[float]:
        """
        Perform one step of optimization on the policy network.
        
        This implements the core DQN training update:
        1. Sample a random batch from replay memory
        2. Compute current Q-values from policy network
        3. Compute target Q-values using target network
        4. Calculate loss and backpropagate
        5. Clip gradients to prevent instability
        
        Uses mixed precision training (AMP) for improved GPU performance.
        
        Returns:
            Optional[float]: Loss value if training occurred, None if not enough samples
        """
        # Wait until we have enough samples
        if len(self.memory) < BATCH_SIZE:
            return None
        
        # Sample random batch from memory
        transitions = self.memory.sample(BATCH_SIZE)
        batch = Transition(*zip(*transitions))
        
        # Identify non-terminal states (where next_state exists)
        non_final_mask = torch.tensor(
            tuple(map(lambda s: s is not None, batch.next_state)), 
            device=device, 
            dtype=torch.bool
        )
        non_final_next_states = torch.cat([s for s in batch.next_state if s is not None])
        
        # Prepare batch tensors
        state_batch = torch.cat(batch.state)
        action_batch = torch.cat(batch.action)
        reward_batch = torch.cat(batch.reward)
        
        # Mixed Precision Training for faster computation
        with torch.amp.autocast('cuda'):
            # Compute Q(s_t, a) - the Q-value of the action taken
            # Policy net returns (q_values, hidden_state), we only need q_values here
            q_values, _ = self.policy_net(state_batch)
            state_action_values = q_values.gather(1, action_batch)
            
            # Compute V(s_{t+1}) for all next states using target network
            next_state_values = torch.zeros(BATCH_SIZE, device=device)
            # Target net also returns (q_values, hidden_state)
            target_q_values, _ = self.target_net(non_final_next_states)
            next_state_values[non_final_mask] = target_q_values.max(1)[0].detach().to(dtype=next_state_values.dtype)
            
            # Compute expected Q-value: reward + gamma * max_a Q(s_{t+1}, a)
            expected_state_action_values = (next_state_values * GAMMA) + reward_batch
            
            # Compute Huber loss (less sensitive to outliers than MSE)
            criterion = nn.SmoothL1Loss()
            loss = criterion(state_action_values, expected_state_action_values.unsqueeze(1))
        
        # Optimize the model
        self.optimizer.zero_grad()
        self.scaler.scale(loss).backward()
        self.scaler.unscale_(self.optimizer)
        
        # Gradient clipping to prevent exploding gradients
        for param in self.policy_net.parameters():
            param.grad.data.clamp_(-1, 1)
            
        self.scaler.step(self.optimizer)
        self.scaler.update()
        
        return loss.item()

