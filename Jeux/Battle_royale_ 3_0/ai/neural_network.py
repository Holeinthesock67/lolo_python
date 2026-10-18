"""
Deep Q-Network (DQN) neural network for Arena of Life AI.

This module implements a Deep Q-Network used for reinforcement learning
in the Arena of Life game. The network takes the agent's state (visual field
and internal stats) and outputs Q-values for each possible action.
"""
import torch
import torch.nn as nn


class DQN(nn.Module):
    """
    Recurrent Q-Network (DRQN-like) with LSTM and Season Awareness.
    
    Architecture:
        - Input: State vector (Vision + Stats + Season + Time)
        - Feature Extractor: Linear layer with ReLU
        - Memory Core: LSTM layer to maintain temporal state
        - Action Head: Linear layers to map LSTM output to Q-values
    
    This architecture allows the agent to:
    1. Adapt strategies based on the current Season (Season inputs)
    2. Manage time pressure (Time input)
    3. Remember short-term history (LSTM memory) for tracking/fleeing
    
    Args:
        input_size (int): Dimension of state vector (62)
        output_size (int): Number of actions (6)
    """
    def __init__(self, input_size: int, output_size: int) -> None:
        super(DQN, self).__init__()
        self.hidden_size = 256
        
        # Feature Extractor
        self.fc1 = nn.Linear(input_size, self.hidden_size)
        
        # Recurrent Layer (Memory)
        self.lstm = nn.LSTM(self.hidden_size, self.hidden_size, batch_first=True)
        
        # Action Head
        self.fc2 = nn.Linear(self.hidden_size, self.hidden_size)
        self.fc3 = nn.Linear(self.hidden_size, output_size)

    def forward(self, x: torch.Tensor, hidden: tuple = None) -> tuple:
        """
        Forward pass through the network.
        
        Args:
            x (torch.Tensor): Input state (batch_size, seq_len, input_size) or (batch_size, input_size)
            hidden (tuple): Previous hidden state (h_0, c_0)
        
        Returns:
            q_values (torch.Tensor): Action values
            hidden (tuple): New hidden state
        """
        # Handle input shape: if (batch, input_size), add seq_len dim -> (batch, 1, input_size)
        if x.dim() == 2:
            x = x.unsqueeze(1)
            
        # Feature Extraction
        x = torch.relu(self.fc1(x))
        
        # LSTM Memory
        # If hidden is None, it defaults to zeros
        lstm_out, new_hidden = self.lstm(x, hidden)
        
        # We take the output of the last time step
        x = lstm_out[:, -1, :]
        
        # Action Head
        x = torch.relu(self.fc2(x))
        q_values = self.fc3(x)
        
        return q_values, new_hidden

