"""
UI Manager for Arena of Life.

This module handles all user interface elements including:
- Widget creation and management (sliders, buttons)
- Event handling
- UI state tracking
"""
import pygame
from typing import List, Dict, Optional, Callable, Any

from config.constants import (
    GRID_PIXEL_SIZE, SEASON_SPRING, SEASON_SUMMER, SEASON_AUTUMN, SEASON_WINTER
)
from ui import Slider, Button


class UIManager:
    """
    Manages all UI widgets and user input.
    
    Attributes:
        sliders (list): List of Slider widgets
        buttons (dict): Dictionary of Button widgets
        selected_agent: Currently selected agent (None if no selection)
        parameter_updates (dict): Latest parameter values from sliders
    """
    
    def __init__(self) -> None:
        """Initialize UI manager and create widgets."""
        self.selected_agent: Optional[Any] = None
        self.parameter_updates: Dict[str, float] = {}
        
        # Create sliders
        self.slider_wood = Slider(
            GRID_PIXEL_SIZE + 20, 20, 200, 20,
            0.0, 0.06, 0.030, "Wood Regrowth"
        )
        self.slider_potion = Slider(
            GRID_PIXEL_SIZE + 20, 60, 200, 20,
            0.0, 0.0002, 0.00005, "Potion Spawn"
        )
        self.slider_timeout = Slider(
            GRID_PIXEL_SIZE + 20, 100, 200, 20,
            100, 3000, 1500, "Gen Timeout"
        )
        
        self.sliders = [self.slider_wood, self.slider_potion, self.slider_timeout]
        
        # Buttons (callbacks will be set externally)
        self.buttons: Dict[str, Button] = {}
        self.season_buttons: List[Button] = []
    
    def create_buttons(self, callbacks: Dict[str, Callable]) -> None:
        """
        Create buttons with callbacks.
        
        Args:
            callbacks (dict): Dictionary mapping button names to callback functions
        """
        # Control buttons
        self.buttons['visuals'] = Button(
            GRID_PIXEL_SIZE + 20, 140, 200, 30,
            "Toggle Visuals",
            callbacks.get('toggle_visuals', lambda: None),
            color=None  # Will be updated based on state
        )
        
        self.buttons['sound'] = Button(
            GRID_PIXEL_SIZE + 20, 175, 200, 30,
            "Toggle Sound",
            callbacks.get('toggle_sound', lambda: None),
            color=None  # Will be updated based on state
        )
        
        self.buttons['reset_epsilon'] = Button(
            GRID_PIXEL_SIZE + 20, 210, 200, 30,
            "Reset Exploration",
            callbacks.get('reset_exploration', lambda: None)
        )
        
        self.buttons['clear_hof'] = Button(
            GRID_PIXEL_SIZE + 20, 245, 200, 30,
            "Clear Hall of Fame",
            callbacks.get('clear_hall_of_fame', lambda: None)
        )
        
        # Season buttons (positions will be updated during rendering)
        self.season_buttons = [
            Button(0, 0, 90, 25, "AUTO", callbacks.get('toggle_auto_season', lambda: None)),
            Button(0, 0, 90, 25, "Sp", lambda: callbacks.get('set_season', lambda x: None)(SEASON_SPRING)),
            Button(0, 0, 90, 25, "Su", lambda: callbacks.get('set_season', lambda x: None)(SEASON_SUMMER)),
            Button(0, 0, 90, 25, "Au", lambda: callbacks.get('set_season', lambda x: None)(SEASON_AUTUMN)),
            Button(0, 0, 90, 25, "Wi", lambda: callbacks.get('set_season', lambda x: None)(SEASON_WINTER))
        ]
    
    def handle_events(self, events: List[pygame.event.Event], grid_size: int,
                     cell_size: int, grid_offset_y: int,
                     agents: List[Any]) -> Dict[str, Any]:
        """
        Process UI events and return commands.
        
        Args:
            events: List of pygame events
            grid_size: Size of the game grid
            cell_size: Size of each grid cell in pixels
            grid_offset_y: Vertical offset of the grid
            agents: List of agents (for selection)
            
        Returns:
            Dict containing: 'quit', 'agent_selected', 'parameters_changed'
        """
        result = {
            'quit': False,
            'agent_selected': None,
            'parameters_changed': False
        }
        
        for event in events:
            if event.type == pygame.QUIT:
                result['quit'] = True
                return result
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                # Check for agent selection in grid
                if mx < GRID_PIXEL_SIZE:
                    grid_y = my - grid_offset_y
                    if 0 <= grid_y < GRID_PIXEL_SIZE:
                        gx, gy = mx // cell_size, grid_y // cell_size
                        if 0 <= gx < grid_size and 0 <= gy < grid_size:
                            # Find agent at this position
                            selected = None
                            for agent in agents:
                                if agent.alive and agent.x == gx and agent.y == gy:
                                    selected = agent
                                    break
                            self.selected_agent = selected
                            result['agent_selected'] = selected
            
            # Handle slider events
            for slider in self.sliders:
                slider.handle_event(event)
            
            # Handle button events
            for button in self.buttons.values():
                button.handle_event(event)
            
            for button in self.season_buttons:
                button.handle_event(event)
        
        # Check if parameters changed
        new_params = self.get_parameter_updates()
        if new_params != self.parameter_updates:
            self.parameter_updates = new_params.copy()
            result['parameters_changed'] = True
        
        return result
    
    def get_parameter_updates(self) -> Dict[str, float]:
        """
        Get current parameter values from sliders.
        
        Returns:
            Dict with 'wood_regrowth', 'potion_spawn', 'gen_timeout'
        """
        return {
            'wood_regrowth': self.slider_wood.val,
            'potion_spawn': self.slider_potion.val,
            'gen_timeout': self.slider_timeout.val
        }
    
    def update_slider_values(self, wood_regrowth: float = None,
                            potion_spawn: float = None,
                            gen_timeout: float = None) -> None:
        """
        Update slider values programmatically (e.g., when season changes).
        
        Args:
            wood_regrowth: Wood regrowth rate
            potion_spawn: Potion spawn rate
            gen_timeout: Generation timeout
        """
        if wood_regrowth is not None:
            self.slider_wood.val = wood_regrowth
            self.slider_wood.update_handle()
        if potion_spawn is not None:
            self.slider_potion.val = potion_spawn
            self.slider_potion.update_handle()
        if gen_timeout is not None:
            self.slider_timeout.val = gen_timeout
            self.slider_timeout.update_handle()
    
    def update_visuals_button_color(self, visuals_enabled: bool) -> None:
        """
        Update the visuals button color based on state.
        
        Args:
            visuals_enabled: Whether visuals are currently enabled
        """
        if 'visuals' in self.buttons:
            # Green if ON, Gray if OFF
            self.buttons['visuals'].color = (0, 200, 0) if visuals_enabled else (100, 100, 100)
    
    def update_sound_button_color(self, sound_enabled: bool) -> None:
        """
        Update the sound button color based on state.
        
        Args:
            sound_enabled: Whether sound is currently enabled
        """
        if 'sound' in self.buttons:
            # Green if ON, Gray if OFF
            self.buttons['sound'].color = (0, 200, 0) if sound_enabled else (100, 100, 100)
    
    def get_ui_state(self, generation: int, gen_steps: int, max_steps_per_gen: int,
                    global_kills_by_type: Dict, kill_history: List,
                    reward_history: List, duration_history: List, loss_history: List,
                    cycles_per_hour: float, epsilon: float,
                    hall_of_fame: List, action_history: List,
                    current_season: str, auto_season_mode: bool,
                    cycle_number: int, season_gens_counter: int,
                    complete_cycle_performance: List, convergence_info: str,
                    agents: List, selected_agent: Any, predators: List = None) -> Dict:
        """
        Compile all UI state into a dictionary for rendering.
        
        Returns:
            Dict containing all UI state
        """
        return {
            'sliders': self.sliders,
            'btn_visuals': self.buttons.get('visuals'),
            'btn_sound': self.buttons.get('sound'),
            'btn_reset_epsilon': self.buttons.get('reset_epsilon'),
            'btn_clear_hof': self.buttons.get('clear_hof'),
            'season_buttons': self.season_buttons,
            'generation': generation,
            'gen_steps': gen_steps,
            'max_steps_per_gen': max_steps_per_gen,
            'global_kills_by_type': global_kills_by_type,
            'kill_history': kill_history,
            'reward_history': reward_history,
            'duration_history': duration_history,
            'loss_history': loss_history,
            'cycles_per_hour': cycles_per_hour,
            'epsilon': epsilon,
            'hall_of_fame': hall_of_fame,
            'action_history': action_history,
            'current_season': current_season,
            'auto_season_mode': auto_season_mode,
            'cycle_number': cycle_number,
            'season_gens_counter': season_gens_counter,
            'complete_cycle_performance': complete_cycle_performance,
            'convergence_info': convergence_info,
            'agents': agents,
            'selected_agent': selected_agent,
            'predators': predators if predators is not None else []
        }
