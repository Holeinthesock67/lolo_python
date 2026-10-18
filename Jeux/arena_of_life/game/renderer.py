"""
Renderer for Arena of Life.

This module handles all Pygame and graphics operations including:
- Pygame initialization
- Sound loading and playback
- Particle effects
- Frame rendering coordination
"""
import pygame
import os
from typing import List, Dict, Any, Optional

from config.constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT, FPS, CELL_SIZE,
    WEAPON_FISTS, WEAPON_SWORD, WEAPON_BOW, WEAPON_WAND
)
from ui import draw_grid, draw_ui


class Renderer:
    """
    Handles all rendering and visual effects.
    
    Attributes:
        screen (pygame.Surface): The main display surface
        clock (pygame.Clock): For FPS management
        font (pygame.font.Font): Small font for UI text
        title_font (pygame.font.Font): Large font for headers
        sounds (dict): Weapon sound effects
        particles (list): Active particle effects
        visuals_enabled (bool): Whether rendering is active (turbo mode toggle)
    """
    
    def __init__(self) -> None:
        """Initialize Pygame and create the renderer."""
        pygame.init()
        pygame.mixer.init()
        
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Arena of Life - AI Battle Royale")
        
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 14)
        self.title_font = pygame.font.SysFont("Arial", 18, bold=True)
        
        self.sounds: Dict[int, pygame.mixer.Sound] = {}
        self.load_sounds()
        
        self.particles: List[List] = []  # [x, y, color, radius, max_radius]
        self.shout_particles: List[List] = []  # [x, y, shout_type, lifetime]
        self.visuals_enabled = False  # Start with visuals OFF for faster initial training
        self.sound_enabled = False  # Start with sound OFF by default
    
    def load_sounds(self) -> None:
        """Load game sound effects from assets/sounds/."""
        try:
            # Get base path (go up from game/renderer.py to project root)
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sound_dir = os.path.join(base_path, "assets", "sounds")
            
            self.sounds[WEAPON_FISTS] = pygame.mixer.Sound(os.path.join(sound_dir, "punch.wav"))
            self.sounds[WEAPON_SWORD] = pygame.mixer.Sound(os.path.join(sound_dir, "sword.wav"))
            self.sounds[WEAPON_BOW] = pygame.mixer.Sound(os.path.join(sound_dir, "bow.wav"))
            self.sounds[WEAPON_WAND] = pygame.mixer.Sound(os.path.join(sound_dir, "magic.wav"))
        except Exception as e:
            print(f"Warning: Sound files not found ({e}). Running silently.")
    
    def toggle_visuals(self) -> bool:
        """
        Toggle visual rendering on/off.
        
        Returns:
            bool: New state of visuals (True = ON, False = OFF)
        """
        self.visuals_enabled = not self.visuals_enabled
        return self.visuals_enabled
    
    def toggle_sound(self) -> bool:
        """
        Toggle sound on/off.
        
        Returns:
            bool: New state of sound (True = ON, False = OFF)
        """
        self.sound_enabled = not self.sound_enabled
        return self.sound_enabled
    
    def trigger_kill_effect(self, x: int, y: int, weapon_type: int) -> None:
        """
        Trigger visual and audio effects when an agent kills another.
        
        Args:
            x, y (int): Grid position where the kill occurred
            weapon_type (int): Type of weapon used (determines color and sound)
        """
        # Sound (only if enabled)
        if self.sound_enabled and weapon_type in self.sounds:
            self.sounds[weapon_type].play()
        
        # Visual Particle (only if visuals enabled)
        if self.visuals_enabled:
            color = (255, 255, 255)
            if weapon_type == WEAPON_SWORD:
                color = (0, 0, 255)  # Blue Flash
            elif weapon_type == WEAPON_BOW:
                color = (0, 255, 0)  # Green Flash
            elif weapon_type == WEAPON_WAND:
                color = (255, 0, 255)  # Purple Flash
            elif weapon_type == WEAPON_FISTS:
                color = (200, 200, 200)  # Grey Flash
            
            # [x, y, color, radius, max_radius]
            px = x * CELL_SIZE + CELL_SIZE // 2
            py = y * CELL_SIZE + CELL_SIZE // 2
            self.particles.append([px, py, color, 2, 20])
    
    def trigger_shout_effect(self, x: int, y: int, shout_type: int) -> None:
        """
        Trigger visual effect when an agent shouts.
        
        Args:
            x, y (int): Grid position where the shout occurred
            shout_type (int): Type of shout (DANGER, HEAL, POTION)
        """
        if self.visuals_enabled:
            px = x * CELL_SIZE + CELL_SIZE // 2
            py = y * CELL_SIZE + CELL_SIZE // 2
            # [x, y, shout_type, lifetime]
            self.shout_particles.append([px, py, shout_type, 30])  # 30 frames lifetime
    
    def update_particles(self) -> None:
        """Update particle effect animations (expanding circles on kills)."""
        for p in self.particles[:]:
            p[3] += 2  # Increase radius
            if p[3] >= p[4]:
                self.particles.remove(p)
        
        # Update shout particles
        for p in self.shout_particles[:]:
            p[3] -= 1  # Decrease lifetime
            if p[3] <= 0:
                self.shout_particles.remove(p)
    
    def render_frame(self, env: Any, agents: List, predators: List,
                    ui_state: Dict, selected_agent: Optional[Any]) -> None:
        """
        Render a complete frame with grid and UI.
        
        Args:
            env: The game environment
            agents: List of agents
            predators: List of predators
            ui_state: Dictionary containing all UI state for rendering
            selected_agent: Currently selected agent (or None)
        """
        if not self.visuals_enabled:
            # In turbo mode, only render UI
            self.render_ui_only(ui_state)
            return
        
        # Draw grid with agents and effects
        draw_grid(self.screen, env, agents, predators, self.particles, self.shout_particles, selected_agent)
        
        # Draw UI
        draw_ui(
            self.screen, self.font, self.title_font,
            ui_state['sliders'],
            ui_state['btn_visuals'],
            agents,
            selected_agent,
            ui_state['generation'],
            ui_state['gen_steps'],
            ui_state['max_steps_per_gen'],
            ui_state['global_kills_by_type'],
            ui_state['kill_history'],
            ui_state['reward_history'],
            ui_state['duration_history'],
            ui_state['loss_history'],
            ui_state['cycles_per_hour'],
            ui_state['epsilon'],
            ui_state['hall_of_fame'],
            ui_state['action_history'],
            ui_state['btn_reset_epsilon'],
            ui_state['btn_clear_hof'],
            ui_state['season_buttons'],
            ui_state['current_season'],
            ui_state['auto_season_mode'],
            ui_state['cycle_number'],
            ui_state['season_gens_counter'],
            ui_state['complete_cycle_performance'],
            ui_state['convergence_info'],
            ui_state.get('btn_sound'),
            predators
        )
        
        pygame.display.flip()
        self.clock.tick(FPS)
    
    def render_ui_only(self, ui_state: Dict) -> None:
        """
        Render only the UI (turbo mode - no grid/agents).
        
        Args:
            ui_state: Dictionary containing all UI state for rendering
        """
        self.screen.fill((0, 0, 0))  # Clear screen
        
        # Get dummy agents list (for UI stats display)
        agents = ui_state.get('agents', [])
        selected_agent = ui_state.get('selected_agent', None)
        
        draw_ui(
            self.screen, self.font, self.title_font,
            ui_state['sliders'],
            ui_state['btn_visuals'],
            agents,
            selected_agent,
            ui_state['generation'],
            ui_state['gen_steps'],
            ui_state['max_steps_per_gen'],
            ui_state['global_kills_by_type'],
            ui_state['kill_history'],
            ui_state['reward_history'],
            ui_state['duration_history'],
            ui_state['loss_history'],
            ui_state['cycles_per_hour'],
            ui_state['epsilon'],
            ui_state['hall_of_fame'],
            ui_state['action_history'],
            ui_state['btn_reset_epsilon'],
            ui_state['btn_clear_hof'],
            ui_state['season_buttons'],
            ui_state['current_season'],
            ui_state['auto_season_mode'],
            ui_state['cycle_number'],
            ui_state['season_gens_counter'],
            ui_state['complete_cycle_performance'],
            ui_state['convergence_info'],
            ui_state.get('btn_sound'),
            ui_state.get('predators', [])
        )
        
        pygame.display.flip()
    
    def cleanup(self) -> None:
        """Clean up Pygame resources."""
        pygame.quit()
