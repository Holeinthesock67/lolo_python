"""
Spatial Hash Grid for optimized collision detection.

This module provides a spatial partitioning data structure that allows
O(1) lookups for entities within a given range, replacing the O(n²) 
brute-force approach.
"""
from typing import List, Set, Tuple, Any
from collections import defaultdict


class SpatialGrid:
    """
    Spatial hash grid for fast proximity queries.
    
    Divides the game space into cells. Each cell maintains a set of entities.
    Collision/proximity checks only query neighboring cells instead of all entities.
    
    Attributes:
        grid_size (int): Total size of the game grid
        cell_size (int): Size of each spatial cell (in grid units)
        cells (dict): Dictionary mapping cell coordinates to entity sets
    """
    
    def __init__(self, grid_size: int, cell_size: int = 5) -> None:
        """
        Initialize the spatial grid.
        
        Args:
            grid_size (int): Total size of the game grid (e.g., 50x50)
            cell_size (int): Size of each spatial cell (default 5 = 10x10 cells for 50x50 grid)
        """
        self.grid_size = grid_size
        self.cell_size = cell_size
        self.num_cells = (grid_size + cell_size - 1) // cell_size
        self.cells = defaultdict(set)
        # Track entity positions for efficient updates
        self.entity_positions = {}
    
    def _get_cell(self, x: int, y: int) -> Tuple[int, int]:
        """
        Get the cell coordinates for a world position.
        
        Args:
            x, y (int): World coordinates
            
        Returns:
            Tuple[int, int]: Cell coordinates
        """
        cell_x = x // self.cell_size
        cell_y = y // self.cell_size
        return (cell_x, cell_y)
    
    def insert(self, entity: Any, x: int, y: int) -> None:
        """
        Insert an entity at the given position.
        
        Args:
            entity: The entity to insert (Agent or Predator)
            x, y (int): World coordinates
        """
        cell = self._get_cell(x, y)
        self.cells[cell].add(entity)
        self.entity_positions[entity] = (x, y)
    
    def remove(self, entity: Any, x: int = None, y: int = None) -> None:
        """
        Remove an entity from the grid.
        
        Args:
            entity: The entity to remove
            x, y (int, optional): If provided, use these coords. Otherwise use tracked position.
        """
        if x is None or y is None:
            if entity in self.entity_positions:
                x, y = self.entity_positions[entity]
            else:
                return  # Entity not in grid
        
        cell = self._get_cell(x, y)
        if cell in self.cells:
            self.cells[cell].discard(entity)
            if not self.cells[cell]:
                del self.cells[cell]
        
        if entity in self.entity_positions:
            del self.entity_positions[entity]
    
    def update_position(self, entity: Any, old_x: int, old_y: int, new_x: int, new_y: int) -> None:
        """
        Update an entity's position efficiently.
        
        Only updates if the cell changed (most movements stay in same cell).
        
        Args:
            entity: The entity to update
            old_x, old_y (int): Previous world coordinates
            new_x, new_y (int): New world coordinates
        """
        old_cell = self._get_cell(old_x, old_y)
        new_cell = self._get_cell(new_x, new_y)
        
        # Only update if cell changed
        if old_cell != new_cell:
            # Remove from old cell
            if old_cell in self.cells:
                self.cells[old_cell].discard(entity)
                if not self.cells[old_cell]:
                    del self.cells[old_cell]
            
            # Add to new cell
            self.cells[new_cell].add(entity)
        
        # Update tracked position
        self.entity_positions[entity] = (new_x, new_y)
    
    def get_entities_in_range(self, x: int, y: int, radius: int) -> List[Any]:
        """
        Get all entities within a given radius of a position.
        
        Args:
            x, y (int): Center position
            radius (int): Search radius in grid units
            
        Returns:
            List[Any]: All entities within radius (toroidal distance)
        """
        # Calculate which cells to check
        cell_radius = (radius + self.cell_size - 1) // self.cell_size
        center_cell = self._get_cell(x, y)
        
        entities = []
        
        # Check all cells within cell_radius
        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                cell_x = center_cell[0] + dx
                cell_y = center_cell[1] + dy
                
                # Handle toroidal wrapping for cells
                cell_x = cell_x % self.num_cells
                cell_y = cell_y % self.num_cells
                
                cell = (cell_x, cell_y)
                if cell in self.cells:
                    for entity in self.cells[cell]:
                        # Verify actual distance (toroidal)
                        if entity in self.entity_positions:
                            ex, ey = self.entity_positions[entity]
                            dist = self._toroidal_distance(x, y, ex, ey)
                            if dist <= radius:
                                entities.append(entity)
        
        return entities
    
    def _toroidal_distance(self, x1: int, y1: int, x2: int, y2: int) -> int:
        """
        Calculate Manhattan distance with toroidal wrapping.
        
        Args:
            x1, y1, x2, y2 (int): Two positions
            
        Returns:
            int: Toroidal Manhattan distance (dx + dy)
        """
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        dx = min(dx, self.grid_size - dx)
        dy = min(dy, self.grid_size - dy)
        return dx + dy
    
    def clear(self) -> None:
        """Clear all entities from the grid."""
        self.cells.clear()
        self.entity_positions.clear()
    
    def get_all_entities(self) -> List[Any]:
        """
        Get all entities currently in the grid.
        
        Returns:
            List[Any]: All entities
        """
        return list(self.entity_positions.keys())
    
    def __len__(self) -> int:
        """Return the number of entities in the grid."""
        return len(self.entity_positions)
