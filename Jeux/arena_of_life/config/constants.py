"""
Configuration and constants for Arena of Life game.

This file centralizes all game configuration including display settings,
colors, tile types, agent parameters, and AI hyperparameters.
"""
import torch
from collections import namedtuple

# ==========================================
# DISPLAY SETTINGS
# ==========================================
GRID_SIZE = 100
CELL_SIZE = 12       # Reverted to 12 to fit screen
GRID_PIXEL_SIZE = GRID_SIZE * CELL_SIZE # 1200
UI_WIDTH = 900
WINDOW_WIDTH = GRID_PIXEL_SIZE + UI_WIDTH
WINDOW_HEIGHT = 1200 # Reverted to match grid size
GRID_OFFSET_Y = 0 # Aligned to top
FPS = 60

# ==========================================
# COLORS
# ==========================================
COLOR_BG = (0, 0, 0)        # Empty
COLOR_WALL = (50, 50, 50)   # Wall
COLOR_WOOD = (34, 139, 34)  # Wood (Forest Green)
COLOR_IRON = (192, 192, 192)# Iron (Silver)
COLOR_POTION_HEALTH = (255, 0, 0)   # Red
COLOR_POTION_ENERGY = (0, 0, 255)   # Blue
COLOR_POTION_MAGIC = (128, 0, 128)  # Purple
COLOR_GRID = (20, 20, 20)
COLOR_UI_BG = (30, 30, 30)
COLOR_TEXT = (200, 200, 200)
COLOR_BTN = (60, 60, 60)
COLOR_BTN_HOVER = (80, 80, 80)

# ==========================================
# TILE TYPES
# ==========================================
TILE_EMPTY = 0
TILE_WALL = 1
TILE_WOOD = 2
TILE_IRON = 3
TILE_POTION_HEALTH = 4
TILE_POTION_ENERGY = 5
TILE_POTION_MAGIC = 6
TILE_PREDATOR = 7  # Predators visible to agents

# ==========================================
# AGENT SETTINGS
# ==========================================
VISION_RANGE = 3  # Radius (3 means 7x7 grid: center + 3 left + 3 right)
VISION_SIZE = 2 * VISION_RANGE + 1 # 7
# Input: 7x7 view + HP, Stamina, WeaponType, Wood, Iron, Strength, Precision, Magic
# + 4 Season One-Hot + 1 Time Remaining + 3 Role One-Hot
# + 6 Signal Inputs (3 types * 2 vector components)
INPUT_SIZE = (VISION_SIZE * VISION_SIZE) + 8 + 4 + 1 + 3 + 6 # 71

NUM_AGENTS = 50 # Reduced from 100 to make room for Predators

# Predators count varies by season
PREDATORS_BY_SEASON = {
    0: 10,  # Spring: Baseline
    1: 10,  # Summer: High threat + scarce resources (Reduced from 12)
    2: 12,  # Autumn: Resource rich but DANGEROUS (Buffed from 8)
    3: 8    # Winter: Survival challenge (Reduced from 12)
}

# ==========================================
# ROLES
# ==========================================
ROLE_WARRIOR = 0
ROLE_SCOUT = 1
ROLE_HEALER = 2
NUM_ROLES = 3

# ==========================================
# ACTIONS
# ==========================================
ACTION_UP = 0
ACTION_DOWN = 1
ACTION_LEFT = 2
ACTION_RIGHT = 3
ACTION_ATTACK = 4
ACTION_WAIT = 5
# New Communication Actions
ACTION_CRI_DANGER = 6
ACTION_CRI_HEAL = 7  # Call for healing
ACTION_CRI_POTION = 8

NUM_ACTIONS = 9 # Increased from 6 to 9

# ==========================================
# WEAPONS
# ==========================================
WEAPON_FISTS = 0
WEAPON_SWORD = 1
WEAPON_BOW = 2
WEAPON_WAND = 3

# ==========================================
# AI HYPERPARAMETERS
# ==========================================
# Batch size increased from 2048 to 4096 for better GPU utilization
# Larger batches smooth out training and improve convergence
BATCH_SIZE = 4096

# Discount factor for future rewards (standard value for RL)
GAMMA = 0.99

# Epsilon-greedy exploration parameters
# High initial epsilon (0.9) ensures extensive early exploration
EPS_START = 0.9
EPS_END = 0.05
# Very high decay constant calibrated for 30-hour exploration phase
# At 300 Gen/h: 30 hours = 9000 gens = ~9M steps.
# To reach epsilon ~0.10 at 9M steps, we need a faster decay.
# EPS_DECAY = 3,500,000 ensures epsilon drops to 0.10 in about 30 hours.
EPS_DECAY = 3500000  # Adjusted for 30-hour target at ~300 Gen/h

# Target network update frequency (in steps)
# Less frequent updates allow policy net to learn more before synchronization
# This improves stability and reduces oscillations in Q-values
TARGET_UPDATE = 1000

# Learning rate for Adam optimizer
LR = 1.4e-4

# Replay memory capacity
MEMORY_SIZE = 1000000

# Train every N steps - adaptive based on render mode
# UI mode: Less frequent training to maintain smooth FPS
TRAIN_FREQUENCY = 8
# Turbo mode: More frequent training for faster learning
TRAIN_FREQUENCY_TURBO = 4

# ==========================================
# DEVICE & DATA STRUCTURES
# ==========================================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

Transition = namedtuple('Transition', ('state', 'action', 'reward', 'next_state'))

# ==========================================
# GAMEPLAY BALANCING
# ==========================================
POTION_HEAL_AMOUNT = 30      # HP restored by Red Potion
POTION_STAMINA_AMOUNT = 30   # Stamina restored by Blue Potion
POTION_MAGIC_AMOUNT = 2      # Magic Power gained by Purple Potion (Buffed from 1)
SWORD_DAMAGE_BASE = 24       # Base damage for Sword (Buffed from 18, 2-shot kill potential)
HEALER_PASSIVE_BASE_HEAL = 12 # Base HP restored by Healer passive (Buffed from 8)

# ==========================================
# COMMUNICATION
# ==========================================
COMM_AUDIBLE_RANGE = 45      # Max distance to hear a shout (Tiles) - TRIPLED (was 15)
REWARD_SHOUT_SUCCESS = 20.0   # Reward for useful, heard communication (DOUBLED from 10.0)
REWARD_SHOUT_FAIL = -0.05    # Penalty for useless/wrong context shout
REWARD_SHOUT_ISOLATED = -0.1 # Penalty for shouting to no one

# ==========================================
# SEASONS SYSTEM
# ==========================================
# Season names
SEASON_SPRING = "Spring"
SEASON_SUMMER = "Summer"
SEASON_AUTUMN = "Autumn"
SEASON_WINTER = "Winter"

# Hybrid cycle parameters
MIN_GENS_PER_SEASON = 100   # Minimum generations before season change
MAX_GENS_PER_SEASON = 500   # Force change if not converged
CONVERGENCE_WINDOW = 100    # Number of recent generations to check
CONVERGENCE_THRESHOLD = 0.10  # CV must be < 10% to converge

# Season parameter presets (wood_regrowth, potion_spawn, gen_timeout)
SEASON_PRESETS = {
    SEASON_SPRING: {
        'wood_regrowth': 0.015,  # Scarce (Halved from 0.025)
        'potion_spawn': 0.00005,
        'gen_timeout': 1500,
        'color': (100, 255, 100),  # Green
        'icon': '🌿'
    },
    SEASON_SUMMER: {
        'wood_regrowth': 0.015,  # Scarce
        'potion_spawn': 0.00003,  # Very rare
        'gen_timeout': 1200,
        'color': (255, 200, 50),  # Yellow-Orange
        'icon': '🔥'
    },
    SEASON_AUTUMN: {
        'wood_regrowth': 0.016,  # NERFED (was 0.020) - Closer to Spring
        'potion_spawn': 0.00006,  # NERFED (was 0.00010) - Less flooding
        'gen_timeout': 2000,
        'color': (255, 150, 50),  # Orange
        'icon': '🍂'
    },
    SEASON_WINTER: {
        'wood_regrowth': 0.010,  # Scarce but viable (was 0.005)
        'potion_spawn': 0.00001,  # Almost none
        'gen_timeout': 800,  # Short time - survival mode
        'color': (150, 200, 255),  # Icy Blue
        'icon': '❄️'
    }
}

SEASON_CYCLE = [SEASON_SPRING, SEASON_SUMMER, SEASON_AUTUMN, SEASON_WINTER]
