"""
Environment module for Arena of Life game.

Handles map generation, resource regeneration, and world state.
Includes optimized line-of-sight calculations for agent vision.
"""
import numpy as np
import random
from typing import List, Tuple, Dict
from config.constants import (
    TILE_EMPTY, TILE_WALL, TILE_WOOD, TILE_IRON,
    TILE_POTION_HEALTH, TILE_POTION_ENERGY, TILE_POTION_MAGIC,
    VISION_RANGE
)


class Environment:
    """
    Manages the game world grid, resources, and environment updates.
    """
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.grid = np.zeros((width, height), dtype=int)
        self.generate_map()
        
        self.wood_regrowth_rate = 0.001
        self.potion_spawn_rate = 0.00005
        
        # Pre-compute Line of Sight paths for performance
        self.los_paths = {}
        self._precompute_los_paths(VISION_RANGE)

    def _precompute_los_paths(self, radius: int) -> None:
        """
        Pre-calculate Bresenham line paths for all relative positions in vision range.
        
        This optimization computes all possible line-of-sight paths once at initialization,
        allowing O(1) path lookup during gameplay instead of calculating them repeatedly.
        Uses Bresenham's line algorithm for accurate grid-based line drawing.
        
        Args:
            radius (int): Vision range radius
        """
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0: continue
                
                # Calculate path from (0,0) to (dx,dy)
                path = []
                x0, y0 = 0, 0
                x1, y1 = dx, dy
                
                adx = abs(x1 - x0)
                ady = abs(y1 - y0)
                sx = 1 if x0 < x1 else -1
                sy = 1 if y0 < y1 else -1
                err = adx - ady
                
                cx, cy = x0, y0
                
                while True:
                    if cx == x1 and cy == y1:
                        break
                        
                    e2 = 2 * err
                    if e2 > -ady:
                        err -= ady
                        cx += sx
                    if e2 < adx:
                        err += adx
                        cy += sy
                        
                    # Don't include the start point (0,0), but include intermediate steps
                    if cx != 0 or cy != 0:
                        path.append((cx, cy))
                
                self.los_paths[(dx, dy)] = path

    def generate_map(self) -> None:
        """
        Generate initial map with walls, resources, and potions.
        
        Populates the grid with:
        - 10% walls (obstacles)
        - 5% wood (renewable resource)
        - 3% iron (armor crafting)
        - 0.5% health potions
        - 0.5% energy potions
        - 0.2% magic potions
        """
        self.grid.fill(TILE_EMPTY)
        total_cells = self.width * self.height
        
        def place_random(tile_type, count):
            for _ in range(count):
                x, y = random.randint(0, self.width-1), random.randint(0, self.height-1)
                self.grid[x, y] = tile_type

        place_random(TILE_WALL, int(total_cells * 0.10))
        place_random(TILE_WOOD, int(total_cells * 0.05))
        place_random(TILE_IRON, int(total_cells * 0.03))
        place_random(TILE_POTION_HEALTH, int(total_cells * 0.005))
        place_random(TILE_POTION_ENERGY, int(total_cells * 0.005))
        place_random(TILE_POTION_MAGIC, int(total_cells * 0.002))

    def update_environment(self) -> None:
        """
        Update environment: regrow wood near trees, spawn potions.
        
        Wood regrows near existing trees (2+ tree neighbors required).
        Potions spawn randomly based on spawn rate.
        This is called periodically during the simulation.
        """
        new_grid = self.grid.copy()
        
        for x in range(self.width):
            for y in range(self.height):
                if self.grid[x, y] == TILE_EMPTY:
                    if random.random() < self.potion_spawn_rate:
                        r = random.random()
                        if r < 0.5: new_grid[x, y] = TILE_POTION_HEALTH
                        elif r < 0.8: new_grid[x, y] = TILE_POTION_ENERGY
                        else: new_grid[x, y] = TILE_POTION_MAGIC
                        continue

                    wood_neighbors = 0
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx == 0 and dy == 0: continue
                            nx, ny = x + dx, y + dy
                            if 0 <= nx < self.width and 0 <= ny < self.height:
                                if self.grid[nx, ny] == TILE_WOOD:
                                    wood_neighbors += 1
                    
                    if wood_neighbors >= 2:
                        if random.random() < self.wood_regrowth_rate:
                            new_grid[x, y] = TILE_WOOD
                            
        self.grid = new_grid

    def get_view(self, x: int, y: int, radius: int) -> np.ndarray:
        """
        Get agent's view using optimized pre-calculated line of sight (single agent).
        
        Returns a flattened view grid where cells are visible based on line-of-sight.
        Walls block vision, and forests reduce effective range. This is the legacy
        single-agent version; for batch processing, use get_batch_views().
        
        Args:
            x (int): Agent's X position
            y (int): Agent's Y position
            radius (int): Vision radius
        
        Returns:
            np.ndarray: Flattened view array of size (2*radius+1)^2
        """
        view_size = 2 * radius + 1
        view = np.full((view_size, view_size), TILE_WALL, dtype=int)
        
        # Center is always visible
        center = radius
        if 0 <= x < self.width and 0 <= y < self.height:
            view[center, center] = self.grid[x, y]
        
        # Iterate over all relative positions in the view
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0: continue
                
                target_x = x + dx
                target_y = y + dy
                
                # Bounds check
                if not (0 <= target_x < self.width and 0 <= target_y < self.height):
                    continue
                
                # Check Line of Sight using pre-computed path
                blocked = False
                range_penalty = 0
                
                # Check path to target
                path = self.los_paths.get((dx, dy), [])
                for px, py in path:
                    # Check intermediate cell
                    ix, iy = x + px, y + py
                    
                    if not (0 <= ix < self.width and 0 <= iy < self.height):
                        blocked = True
                        break
                        
                    tile = self.grid[ix, iy]
                    if tile == TILE_WALL:
                        blocked = True
                        break
                    if tile == TILE_WOOD:
                        range_penalty += 1
            
                if not blocked:
                    # Check range limit
                    dist = abs(dx) + abs(dy)
                    if dist - range_penalty <= radius:
                        view[center + dx, center + dy] = self.grid[target_x, target_y]
        
        return view.flatten()

    def get_batch_views(self, agent_positions: List[Tuple[int, int]], radius: int) -> np.ndarray:
        """
        Get views for multiple agents simultaneously using vectorized operations.
        
        This is a highly optimized version that processes all agent views in parallel
        using NumPy broadcasting and vectorization. It's significantly faster than
        calling get_view() for each agent individually.
        
        Process:
        1. Create padded grid to simplify boundary handling
        2. Extract raw views for all agents using advanced indexing
        3. Apply line-of-sight masks using pre-computed dependency paths
        4. Return batch of flattened views
        
        Args:
            agent_positions (List[Tuple[int, int]]): List of (x, y) positions
            radius (int): Vision radius
        
        Returns:
            np.ndarray: Array of shape (N, view_size^2) containing flattened views
        """
        positions = np.array(agent_positions)
        n_agents = len(positions)
        view_size = 2 * radius + 1
        
        # 1. Create padded grid with WRAP mode for Toroidal world
        # This automatically handles "seeing through edges"
        padded_grid = np.pad(self.grid, radius, mode='wrap')
        
        # 2. Extract all views at once using advanced indexing
        # Create a grid of offsets
        x_offsets = np.arange(view_size)
        y_offsets = np.arange(view_size)
        xx, yy = np.meshgrid(x_offsets, y_offsets, indexing='ij') # (7, 7)
        
        # Adjust positions to padded coordinates
        pad_x = positions[:, 0] # (N,)
        pad_y = positions[:, 1] # (N,)
        
        # Broadcast addition to get all indices: (N, 7, 7)
        # We want view[i, dx, dy] = grid[pad_x[i] + dx, pad_y[i] + dy]
        # But indices are relative to top-left of the view window (pad_x, pad_y are top-left)
        # Actually positions are centers. So top-left is center - radius.
        # But we added radius padding. So top-left in padded grid is (x+r) - r = x.
        # Wait, let's trace carefully.
        # Grid (0,0) is at Padded(r,r).
        # Agent at (x,y) wants view from x-r to x+r.
        # In padded coords, this is (x+r)-r to (x+r)+r => x to x+2r+1.
        # So start index is just x, y.
        
        start_x = pad_x[:, None, None] + xx[None, :, :]
        start_y = pad_y[:, None, None] + yy[None, :, :]
        
        # Extract raw views (N, 7, 7)
        raw_views = padded_grid[start_x, start_y]
        
        # 3. Apply Line of Sight Mask (Vectorized)
        # We use the pre-computed dependencies.
        # For each cell (dx, dy) in the view (relative to center), we check if it's blocked.
        # But dependency check is sequential (need to check parent first).
        # However, we can process "shells" of distance.
        # Distance 1 cells depend on center (always visible).
        # Distance 2 cells depend on Dist 1 cells.
        # So we can iterate by distance layer.
        
        # Initialize visibility mask (1 = visible, 0 = blocked)
        visibility = np.ones((n_agents, view_size, view_size), dtype=bool)
        
        # Center is always visible
        center = radius
        
        # We need a dependency map: cell -> parent_cell
        # Since we have self.los_paths, we can derive immediate parents.
        # Actually, simpler: iterate through our pre-computed paths.
        # But iterating 48 paths for 100 agents is still 4800 checks.
        # Better: Iterate over unique relative coordinates sorted by distance.
        
        # Get all relative coords sorted by distance
        coords = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0: continue
                coords.append((dx, dy))
        coords.sort(key=lambda p: abs(p[0]) + abs(p[1]))
        
        for dx, dy in coords:
            # Map relative (dx, dy) to array indices (rx, ry)
            rx, ry = center + dx, center + dy
            
            # Find parent from pre-computed path
            # The parent is the last step in the path before the target
            path = self.los_paths.get((dx, dy), [])
            if not path:
                # Distance 1 neighbors have no intermediate path, so they depend only on center (always visible)
                # But we must check if THEY are walls themselves (handled later by raw_views check)
                pass
            else:
                # Parent is the last element in path
                px, py = path[-1]
                prx, pry = center + px, center + py
                
                # Visibility propagation logic:
                # Visible if Parent is Visible AND Parent is NOT a Wall
                # (We ignore forests for now to keep it fast, or we can add range penalty logic)
                
                # Vectorized check for all agents:
                # Is parent visible?
                parent_visible = visibility[:, prx, pry]
                
                # Is parent NOT a wall?
                parent_tile = raw_views[:, prx, pry]
                parent_transparent = (parent_tile != TILE_WALL)
                
                # Update current cell visibility
                visibility[:, rx, ry] = parent_visible & parent_transparent
                
                # Handle Forest Range Penalty (Optional, maybe skip for pure speed first?)
                # If we want to be exact, we need to track "remaining range" per agent/cell.
                # That's complex to vectorize simply.
                # Simplified: If parent is Wood, it blocks vision for cells behind it?
                # No, wood reduces range.
                # Let's stick to Wall blocking for the vectorized version to ensure speed.
                # It's a "Turbo" mode after all.
        
        # Apply mask: Set blocked cells to TILE_WALL (or a generic "unknown" if we had one)
        # In this game, "unseen" is usually treated as Wall or just not updated.
        # Let's set to TILE_WALL to represent "cannot see/cannot go".
        
        final_views = np.where(visibility, raw_views, TILE_WALL)
        
        return final_views.reshape(n_agents, -1)

    def is_walkable(self, x: int, y: int) -> bool:
        """Check if a position is walkable (not a wall)"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[x, y] != TILE_WALL
        return False
