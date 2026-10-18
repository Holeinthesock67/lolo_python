"""
Agent entity for Arena of Life game.

This module defines the Agent class which represents a player in the arena.
Each agent has unique stats, inventory, and uses AI to make decisions.
"""
import torch
import numpy as np
import random
from typing import Optional, Dict
from config.constants import (
    VISION_RANGE, WEAPON_FISTS, WEAPON_SWORD, WEAPON_BOW, WEAPON_WAND,
    ROLE_WARRIOR, ROLE_SCOUT, ROLE_HEALER, NUM_ROLES,
    device
)


class Agent:
    """
    Represents an agent in the arena with stats, inventory, and AI state.
    
    Each agent is initialized with random stats and equipment, creating
    diverse strategies. The agent's state (vision + internal stats) is
    used by the DQN to make decisions.
    
    Attributes:
        id (int): Unique identifier
        x, y (int): Grid position
        color (tuple): RGB color for visual identification
        hp, max_hp (int): Current and maximum health
        stamina (int): Energy for actions
        armor (int): Damage reduction
        strength, precision, magic (int): Combat stats
        wood, iron, arrows (int): Inventory items
        weapon (int): Current weapon type
        alive (bool): Whether agent is still in the game
        steps_alive (int): Survival time
        kills (int): Total kills
        kills_by_type (dict): Kills per weapon type
    
    Args:
        id (int): Unique identifier
        x (int): Initial X position
        y (int): Initial Y position
        brain_net (Optional): Neural network (unused, kept for compatibility)
    """
    def __init__(self, id: int, x: int, y: int, brain_net=None) -> None:
        self.id = id
        self.x = x
        self.y = y
        # Role Assignment & Specialization
        self.role = random.randint(0, NUM_ROLES - 1)
        
        # Base Stats
        self.max_hp = 100
        self.stamina = 100
        self.strength = 10
        self.precision = 10
        self.magic = 10
        self.armor = 0
        
        # Apply Role Modifiers
        if self.role == ROLE_WARRIOR:
            self.max_hp = 160 # Buffed from 150
            self.strength = 20
            self.armor = 40  # Massive buff from 15 (Tank role)
            self.color = (50, 100, 255)  # Blue
            self.weapon = WEAPON_SWORD
        elif self.role == ROLE_SCOUT:
            self.max_hp = 130 # Buffed from 120 (Survival Boost)
            self.stamina = 150  # Balanced (was 200, too much)
            self.precision = 20
            self.color = (255, 255, 50)  # Yellow
            self.weapon = WEAPON_BOW
        elif self.role == ROLE_HEALER:
            self.magic = 15  # Support role, not DPS (was 25)
            self.max_hp = 115 # Buffed from 100 (Survival Boost)

            self.color = (50, 255, 50)  # Green
            self.weapon = WEAPON_WAND
        else:
            self.weapon = WEAPON_FISTS  # Fallback
            
        # Initialize HP and Resources
        self.hp = self.max_hp
        self.wood = 0
        self.iron = 0
        self.arrows = 0
            
        self.alive = True
        self.steps_alive = 0
        self.kills = 0
        self.kills_by_type = {
            WEAPON_FISTS: 0,
            WEAPON_SWORD: 0,
            WEAPON_BOW: 0,
            WEAPON_WAND: 0
        }
        self.total_reward = 0.0  # Track total accumulated rewards
        
        # LSTM Hidden State (h_0, c_0)
        # Initialized to None, will be created by network on first pass

        self.hidden_state = None
        
        # Inspection Data
        self.last_q_values = None  # Stores Q-values from last decision
        
        # Specific Reward Tracking (New)
        self.reward_healing = 0.0
        self.reward_combat = 0.0
        self.reward_resource = 0.0
        self.reward_shout = 0.0
        
        self.shout_cooldown = 0
        
    def get_internal_state_numpy(self) -> np.ndarray:
        """
        Get agent's internal stats (without view) as normalized numpy array.
        
        This returns the agent's internal state (HP, stamina, weapon, inventory, stats)
        normalized to [0, 1] range for better neural network training.
        
        Returns:
            np.ndarray: Array of 8 normalized values representing agent state
        """
        stats = np.array([
            self.hp / 100.0,
            self.stamina / 100.0,
            self.weapon / 3.0, # Normalize weapon type (0-3)
            min(self.wood, 10) / 10.0,
            min(self.iron, 10) / 10.0,
            self.strength / 20.0,
            self.precision / 20.0,
            self.magic / 20.0
        ])
        return stats

    def get_state_numpy(self, env, season_idx: int = 0, time_remaining: float = 1.0, view_override: np.ndarray = None, **kwargs) -> np.ndarray:
        """
        Get agent's complete state as a numpy array for AI input.
        
        Combines:
        1. Visual field (49)
        2. Internal stats (8)
        3. Season One-Hot (4)
        4. Time Remaining (1)
        
        Total Size: 62
        
        Args:
            env (Environment): The game environment
            season_idx (int): Index of current season (0=Spring, 1=Summer, etc.)
            time_remaining (float): Normalized time remaining in generation (0.0-1.0)
            view_override (np.ndarray, optional): Pre-computed view to avoid recalculation
        
        Returns:
            np.ndarray: Complete state vector (62,)
        """
        # 1. Vision (49)
        if view_override is not None:
            view = view_override
        else:
            view = env.get_view(self.x, self.y, VISION_RANGE)
            
        view = view / 7.0  # Normalize by max tile ID (7)
        
        # 2. Stats (8)
        stats = self.get_internal_state_numpy()
        
        # 3. Season One-Hot (4)
        season_one_hot = np.zeros(4)
        season_one_hot[season_idx] = 1.0
        
        # 4. Time Remaining (1)
        time_arr = np.array([time_remaining])
        
        # 5. Role One-Hot (3)
        role_one_hot = np.zeros(NUM_ROLES)
        role_one_hot[self.role] = 1.0
        
        # 6. Signals (6)
        # Passed as argument or defaults to zeros
        if 'signals' in kwargs:
            signal_vec = kwargs['signals']
        else:
            signal_vec = np.zeros(6)
            
        return np.concatenate((view, stats, season_one_hot, time_arr, role_one_hot, signal_vec))

    def get_state_tensor(self, env, season_idx: int = 0, time_remaining: float = 1.0) -> torch.Tensor:
        """
        Get agent's state as a PyTorch tensor (legacy version).
        
        Args:
            env (Environment): The game environment
            season_idx (int): Index of current season
            time_remaining (float): Normalized time remaining
        
        Returns:
            torch.Tensor: State tensor of shape (1, INPUT_SIZE) on correct device
        """
        state = self.get_state_numpy(env, season_idx, time_remaining)
        return torch.FloatTensor(state).unsqueeze(0).to(device)

    def take_damage(self, amount: float) -> bool:
        """
        Apply damage to agent, accounting for armor.
        Returns True if agent died, False otherwise.
        """
        damage = max(0, amount - self.armor)
        self.armor = max(0, self.armor - amount)
        self.hp -= damage
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def craft(self) -> bool:
        """
        Attempt to craft items (arrows for bow, armor from iron).
        Returns True if something was crafted, False otherwise.
        """
        crafted = False
        if self.weapon == WEAPON_BOW and self.wood >= 3:
            self.wood -= 3
            self.arrows += 5
            crafted = True
        if self.iron >= 3:
            self.iron -= 3
            self.armor += 10
            crafted = True
        return crafted
