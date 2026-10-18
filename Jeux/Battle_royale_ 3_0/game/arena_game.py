"""
Main game orchestration module for Arena of Life.

This module contains the ArenaGame class which orchestrates all game systems:
- Environment and agent management
- AI training loop (DQN with experience replay)
- UI rendering and user interaction
- Performance tracking and optimization
- State persistence (brain saving/loading)
"""
import pygame
import torch
import torch.optim as optim
import numpy as np
import random
import os
import concurrent.futures
import time
import collections

from config.constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, GRID_SIZE, GRID_PIXEL_SIZE, CELL_SIZE, UI_WIDTH,
    FPS, TILE_EMPTY, TILE_WOOD, TILE_IRON, TILE_POTION_HEALTH, TILE_POTION_ENERGY, TILE_POTION_MAGIC,
    ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_ATTACK, ACTION_WAIT,
    WEAPON_FISTS, WEAPON_SWORD, WEAPON_BOW, WEAPON_WAND,
    INPUT_SIZE, NUM_ACTIONS, MEMORY_SIZE, LR,
    BATCH_SIZE, EPS_START, EPS_END, EPS_DECAY, TARGET_UPDATE, TRAIN_FREQUENCY, TRAIN_FREQUENCY_TURBO,
    device, Transition, NUM_AGENTS, GRID_OFFSET_Y, VISION_RANGE,
    SEASON_SPRING, SEASON_SUMMER, SEASON_AUTUMN, SEASON_WINTER, SEASON_CYCLE, SEASON_PRESETS,
    MIN_GENS_PER_SEASON, MAX_GENS_PER_SEASON, CONVERGENCE_WINDOW, CONVERGENCE_THRESHOLD
)
from ai import DQN, ReplayMemory, Trainer
from environment import Environment
from entities import Agent
from ui import Slider, Button, draw_grid, draw_ui


class ArenaGame:
    """
    Main game class that orchestrates the environment, agents, AI, and UI.
    
    This class manages the entire game loop including:
    - Environment simulation (grid, resources, agents)
    - AI training (DQN with epsilon-greedy policy)
    - Rendering (grid, UI, particles)
    - State persistence (saving/loading brain and stats)
    - Performance tracking (Gen/h, epsilon decay)
    
    The game runs generations where agents compete until only one survives
    or the time limit is reached. The shared AI brain improves over time
    through reinforcement learning.
    """
    def __init__(self) -> None:
        """Initialize the game with all systems (graphics, AI, UI, environment)."""
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Arena of Life - AI Battle Royale")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 14)
        self.title_font = pygame.font.SysFont("Arial", 18, bold=True)
        
        self.env = Environment(GRID_SIZE, GRID_SIZE)
        
        # Sound & Visual Effects
        pygame.mixer.init()
        self.sounds = {}
        self.load_sounds()
        
        self.particles = [] # List of [x, y, color, radius, max_radius]
        
        self.global_kills_by_type = {
            WEAPON_FISTS: 0,
            WEAPON_SWORD: 0,
            WEAPON_BOW: 0,
            WEAPON_WAND: 0
        }
        
        self.loss_history = []
        self.reward_history = []
        self.duration_history = []
        self.kill_history = [] # Track kills per generation
        self.current_gen_kills = 0 # Track kills for current generation
        self.hall_of_fame = [] # List of top agents all-time
        
        # Action Distribution Tracking
        self.action_counts = {i: 0 for i in range(NUM_ACTIONS)}
        self.action_history = [] # List of dicts with action distributions per generation
        
        # Performance Tracking
        self.gen_timestamps = collections.deque(maxlen=10)
        self.cycles_per_hour = 0
        
        # AI Setup
        self.policy_net = DQN(INPUT_SIZE, NUM_ACTIONS).to(device)
        self.target_net = DQN(INPUT_SIZE, NUM_ACTIONS).to(device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        
        self.memory = ReplayMemory(MEMORY_SIZE)
        self.trainer = Trainer(self.policy_net, self.target_net, self.memory)
        
        self.generation = 1
        self.gen_steps = 0
        self.max_steps_per_gen = 1000
        self.agents = []
        
        # Season System - Initialize BEFORE loading brain to avoid overwriting loaded state
        self.current_season = SEASON_SPRING
        self.auto_season_mode = True  # Enable AUTO mode by default
        self.season_gens_counter = 0  # Generations spent in current season
        self.season_rewards_window = collections.deque(maxlen=CONVERGENCE_WINDOW)
        self.cycle_number = 1  # Track complete cycles (4 seasons = 1 cycle)
        self.season_cycle_rewards = []  # Accumulate avg rewards for current cycle's seasons
        self.complete_cycle_performance = []  # List of avg rewards per completed cycle
        
        self.load_brain()
        self.spawn_agents()
        
        # UI Elements
        self.slider_wood = Slider(GRID_PIXEL_SIZE + 20, 20, 200, 20, 0.0, 0.06, 0.030, "Wood Regrowth")
        self.slider_potion = Slider(GRID_PIXEL_SIZE + 20, 60, 200, 20, 0.0, 0.0002, 0.00005, "Potion Spawn")
        self.slider_timeout = Slider(GRID_PIXEL_SIZE + 20, 100, 200, 20, 100, 3000, 1500, "Gen Timeout")
        
        self.render_visuals = False # Default to OFF as requested
        # Green button if visuals are ON, default otherwise
        btn_color = (0, 200, 0) if self.render_visuals else None
        self.btn_visuals = Button(GRID_PIXEL_SIZE + 20, 140, 200, 30, "Toggle Visuals", self.toggle_visuals, color=btn_color)
        self.btn_reset_epsilon = Button(GRID_PIXEL_SIZE + 20, 175, 200, 30, "Reset Exploration", self.reset_exploration)
        self.btn_clear_hof = Button(GRID_PIXEL_SIZE + 20, 210, 200, 30, "Clear Hall of Fame", self.clear_hall_of_fame)
        
        # Season buttons (positions will be updated in rendering)
        self.btn_season_auto = Button(0, 0, 90, 25, "AUTO", self.toggle_auto_season)
        self.btn_season_spring = Button(0, 0, 90, 25, "Sp", lambda: self.set_season(SEASON_SPRING))
        self.btn_season_summer = Button(0, 0, 90, 25, "Su", lambda: self.set_season(SEASON_SUMMER))
        self.btn_season_autumn = Button(0, 0, 90, 25, "Au", lambda: self.set_season(SEASON_AUTUMN))
        self.btn_season_winter = Button(0, 0, 90, 25, "Wi", lambda: self.set_season(SEASON_WINTER))
        
        # Apply initial season (if not loaded from brain, this will apply the default Spring)
        self.apply_season(self.current_season, reset_stats=False)
        
        self.ui_update_counter = 0 # Track frames for UI updates in turbo mode
        self.selected_agent = None

    def load_sounds(self) -> None:
        """Load game sound effects"""
        try:
            # Paths relative to this file: ../assets/sounds/
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sound_dir = os.path.join(base_path, "assets", "sounds")
            
            self.sounds[WEAPON_FISTS] = pygame.mixer.Sound(os.path.join(sound_dir, "punch.wav"))
            self.sounds[WEAPON_SWORD] = pygame.mixer.Sound(os.path.join(sound_dir, "sword.wav"))
            self.sounds[WEAPON_BOW] = pygame.mixer.Sound(os.path.join(sound_dir, "bow.wav"))
            self.sounds[WEAPON_WAND] = pygame.mixer.Sound(os.path.join(sound_dir, "magic.wav"))
        except Exception as e:
            print(f"Warning: Sound files not found ({e}). Running silently.")

    def toggle_visuals(self) -> None:
        """Toggle visual rendering for turbo mode (faster training)."""
        self.render_visuals = not self.render_visuals
        # Update button color: Green if ON, None (default) if OFF
        self.btn_visuals.color = (0, 200, 0) if self.render_visuals else None
    
    def reset_exploration(self) -> None:
        """Boost exploration by reducing steps_done by 50% (progressive increase in epsilon)."""
        old_steps = self.trainer.steps_done
        self.trainer.steps_done = int(self.trainer.steps_done * 0.5)
        old_eps = EPS_END + (EPS_START - EPS_END) * np.exp(-1. * old_steps / EPS_DECAY)
        new_eps = self.trainer.get_epsilon()
        print(f"Exploration boosted! Epsilon: {old_eps:.4f} → {new_eps:.4f}")
    
    def clear_hall_of_fame(self) -> None:
        """Clear the Hall of Fame (reset all-time top agents)."""
        self.hall_of_fame = []
        print("Hall of Fame cleared!")
    
    def toggle_auto_season(self) -> None:
        """Toggle automatic season cycling."""
        self.auto_season_mode = not self.auto_season_mode
        status = "ON" if self.auto_season_mode else "OFF"
        print(f"Auto Season Mode: {status}")
    
    def set_season(self, season_name: str) -> None:
        """Manually set a specific season (disables auto mode)."""
        self.auto_season_mode = False
        if season_name != self.current_season:
            self.apply_season(season_name)
            print(f"Season manually changed to: {season_name}")
    
    def apply_season(self, season_name: str, reset_stats: bool = True) -> None:
        """Apply a season's parameters to the environment and UI."""
        if season_name not in SEASON_PRESETS:
            print(f"Warning: Unknown season '{season_name}'")
            return
        
        preset = SEASON_PRESETS[season_name]
        self.current_season = season_name
        
        # Update environment parameters
        self.env.wood_regrowth_rate = preset['wood_regrowth']
        self.env.potion_spawn_rate = preset['potion_spawn']
        self.max_steps_per_gen = preset['gen_timeout']
        
        # Update sliders to reflect new values
        self.slider_wood.val = preset['wood_regrowth']
        self.slider_potion.val = preset['potion_spawn']
        self.slider_timeout.val = preset['gen_timeout']
        
        # Reset season tracking only if requested (default)
        # When loading from save, we want to keep the loaded counters
        if reset_stats:
            self.season_gens_counter = 0
            self.season_rewards_window.clear()
    
    def is_season_converged(self) -> bool:
        """Check if AI has converged in current season (reward plateau)."""
        if len(self.season_rewards_window) < CONVERGENCE_WINDOW:
            return False
        
        # Calculate coefficient of variation (std/mean)
        rewards = list(self.season_rewards_window)
        mean_reward = np.mean(rewards)
        std_reward = np.std(rewards)
        
        if mean_reward == 0:
            return False
        
        cv = std_reward / abs(mean_reward)
        
        # Debug output
        converged = cv < CONVERGENCE_THRESHOLD
        status = "✓ CONVERGED" if converged else "○ Not converged"
        print(f"    Convergence Check: CV={cv:.4f} ({cv*100:.2f}%) | Threshold={CONVERGENCE_THRESHOLD*100:.1f}% | {status}")
        
        return converged
    
    def get_convergence_info(self) -> str:
        """Get formatted convergence status string for UI display."""
        if len(self.season_rewards_window) < CONVERGENCE_WINDOW:
            return f"CV: Waiting ({len(self.season_rewards_window)}/{CONVERGENCE_WINDOW})"
        
        rewards = list(self.season_rewards_window)
        mean_reward = np.mean(rewards)
        std_reward = np.std(rewards)
        
        if mean_reward == 0:
            return "CV: N/A"
        
        cv = std_reward / abs(mean_reward)
        cv_pct = cv * 100
        threshold_pct = CONVERGENCE_THRESHOLD * 100
        
        if cv < CONVERGENCE_THRESHOLD:
            return f"CV={cv_pct:.2f}% <{threshold_pct:.0f}% OK"
        else:
            return f"CV={cv_pct:.2f}% >{threshold_pct:.0f}% NO"

    
    def cycle_to_next_season(self) -> None:
        """Advance to the next season in the cycle."""
        # Store average reward of the season that's ending
        if len(self.season_rewards_window) > 0:
            season_avg = np.mean(list(self.season_rewards_window))
            self.season_cycle_rewards.append(season_avg)
        
        current_idx = SEASON_CYCLE.index(self.current_season)
        next_idx = (current_idx + 1) % len(SEASON_CYCLE)
        next_season = SEASON_CYCLE[next_idx]
        
        # If we just finished Winter (end of cycle), record cycle performance
        if self.current_season == SEASON_WINTER:
            if len(self.season_cycle_rewards) > 0:
                cycle_avg = np.mean(self.season_cycle_rewards)
                self.complete_cycle_performance.append(cycle_avg)
                print(f"\\n=== CYCLE {self.cycle_number} COMPLETE ===")
                print(f"    Cycle Avg Reward: {cycle_avg:.2f}")
                print(f"    Season Breakdown: {[f'{r:.1f}' for r in self.season_cycle_rewards]}")
                self.season_cycle_rewards = []  # Reset for next cycle
            self.cycle_number += 1
        
        print(f"Season Change: {self.current_season} → {next_season} (After {self.season_gens_counter} gens)")
        self.apply_season(next_season)

    def trigger_kill_effect(self, x: int, y: int, weapon_type: int) -> None:
        """
        Trigger visual and audio effects when an agent kills another.
        
        Args:
            x, y (int): Grid position where the kill occurred
            weapon_type (int): Type of weapon used (determines color and sound)
        """
        # Sound
        if weapon_type in self.sounds:
            self.sounds[weapon_type].play()
            
        # Visual Particle
        color = (255, 255, 255)
        if weapon_type == WEAPON_SWORD: color = (0, 0, 255) # Blue Flash
        elif weapon_type == WEAPON_BOW: color = (0, 255, 0) # Green Flash
        elif weapon_type == WEAPON_WAND: color = (255, 0, 255) # Purple Flash
        elif weapon_type == WEAPON_FISTS: color = (200, 200, 200) # Grey Flash
        
        # [x, y, color, radius, max_radius]
        self.particles.append([x * CELL_SIZE + CELL_SIZE//2, y * CELL_SIZE + CELL_SIZE//2, color, 2, 20])

    def update_particles(self) -> None:
        """Update particle effect animations (expanding circles on kills)."""
        for p in self.particles[:]:
            p[3] += 2 # Increase radius
            if p[3] >= p[4]:
                self.particles.remove(p)

    def update_hall_of_fame(self) -> None:
        """Update the Hall of Fame with top agents from current generation"""
        # 1. Identify top agents of this generation
        # Criteria: Kills (primary), Steps Alive (secondary)
        sorted_agents = sorted(self.agents, key=lambda a: (a.kills, a.steps_alive), reverse=True)
        top_gen_agents = sorted_agents[:3] # Take top 3 candidates
        
        for agent in top_gen_agents:
            if agent.total_reward < 10: continue # Only significant performers
            
            # Create snapshot
            snapshot = {
                'gen': self.generation,
                'id': agent.id,
                'kills': agent.kills,
                'steps': agent.steps_alive,
                'weapon': agent.weapon,
                'reward': agent.total_reward,  # Save total reward
                'kills_by_type': agent.kills_by_type.copy(),
                'stats': {
                    'str': agent.strength,
                    'prc': agent.precision,
                    'mag': agent.magic,
                    'hp': agent.max_hp,
                    'stam': agent.stamina
                }
            }
            
            # Add to HoF
            self.hall_of_fame.append(snapshot)
            
        # 2. Sort Hall of Fame and keep top 3 All-Time
        # Sort by Reward (desc) - the actual training metric
        self.hall_of_fame.sort(key=lambda x: x['reward'], reverse=True)
        self.hall_of_fame = self.hall_of_fame[:3] # Keep only top 3 Legends

    def spawn_agents(self) -> None:
        """
        Spawn a new generation of agents with random stats and positions.
        
        Each agent gets:
        - Random position on empty tiles
        - Random stats (HP, strength, precision, magic)
        - Random starting weapon
        
        Resets generation-specific tracking (rewards, kills, steps).
        """
        self.agents = []
        for i in range(NUM_AGENTS):
            while True:
                x, y = random.randint(0, GRID_SIZE-1), random.randint(0, GRID_SIZE-1)
                if self.env.grid[x, y] == TILE_EMPTY:
                    self.agents.append(Agent(i, x, y))
                    break
        self.selected_agent = None
        self.gen_steps = 0
        self.current_gen_kills = 0
        # Reset action counts for new generation
        self.action_counts = {i: 0 for i in range(NUM_ACTIONS)}

    def get_agent_at(self, x: int, y: int):
        for a in self.agents:
            if a.alive and a.x == x and a.y == y:
                return a
        return None

    def step_agents_batch(self) -> None:
        """
        Execute one simulation step for all agents using optimized batch processing.
        
        This is the core training loop optimization that processes all agents simultaneously:
        1. Collect states for all alive agents (vectorized view extraction)
        2. Batch inference through neural network (all agents at once)
        3. Apply actions and calculate rewards
        4. Collect next states (vectorized)
        5. Store transitions in replay memory
        6. Train the network periodically
        
        Batch processing provides massive speedup compared to sequential processing,
        especially when using GPU acceleration.
        """
        alive_agents = [a for a in self.agents if a.alive]
        if not alive_agents: return

        # 1. Collect States (Vectorized & Optimized)
        # Extract positions
        positions = [(a.x, a.y) for a in alive_agents]
        
        # Get all views at once (N, 49)
        batch_views = self.env.get_batch_views(positions, VISION_RANGE)
        
        # Pre-allocate numpy array for full states to avoid list overhead
        num_alive = len(alive_agents)
        states_np = np.zeros((num_alive, INPUT_SIZE), dtype=np.float32)
        
        # Calculate context variables
        season_idx = SEASON_CYCLE.index(self.current_season)
        time_remaining = 1.0 - (self.gen_steps / self.max_steps_per_gen)
        
        # Prepare hidden states batch
        hidden_states_h = []
        hidden_states_c = []
        
        # Fill states
        for i, agent in enumerate(alive_agents):
            # Use the new get_state_numpy with context
            # Note: get_state_numpy does concatenation, but here we optimize by filling pre-allocated array
            # We pass the pre-computed view to avoid re-calculating it (huge speedup)
            states_np[i] = agent.get_state_numpy(self.env, season_idx, time_remaining, view_override=batch_views[i])
            
            # Collect hidden states
            if agent.hidden_state is None:
                # Initialize (1, 1, hidden_size)
                h = torch.zeros(1, 1, 256, device=device)
                c = torch.zeros(1, 1, 256, device=device)
                agent.hidden_state = (h, c)
            
            hidden_states_h.append(agent.hidden_state[0])
            hidden_states_c.append(agent.hidden_state[1])
            
        # Stack hidden states: List[(1,1,256)] -> (1, batch, 256)
        batch_h = torch.cat(hidden_states_h, dim=1)
        batch_c = torch.cat(hidden_states_c, dim=1)
        hidden_batch = (batch_h, batch_c)
            
        # Convert to tensor efficiently
        states_tensor = torch.as_tensor(states_np, device=device)

        # 2. Batch Inference
        sample = random.random()
        eps_threshold = self.trainer.get_epsilon()
        self.trainer.steps_done += 1

        actions = None
        new_hidden_batch = None
        
        if sample > eps_threshold:
            with torch.no_grad():
                # policy_net(states, hidden) -> (q_values, new_hidden)
                # q_values: [batch, NUM_ACTIONS]
                q_values, new_hidden_batch = self.policy_net(states_tensor, hidden_batch)
                actions = q_values.max(1)[1].cpu().numpy()
        else:
            actions = np.random.randint(0, NUM_ACTIONS, size=len(alive_agents))
            # Even if random action, we must forward pass to update hidden state!
            with torch.no_grad():
                _, new_hidden_batch = self.policy_net(states_tensor, hidden_batch)
        
        # Update agents with new hidden states
        # new_hidden_batch is ((1, batch, 256), (1, batch, 256))
        # We need to split it back to agents
        if new_hidden_batch is not None:
            h_batch, c_batch = new_hidden_batch
            for i, agent in enumerate(alive_agents):
                # Slice to keep (1, 1, 256) shape
                h = h_batch[:, i:i+1, :]
                c = c_batch[:, i:i+1, :]
                agent.hidden_state = (h, c)
        
        # Track action distribution
        for action in actions:
            self.action_counts[int(action)] += 1

        # 3. Apply Actions
        rewards_list = []
        for i, agent in enumerate(alive_agents):
            act_val = actions[i]
            reward = 0.1 # Survival

            dx, dy = 0, 0
            if act_val == ACTION_UP: dy = -1
            elif act_val == ACTION_DOWN: dy = 1
            elif act_val == ACTION_LEFT: dx = -1
            elif act_val == ACTION_RIGHT: dx = 1
            
            # Movement
            if dx != 0 or dy != 0:
                # Toroidal Movement: Wrap around edges
                nx = (agent.x + dx) % GRID_SIZE
                ny = (agent.y + dy) % GRID_SIZE
                
                if self.env.is_walkable(nx, ny):
                    target_agent = self.get_agent_at(nx, ny)
                    if target_agent:
                        reward -= 0.1
                    else:
                        agent.x, agent.y = nx, ny
                        tile = self.env.grid[nx, ny]
                        if tile == TILE_WOOD:
                            agent.wood += 1
                            self.env.grid[nx, ny] = TILE_EMPTY
                            reward += 5
                        elif tile == TILE_IRON:
                            agent.iron += 1
                            self.env.grid[nx, ny] = TILE_EMPTY
                            reward += 5
                        elif tile == TILE_POTION_HEALTH:
                            agent.hp = min(agent.max_hp, agent.hp + 20 + agent.magic)
                            self.env.grid[nx, ny] = TILE_EMPTY
                            reward += 2
                        elif tile == TILE_POTION_ENERGY:
                            agent.stamina = min(100, agent.stamina + 30)
                            self.env.grid[nx, ny] = TILE_EMPTY
                            reward += 2
                        elif tile == TILE_POTION_MAGIC:
                            agent.magic += 1
                            self.env.grid[nx, ny] = TILE_EMPTY
                            reward += 5
                else:
                    # Hit Wall (internal obstacle)
                    reward -= 0.1

            # Attack
            elif act_val == ACTION_ATTACK:
                damage = 0
                range_val = 1
                cost = 5
                
                if agent.weapon == WEAPON_FISTS:
                    damage = 5 + (agent.strength * 0.5)
                    cost = 2
                elif agent.weapon == WEAPON_SWORD:
                    damage = 10 + agent.strength
                    cost = 8
                elif agent.weapon == WEAPON_BOW:
                    range_val = 5
                    damage = 8 + agent.precision
                    cost = 5
                    if agent.arrows > 0:
                        agent.arrows -= 1
                    else:
                        damage = 2
                elif agent.weapon == WEAPON_WAND:
                    range_val = 3
                    damage = 12 + agent.magic
                    cost = 6
                
                if agent.stamina >= cost:
                    agent.stamina -= cost
                    target = None
                    min_dist = 999
                    for enemy in self.agents:
                        if enemy is not agent and enemy.alive:
                            # Toroidal Distance Calculation
                            dx = abs(enemy.x - agent.x)
                            dy = abs(enemy.y - agent.y)
                            
                            # Shortest path considering wrap-around
                            dx = min(dx, GRID_SIZE - dx)
                            dy = min(dy, GRID_SIZE - dy)
                            
                            dist = dx + dy
                            
                            if dist <= range_val and dist < min_dist:
                                min_dist = dist
                                target = enemy
                    
                    if target:
                        killed = target.take_damage(damage)
                        reward += 10
                        if killed:
                            agent.kills += 1
                            agent.kills_by_type[agent.weapon] += 1
                            self.global_kills_by_type[agent.weapon] += 1
                            self.current_gen_kills += 1
                            reward += 100
                            
                            if self.render_visuals:
                                self.trigger_kill_effect(target.x, target.y, agent.weapon)
                else:
                    reward -= 1

            # Wait / Craft
            elif act_val == ACTION_WAIT:
                agent.stamina = min(100, agent.stamina + 10)
                if agent.craft():
                    reward += 5
            
            agent.steps_alive += 1
            agent.total_reward += reward  # Accumulate total reward
            rewards_list.append(reward)
            
        # 4. Collect Next States (Vectorized & Optimized)
        # Re-extract positions for alive agents (some might have moved)
        next_positions = [(a.x, a.y) for a in alive_agents]
        next_batch_views = self.env.get_batch_views(next_positions, VISION_RANGE)
        
        # Pre-allocate next states array
        # Note: We need to handle dead agents. But here we iterate over alive_agents only?
        # No, we need next_state for the transition.
        # If agent is alive, next_state is valid. If dead, next_state is None.
        # But wait, the loop below iterates over alive_agents.
        # If an agent died during this step, is it still in alive_agents list?
        # YES. alive_agents was created at start of function.
        # So we can safely iterate over it.
        
        next_states_np = np.zeros((num_alive, INPUT_SIZE), dtype=np.float32)
        
        # Calculate time remaining for next state (t+1)
        next_time_remaining = 1.0 - ((self.gen_steps + 1) / self.max_steps_per_gen)
        next_time_remaining = max(0.0, next_time_remaining) # Clamp to 0
        
        for i, agent in enumerate(alive_agents):
            if agent.alive:
                # Use the new get_state_numpy with context for t+1
                next_states_np[i] = agent.get_state_numpy(self.env, season_idx, next_time_remaining, view_override=next_batch_views[i])
        
        # Convert all next states to tensor at once
        # But wait, dead agents should have None as next state.
        # We can't put None in a tensor.
        # We'll keep the tensor for alive ones, and handle None separately?
        # Or just use the tensor and ignore rows for dead agents in the memory push loop.
        
        next_states_tensor = torch.as_tensor(next_states_np, device=device)

        # 5. Store Transitions
        for i, agent in enumerate(alive_agents):
            curr_state_t = states_tensor[i].unsqueeze(0)
            
            if agent.alive:
                next_state_t = next_states_tensor[i].unsqueeze(0)
            else:
                next_state_t = None
            
            reward = rewards_list[i]
            if not agent.alive:
                reward = -100 # Ensure death penalty is recorded
            
            action_t = torch.tensor([[actions[i]]], device=device, dtype=torch.long)
            reward_t = torch.tensor([reward], device=device)
            
            self.memory.push(curr_state_t, action_t, reward_t, next_state_t)



        # Adaptive training frequency based on render mode
        train_freq = TRAIN_FREQUENCY if self.render_visuals else TRAIN_FREQUENCY_TURBO
        if self.trainer.steps_done % train_freq == 0:
            loss = self.trainer.optimize_model()
            if loss is not None:
                self.loss_history.append(loss)
                if len(self.loss_history) > 200:
                    self.loss_history.pop(0)

    def log_brain_activity(self, message: str) -> None:
        """Log brain activity to a file for debugging"""
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_path = os.path.join(base_path, "brain_log.txt")
            with open(log_path, "a") as f:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {message}\\n")
        except Exception:
            pass

    def save_brain(self) -> None:
        """
        Save the AI brain (neural network + training state + game stats) to disk.
        
        The checkpoint includes:
        - Model weights (policy network)
        - Optimizer state (for resuming training)
        - Training progress (steps_done for epsilon decay)
        - Game state (generation, histories, Hall of Fame)
        
        Creates a backup before overwriting to prevent data loss.
        """
        # Save in assets/models/
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_dir = os.path.join(base_path, "assets", "models")
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
            
        brain_path = os.path.join(model_dir, "arena_brain.pth")
        backup_path = os.path.join(model_dir, "arena_brain_backup.pth")
        
        # Backup existing brain before overwriting
        if os.path.exists(brain_path):
            try:
                import shutil
                shutil.copy2(brain_path, backup_path)
                self.log_brain_activity(f"Backed up brain to {backup_path}")
            except Exception as e:
                self.log_brain_activity(f"Failed to backup brain: {e}")
        
        # Create Checkpoint Dictionary
        checkpoint = {
            'model_state_dict': self.policy_net.state_dict(),
            'optimizer_state_dict': self.trainer.optimizer.state_dict(),
            'steps_done': self.trainer.steps_done,
            'generation': self.generation,
            'kill_history': list(self.kill_history),
            'reward_history': list(self.reward_history),
            'duration_history': list(self.duration_history),
            'global_kills_by_type': self.global_kills_by_type,
            'hall_of_fame': self.hall_of_fame,
            'action_history': self.action_history,
            # Season state
            'current_season': self.current_season,
            'auto_season_mode': self.auto_season_mode,
            'season_gens_counter': self.season_gens_counter,
            'cycle_number': self.cycle_number,
            'complete_cycle_performance': self.complete_cycle_performance
        }
        
        try:
            torch.save(checkpoint, brain_path)
            print(f"Brain & Stats saved to {brain_path}")
            self.log_brain_activity(f"Saved brain to {brain_path} (Gen {self.generation})")
            
            # Also save statistics to text file
            self.save_statistics()
            
        except Exception as e:
            print(f"Error saving brain: {e}")
            self.log_brain_activity(f"Error saving brain: {e}")

    def save_statistics(self) -> None:
        """
        Append current generation statistics to a text file for analysis.
        Format: Gen, AvgReward, Kills, Season, Epsilon, CV
        """
        stats_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "training_stats.txt")
        
        avg_reward = self.reward_history[-1] if self.reward_history else 0.0
        kills = self.kill_history[-1] if self.kill_history else 0
        epsilon = self.trainer.get_epsilon()
        
        # Calculate CV (Coefficient of Variation)
        cv = 0.0
        if len(self.season_rewards_window) > 0:
            rewards = list(self.season_rewards_window)
            mean_reward = np.mean(rewards)
            std_reward = np.std(rewards)
            if mean_reward != 0:
                cv = std_reward / abs(mean_reward)
        
        # Create header if file doesn't exist
        if not os.path.exists(stats_path):
            with open(stats_path, "w") as f:
                f.write("Generation,AvgReward,Kills,Season,Epsilon,CV\\n")
        
        with open(stats_path, "a") as f:
            f.write(f"{self.generation},{avg_reward:.4f},{kills},{self.current_season},{epsilon:.4f},{cv:.4f}\\n")
        
        self.log_brain_activity(f"Stats saved to {stats_path}")

    def load_brain(self) -> None:
        """
        Load the AI brain from disk if it exists.
        
        Attempts to load from main save file, then backup if main fails.
        Restores the complete training state including neural network weights,
        optimizer state, generation counter, and all historical data.
        
        If no valid save is found, starts fresh with a new brain.
        """
        # Load from assets/models/
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        brain_path = os.path.join(base_path, "assets", "models", "arena_brain.pth")
        backup_path = os.path.join(base_path, "assets", "models", "arena_brain_backup.pth")
        
        self.log_brain_activity(f"Attempting to load brain from {brain_path}")
        print(f"DEBUG: Attempting to load brain from: {brain_path}")
        print(f"DEBUG: Device: {device}")
        
        loaded = False
        paths_to_try = [brain_path, backup_path]
        
        for path in paths_to_try:
            if not os.path.exists(path):
                continue
                
            try:
                try:
                    checkpoint = torch.load(path, map_location=device, weights_only=False)
                except TypeError:
                    # Fallback for older PyTorch versions
                    self.log_brain_activity("weights_only not supported, trying without it")
                    checkpoint = torch.load(path, map_location=device)
                
                # Check if it's a full checkpoint or just legacy weights
                if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                    try:
                        self.policy_net.load_state_dict(checkpoint['model_state_dict'])
                        self.target_net.load_state_dict(checkpoint['model_state_dict'])
                    except RuntimeError as e:
                        print(f"⚠️ Brain Architecture Mismatch: {e}")
                        print("Starting fresh brain (Gen 1) with new architecture.")
                        self.log_brain_activity("Brain architecture mismatch - starting fresh")
                        return

                    
                    # Restore Trainer State
                    if 'optimizer_state_dict' in checkpoint:
                        self.trainer.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
                    if 'steps_done' in checkpoint:
                        self.trainer.steps_done = checkpoint['steps_done']
                        
                    # Restore Game State
                    if 'generation' in checkpoint:
                        self.generation = checkpoint['generation']
                        print(f"DEBUG: Restored generation: {self.generation}")
                    if 'kill_history' in checkpoint:
                        self.kill_history = collections.deque(checkpoint['kill_history'], maxlen=200)
                    if 'reward_history' in checkpoint:
                        self.reward_history = collections.deque(checkpoint['reward_history'], maxlen=200)
                    if 'duration_history' in checkpoint:
                        self.duration_history = collections.deque(checkpoint['duration_history'], maxlen=200)
                    if 'global_kills_by_type' in checkpoint:
                        self.global_kills_by_type = checkpoint['global_kills_by_type']
                    if 'hall_of_fame' in checkpoint:
                        self.hall_of_fame = checkpoint['hall_of_fame']
                    if 'action_history' in checkpoint:
                        self.action_history = checkpoint['action_history']
                    
                    # Restore Season State
                    if 'current_season' in checkpoint:
                        self.current_season = checkpoint['current_season']
                    if 'auto_season_mode' in checkpoint:
                        self.auto_season_mode = checkpoint['auto_season_mode']
                    if 'season_gens_counter' in checkpoint:
                        self.season_gens_counter = checkpoint['season_gens_counter']
                    if 'cycle_number' in checkpoint:
                        self.cycle_number = checkpoint['cycle_number']
                    if 'complete_cycle_performance' in checkpoint:
                        self.complete_cycle_performance = checkpoint['complete_cycle_performance']
                        
                        
                    print(f"Brain & Stats loaded from {path} (Gen {self.generation})")
                    self.log_brain_activity(f"Successfully loaded brain from {path} (Gen {self.generation})")
                    loaded = True
                    break
                else:
                    # Legacy: Just weights
                    self.policy_net.load_state_dict(checkpoint)
                    self.target_net.load_state_dict(self.policy_net.state_dict())
                    print(f"Legacy Brain loaded from {path} (Starting fresh stats)")
                    self.log_brain_activity(f"Legacy brain loaded from {path}")
                    loaded = True
                    break
                    
            except Exception as e:
                print(f"ERROR: Could not load brain from {path} ({e})")
                self.log_brain_activity(f"Error loading from {path}: {e}")
                import traceback
                traceback.print_exc()
        
        if not loaded:
            print(f"DEBUG: No valid brain found, starting fresh.")
            self.log_brain_activity("No valid brain found, starting fresh")

    def run(self) -> None:
        """
        Main game loop.
        
        Handles:
        - Event processing (mouse, keyboard, window close)
        - Game state updates (agent actions, environment changes)
        - Rendering (graphics and UI)
        - Performance modes (normal vs turbo)
        - Generation cycling (spawn new agents when generation ends)
        - Periodic brain saving
        
        In turbo mode (visuals OFF), runs up to 20000 steps per frame for
        ultra-fast training.
        """
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    self.save_brain()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    if mx < GRID_PIXEL_SIZE:
                        # Apply offset for grid interaction
                        grid_y = my - GRID_OFFSET_Y
                        if 0 <= grid_y < GRID_PIXEL_SIZE:
                            gx, gy = mx // CELL_SIZE, grid_y // CELL_SIZE
                            if 0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE:
                                self.selected_agent = self.get_agent_at(gx, gy)
                                if self.selected_agent:
                                    print(f"Selected Agent {self.selected_agent.id}")
                
                self.slider_wood.handle_event(event)
                self.slider_potion.handle_event(event)
                self.slider_timeout.handle_event(event)
                self.btn_visuals.handle_event(event)
                self.btn_reset_epsilon.handle_event(event)
                self.btn_clear_hof.handle_event(event)
                
                # Season buttons
                self.btn_season_auto.handle_event(event)
                self.btn_season_spring.handle_event(event)
                self.btn_season_summer.handle_event(event)
                self.btn_season_autumn.handle_event(event)
                self.btn_season_winter.handle_event(event)

            # Update Parameters
            self.env.wood_regrowth_rate = self.slider_wood.val
            self.env.potion_spawn_rate = self.slider_potion.val
            self.max_steps_per_gen = self.slider_timeout.val
            
            # Logic
            steps_to_run = 1 if self.render_visuals else 1000 # Reduced from 20000 to 1000 for better UI responsiveness
            
            for _ in range(steps_to_run):
                # Optimize: Update environment (regrowth/spawns) less frequently
                if self.gen_steps % 10 == 0:
                    self.env.update_environment()
                
                self.step_agents_batch()
                
                self.gen_steps += 1
                alive_agents = [a for a in self.agents if a.alive]
                
                if self.render_visuals:
                    self.update_particles()
                
                # Handle events during fast simulation to keep UI responsive
                if self.gen_steps % 100 == 0: # Check less frequently (every 100 steps)
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            running = False
                            self.save_brain()
                            return
                        
                        # Allow toggling visuals back ON
                        self.btn_visuals.handle_event(event)
                        self.btn_reset_epsilon.handle_event(event)
                        self.btn_clear_hof.handle_event(event)
                        # Allow adjusting sliders too
                        self.slider_wood.handle_event(event)
                        self.slider_potion.handle_event(event)
                        self.slider_timeout.handle_event(event)

                    # If visuals are ON (either already or just toggled), break the fast loop
                    # to allow rendering to happen immediately
                    if self.render_visuals:
                        break
                
                if len(alive_agents) <= 1 or self.gen_steps >= self.max_steps_per_gen:
                    break
            
            # Rendering
            if self.render_visuals:
                draw_grid(self.screen, self.env, self.agents, self.particles, self.selected_agent)
                # Get current epsilon
                epsilon = self.trainer.get_epsilon()
                
                draw_ui(
                    self.screen, self.font, self.title_font,
                    [self.slider_wood, self.slider_potion, self.slider_timeout],
                    self.btn_visuals, self.agents, self.selected_agent,
                    self.generation, self.gen_steps, self.max_steps_per_gen,
                    self.global_kills_by_type, self.kill_history,
                    self.reward_history, self.duration_history,
                    self.cycles_per_hour, epsilon, self.hall_of_fame,
                    self.action_history, self.btn_reset_epsilon, self.btn_clear_hof,
                    # Season parameters
                    [self.btn_season_auto, self.btn_season_spring, self.btn_season_summer, 
                     self.btn_season_autumn, self.btn_season_winter],
                    self.current_season, self.auto_season_mode, self.cycle_number, self.season_gens_counter,
                    self.complete_cycle_performance, self.get_convergence_info()
                )
                pygame.display.flip()
                self.clock.tick(FPS)
            else:
                # In turbo mode: Update UI every frame (every 1000 steps)
                self.screen.fill((0, 0, 0)) # Clear screen
                epsilon = self.trainer.get_epsilon()
                draw_ui(
                    self.screen, self.font, self.title_font,
                    [self.slider_wood, self.slider_potion, self.slider_timeout],
                    self.btn_visuals, self.agents, self.selected_agent,
                    self.generation, self.gen_steps, self.max_steps_per_gen,
                    self.global_kills_by_type, self.kill_history,
                    self.reward_history, self.duration_history,
                    self.cycles_per_hour, epsilon, self.hall_of_fame,
                    self.action_history, self.btn_reset_epsilon, self.btn_clear_hof,
                    # Season parameters
                    [self.btn_season_auto, self.btn_season_spring, self.btn_season_summer, 
                     self.btn_season_autumn, self.btn_season_winter],
                    self.current_season, self.auto_season_mode, self.cycle_number, self.season_gens_counter,
                    self.complete_cycle_performance, self.get_convergence_info()
                )
                pygame.display.flip()

            
            if self.trainer.steps_done % TARGET_UPDATE == 0:
                self.target_net.load_state_dict(self.policy_net.state_dict())
            
            if len(alive_agents) <= 1 or self.gen_steps >= self.max_steps_per_gen:
                # End of Generation Stats
                self.duration_history.append(self.gen_steps)
                if len(self.duration_history) > 200: self.duration_history.pop(0)
                
                # Calculate Avg Reward for the entire generation (Total Reward per Agent)
                if self.agents:
                    total_rewards = [a.total_reward for a in self.agents]
                    gen_avg_reward = sum(total_rewards) / len(total_rewards)
                    self.reward_history.append(gen_avg_reward)
                    if len(self.reward_history) > 200: self.reward_history.pop(0)
                
                # Record Kills for this generation
                self.kill_history.append(self.current_gen_kills)
                if len(self.kill_history) > 200: self.kill_history.pop(0)
                
                # Record Action Distribution for this generation
                total_actions = sum(self.action_counts.values())
                if total_actions > 0:
                    action_distribution = {k: v / total_actions for k, v in self.action_counts.items()}
                    self.action_history.append(action_distribution)
                    if len(self.action_history) > 200:
                        self.action_history.pop(0)
                
                # Update Cycles Per Hour
                now = time.time()
                self.gen_timestamps.append(now)
                if len(self.gen_timestamps) > 1:
                    # Calculate speed based on time diff between oldest and newest timestamp
                    time_diff = self.gen_timestamps[-1] - self.gen_timestamps[0]
                    if time_diff > 0:
                        # (N-1) intervals / time_diff * 3600 seconds
                        self.cycles_per_hour = ((len(self.gen_timestamps) - 1) / time_diff) * 3600
                
                self.update_hall_of_fame()
                
                # Season System: Track rewards and check for season change
                if self.agents:
                    total_rewards = [a.total_reward for a in self.agents]
                    gen_avg_reward = sum(total_rewards) / len(total_rewards)
                    self.season_rewards_window.append(gen_avg_reward)
                
                self.season_gens_counter += 1
                
                # Auto-cycle seasons based on hybrid criteria
                if self.auto_season_mode:
                    should_change = False
                    reason = ""
                    
                    # Periodic convergence check (every 10 gens after minimum)
                    if self.season_gens_counter >= MIN_GENS_PER_SEASON and self.season_gens_counter % 10 == 0:
                        print(f"  Season: {self.current_season} | Gen {self.season_gens_counter}/{MAX_GENS_PER_SEASON}")
                        self.is_season_converged()  # This will print debug info
                    
                    if self.season_gens_counter >= MAX_GENS_PER_SEASON:
                        should_change = True
                        reason = f"Max {MAX_GENS_PER_SEASON} gens reached"
                    elif self.season_gens_counter >= MIN_GENS_PER_SEASON and self.is_season_converged():
                        should_change = True
                        reason = "Converged (reward plateau)"
                    
                    if should_change:
                        print(f"  → Season Change Trigger: {reason}")
                        self.cycle_to_next_season()
                
                print(f"Generation {self.generation} finished. Steps: {self.gen_steps} | Speed: {int(self.cycles_per_hour)} Gen/h | Season: {self.current_season} ({self.season_gens_counter} gens)")
                self.save_brain()
                self.generation += 1
                self.env.generate_map()
                self.spawn_agents()
                
        pygame.quit()
