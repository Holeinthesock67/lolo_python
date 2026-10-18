"""
Deep Q-Network (DQN) neural network for Arena of Life AI.

This module implements a Multi-Head Deep Q-Network used for reinforcement learning
in the Arena of Life game. The network takes the agent's state and outputs Q-values.

Architecture:
    - Shared Backbone: Linear + LSTM (processes vision, memory, stats)
    - 3 Specialized Heads: Warrior, Scout, Healer (distinct policies)
    
This allows agents to share a common understanding of the world (physics, vision)
while having completely different strategies based on their role.
"""
import torch
import torch.nn as nn
from config.constants import ROLE_WARRIOR, ROLE_SCOUT, ROLE_HEALER

class MultiHeadDQN(nn.Module):
    """
    Multi-Head Recurrent Q-Network with CNN Vision Processing.
    
    Args:
        input_size (int): Dimension of state vector (71)
        output_size (int): Number of actions
    """
    def __init__(self, input_size: int, output_size: int) -> None:
        super(MultiHeadDQN, self).__init__()
        self.hidden_size = 512
        
        # =================================================================
        # VISION PROCESSING (CNN)
        # =================================================================
        # Input: 7x7 grid (flattened to 49 in state vector)
        # We reshape it back to (1, 7, 7) image
        self.vision_conv = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),  # 7x7 -> 7x7, 16 channels
            nn.ReLU(),
            nn.Conv2d(16, 32, kernel_size=3, padding=1), # 7x7 -> 7x7, 32 channels
            nn.ReLU(),
            nn.Flatten()  # 32 * 7 * 7 = 1568
        )
        
        # Vision output size + Stats size (71 - 49 = 22)
        # 1568 + 22 = 1590
        combined_input_size = 1568 + (input_size - 49)
        
        # =================================================================
        # SHARED BACKBONE (The "Reptilian Brain")
        # =================================================================
        # Processes processed vision + stats into high-level representation
        self.feature_extractor = nn.Linear(combined_input_size, self.hidden_size)
        self.lstm = nn.LSTM(self.hidden_size, self.hidden_size, batch_first=True)
        
        # =================================================================
        # SPECIALIZED HEADS (The "Role Personalities")
        # =================================================================
        # Each head learns a different policy mapping from the same state
        # Added an extra layer (512 -> 256) for deeper reasoning
        
        # Head 0: Warrior (Aggressive, Protective)
        self.head_warrior = nn.Sequential(
            nn.Linear(self.hidden_size, self.hidden_size),
            nn.ReLU(),
            nn.Linear(self.hidden_size, 256),
            nn.ReLU(),
            nn.Linear(256, output_size)
        )
        
        # Head 1: Scout (Exploration, Resource Gathering)
        self.head_scout = nn.Sequential(
            nn.Linear(self.hidden_size, self.hidden_size),
            nn.ReLU(),
            nn.Linear(self.hidden_size, 256),
            nn.ReLU(),
            nn.Linear(256, output_size)
        )
        
        # Head 2: Healer (Support, Survival)
        self.head_healer = nn.Sequential(
            nn.Linear(self.hidden_size, self.hidden_size),
            nn.ReLU(),
            nn.Linear(self.hidden_size, 256),
            nn.ReLU(),
            nn.Linear(256, output_size)
        )

    def forward(self, x: torch.Tensor, hidden: tuple = None) -> tuple:
        """
        Forward pass with CNN vision and dynamic head selection.
        """
        # Handle input shape: if (batch, input_size), add seq_len dim -> (batch, 1, input_size)
        if x.dim() == 2:
            x = x.unsqueeze(1)
            
        batch_size, seq_len, _ = x.size()
        
        # Flatten sequence for CNN processing: (batch*seq, input_size)
        x_flat = x.view(-1, x.size(-1))
        
        # Split into Vision (first 49) and Stats (rest)
        vision_flat = x_flat[:, :49]
        stats = x_flat[:, 49:]
        
        # Reshape vision to image: (batch*seq, 1, 7, 7)
        vision_img = vision_flat.view(-1, 1, 7, 7)
        
        # 1. VISION PROCESSING
        # --------------------
        vision_features = self.vision_conv(vision_img) # (batch*seq, 1568)
        
        # Concatenate with stats
        combined_features = torch.cat([vision_features, stats], dim=1) # (batch*seq, 1590)
        
        # 2. SHARED BACKBONE
        # ------------------
        features = torch.relu(self.feature_extractor(combined_features))
        
        # Reshape back to sequence for LSTM: (batch, seq, hidden_size)
        features_seq = features.view(batch_size, seq_len, -1)
        
        lstm_out, new_hidden = self.lstm(features_seq, hidden)
        
        # We take the output of the last time step for the heads
        # Shape: (batch, hidden_size)
        core_state = lstm_out[:, -1, :]
        
        # 3. COMPUTE ALL HEADS
        # --------------------
        q_warrior = self.head_warrior(core_state) # (batch, actions)
        q_scout = self.head_scout(core_state)     # (batch, actions)
        q_healer = self.head_healer(core_state)   # (batch, actions)
        
        # 4. SELECT RELEVANT HEAD
        # -----------------------
        # Extract role from input to decide which head to use.
        # Role is at indices 62, 63, 64 of the last timestep.
        # x shape: (batch, seq, input) -> take last seq -> (batch, input)
        current_input = x[:, -1, :]
        
        # Indices for roles (Vision 49 + Stats 8 + Season 4 + Time 1 = 62)
        # Role One-Hot: [Warrior, Scout, Healer]
        role_start_idx = 62
        
        # Create a mask for each role
        # role_mask shape: (batch, 1)
        is_warrior = current_input[:, role_start_idx].unsqueeze(1)
        is_scout = current_input[:, role_start_idx + 1].unsqueeze(1)
        is_healer = current_input[:, role_start_idx + 2].unsqueeze(1)
        
        # Combine outputs: q_final = w*q_w + s*q_s + h*q_h
        # Since roles are one-hot, only one term is non-zero per agent.
        q_values = (q_warrior * is_warrior) + \
                   (q_scout * is_scout) + \
                   (q_healer * is_healer)
        
        return q_values, new_hidden
