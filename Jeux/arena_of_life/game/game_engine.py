"""
Game Engine for Arena of Life.

This module contains the core game logic including agent spawning,
combat resolution, resource collection, season management, and statistics tracking.
"""
import random
import numpy as np
import collections
from typing import List, Dict, Tuple, Optional, Any

from config.constants import *
from environment.environment import Environment
from entities.agent import Agent
from entities.predator import Predator
from game.spatial_grid import SpatialGrid

class GameEngine:
    """
    Core game logic engine.
    
    Handles:
    - Agent and predator spawning
    - Combat resolution
    - Resource collection
    - Reward calculation
    - Season system
    - Hall of Fame tracking
    - Game statistics
    """
    
    def __init__(self, env: Environment) -> None:
        """
        Initialize the game engine.
        
        Args:
            env (Environment): The game environment
        """
        self.env = env
        self.agents: List[Agent] = []
        self.predators: List[Predator] = []
        self.spatial_grid = SpatialGrid(GRID_SIZE, cell_size=10)
        
        # Statistics
        self.global_kills_by_type = {
            WEAPON_FISTS: 0,
            WEAPON_SWORD: 0,
            WEAPON_BOW: 0,
            WEAPON_WAND: 0
        }
        self.current_gen_kills = 0
        self.hall_of_fame: List[Dict] = []
        self.kill_history = collections.deque(maxlen=200)
        
        # Season System
        self.current_season = SEASON_CYCLE[0]
        self.auto_season_mode = True
        self.season_gens_counter = 0
        self.season_rewards_window = collections.deque(maxlen=CONVERGENCE_WINDOW)
        self.cycle_number = 1
        self.season_cycle_rewards: List[float] = []
        self.complete_cycle_performance: List[float] = []
        
    def spawn_agents(self) -> List[Agent]:
        """
        Spawn a new generation of agents with random positions and stats.
        
        Returns:
            List[Agent]: The spawned agents
        """
        self.agents = []
        self.spatial_grid.clear()
        
        for i in range(NUM_AGENTS):
            while True:
                x, y = random.randint(0, GRID_SIZE-1), random.randint(0, GRID_SIZE-1)
                if self.env.grid[x, y] == TILE_EMPTY:
                    agent = Agent(i, x, y)
                    self.agents.append(agent)
                    self.spatial_grid.insert(agent, x, y)
                    break
        
        self.current_gen_kills = 0
        return self.agents
    
    def spawn_predators(self) -> List[Predator]:
        """
        Spawn enemy predators based on current season.
        
        Returns:
            List[Predator]: The spawned predators
        """
        self.predators = []
        season_idx = SEASON_CYCLE.index(self.current_season)
        num_predators = PREDATORS_BY_SEASON.get(season_idx, 10)
        
        for i in range(num_predators):
            while True:
                x, y = random.randint(0, GRID_SIZE-1), random.randint(0, GRID_SIZE-1)
                if self.env.grid[x, y] == TILE_EMPTY:
                    predator = Predator(i, x, y)
                    self.predators.append(predator)
                    self.spatial_grid.insert(predator, x, y)
                    break
        
        return self.predators
    
    def apply_season(self, season_name: str, reset_stats: bool = True) -> None:
        """
        Apply a season's parameters to the environment.
        
        Args:
            season_name (str): Name of the season
            reset_stats (bool): Whether to reset season counters
        """
        if season_name not in SEASON_PRESETS:
            print(f"Warning: Unknown season '{season_name}'")
            return
        
        preset = SEASON_PRESETS[season_name]
        self.current_season = season_name
        
        # Update environment parameters
        self.env.wood_regrowth_rate = preset['wood_regrowth']
        self.env.potion_spawn_rate = preset['potion_spawn']
        # Note: gen_timeout is handled by ArenaGame, not GameEngine
        
        # Reset season tracking if requested
        if reset_stats:
            self.season_gens_counter = 0
            self.season_rewards_window.clear()
    
    def is_season_converged(self) -> bool:
        """
        Check if AI has converged in current season (reward plateau).
        
        Returns:
            bool: True if converged, False otherwise
        """
        if len(self.season_rewards_window) < CONVERGENCE_WINDOW:
            return False
        
        rewards = list(self.season_rewards_window)
        mean_reward = np.mean(rewards)
        std_reward = np.std(rewards)
        
        if mean_reward == 0:
            return False
        
        cv = std_reward / abs(mean_reward)
        converged = cv < CONVERGENCE_THRESHOLD
        
        status = "✓ CONVERGED" if converged else "○ Not converged"
        print(f"    Convergence Check: CV={cv:.4f} ({cv*100:.2f}%) | Threshold={CONVERGENCE_THRESHOLD*100:.1f}% | {status}")
        
        return converged
    
    def get_convergence_info(self) -> str:
        """
        Get formatted convergence status string for UI display.
        
        Returns:
            str: Convergence status text
        """
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
        if self.current_season == SEASON_CYCLE[-1]:  # Winter
            if len(self.season_cycle_rewards) > 0:
                cycle_avg = np.mean(self.season_cycle_rewards)
                self.complete_cycle_performance.append(cycle_avg)
                print(f"\n=== CYCLE {self.cycle_number} COMPLETE ===")
                print(f"    Cycle Avg Reward: {cycle_avg:.2f}")
                print(f"    Season Breakdown: {[f'{r:.1f}' for r in self.season_cycle_rewards]}")
                self.season_cycle_rewards = []
            self.cycle_number += 1
        
        print(f"Season Change: {self.current_season} → {next_season} (After {self.season_gens_counter} gens)")
        self.apply_season(next_season)
    
    def update_hall_of_fame(self, global_generation: int) -> None:
        """Update the Hall of Fame with top agents from current generation."""
        # Identify top agents of this generation
        sorted_agents = sorted(self.agents, key=lambda a: (a.kills, a.steps_alive), reverse=True)
        top_gen_agents = sorted_agents[:3]
        
        for agent in top_gen_agents:
            if agent.total_reward < 10:
                continue  # Only significant performers
            
            # Create snapshot
            snapshot = {
                'gen': global_generation,  # Store Global Generation
                'id': agent.id,
                'kills': agent.kills,
                'steps': agent.steps_alive,
                'weapon': agent.weapon,
                'reward': agent.total_reward,
                'kills_by_type': agent.kills_by_type.copy(),
                'stats': {
                    'str': agent.strength,
                    'prc': agent.precision,
                    'mag': agent.magic,
                    'hp': agent.max_hp,
                    'stam': agent.stamina
                }
            }
            
            self.hall_of_fame.append(snapshot)
        
        # Sort Hall of Fame and keep top 3 All-Time
        self.hall_of_fame.sort(key=lambda x: x['reward'], reverse=True)
        self.hall_of_fame = self.hall_of_fame[:3]
    
    def get_agent_at(self, x: int, y: int) -> Optional[Agent]:
        """
        Get the agent at a specific position.
        
        Args:
            x, y (int): Grid coordinates
            
        Returns:
            Optional[Agent]: The agent at the position, or None
        """
        for a in self.agents:
            if a.alive and a.x == x and a.y == y:
                return a
        return None
    
    def update_predators(self) -> None:
        """Update all predators."""
        for pred in self.predators:
            if pred.alive:
                old_x, old_y = pred.x, pred.y
                pred.update(self.agents, self.env)
                # Update spatial grid if predator moved
                if (pred.x != old_x or pred.y != old_y):
                    self.spatial_grid.update_position(pred, old_x, old_y, pred.x, pred.y)
    
    def apply_action(self, agent: Agent, action: int, alive_agents: List[Agent]) -> Tuple[float, Optional[Dict]]:
        """
        Apply an action for a single agent and return the reward and kill event.
        
        Args:
            agent (Agent): The agent performing the action
            action (int): The action to perform
            alive_agents (List[Agent]): List of currently alive agents (for healer passive)
            
        Returns:
            Tuple[float, Optional[Dict]]: (reward, kill_event)
                kill_event is None or {'x': int, 'y': int, 'weapon': int}
        """
        reward = 0.2  # Base survival reward (Doubled from 0.1)
        kill_event = None
        
        dx, dy = 0, 0
        if action == ACTION_UP:
            dy = -1
        elif action == ACTION_DOWN:
            dy = 1
        elif action == ACTION_LEFT:
            dx = -1
        elif action == ACTION_RIGHT:
            dx = 1
        
        # Movement
        if dx != 0 or dy != 0:
            old_x, old_y = agent.x, agent.y
            # Toroidal Movement: Wrap around edges
            nx = (agent.x + dx) % GRID_SIZE
            ny = (agent.y + dy) % GRID_SIZE
            
            if self.env.is_walkable(nx, ny):
                target_agent = self.get_agent_at(nx, ny)
                if target_agent:
                    # Friendly Fire Disabled - collision penalty
                    reward -= 0.1
                else:
                    agent.x, agent.y = nx, ny
                    # Update spatial grid
                    self.spatial_grid.update_position(agent, old_x, old_y, nx, ny)
                    
                    # --- SCOUT SWIFTNESS (Speed Buff) ---
                    if agent.role == ROLE_SCOUT and random.random() < 0.20:
                        # 20% chance to move AGAIN in same direction
                        sx, sy = (agent.x + dx) % GRID_SIZE, (agent.y + dy) % GRID_SIZE
                        if self.env.is_walkable(sx, sy) and not self.get_agent_at(sx, sy):
                            old_sx, old_sy = agent.x, agent.y
                            agent.x, agent.y = sx, sy
                            self.spatial_grid.update_position(agent, old_sx, old_sy, sx, sy)
                    # ------------------------------------
                    
                    # Resource collection
                    tile = self.env.grid[nx, ny]
                    if tile == TILE_WOOD:
                        agent.wood += 1
                        self.env.grid[nx, ny] = TILE_EMPTY
                        reward += 5 # Nerfed to 5 (Scarcity Value)
                        if agent.role == ROLE_SCOUT:
                            reward += 2  # Bonus 2 = Total 7 pts (Nerfed from 15)

                        agent.reward_resource += reward
                    elif tile == TILE_IRON:
                        agent.iron += 1
                        self.env.grid[nx, ny] = TILE_EMPTY
                        reward += 5 # Nerfed to 5
                        if agent.role == ROLE_SCOUT:
                            reward += 2  # Total 7 pts

                        agent.reward_resource += reward
                    elif tile == TILE_POTION_HEALTH:
                        agent.hp = min(agent.max_hp, agent.hp + POTION_HEAL_AMOUNT + agent.magic)
                        self.env.grid[nx, ny] = TILE_EMPTY
                        reward += 2
                    elif tile == TILE_POTION_ENERGY:
                        agent.stamina = min(100, agent.stamina + POTION_STAMINA_AMOUNT)
                        self.env.grid[nx, ny] = TILE_EMPTY
                        reward += 2
                    elif tile == TILE_POTION_MAGIC:
                        agent.magic += POTION_MAGIC_AMOUNT
                        self.env.grid[nx, ny] = TILE_EMPTY
                        reward += 20
                        if agent.role == ROLE_HEALER:
                            reward += 50  # Huge buff for Healers
            else:
                # Hit Wall
                reward -= 0.1
        
        # Attack
        elif action == ACTION_ATTACK:
            attack_result = self._handle_attack(agent)
            reward += attack_result['reward']
            if attack_result.get('kill'):
                kill_event = attack_result['kill']
        
        # Wait / Craft
        elif action == ACTION_WAIT:
            # Simple wait / recover small stamina
            agent.stamina = min(100, agent.stamina + 2)
            reward += 0.05
        
        # Shout / Communicate
        elif action in [ACTION_CRI_DANGER, ACTION_CRI_HEAL, ACTION_CRI_POTION]:
            cost = 2
            if agent.stamina >= cost and agent.shout_cooldown == 0:
                agent.stamina -= cost
                agent.shout_cooldown = 10  # Set cooldown to 10 steps
                
                # Context-Aware Reward Calculation
                shout_reward, context_valid = self._check_shout_context(agent, action)
                
                reward += shout_reward
                agent.reward_shout += shout_reward
                
                kill_event = {
                    'type': 'shout',
                    'x': agent.x,
                    'y': agent.y,
                    'agent_id': agent.id,
                    'shout_type': action
                }
            else:
                reward -= 0.1 # Penalty for trying to shout without stamina or on cooldown
        
        # Healer Passive: Heal Nearby Allies
        if agent.role == ROLE_HEALER and agent.alive:
            heal_reward = self._handle_healer_passive(agent, alive_agents)
            reward += heal_reward
            agent.reward_healing += heal_reward
        
        # Decrement cooldown
        if agent.shout_cooldown > 0:
            agent.shout_cooldown -= 1
        
        agent.steps_alive += 1
        return reward, kill_event
    
    def _handle_attack(self, agent: Agent) -> Dict:
        """
        Handle attack action using spatial grid for optimized target finding.
        
        Args:
            agent (Agent): The attacking agent
            
        Returns:
            Dict: {'reward': float, 'kill': Optional[Dict]}
                kill contains {'x': int, 'y': int, 'weapon': int} if a kill occurred
        """
        damage = 0
        range_val = 1
        cost = 5
        
        # Calculate weapon stats
        if agent.weapon == WEAPON_FISTS:
            damage = 5 + (agent.strength * 0.5)
            cost = 2
        elif agent.weapon == WEAPON_SWORD:
            damage = SWORD_DAMAGE_BASE + agent.strength
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
            damage = 6 + (agent.magic * 0.5)  # Nerfed from 12 + magic
            cost = 8  # Increased from 6
        
        if agent.stamina < cost:
            return {'reward': -1, 'kill': None}
        
        agent.stamina -= cost
        
        # Use spatial grid to find nearby targets (OPTIMIZED!)
        nearby_entities = self.spatial_grid.get_entities_in_range(agent.x, agent.y, range_val)
        
        target = None
        min_dist = 999
        
        # Prioritize predators
        for entity in nearby_entities:
            if isinstance(entity, Predator) and entity.alive and entity is not agent:
                dist = self._manhattan_distance(agent.x, agent.y, entity.x, entity.y)
                if dist <= range_val and dist < min_dist:
                    min_dist = dist
                    target = entity
        
        # If no predator, check agents (but no damage, just for avoiding wasted attack penalty)
        if not target:
            for entity in nearby_entities:
                if isinstance(entity, Agent) and entity.alive and entity is not agent:
                    dist = self._manhattan_distance(agent.x, agent.y, entity.x, entity.y)
                    if dist <= range_val and dist < min_dist:
                        min_dist = dist
                        target = entity
        
        if target:
            if isinstance(target, Predator):
                target.hp -= damage
                
                # REWARD: Damage Dealt (Consistency > Luck)
                # 5 pts per hit to encourage fighting even if no kill
                reward = 5 
                agent.reward_combat += reward
                
                if target.hp <= 0:
                    target.alive = False
                    self.spatial_grid.remove(target)
                    
                    # REWARD: Kill (Capped to avoid "Lottery")
                    kill_bonus = 100 # Capped from 500
                    if agent.role == ROLE_WARRIOR:
                        kill_bonus += 200  # Warrior Bonus (Specialist) remains high
                    
                    reward += kill_bonus
                    agent.reward_combat += kill_bonus
                    
                    # Track kills
                    agent.kills += 1
                    agent.kills_by_type[agent.weapon] += 1
                    self.global_kills_by_type[agent.weapon] += 1
                    self.current_gen_kills += 1
                    
                    # Return kill event for sound/visual effects
                    return {
                        'reward': reward,
                        'kill': {'type': 'kill', 'x': target.x, 'y': target.y, 'weapon': agent.weapon}
                    }
                return {'reward': reward, 'kill': None}
            else:
                # Ally hit - no damage (friendly fire off), no penalty
                return {'reward': 0, 'kill': None}
        else:
            return {'reward': -0.5, 'kill': None}  # Wasted attack
    
    def _handle_healer_passive(self, healer: Agent, alive_agents: List[Agent]) -> float:
        """
        Handle healer's passive healing ability.
        
        Uses spatial grid to efficiently find nearby allies.
        
        Args:
            healer (Agent): The healer agent
            alive_agents (List[Agent]): All alive agents (unused in optimized version but kept for signature compatibility)
            
        Returns:
            float: Reward for healing
        """
        heal_range = 2
        heal_amount = HEALER_PASSIVE_BASE_HEAL + (healer.magic * 0.5)
        allies_healed = 0
        
        # Use spatial grid for O(1) lookup instead of O(N) scan of all agents
        nearby_entities = self.spatial_grid.get_entities_in_range(healer.x, healer.y, heal_range)
        
        for entity in nearby_entities:
            # Check if entity is an ally agent (not self, not predator)
            if isinstance(entity, Agent) and entity is not healer and entity.alive:
                if entity.hp < entity.max_hp:
                    entity.hp = min(entity.max_hp, entity.hp + heal_amount)
                    allies_healed += 1
        
        if allies_healed > 0:
            return allies_healed * 2  # MEGA NERF: 30 -> 2 (Prevent AFK farming)

        return 0
    
    def _manhattan_distance(self, x1: int, y1: int, x2: int, y2: int) -> int:
        """
        Calculate toroidal Manhattan distance.
        
        Args:
            x1, y1, x2, y2 (int): Two positions
            
        Returns:
            int: Toroidal distance
        """
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        dx = min(dx, GRID_SIZE - dx)
        dy = min(dy, GRID_SIZE - dy)
        return dx + dy

    def _check_shout_context(self, agent: Agent, shout_type: int) -> Tuple[float, bool]:
        """
        Verify if a shout is relevant and heard.
        
        Args:
            agent (Agent): Shouting agent
            shout_type (int): Type of shout
            
        Returns:
            Tuple[float, bool]: (Reward, IsValid)
        """
        # 1. Check Audience (Is anyone listening?)
        nearby_entities = self.spatial_grid.get_entities_in_range(agent.x, agent.y, COMM_AUDIBLE_RANGE)
        has_audience = False
        for entity in nearby_entities:
            if isinstance(entity, Agent) and entity is not agent and entity.alive:
                has_audience = True
                break
        
        if not has_audience:
            return REWARD_SHOUT_ISOLATED, False

        # 2. Check Context (Is the shout true/useful?)
        context_valid = False
        
        if shout_type == ACTION_CRI_DANGER:
            # Valid if Predator in Vision
            view_entities = self.spatial_grid.get_entities_in_range(agent.x, agent.y, VISION_RANGE)
            for entity in view_entities:
                if isinstance(entity, Predator) and entity.alive:
                    context_valid = True
                    break
                    
        elif shout_type == ACTION_CRI_HEAL:
            # Valid if injured OR is a Healer advertising to an INJURED ally nearby
            if agent.hp < (agent.max_hp * 0.5):
                context_valid = True
            elif agent.role == ROLE_HEALER:
                # Must have an injured ally within short range to justify shouting "HEAL HERE"
                nearby = self.spatial_grid.get_entities_in_range(agent.x, agent.y, 5) # Short range check
                for entity in nearby:
                    if isinstance(entity, Agent) and entity is not agent and entity.alive:
                        if entity.hp < entity.max_hp * 0.8: # Ally is actually hurt
                            context_valid = True
                            break
                
        elif shout_type == ACTION_CRI_POTION:
            # Valid if Potion nearby
            # Note: TILE_POTION_XX are in env.grid. We check nearby tiles.
            # Grid check is efficient around agent
            r = VISION_RANGE
            x_min, x_max = agent.x - r, agent.x + r
            y_min, y_max = agent.y - r, agent.y + r
            
            for tx in range(x_min, x_max + 1):
                for ty in range(y_min, y_max + 1):
                    nx, ny = tx % GRID_SIZE, ty % GRID_SIZE
                    tile = self.env.grid[nx, ny]
                    if tile in [TILE_POTION_HEALTH, TILE_POTION_ENERGY, TILE_POTION_MAGIC]:
                        context_valid = True
                        break
                if context_valid: break

        if context_valid:
            return REWARD_SHOUT_SUCCESS, True
        else:
            return REWARD_SHOUT_FAIL, False

