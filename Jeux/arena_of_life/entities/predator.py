"""
Predator entity for Arena of Life.

Simple AI bot that chases the nearest agent.
Used as a threat to drive collective behavior.
"""
import random
import numpy as np
from config.constants import GRID_SIZE, CELL_SIZE, WEAPON_FISTS

class Predator:
    """
    A simple aggressive bot that chases agents.
    """
    def __init__(self, id: int, x: int, y: int):
        self.id = id
        self.x = x
        self.y = y
        self.color = (255, 0, 0) # Red
        self.hp = 140 # Buffed to match Agents (Boss Mode)
        self.max_hp = 140
        self.damage = 14 # Nerfed from 20 (Balance adjustment)
        self.alive = True
        self.weapon = WEAPON_FISTS # Visual only
        self.tick_counter = 0 # For speed control

        
    def update(self, agents, env):
        """
        Move towards nearest alive agent and attack.
        """
        if not self.alive: return
        
        # FATIGUE MECHANIC: Predators only move every 2nd tick
        self.tick_counter += 1
        if self.tick_counter % 2 != 0:
            return

        
        # Find nearest agent
        target = None
        min_dist = 9999
        
        for agent in agents:
            if not agent.alive: continue
            
            # Toroidal distance
            dx = abs(agent.x - self.x)
            dy = abs(agent.y - self.y)
            dx = min(dx, GRID_SIZE - dx)
            dy = min(dy, GRID_SIZE - dy)
            dist = dx + dy
            
            if dist < min_dist:
                min_dist = dist
                target = agent
        
        if target:
            # Attack if close
            if min_dist <= 1:
                target.take_damage(self.damage)
                return # Action done
            
            # Move towards target
            # Simple greedy movement
            move_x, move_y = 0, 0
            
            # Determine direction (handling wrap-around)
            dx = target.x - self.x
            dy = target.y - self.y
            
            # Adjust for wrap-around shortest path
            if abs(dx) > GRID_SIZE / 2:
                dx = -dx # Go the other way
            if abs(dy) > GRID_SIZE / 2:
                dy = -dy
                
            if abs(dx) > abs(dy):
                move_x = 1 if dx > 0 else -1
            else:
                move_y = 1 if dy > 0 else -1
                
            nx = (self.x + move_x) % GRID_SIZE
            ny = (self.y + move_y) % GRID_SIZE
            
            if env.is_walkable(nx, ny):
                # Check if blocked by another predator (simple check)
                self.x, self.y = nx, ny
