"""
UI package for Arena of Life.
"""
from .widgets import Slider, Button
from .rendering import (
    draw_tree, draw_rock, draw_potion, draw_agent_visual,
    draw_grid, draw_ui
)

__all__ = [
    'Slider', 'Button',
    'draw_tree', 'draw_rock', 'draw_potion', 'draw_agent_visual',
    'draw_grid', 'draw_ui'
]
