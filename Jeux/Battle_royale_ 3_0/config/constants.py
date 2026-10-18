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
CELL_SIZE = 12
GRID_PIXEL_SIZE = GRID_SIZE * CELL_SIZE # 1200
UI_WIDTH = 900
WINDOW_WIDTH = GRID_PIXEL_SIZE + UI_WIDTH
WINDOW_HEIGHT = 1200 # Reverted to match grid size
GRID_OFFSET_Y = 0 # Aligned to top
FPS = 30

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

# ==========================================
# AGENT SETTINGS
# ==========================================
VISION_RANGE = 3  # Radius (3 means 7x7 grid: center + 3 left + 3 right)
VISION_SIZE = 2 * VISION_RANGE + 1 # 7
# Input: 7x7 view + HP, Stamina, WeaponType, Wood, Iron, Strength, Precision, Magic
# + 4 Season One-Hot + 1 Time Remaining
INPUT_SIZE = (VISION_SIZE * VISION_SIZE) + 8 + 4 + 1  # 62 
NUM_ACTIONS = 6 # Up, Down, Left, Right, Attack, Wait/Craft
NUM_AGENTS = 100

# ==========================================
# ACTIONS
# ==========================================
ACTION_UP = 0
ACTION_DOWN = 1
ACTION_LEFT = 2
ACTION_RIGHT = 3
ACTION_ATTACK = 4
ACTION_WAIT = 5

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
# Very high decay constant to account for multi-agent batch processing
# With 100 agents, steps_done increments 100× faster than single-agent RL
# In turbo mode (20k steps/frame × 100 agents), we need massive decay to maintain exploration
EPS_DECAY = 500000

# Target network update frequency (in steps)
# Less frequent updates allow policy net to learn more before synchronization
# This improves stability and reduces oscillations in Q-values
TARGET_UPDATE = 200

# Learning rate for Adam optimizer
LR = 2e-4

# Replay memory capacity
MEMORY_SIZE = 50000

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
# SEASONS SYSTEM
# ==========================================
# Season names
SEASON_SPRING = "Spring"
SEASON_SUMMER = "Summer"
SEASON_AUTUMN = "Autumn"
SEASON_WINTER = "Winter"

# Hybrid cycle parameters
MIN_GENS_PER_SEASON = 50    # Minimum generations before season change
MAX_GENS_PER_SEASON = 200   # Force change if not converged
CONVERGENCE_WINDOW = 10     # Number of recent generations to check
CONVERGENCE_THRESHOLD = 0.05  # Std dev must be < 5% of mean to converge

# Season parameter presets (wood_regrowth, potion_spawn, gen_timeout)
SEASON_PRESETS = {
    SEASON_SPRING: {
        'wood_regrowth': 0.030,
        'potion_spawn': 0.00005,
        'gen_timeout': 1500,
        'color': (100, 255, 100),  # Green
        'icon': '🌿'
    },
    SEASON_SUMMER: {
        'wood_regrowth': 0.010,  # Scarce
        'potion_spawn': 0.00002,  # Very rare
        'gen_timeout': 1200,
        'color': (255, 200, 50),  # Yellow-Orange
        'icon': '🔥'
    },
    SEASON_AUTUMN: {
        'wood_regrowth': 0.050,  # Abundant
        'potion_spawn': 0.00010,  # Frequent
        'gen_timeout': 2000,
        'color': (255, 150, 50),  # Orange
        'icon': '🍂'
    },
    SEASON_WINTER: {
        'wood_regrowth': 0.005,  # Extremely scarce
        'potion_spawn': 0.00001,  # Almost none
        'gen_timeout': 800,  # Short time - survival mode
        'color': (150, 200, 255),  # Icy Blue
        'icon': '❄️'
    }
}

SEASON_CYCLE = [SEASON_SPRING, SEASON_SUMMER, SEASON_AUTUMN, SEASON_WINTER]
