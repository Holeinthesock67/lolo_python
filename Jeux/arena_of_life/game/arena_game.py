"""
Main game orchestration module for Arena of Life (Refactored).

This module contains the ArenaGame class which orchestrates all game systems
by coordinating specialized components: GameEngine, Renderer, and UIManager.
"""
import pygame
import torch
import torch.optim as optim
import numpy as np
import random
import os
import collections
import time

from config.constants import (
    GRID_SIZE, CELL_SIZE, GRID_OFFSET_Y,
    INPUT_SIZE, NUM_ACTIONS, MEMORY_SIZE, LR,
    TARGET_UPDATE, TRAIN_FREQUENCY, TRAIN_FREQUENCY_TURBO,
    device, Transition, VISION_RANGE, SEASON_CYCLE,
    MIN_GENS_PER_SEASON, MAX_GENS_PER_SEASON,
    ACTION_CRI_DANGER, ACTION_CRI_HEAL, ACTION_CRI_POTION,
    ROLE_WARRIOR, ROLE_SCOUT, ROLE_HEALER, NUM_AGENTS,
    WEAPON_SWORD, WEAPON_BOW, WEAPON_WAND,
    ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_ATTACK, ACTION_WAIT
)
from ai import DQN, ReplayMemory, Trainer
from environment import Environment
from game.game_engine import GameEngine
from game.renderer import Renderer
from game.ui_manager import UIManager


class ArenaGame:
    """
    Main game orchestrator (refactored).
    
    Coordinates the interaction between:
    - GameEngine: Core game logic
    - Renderer: Graphics and audio
    - UIManager: User interface
    - Trainer: AI training
    
    This class is now a thin orchestrator that delegates responsibilities
    to specialized components.
    """
    
    def __init__(self) -> None:
        """Initialize the game with all systems."""
        # Core Components
        self.env = Environment(GRID_SIZE, GRID_SIZE)
        self.engine = GameEngine(self.env)
        self.renderer = Renderer()
        self.ui_manager = UIManager()
        
        # AI Setup
        self.policy_net = DQN(INPUT_SIZE, NUM_ACTIONS).to(device)
        self.target_net = DQN(INPUT_SIZE, NUM_ACTIONS).to(device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        
        self.memory = ReplayMemory(MEMORY_SIZE)
        self.trainer = Trainer(self.policy_net, self.target_net, self.memory)
        
        # Game State
        self.generation = 1
        self.gen_steps = 0
        self.max_steps_per_gen = 1500
        
        # History Tracking
        self.loss_history = []      # Kept for backward compatibility/rendering interface
        self.gen_loss_history = []  # Average loss per generation
        self.current_gen_loss_sum = 0.0
        self.current_gen_loss_count = 0
        self.reward_history = collections.deque(maxlen=200)
        self.duration_history = collections.deque(maxlen=200)
        self.action_counts = {i: 0 for i in range(NUM_ACTIONS)}
        self.action_history = []
        
        # Performance Tracking
        self.gen_timestamps = collections.deque(maxlen=10)
        self.cycles_per_hour = 0
        
        # Communication
        self.active_signals = [] # List of {'x', 'y', 'type'}
        
        # Load brain and spawn initial entities
        self.load_brain()
        
        # --- MIGRATION DONE ---

        self.engine.spawn_agents()
        self.engine.spawn_predators()
        
        # Create UI callbacks
        callbacks = {
            'toggle_visuals': self.toggle_visuals,
            'toggle_sound': self.toggle_sound,
            'reset_exploration': self.reset_exploration,
            'clear_hall_of_fame': self.clear_hall_of_fame,
            'toggle_auto_season': self.toggle_auto_season,
            'set_season': self.set_season
        }
        self.ui_manager.create_buttons(callbacks)
        
        # Apply initial season
        self.engine.apply_season(self.engine.current_season, reset_stats=False)
        self._sync_ui_with_engine()
        
        # Update initial button colors
        self.ui_manager.update_visuals_button_color(self.renderer.visuals_enabled)
        self.ui_manager.update_sound_button_color(self.renderer.sound_enabled)
    
    def _sync_ui_with_engine(self) -> None:
        """Synchronize UI sliders with engine parameters."""
        from config.constants import SEASON_PRESETS
        preset = SEASON_PRESETS[self.engine.current_season]
        self.max_steps_per_gen = preset['gen_timeout']
        self.ui_manager.update_slider_values(
            wood_regrowth=self.env.wood_regrowth_rate,
            potion_spawn=self.env.potion_spawn_rate,
            gen_timeout=self.max_steps_per_gen
        )
    
    def toggle_visuals(self) -> None:
        """Toggle visual rendering for turbo mode."""
        new_state = self.renderer.toggle_visuals()
        self.ui_manager.update_visuals_button_color(new_state)
        status = "ON" if new_state else "OFF"
        print(f"Visuals: {status}")
    
    def toggle_sound(self) -> None:
        """Toggle sound effects."""
        new_state = self.renderer.toggle_sound()
        self.ui_manager.update_sound_button_color(new_state)
        status = "ON" if new_state else "OFF"
        print(f"Sound: {status}")
    
    def reset_exploration(self) -> None:
        """Boost exploration by reducing steps_done by 50%."""
        old_steps = self.trainer.steps_done
        self.trainer.steps_done = int(self.trainer.steps_done * 0.5)
        old_eps = self.trainer.get_epsilon_at_step(old_steps)
        new_eps = self.trainer.get_epsilon()
        print(f"Exploration boosted! Epsilon: {old_eps:.4f} → {new_eps:.4f}")
    
    def clear_hall_of_fame(self) -> None:
        """Clear the Hall of Fame."""
        self.engine.hall_of_fame = []
        print("Hall of Fame cleared!")
    
    def toggle_auto_season(self) -> None:
        """Toggle automatic season cycling."""
        self.engine.auto_season_mode = not self.engine.auto_season_mode
        status = "ON" if self.engine.auto_season_mode else "OFF"
        print(f"Auto Season Mode: {status}")
    
    def set_season(self, season_name: str) -> None:
        """Manually set a specific season."""
        self.engine.auto_season_mode = False
        if season_name != self.engine.current_season:
            self.engine.apply_season(season_name)
            self._sync_ui_with_engine()
            print(f"Season manually changed to: {season_name}")
            
    def _compute_signal_vectors(self, agents: list) -> np.ndarray:
        """
        Compute signal perception vectors for all agents.
        
        Returns:
            np.ndarray: Shape (num_agents, 6) containing [Dx, Dy, Fx, Fy, Px, Py]
        """
        num_agents = len(agents)
        vectors = np.zeros((num_agents, 6), dtype=np.float32)
        
        if not self.active_signals:
            return vectors
            
        # Pre-process signals by type
        danger_signals = [(s['x'], s['y']) for s in self.active_signals if s['type'] == ACTION_CRI_DANGER]
        heal_signals = [(s['x'], s['y']) for s in self.active_signals if s['type'] == ACTION_CRI_HEAL]
        potion_signals = [(s['x'], s['y']) for s in self.active_signals if s['type'] == ACTION_CRI_POTION]
        
        signal_groups = [
            (danger_signals, 0), # Indices 0, 1
            (heal_signals, 2),   # Indices 2, 3
            (potion_signals, 4)  # Indices 4, 5
        ]
        
        for i, agent in enumerate(agents):
            for signals, start_idx in signal_groups:
                if not signals:
                    continue
                    
                total_dx, total_dy = 0.0, 0.0
                
                for sx, sy in signals:
                    # Calculate toroidal vector
                    dx = sx - agent.x
                    dy = sy - agent.y
                    
                    # Wrap around
                    if abs(dx) > GRID_SIZE / 2:
                        dx = -np.sign(dx) * (GRID_SIZE - abs(dx))
                    if abs(dy) > GRID_SIZE / 2:
                        dy = -np.sign(dy) * (GRID_SIZE - abs(dy))
                        
                    dist_sq = dx*dx + dy*dy
                    if dist_sq == 0:
                        continue
                        
                    # Weight by inverse distance squared (gravity-like)
                    weight = 1.0 / dist_sq
                    total_dx += dx * weight
                    total_dy += dy * weight
                
                # Normalize if non-zero
                mag = np.sqrt(total_dx*total_dx + total_dy*total_dy)
                if mag > 0:
                    vectors[i, start_idx] = total_dx / mag
                    vectors[i, start_idx + 1] = total_dy / mag
                    
        return vectors
    
    def step_agents_batch(self) -> None:
        """
        Execute one simulation step for all agents using batch processing.
        
        This is the core training loop that processes all agents simultaneously.
        It performs the following steps:
        1. Collects states for all alive agents (vectorized).
        2. Computes actions using the policy network (batch inference).
        3. Applies actions to the environment using the GameEngine.
        4. Calculates rewards and updates agent stats.
        5. Collects next states and stores transitions in ReplayMemory.
        6. Triggers training step if conditions are met.
        """
        alive_agents = [a for a in self.engine.agents if a.alive]
        if not alive_agents:
            return
        
        # 1. Collect States (Vectorized)
        # We gather positions to optimize view extraction from the grid
        positions = [(a.x, a.y) for a in alive_agents]
        batch_views = self.env.get_batch_views(positions, VISION_RANGE, self.engine.predators)
        
        # Compute signal vectors for all agents
        signal_vectors = self._compute_signal_vectors(alive_agents)
        
        num_alive = len(alive_agents)
        states_np = np.zeros((num_alive, INPUT_SIZE), dtype=np.float32)
        
        # Calculate context variables
        season_idx = SEASON_CYCLE.index(self.engine.current_season)
        time_remaining = 1.0 - (self.gen_steps / self.max_steps_per_gen)
        
        # Prepare hidden states for LSTM
        hidden_states_h = []
        hidden_states_c = []
        
        for i, agent in enumerate(alive_agents):
            states_np[i] = agent.get_state_numpy(
                self.env, season_idx, time_remaining, 
                view_override=batch_views[i],
                signals=signal_vectors[i]
            )
            
            # Initialize hidden state if missing
            if agent.hidden_state is None:
                h = torch.zeros(1, 1, 512, device=device)
                c = torch.zeros(1, 1, 512, device=device)
                agent.hidden_state = (h, c)
            
            hidden_states_h.append(agent.hidden_state[0])
            hidden_states_c.append(agent.hidden_state[1])
        
        # Stack hidden states for batch processing
        batch_h = torch.cat(hidden_states_h, dim=1)
        batch_c = torch.cat(hidden_states_c, dim=1)
        hidden_batch = (batch_h, batch_c)
        
        states_tensor = torch.as_tensor(states_np, device=device)
        
        # 2. Get Actions (Batch Inference)
        sample = random.random()
        eps_threshold = self.trainer.get_epsilon()
        self.trainer.steps_done += 1
        
        new_hidden_batch = None
        if sample > eps_threshold:
            # Exploitation: Use model prediction
            with torch.no_grad():
                q_values, new_hidden_batch = self.policy_net(states_tensor, hidden_batch)
                
                # Store Q-values for inspection
                q_values_np = q_values.cpu().numpy()
                for i, agent in enumerate(alive_agents):
                    agent.last_q_values = q_values_np[i]
                    
                actions = q_values.max(1)[1].cpu().numpy()
        else:
            # Exploration: Random actions
            actions = np.random.randint(0, NUM_ACTIONS, size=num_alive)
            # We still run the model to update hidden states
            with torch.no_grad():
                _, new_hidden_batch = self.policy_net(states_tensor, hidden_batch)
        
        # Update hidden states for next step
        if new_hidden_batch is not None:
            h_batch, c_batch = new_hidden_batch
            for i, agent in enumerate(alive_agents):
                h = h_batch[:, i:i+1, :]
                c = c_batch[:, i:i+1, :]
                agent.hidden_state = (h, c)
        
        # Track action distribution
        for action in actions:
            self.action_counts[int(action)] += 1
        
        # 3. Apply Actions
        rewards_list = []
        next_active_signals = []
        
        for i, agent in enumerate(alive_agents):
            reward, event = self.engine.apply_action(agent, actions[i], alive_agents)
            rewards_list.append(reward)
            
            # Handle Events (Kill / Shout)
            if event:
                if event['type'] == 'kill':
                    self.renderer.trigger_kill_effect(
                        event['x'], event['y'], event['weapon']
                    )
                elif event['type'] == 'shout':
                    next_active_signals.append(event)
                    # Trigger visual effect
                    self.renderer.trigger_shout_effect(
                        event['x'], event['y'], event['shout_type']
                    )
        
        # Update signals for next step
        self.active_signals = next_active_signals
        
        # Team Reward Sharing (Cooperative Incentive)
        step_total_reward = sum(rewards_list)
        if step_total_reward > 0:
            team_bonus = (step_total_reward * 0.01) / len(alive_agents)  # Reduced from 10% to 1%
            for i in range(len(rewards_list)):
                rewards_list[i] += team_bonus
        
        # Update total rewards for agents
        for i, agent in enumerate(alive_agents):
            agent.total_reward += rewards_list[i]
        
        # Update Predators (AI movement)
        self.engine.update_predators()
        
        # 4. Collect Next States
        next_positions = [(a.x, a.y) for a in alive_agents]
        next_batch_views = self.env.get_batch_views(next_positions, VISION_RANGE, self.engine.predators)
        
        # Recompute signals for next state (using updated active_signals)
        next_signal_vectors = self._compute_signal_vectors(alive_agents)
        
        next_states_np = np.zeros((num_alive, INPUT_SIZE), dtype=np.float32)
        next_time_remaining = max(0.0, 1.0 - ((self.gen_steps + 1) / self.max_steps_per_gen))
        
        for i, agent in enumerate(alive_agents):
            if agent.alive:
                next_states_np[i] = agent.get_state_numpy(
                    self.env, season_idx, next_time_remaining, 
                    view_override=next_batch_views[i],
                    signals=next_signal_vectors[i]
                )
        
        next_states_tensor = torch.as_tensor(next_states_np, device=device)
        
        # 5. Store Transitions in Replay Memory
        for i, agent in enumerate(alive_agents):
            curr_state_t = states_tensor[i].unsqueeze(0)
            next_state_t = next_states_tensor[i].unsqueeze(0) if agent.alive else None
            
            reward = rewards_list[i]
            if not agent.alive:
                reward = -100  # Heavy penalty for death
            
            action_t = torch.tensor([[actions[i]]], device=device, dtype=torch.long)
            reward_t = torch.tensor([reward], device=device)
            
            self.memory.push(curr_state_t, action_t, reward_t, next_state_t)
        
        # 6. Train the Model
        train_freq = TRAIN_FREQUENCY if self.renderer.visuals_enabled else TRAIN_FREQUENCY_TURBO
        if self.trainer.steps_done % train_freq == 0:
            loss = self.trainer.optimize_model()
            if loss is not None:
                # Accumulate loss for generation average
                loss_val = loss.item() if isinstance(loss, torch.Tensor) else loss
                self.current_gen_loss_sum += loss_val
                self.current_gen_loss_count += 1
                
                # Keep short history for immediate debugging/logging if needed
                self.loss_history.append(loss)
                if len(self.loss_history) > 200:
                    self.loss_history.pop(0)
    
    
    def log_brain_activity(self, message: str) -> None:
        """Log brain activity to file for debugging."""
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_path = os.path.join(base_path, "brain_log.txt")
            with open(log_path, "a") as f:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

    def _get_generation_from_file(self, path: str) -> int:
        """
        Extract generation number from a brain file.
        
        Args:
            path: Path to the .pth file
            
        Returns:
            int: Generation number, or -1 if extraction fails
        """
        try:
            # We use map_location='cpu' to avoid GPU memory overhead just for checking
            # We assume the file is a dictionary checkpoint
            # Using weights_only=False because we need to read the dict structure
            try:
                checkpoint = torch.load(path, map_location='cpu', weights_only=False)
            except TypeError:
                checkpoint = torch.load(path, map_location='cpu')
                
            if isinstance(checkpoint, dict) and 'generation' in checkpoint:
                return checkpoint['generation']
        except Exception:
            pass
        return -1

    def load_brain(self) -> None:
        """
        Smart load: Find the latest available brain checkpoint.
        Scans all files and inspects their content to find the highest generation.
        """
        import re
        
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_dir = os.path.join(base_path, "assets", "models")
        
        candidates = [] # List of (generation, path, source_type)
        
        print("\n>> Scanning for save files...")
        
        if os.path.exists(model_dir):
            files = os.listdir(model_dir)
            
            # 1. Scan numbered checkpoints (FAST: Trust filename)
            for filename in files:
                match = re.match(r"arena_brain_gen_(\d+)\.pth", filename)
                if match:
                    gen_num = int(match.group(1))
                    full_path = os.path.join(model_dir, filename)
                    candidates.append((gen_num, full_path, "Checkpoint"))

            # 2. Inspect Standard Files (SLOW: Must read content)
            std_files = ["arena_brain.pth", "arena_brain_backup.pth"]
            for filename in std_files:
                if filename in files:
                    full_path = os.path.join(model_dir, filename)
                    print(f"   Inspecting {filename}...")
                    gen_num = self._get_generation_from_file(full_path)
                    if gen_num > 0:
                        candidates.append((gen_num, full_path, "Standard"))
        
        # Sort by generation descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        if not candidates:
            print("❌ No valid brain files found. Starting fresh (Gen 1).")
            self.log_brain_activity("No valid brain files found, starting fresh")
            return

        top_gen, top_path, top_type = candidates[0]
        print(f"✅ Best candidate found: {os.path.basename(top_path)} (Gen {top_gen})")
        
        # Attempt to load the best candidate
        try:
            print(f"📂 Loading {os.path.basename(top_path)}...")
            try:
                checkpoint = torch.load(top_path, map_location=device, weights_only=False)
            except TypeError:
                checkpoint = torch.load(top_path, map_location=device)
            
            self.policy_net.load_state_dict(checkpoint['model_state_dict'])
            self.target_net.load_state_dict(checkpoint['model_state_dict'])
            
            # Restore state
            if 'optimizer_state_dict' in checkpoint:
                self.trainer.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
            if 'steps_done' in checkpoint:
                self.trainer.steps_done = checkpoint['steps_done']
            if 'generation' in checkpoint:
                self.generation = checkpoint['generation']
            if 'kill_history' in checkpoint:
                self.engine.kill_history = collections.deque(checkpoint['kill_history'], maxlen=200)
            if 'reward_history' in checkpoint:
                self.reward_history = collections.deque(checkpoint['reward_history'], maxlen=200)
            if 'duration_history' in checkpoint:
                self.duration_history = collections.deque(checkpoint['duration_history'], maxlen=200)
            if 'global_kills_by_type' in checkpoint:
                self.engine.global_kills_by_type = checkpoint['global_kills_by_type']
            if 'hall_of_fame' in checkpoint:
                self.engine.hall_of_fame = checkpoint['hall_of_fame']
            if 'action_history' in checkpoint:
                self.action_history = checkpoint['action_history']
            if 'current_season' in checkpoint:
                self.engine.current_season = checkpoint['current_season']
            if 'auto_season_mode' in checkpoint:
                self.engine.auto_season_mode = checkpoint['auto_season_mode']
            if 'season_gens_counter' in checkpoint:
                self.engine.season_gens_counter = checkpoint['season_gens_counter']
            if 'cycle_number' in checkpoint:
                self.engine.cycle_number = checkpoint['cycle_number']
            if 'complete_cycle_performance' in checkpoint:
                self.engine.complete_cycle_performance = checkpoint['complete_cycle_performance']
            if 'gen_loss_history' in checkpoint:
                self.gen_loss_history = checkpoint['gen_loss_history']
            
            print(f"🚀 Simulation resumed at Generation {self.generation}")
            self.log_brain_activity(f"Successfully loaded brain from {top_path}")

        except Exception as e:
            print(f"❌ Failed to load {os.path.basename(top_path)}: {e}")
            self.log_brain_activity(f"Error loading from {top_path}: {e}")
            # Could implement fallback to next candidate here if needed
            print("Critical error loading best candidate. Please check file integrity.")

    def save_brain(self) -> None:
        """Save the AI brain to disk using atomic write pattern."""
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_dir = os.path.join(base_path, "assets", "models")
        if not os.path.exists(model_dir):
            os.makedirs(model_dir)
        
        brain_path = os.path.join(model_dir, "arena_brain.pth")
        backup_path = os.path.join(model_dir, "arena_brain_backup.pth")
        tmp_path = os.path.join(model_dir, "arena_brain.tmp")
        
        # 1. Backup existing brain before doing anything
        if os.path.exists(brain_path):
            try:
                import shutil
                shutil.copy2(brain_path, backup_path)
            except Exception as e:
                self.log_brain_activity(f"Warning: Failed to backup brain: {e}")
        
        # 2. Create checkpoint dictionary
        checkpoint = {
            'model_state_dict': self.policy_net.state_dict(),
            'optimizer_state_dict': self.trainer.optimizer.state_dict(),
            'steps_done': self.trainer.steps_done,
            'generation': self.generation,
            'kill_history': list(self.engine.kill_history),
            'reward_history': list(self.reward_history),
            'duration_history': list(self.duration_history),
            'global_kills_by_type': self.engine.global_kills_by_type,
            'hall_of_fame': self.engine.hall_of_fame,
            'action_history': self.action_history,
            'current_season': self.engine.current_season,
            'auto_season_mode': self.engine.auto_season_mode,
            'season_gens_counter': self.engine.season_gens_counter,
            'cycle_number': self.engine.cycle_number,
            'complete_cycle_performance': self.engine.complete_cycle_performance,
            'gen_loss_history': self.gen_loss_history
        }
        
        # 3. Atomic Save: Write to .tmp then rename
        try:
            torch.save(checkpoint, tmp_path)
            
            # Windows atomic replace is tricky, so we remove then rename
            if os.path.exists(brain_path):
                os.remove(brain_path)
            os.rename(tmp_path, brain_path)
            
            self.log_brain_activity(f"Brain saved successfully (Gen {self.generation})")
            
        except Exception as e:
            self.log_brain_activity(f"CRITICAL: Failed to save brain: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return

        # 4. Create Checkpoint (if needed)
        # We copy the SAFELY saved file, not the memory dict (to save serialization time/risk)
        if self.generation % 50 == 0:
            ckpt_name = f"arena_brain_gen_{self.generation}.pth"
            ckpt_path = os.path.join(model_dir, ckpt_name)
            try:
                import shutil
                shutil.copy2(brain_path, ckpt_path)
                self.log_brain_activity(f"Created checkpoint: {ckpt_name}")
            except Exception as e:
                self.log_brain_activity(f"Failed to create checkpoint: {e}")
        
        # Save statistics
        self.save_statistics()
    
    def save_statistics(self) -> None:
        """
        Calculates and saves detailed statistics to training_stats.csv.
        Matches the exact schema of the existing file to prevent corruption.
        """
        import csv
        from datetime import datetime
        
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_path = os.path.join(base_path, "training_stats.csv")
        file_exists = os.path.exists(csv_path)
        
        # 1. Calculate Aggregated Metrics
        
        # Loss
        avg_loss = self.gen_loss_history[-1] if self.gen_loss_history else 0.0
        
        # CV (Coefficient of Variation)
        cv = 0.0
        if len(self.engine.season_rewards_window) >= 2:
            rewards = list(self.engine.season_rewards_window)
            if np.mean(rewards) != 0:
                cv = np.std(rewards) / abs(np.mean(rewards))
        
        # Class Stats
        warriors = [a for a in self.engine.agents if a.role == ROLE_WARRIOR]
        scouts = [a for a in self.engine.agents if a.role == ROLE_SCOUT]
        healers = [a for a in self.engine.agents if a.role == ROLE_HEALER]
        
        alive_war = sum(1 for a in warriors if a.alive)
        alive_sco = sum(1 for a in scouts if a.alive)
        alive_hea = sum(1 for a in healers if a.alive)
        active_agents = alive_war + alive_sco + alive_hea
        deaths = NUM_AGENTS - active_agents
        
        # Rewards Min/Max
        all_rewards = [a.total_reward for a in self.engine.agents]
        max_reward = max(all_rewards) if all_rewards else 0.0
        min_reward = min(all_rewards) if all_rewards else 0.0
        
        # Helper for averages
        def safe_avg(lst, attr_func):
            if not lst: return 0.0
            return sum(attr_func(a) for a in lst) / len(lst)
            
        avg_reward_war = safe_avg(warriors, lambda a: a.total_reward)
        avg_reward_sco = safe_avg(scouts, lambda a: a.total_reward)
        avg_reward_hea = safe_avg(healers, lambda a: a.total_reward)
        
        avg_rew_heal_hea = safe_avg(healers, lambda a: a.reward_healing)
        avg_rew_combat_war = safe_avg(warriors, lambda a: a.reward_combat)
        avg_rew_res_sco = safe_avg(scouts, lambda a: a.reward_resource)
        
        # Weapon Kills (Current Gen)
        kills_sword = sum(a.kills_by_type[WEAPON_SWORD] for a in self.engine.agents)
        kills_bow = sum(a.kills_by_type[WEAPON_BOW] for a in self.engine.agents)
        kills_wand = sum(a.kills_by_type[WEAPON_WAND] for a in self.engine.agents)
        
        # Action Distribution (%)
        total_actions = sum(self.action_counts.values())
        if total_actions == 0: total_actions = 1
        
        move_acts = sum(self.action_counts.get(i, 0) for i in [ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT])
        attack_acts = self.action_counts.get(ACTION_ATTACK, 0)
        wait_acts = self.action_counts.get(ACTION_WAIT, 0)
        shout_acts = sum(self.action_counts.get(i, 0) for i in [ACTION_CRI_DANGER, ACTION_CRI_HEAL, ACTION_CRI_POTION])
        
        act_move_pct = (move_acts / total_actions) * 100
        act_attack_pct = (attack_acts / total_actions) * 100
        act_wait_pct = (wait_acts / total_actions) * 100
        act_shout_pct = (shout_acts / total_actions) * 100
        
        # Resources
        total_wood = sum(a.wood for a in self.engine.agents)
        total_iron = sum(a.iron for a in self.engine.agents)
        
        # Create Row Data (Matching EXACTLY the old CSV structure)
        # Header: Timestamp,Generation,Season,SeasonGen,AvgReward,MaxReward,MinReward,Kills,Kills_Sword,Kills_Bow,Kills_Wand,Deaths,ActiveAgents,Alive_War,Alive_Sco,Alive_Hea,Total_Wood,Total_Iron,Duration,Epsilon,Loss,CV,Gen/h,AvgReward_War,AvgReward_Sco,AvgReward_Hea,AvgRew_Combat_War,AvgRew_Res_Sco,AvgRew_Heal_Hea,Act_Move,Act_Attack,Act_Wait,Act_Shout
        
        row_data = {
            'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'Generation': self.generation,
            'Season': self.engine.current_season,
            'SeasonGen': self.engine.season_gens_counter,
            'AvgReward': f"{self.reward_history[-1]:.4f}" if self.reward_history else "0.0000",
            'MaxReward': f"{max_reward:.4f}",
            'MinReward': f"{min_reward:.4f}",
            'Kills': self.engine.current_gen_kills,
            'Kills_Sword': kills_sword,
            'Kills_Bow': kills_bow,
            'Kills_Wand': kills_wand,
            'Deaths': deaths,
            'ActiveAgents': active_agents,
            'Alive_War': alive_war,
            'Alive_Sco': alive_sco,
            'Alive_Hea': alive_hea,
            'Total_Wood': total_wood,
            'Total_Iron': total_iron,
            'Duration': self.gen_steps,  # Assuming Duration was steps
            'Epsilon': f"{self.trainer.get_epsilon():.4f}",
            'Loss': f"{avg_loss:.6f}",
            'CV': f"{cv:.4f}",
            'Gen/h': f"{self.cycles_per_hour:.2f}",
            'AvgReward_War': f"{avg_reward_war:.4f}",
            'AvgReward_Sco': f"{avg_reward_sco:.4f}",
            'AvgReward_Hea': f"{avg_reward_hea:.4f}",
            'AvgRew_Combat_War': f"{avg_rew_combat_war:.4f}",
            'AvgRew_Res_Sco': f"{avg_rew_res_sco:.4f}",
            'AvgRew_Heal_Hea': f"{avg_rew_heal_hea:.4f}",
            'Act_Move': f"{act_move_pct:.2f}",
            'Act_Attack': f"{act_attack_pct:.2f}",
            'Act_Wait': f"{act_wait_pct:.2f}",
            'Act_Shout': f"{act_shout_pct:.2f}"
        }
        
        fieldnames = [
            'Timestamp', 'Generation', 'Season', 'SeasonGen', 'AvgReward', 'MaxReward', 'MinReward',
            'Kills', 'Kills_Sword', 'Kills_Bow', 'Kills_Wand', 'Deaths', 'ActiveAgents',
            'Alive_War', 'Alive_Sco', 'Alive_Hea', 'Total_Wood', 'Total_Iron', 'Duration',
            'Epsilon', 'Loss', 'CV', 'Gen/h', 'AvgReward_War', 'AvgReward_Sco', 'AvgReward_Hea',
            'AvgRew_Combat_War', 'AvgRew_Res_Sco', 'AvgRew_Heal_Hea',
            'Act_Move', 'Act_Attack', 'Act_Wait', 'Act_Shout'
        ]
        
        try:
            with open(csv_path, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                # Only write header if file is empty (should usually exist)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row_data)
        except Exception as e:
            print(f"Error saving statistics: {e}")
    
    def run(self) -> None:
        """Main game loop."""
        running = True
        while running:
            events = pygame.event.get()
            
            # Handle UI events
            ui_result = self.ui_manager.handle_events(
                events, GRID_SIZE, CELL_SIZE, GRID_OFFSET_Y, self.engine.agents
            )
            
            if ui_result['quit']:
                running = False
                self.save_brain()
                break
            
            # Update parameters from sliders
            if ui_result['parameters_changed']:
                params = self.ui_manager.get_parameter_updates()
                self.env.wood_regrowth_rate = params['wood_regrowth']
                self.env.potion_spawn_rate = params['potion_spawn']
                self.max_steps_per_gen = params['gen_timeout']
            
            # Run simulation steps
            steps_to_run = 1 if self.renderer.visuals_enabled else 1000
            
            for _ in range(steps_to_run):
                if self.gen_steps % 10 == 0:
                    self.env.update_environment()
                
                self.step_agents_batch()
                self.gen_steps += 1
                
                alive_agents = [a for a in self.engine.agents if a.alive]
                
                if self.renderer.visuals_enabled:
                    self.renderer.update_particles()
                
                # Handle events during fast simulation
                if self.gen_steps % 100 == 0:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            running = False
                            self.save_brain()
                            return
                        self.ui_manager.buttons['visuals'].handle_event(event)
                    
                    if self.renderer.visuals_enabled:
                        break
                
                if len(alive_agents) <= 1 or self.gen_steps >= self.max_steps_per_gen:
                    break
            
            # Rendering
            ui_state = self.ui_manager.get_ui_state(
                self.generation, self.gen_steps, self.max_steps_per_gen,
                self.engine.global_kills_by_type, self.engine.kill_history,
                self.reward_history, self.duration_history, self.gen_loss_history,
                self.cycles_per_hour, self.trainer.get_epsilon(),
                self.engine.hall_of_fame, self.action_history,
                self.engine.current_season, self.engine.auto_season_mode,
                self.engine.cycle_number, self.engine.season_gens_counter,
                self.engine.complete_cycle_performance, self.engine.get_convergence_info(),
                self.engine.agents, self.ui_manager.selected_agent, self.engine.predators
            )
            
            self.renderer.render_frame(
                self.env, self.engine.agents, self.engine.predators,
                ui_state, self.ui_manager.selected_agent
            )
            
            # Update target network
            if self.trainer.steps_done % TARGET_UPDATE == 0:
                self.target_net.load_state_dict(self.policy_net.state_dict())
            
            # Check for generation end
            if len(alive_agents) <= 1 or self.gen_steps >= self.max_steps_per_gen:
                self._handle_generation_end()
        
        self.renderer.cleanup()
    
    def _handle_generation_end(self) -> None:
        """
        Handle end-of-generation tasks.
        
        Tasks include:
        1. Recording statistics (duration, rewards, kills, action distribution).
        2. Updating Hall of Fame.
        3. Managing Season progression (auto-cycling).
        4. Saving the brain and stats.
        5. Resetting the environment for the next generation.
        """
        # Record statistics
        self.duration_history.append(self.gen_steps)
        
        if self.engine.agents:
            total_rewards = [a.total_reward for a in self.engine.agents]
            gen_avg_reward = sum(total_rewards) / len(total_rewards)
            self.reward_history.append(gen_avg_reward)
            self.engine.season_rewards_window.append(gen_avg_reward)  # For convergence
        
        # Calculate and store average loss for this generation
        avg_loss = 0.0
        if self.current_gen_loss_count > 0:
            avg_loss = self.current_gen_loss_sum / self.current_gen_loss_count
        self.gen_loss_history.append(avg_loss)
        
        # Reset loss accumulators
        self.current_gen_loss_sum = 0.0
        self.current_gen_loss_count = 0
        
        self.engine.kill_history.append(self.engine.current_gen_kills)
        
        # Record action distribution
        total_actions = sum(self.action_counts.values())
        if total_actions > 0:
            action_distribution = {k: v / total_actions for k, v in self.action_counts.items()}
            self.action_history.append(action_distribution)
            if len(self.action_history) > 200:
                self.action_history.pop(0)
        
        # Update performance metrics (Generations per Hour)
        now = time.time()
        self.gen_timestamps.append(now)
        if len(self.gen_timestamps) > 1:
            time_diff = self.gen_timestamps[-1] - self.gen_timestamps[0]
            if time_diff > 0:
                self.cycles_per_hour = ((len(self.gen_timestamps) - 1) / time_diff) * 3600
        
        self.engine.update_hall_of_fame(self.generation)
        self.engine.season_gens_counter += 1
        
        # Auto-cycle seasons based on convergence or max generations
        if self.engine.auto_season_mode:
            should_change = False
            reason = ""
            
            if self.engine.season_gens_counter >= MIN_GENS_PER_SEASON and self.engine.season_gens_counter % 10 == 0:
                print(f"  Season: {self.engine.current_season} | Gen {self.engine.season_gens_counter}/{MAX_GENS_PER_SEASON}")
                self.engine.is_season_converged()
            
            if self.engine.season_gens_counter >= MAX_GENS_PER_SEASON:
                should_change = True
                reason = f"Max {MAX_GENS_PER_SEASON} gens reached"
            elif self.engine.season_gens_counter >= MIN_GENS_PER_SEASON and self.engine.is_season_converged():
                should_change = True
                reason = "Converged (reward plateau)"
            
            if should_change:
                print(f"  → Season Change Trigger: {reason}")
                self.engine.cycle_to_next_season()
                self._sync_ui_with_engine()
        
        print(f"Generation {self.generation} finished. Steps: {self.gen_steps} | Speed: {int(self.cycles_per_hour)} Gen/h | Season: {self.engine.current_season} ({self.engine.season_gens_counter} gens)")
        
        self.save_brain()
        self.generation += 1
        self.env.generate_map()
        self.engine.spawn_agents()
        self.engine.spawn_predators()
        self.gen_steps = 0
        self.action_counts = {i: 0 for i in range(NUM_ACTIONS)}
