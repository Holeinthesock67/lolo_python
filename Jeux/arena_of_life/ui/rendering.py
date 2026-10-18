"""
Rendering functions for Arena of Life game.

This module handles all visual rendering including the game grid, agents,
particle effects, and the comprehensive UI panel.
"""
import pygame
import numpy as np
from typing import List, Optional, Any
from config.constants import (
    CELL_SIZE, GRID_SIZE, GRID_PIXEL_SIZE, UI_WIDTH, WINDOW_HEIGHT, GRID_OFFSET_Y,
    COLOR_BG, COLOR_WALL, COLOR_WOOD, COLOR_IRON,
    COLOR_POTION_HEALTH, COLOR_POTION_ENERGY, COLOR_POTION_MAGIC,
    TILE_WALL, TILE_WOOD, TILE_IRON,
    TILE_POTION_HEALTH, TILE_POTION_ENERGY, TILE_POTION_MAGIC,
    WEAPON_SWORD, WEAPON_BOW, WEAPON_WAND, WEAPON_FISTS,
    ACTION_CRI_DANGER, ACTION_CRI_HEAL, ACTION_CRI_POTION,
    device,
    POTION_HEAL_AMOUNT, POTION_STAMINA_AMOUNT, POTION_MAGIC_AMOUNT, SWORD_DAMAGE_BASE, HEALER_PASSIVE_BASE_HEAL,
    PREDATORS_BY_SEASON, COMM_AUDIBLE_RANGE, REWARD_SHOUT_SUCCESS
)


def draw_tree(screen: pygame.Surface, x: int, y: int) -> None:
    """Draw a stylized tree at grid position (x, y)."""
    cx, cy = x * CELL_SIZE + CELL_SIZE//2, y * CELL_SIZE + CELL_SIZE//2 + GRID_OFFSET_Y
    # Trunk
    pygame.draw.rect(screen, (101, 67, 33), (cx - 2, cy, 4, CELL_SIZE//2))
    # Leaves
    pygame.draw.circle(screen, (34, 139, 34), (cx, cy - 4), 6)
    pygame.draw.circle(screen, (34, 139, 34), (cx - 4, cy + 2), 5)
    pygame.draw.circle(screen, (34, 139, 34), (cx + 4, cy + 2), 5)


def draw_rock(screen: pygame.Surface, x: int, y: int) -> None:
    """Draw a stylized rock/iron ore at grid position (x, y)."""
    cx, cy = x * CELL_SIZE + CELL_SIZE//2, y * CELL_SIZE + CELL_SIZE//2 + GRID_OFFSET_Y
    points = [(cx, cy-6), (cx+5, cy-2), (cx+6, cy+4), (cx, cy+6), (cx-5, cy+4), (cx-6, cy-2)]
    pygame.draw.polygon(screen, (169, 169, 169), points)
    pygame.draw.polygon(screen, (120, 120, 120), points, 1)


def draw_potion(screen: pygame.Surface, x: int, y: int, color: tuple) -> None:
    """Draw a stylized potion bottle at grid position (x, y)."""
    cx, cy = x * CELL_SIZE + CELL_SIZE//2, y * CELL_SIZE + CELL_SIZE//2 + GRID_OFFSET_Y
    # Bottle
    pygame.draw.circle(screen, color, (cx, cy + 2), 5)
    # Neck
    pygame.draw.rect(screen, (200, 200, 200), (cx - 2, cy - 6, 4, 6))
    # Cork
    pygame.draw.rect(screen, (139, 69, 19), (cx - 2, cy - 8, 4, 2))


def draw_predator(screen: pygame.Surface, predator: Any) -> None:
    """Draw a predator (Red enemy)."""
    cx, cy = predator.x * CELL_SIZE + CELL_SIZE//2, predator.y * CELL_SIZE + CELL_SIZE//2 + GRID_OFFSET_Y
    
    # Spiky/Aggressive shape (Red Diamond)
    points = [(cx, cy-7), (cx+7, cy), (cx, cy+7), (cx-7, cy)]
    pygame.draw.polygon(screen, (255, 0, 0), points)
    pygame.draw.polygon(screen, (100, 0, 0), points, 1)
    
    # Eyes
    pygame.draw.circle(screen, (0, 0, 0), (cx - 2, cy - 2), 1)
    pygame.draw.circle(screen, (0, 0, 0), (cx + 2, cy - 2), 1)


def draw_agent_visual(screen: pygame.Surface, agent: Any) -> None:
    """
    Draw a stylized agent with eyes and weapon indicator.
    
    The agent is rendered as a colored circle with eyes and a weapon
    indicator dot showing the current equipped weapon.
    """
    cx, cy = agent.x * CELL_SIZE + CELL_SIZE//2, agent.y * CELL_SIZE + CELL_SIZE//2 + GRID_OFFSET_Y
    
    # Body
    pygame.draw.circle(screen, agent.color, (cx, cy), 7)
    pygame.draw.circle(screen, (255, 255, 255), (cx, cy), 7, 1) # Outline
    
    # Eyes
    pygame.draw.circle(screen, (255, 255, 255), (cx - 2, cy - 2), 2)
    pygame.draw.circle(screen, (255, 255, 255), (cx + 2, cy - 2), 2)
    pygame.draw.circle(screen, (0, 0, 0), (cx - 2, cy - 2), 1)
    pygame.draw.circle(screen, (0, 0, 0), (cx + 2, cy - 2), 1)

    # Weapon
    w_color = (200, 200, 200)
    if agent.weapon == WEAPON_SWORD: w_color = (0, 0, 255)
    elif agent.weapon == WEAPON_BOW: w_color = (0, 255, 0)
    elif agent.weapon == WEAPON_WAND: w_color = (255, 0, 255)
    
    # Draw weapon as a small dot/item next to hand
    pygame.draw.circle(screen, w_color, (cx + 6, cy + 4), 3)


def draw_grid(screen: pygame.Surface, env: Any, agents: List[Any], predators: List[Any],
              particles: List[List], shout_particles: List[List], selected_agent: Optional[Any]) -> None:
    """
    Draw the entire game grid with tiles, agents, and visual effects.
    
    Uses optimized rendering by only drawing non-empty tiles. Applies
    the vertical grid offset for proper alignment.
    
    Args:
        screen: Pygame surface to draw on
        env: Environment containing the grid
        agents: List of agent objects
        particles: List of particle effects [x, y, color, radius, max_radius]
        shout_particles: List of shout effects [x, y, shout_type, lifetime]
        selected_agent: Currently selected agent (highlighted)
    """
    screen.fill(COLOR_BG, (0, 0, GRID_PIXEL_SIZE, WINDOW_HEIGHT)) # Fill full height
    
    # Optimize: Only iterate over non-empty tiles
    # Get indices of all non-empty tiles
    non_empty_indices = np.argwhere(env.grid != 0) # 0 is TILE_EMPTY
    
    for x, y in non_empty_indices:
        tile = env.grid[x, y]
        
        # Apply offset to rects
        rect_y = y * CELL_SIZE + GRID_OFFSET_Y
        
        if tile == TILE_WALL:
            pygame.draw.rect(screen, COLOR_WALL, (x * CELL_SIZE, rect_y, CELL_SIZE, CELL_SIZE))
            pygame.draw.rect(screen, (100, 100, 100), (x * CELL_SIZE, rect_y, CELL_SIZE, CELL_SIZE), 1)
        elif tile == TILE_WOOD:
            draw_tree(screen, x, y)
        elif tile == TILE_IRON:
            draw_rock(screen, x, y)
        elif tile == TILE_POTION_HEALTH:
            draw_potion(screen, x, y, COLOR_POTION_HEALTH)
        elif tile == TILE_POTION_ENERGY:
            draw_potion(screen, x, y, COLOR_POTION_ENERGY)
        elif tile == TILE_POTION_MAGIC:
            draw_potion(screen, x, y, COLOR_POTION_MAGIC)
    
    for agent in agents:
        if agent.alive:
            draw_agent_visual(screen, agent)
            if agent == selected_agent:
                rect = (agent.x * CELL_SIZE, agent.y * CELL_SIZE + GRID_OFFSET_Y, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(screen, (255, 255, 0), rect, 1) # Selection box
    
    # Draw Predators
    for pred in predators: 
        if pred.alive:
            draw_predator(screen, pred)
            
    # Draw Kill Particles
    for p in particles:
        # p[1] is y coordinate in pixels, need to add offset
        pygame.draw.circle(screen, p[2], (int(p[0]), int(p[1] + GRID_OFFSET_Y)), int(p[3]), 2)
    
    # Draw Shout Particles (Speech Bubbles)
    for p in shout_particles:
        px, py, shout_type, lifetime = p
        py_offset = int(py + GRID_OFFSET_Y)
        
        # Determine color and symbol based on shout type
        if shout_type == ACTION_CRI_DANGER:
            color = (255, 0, 0)  # Red
            symbol = "!"
        elif shout_type == ACTION_CRI_HEAL:
            color = ( 0, 255, 0)  # Green
            symbol = "+"
        elif shout_type == ACTION_CRI_POTION:
            color = (255, 0, 255)  # Magenta
            symbol = "P"
        else:
            color = (255, 255, 255)
            symbol = "?"
        
        # Fade effect based on lifetime
        alpha_ratio = min(1.0, lifetime / 15.0)
        faded_color = tuple(int(c * alpha_ratio) for c in color)
        
        # Draw speech bubble (circle with text)
        radius = 10
        pygame.draw.circle(screen, faded_color, (int(px), py_offset - 15), radius)
        pygame.draw.circle(screen, (255, 255, 255), (int(px), py_offset - 15), radius, 1)
        
        # Draw symbol
        font = pygame.font.SysFont("Arial", 12, bold=True)
        text = font.render(symbol, True, (0, 0, 0))
        text_rect = text.get_rect(center=(int(px), py_offset - 15))
        screen.blit(text, text_rect)



def draw_ui(screen: pygame.Surface, font: pygame.font.Font, title_font: pygame.font.Font,
            sliders: List[Any], button: Any, agents: List[Any], selected_agent: Optional[Any],
            generation: int, gen_steps: int, max_steps_per_gen: int, 
            global_kills_by_type: dict, kill_history: List[int], 
            reward_history: List[float], duration_history: List[int], loss_history: List[float],
            cycles_per_hour: float, epsilon: float, hall_of_fame: List[dict],
            action_history: List[dict], btn_reset_epsilon: Any, btn_clear_hof: Any,
            season_buttons: List[Any], current_season: str, auto_season_mode: bool,
            cycle_number: int, season_gens_counter: int, cycle_performance: List[float],
            convergence_info: str, btn_sound: Any = None, predators: List[Any] = None) -> None:
    """
    Draw the complete UI panel with 2-column responsive layout.
    
    Column 1: Controls, Seasons, Legend, Game Rules, Selected Agent
    Column 2: Learning Phase, Game Stats, Top Agents, Hall of Fame, Graphs
    
    Uses a card-based design system with dynamic positioning for a clean,
    professional appearance.
    """
    # UI Background
    pygame.draw.rect(screen, (30, 30, 30), (GRID_PIXEL_SIZE, 0, UI_WIDTH, WINDOW_HEIGHT))
    
    # Column Setup
    col_padding = 10
    col_width = (UI_WIDTH - (3 * col_padding)) // 2
    col1_x = GRID_PIXEL_SIZE + col_padding
    col2_x = col1_x + col_width + col_padding
    
    col1_y = 10
    col2_y = 10
    
    def draw_card_dynamic(x, y, width, height, title):
        rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(screen, (45, 45, 45), rect, border_radius=5)
        pygame.draw.rect(screen, (60, 60, 60), rect, 1, border_radius=5)
        screen.blit(title_font.render(title, True, (200, 200, 200)), (x + 10, y + 5))
        return y + height + 10 # Return next Y position

    def draw_graph_dynamic(x, y, width, title, data, color, y_label="", x_label=""):
        height = 90  # Increased height for X-axis labels
        draw_card_dynamic(x, y, width, height, title)
        
        # Graph rect inside card
        graph_rect = pygame.Rect(x + 45, y + 30, width - 55, 40) # More padding for Y-axis
        pygame.draw.rect(screen, (20, 20, 20), graph_rect)
        pygame.draw.rect(screen, (100, 100, 100), graph_rect, 1)
        
        # Axis Titles
        if y_label:
            # Rotate text for Y-axis title
            y_surf = font.render(y_label, True, (120, 120, 120))
            y_surf = pygame.transform.rotate(y_surf, 90)
            screen.blit(y_surf, (x + 5, y + 30))
            
        if x_label:
            x_surf = font.render(x_label, True, (120, 120, 120))
            screen.blit(x_surf, (graph_rect.centerx - x_surf.get_width()//2, graph_rect.bottom + 2))

        # X-Axis Start/End Labels
        if len(data) > 0:
            # Start (1)
            start_surf = font.render("1", True, (150, 150, 150))
            screen.blit(start_surf, (graph_rect.left, graph_rect.bottom + 2))
            
            # End (len(data))
            end_surf = font.render(str(len(data)), True, (150, 150, 150))
            screen.blit(end_surf, (graph_rect.right - end_surf.get_width(), graph_rect.bottom + 2))

        if len(data) > 1:
            max_val = max(data)
            min_val = min(data)
            
            # Draw Value Labels
            # Max (Top)
            screen.blit(font.render(f"{max_val:.1f}", True, (150, 150, 150)), (x + 20, y + 25))
            # Min (Bottom)
            screen.blit(font.render(f"{min_val:.1f}", True, (150, 150, 150)), (x + 20, y + 60))
            
            points = []
            if max_val > min_val:
                for i, val in enumerate(data):
                    px = graph_rect.left + (i / (len(data)-1)) * graph_rect.width
                    norm_val = (val - min_val) / (max_val - min_val)
                    py = graph_rect.bottom - norm_val * graph_rect.height
                    points.append((px, py))
            else:
                # Flat line
                py = graph_rect.centery
                points = [(graph_rect.left, py), (graph_rect.right, py)]
                
            if len(points) > 1:
                pygame.draw.lines(screen, color, False, points, 2)
                
        return y + height + 10

    # ... (rest of the function remains unchanged until graph calls) ...

    # Graphs (Stacked in Column 2)
    col2_y = draw_graph_dynamic(col2_x, col2_y, col_width, "Kills / Gen", kill_history, (255, 50, 50), "Kills", "Generations")
    col2_y = draw_graph_dynamic(col2_x, col2_y, col_width, "Avg Reward", reward_history, (128, 0, 128), "Points", "Generations")
    col2_y = draw_graph_dynamic(col2_x, col2_y, col_width, "Episode Length", duration_history, (255, 165, 0), "Steps", "Generations")

    # Cycle Performance Graph (Moved to Col 2 Top)
    h_cycle_perf = 100
    draw_card_dynamic(col2_x, col2_y, col_width, h_cycle_perf, f"Cycle Performance (Avg)")
    
    # Sanitize data: keep only numbers
    clean_cycle_perf = []
    for x in cycle_performance:
        try:
            val = float(x)
            clean_cycle_perf.append(val)
        except (ValueError, TypeError):
            continue
            
    if len(clean_cycle_perf) > 0:
        # Graph rect inside card
        graph_rect = pygame.Rect(col2_x + 45, col2_y + 30, col_width - 55, 40)
        pygame.draw.rect(screen, (20, 20, 20), graph_rect)
        pygame.draw.rect(screen, (100, 100, 100), graph_rect, 1)
        
        # Y-axis label
        y_surf = font.render("Reward", True, (120, 120, 120))
        y_surf = pygame.transform.rotate(y_surf, 90)
        screen.blit(y_surf, (col2_x + 5, col2_y + 30))
        
        # X-axis label
        x_surf = font.render("Cycles", True, (120, 120, 120))
        screen.blit(x_surf, (graph_rect.centerx - x_surf.get_width()//2, graph_rect.bottom + 2))
        
        # X-Axis Start/End Labels
        # Start (1)
        start_surf = font.render("1", True, (150, 150, 150))
        screen.blit(start_surf, (graph_rect.left, graph_rect.bottom + 2))
        
        # End (len(data))
        end_surf = font.render(str(len(clean_cycle_perf)), True, (150, 150, 150))
        screen.blit(end_surf, (graph_rect.right - end_surf.get_width(), graph_rect.bottom + 2))
        
        max_val = max(clean_cycle_perf)
        min_val = min(clean_cycle_perf)
        
        # Draw Value Labels
        screen.blit(font.render(f"{max_val:.1f}", True, (150, 150, 150)), (col2_x + 20, col2_y + 25))
        screen.blit(font.render(f"{min_val:.1f}", True, (150, 150, 150)), (col2_x + 20, col2_y + 60))
        
        # Draw points
        points = []
        if max_val > min_val:
            for i, val in enumerate(clean_cycle_perf):
                px = graph_rect.left + (i / max(1, len(clean_cycle_perf)-1)) * graph_rect.width
                norm_val = (val - min_val) / (max_val - min_val)
                py = graph_rect.bottom - norm_val * graph_rect.height
                points.append((px, py))
        else:
            # Flat line
            py = graph_rect.centery
            for i in range(len(clean_cycle_perf)):
                px = graph_rect.left + (i / max(1, len(clean_cycle_perf)-1)) * graph_rect.width
                points.append((px, py))
        
        if len(points) > 1:
            pygame.draw.lines(screen, (100, 200, 255), False, points, 2)  # Cyan for cycle perf
        elif len(points) == 1:
            pygame.draw.circle(screen, (100, 200, 255), (int(points[0][0]), int(points[0][1])), 3)
    else:
        # Show placeholder when no cycles completed yet
        msg1 = "Waiting for first cycle..."
        msg2 = f"Current: Cycle {cycle_number}, {current_season}"
        screen.blit(font.render(msg1, True, (120, 120, 120)), (col2_x + 20, col2_y + 35))
        screen.blit(font.render(msg2, True, (150, 150, 150)), (col2_x + 20, col2_y + 55))
    
    col2_y += h_cycle_perf + 10

    # ==========================
    # COLUMN 1: Controls & Info
    # ==========================
    
    # Controls Card
    h_controls = 180  # Reduced height for side-by-side layout
    draw_card_dynamic(col1_x, col1_y, col_width, h_controls, "Controls")
    
    # Sliders (Left Side)
    sliders[0].rect.x = col1_x + 10
    sliders[0].rect.y = col1_y + 40
    sliders[0].handle_rect.centery = sliders[0].rect.centery
    sliders[0].update_handle()
    sliders[0].draw(screen, font)
    
    sliders[1].rect.x = col1_x + 10
    sliders[1].rect.y = col1_y + 72
    sliders[1].handle_rect.centery = sliders[1].rect.centery
    sliders[1].update_handle()
    sliders[1].draw(screen, font)
    
    sliders[2].rect.x = col1_x + 10
    sliders[2].rect.y = col1_y + 104
    sliders[2].handle_rect.centery = sliders[2].rect.centery
    sliders[2].update_handle()
    sliders[2].draw(screen, font)
    
    # Buttons (Right Side)
    btn_x = col1_x + col_width - 210  # Right aligned
    
    # Update Visuals Button
    button.rect.x = btn_x
    button.rect.y = col1_y + 40
    button.draw(screen, font)
    
    # Sound button
    if btn_sound:
        btn_sound.rect.x = btn_x
        btn_sound.rect.y = col1_y + 72
        btn_sound.draw(screen, font)
    
    # Reset Epsilon button
    btn_reset_epsilon.rect.x = btn_x
    btn_reset_epsilon.rect.y = col1_y + 104
    btn_reset_epsilon.draw(screen, font)
    
    # Clear Hall of Fame button
    btn_clear_hof.rect.x = btn_x
    btn_clear_hof.rect.y = col1_y + 136
    btn_clear_hof.draw(screen, font)
    
    col1_y += h_controls + 10
    
    # Seasons Card
    h_seasons = 130
    draw_card_dynamic(col1_x, col1_y, col_width, h_seasons, "Seasons")
    
    # Import season presets for colors
    from config.constants import SEASON_PRESETS
    
    # Season buttons
    btn_auto, btn_spring, btn_summer, btn_autumn, btn_winter = season_buttons
    
    # Row 1: AUTO button (full width)
    btn_auto.rect.x = col1_x + 10
    btn_auto.rect.y = col1_y + 35
    btn_auto.rect.width = col_width - 20
    if auto_season_mode:
        # Highlight when active
        pygame.draw.rect(screen, (0, 150, 0), btn_auto.rect)
        pygame.draw.rect(screen, (0, 255, 0), btn_auto.rect, 2)
        screen.blit(font.render("AUTO (ON)", True, (255, 255, 255)), (btn_auto.rect.x + 10, btn_auto.rect.y + 5))
    else:
        btn_auto.draw(screen, font)
    
    # Row 2: 4 Season buttons (4 columns)
    btn_width = (col_width - 60) // 4  # 4 buttons with spacing
    buttons = [btn_spring, btn_summer, btn_autumn, btn_winter]
    seasons = ["Spring", "Summer", "Autumn", "Winter"]
    season_abbr = ["Sp", "Su", "Au", "Wi"]
    
    for i, (btn, season_name, abbr) in enumerate(zip(buttons, seasons, season_abbr)):
        btn.rect.x = col1_x + 10 + i * (btn_width + 10)
        btn.rect.y = col1_y + 70
        btn.rect.width = btn_width
        
        # Highlight current season
        if season_name == current_season:
            color = SEASON_PRESETS[season_name]['color']
            pygame.draw.rect(screen, color, btn.rect)
            pygame.draw.rect(screen, (255, 255, 255), btn.rect, 2)
            # Draw text centered
            text = title_font.render(abbr, True, (0, 0, 0))
            text_x = btn.rect.x + (btn.rect.width - text.get_width()) // 2
            screen.blit(text, (text_x, btn.rect.y + 5))
        else:
            btn.draw(screen, font)
    
    # Row 3: Current season info + Convergence status
    season_color = SEASON_PRESETS[current_season]['color']
    info_text = f"{current_season} | Cycle {cycle_number} | Season Gen {season_gens_counter}"
    screen.blit(font.render(info_text, True, season_color), (col1_x + 10, col1_y + 100))
    
    # Convergence info on second line
    cv_color = (100, 255, 100) if "OK" in convergence_info else (255, 150, 150)
    screen.blit(font.render(convergence_info, True, cv_color), (col1_x + 10, col1_y + 115))
    
    col1_y += h_seasons + 10

    # Game Stats Card (moved between Seasons and Season Effects)
    h_stats = 115
    draw_card_dynamic(col1_x, col1_y, col_width, h_stats, "Game Stats")
    alive_count = sum(1 for a in agents if a.alive)
    predators_alive = sum(1 for p in predators if p.alive) if predators else 0
    
    # Split into 2 columns
    inner_col_w = col_width // 2
    
    # Row 1
    screen.blit(font.render(f"Global Gen: {generation}", True, (180, 180, 180)), (col1_x + 10, col1_y + 30))
    screen.blit(font.render(f"Steps: {gen_steps}/{int(max_steps_per_gen)}", True, (180, 180, 180)), (col1_x + 10 + inner_col_w, col1_y + 30))
    
    # Row 2
    screen.blit(font.render(f"Alive: {alive_count}", True, (180, 180, 180)), (col1_x + 10, col1_y + 48))
    screen.blit(font.render(f"Predators: {predators_alive}", True, (180, 180, 180)), (col1_x + 10 + inner_col_w, col1_y + 48))
    
    # Row 3
    screen.blit(font.render(f"Speed: {int(cycles_per_hour)} Gen/h", True, (180, 180, 180)), (col1_x + 10, col1_y + 66))
    screen.blit(font.render(f"Device: {device.type.upper()}", True, (180, 180, 180)), (col1_x + 10 + inner_col_w, col1_y + 66))
    
    # Row 4 (Full width)
    kill_str = f"Kills: S:{global_kills_by_type[WEAPON_SWORD]} B:{global_kills_by_type[WEAPON_BOW]} M:{global_kills_by_type[WEAPON_WAND]}"
    screen.blit(font.render(kill_str, True, (180, 180, 180)), (col1_x + 10, col1_y + 84))

    col1_y += h_stats + 10

    # Season Explanation Card
    h_explanation = 100
    draw_card_dynamic(col1_x, col1_y, col_width, h_explanation, "Season Effects")
    
    explanation_lines = [
        ("Sp: Balanced (Baseline, 10 Preds)", (100, 255, 100)),
        ("Su: Heat (Rare Potions, 10 Preds)", (255, 200, 50)),
        (f"Au: Scarce but Viable (+% Wood, 12 Preds)", (255, 150, 50)),
        ("Wi: Survival (-33% Wood, -47% Time, 8 Preds)", (150, 200, 255))
    ]
    
    for i, (text, color) in enumerate(explanation_lines):
        screen.blit(font.render(text, True, color), (col1_x + 10, col1_y + 30 + i * 16))
    
    col1_y += h_explanation + 10

    
    # Legend Card - 3 columns layout
    h_legend = 85  # Reduced height with 3-column layout
    draw_card_dynamic(col1_x, col1_y, col_width, h_legend, "Legend")
    
    # Organize items into 3 columns: Materials, Potions, Entities
    legend_items = [
        (COLOR_WALL, "Wall"),
        (COLOR_WOOD, "Wood"),
        (COLOR_IRON, "Iron"),
        (COLOR_POTION_HEALTH, "Health"),
        (COLOR_POTION_ENERGY, "Energy"),
        (COLOR_POTION_MAGIC, "Magic"),
        ((50, 100, 255), "Warrior"),
        ((255, 255, 50), "Scout"),
        ((50, 255, 50), "Healer"),
        ((255, 0, 0), "Predator")
    ]
    
    col_w = col_width // 3  # Divide into 3 columns
    items_per_col = 4  # Max 4 items per column
    
    for i, (color, text) in enumerate(legend_items):
        col_idx = i // items_per_col  # Which column (0, 1, 2)
        row_idx = i % items_per_col   # Which row in that column
        
        lx = col1_x + 10 + col_idx * col_w
        ly = col1_y + 30 + row_idx * 14  # Reduced spacing to 14px
        
        # Draw icon based on type
        if text == "Wood": 
            draw_tree(screen, lx//CELL_SIZE, ly//CELL_SIZE)
        elif text == "Iron": 
            draw_rock(screen, lx//CELL_SIZE, ly//CELL_SIZE)
        elif text in ["Health", "Energy", "Magic"]: 
            c = COLOR_POTION_HEALTH
            if text == "Energy": c = COLOR_POTION_ENERGY
            elif text == "Magic": c = COLOR_POTION_MAGIC
            draw_potion(screen, lx//CELL_SIZE, ly//CELL_SIZE, c)
        elif text == "Predator":
            pygame.draw.polygon(screen, (255, 0, 0), [(lx+6, ly), (lx+12, ly+6), (lx+6, ly+12), (lx, ly+6)])
        else:
            pygame.draw.rect(screen, color, (lx, ly, 12, 12))
        
        # Draw label
        screen.blit(font.render(text, True, (180, 180, 180)), (lx + 20, ly - 2))
    
    col1_y += h_legend + 10

    # Game Rules Card - 2 columns layout
    h_rules = 220  # Increased from 175 to fix overflow
    draw_card_dynamic(col1_x, col1_y, col_width, h_rules, "Game Rules")
    
    rules = [
        ("LOOT & CRAFTING:", (255, 255, 255)),
        ("- Wood -> Arrows (Bow Ammo)", (180, 180, 180)),
        ("- Iron -> Armor (Reduces Dmg)", (180, 180, 180)),
        ("POTIONS:", (255, 255, 255)),
        (f"- Red: +{POTION_HEAL_AMOUNT} HP + Magic Bonus", (255, 100, 100)),
        (f"- Blue: +{POTION_STAMINA_AMOUNT} Stamina", (100, 100, 255)),
        (f"- Purple: +{POTION_MAGIC_AMOUNT} Magic Power", (200, 100, 200)),
        ("STATS:", (255, 255, 255)),
        (f"- STR: Sword Dmg (Warrior) [Base: {SWORD_DAMAGE_BASE}]", (200, 200, 200)),
        ("- PRC: Bow Dmg (Scout)", (200, 200, 200)),
        ("- MAG: Wand Dmg + Heal (Healer)", (200, 200, 200)),
        ("REWARDS (COLLECTIVE):", (255, 255, 0)),
        ("- Team Share: 1% of ALL rewards!", (100, 255, 100)),
        ("- Predator Kill: +100 (+200 War)", (255, 100, 100)),
        ("- Predator Hit: +5 (Damage)", (255, 100, 100)),
        ("- Resources: +5 (+2 Scout)", (255, 255, 50)),
        ("- Posion Magic: +20 (+50 Healer)", (50, 255, 50)),
        (f"- Healer Aura: +2 per Ally", (50, 255, 50)),
        (f"- Shout: +{int(REWARD_SHOUT_SUCCESS)} (Success) / -0.1 (Fail)", (180, 180, 180)),
        ("- Survival: +0.2/step", (180, 180, 180)),
        ("- Wall hit: -0.1", (180, 180, 180)),
        ("- Death: -100", (180, 180, 180))
    ]
    # Split into 2 columns
    mid_point = 10  # First 10 items in left column
    col_w = col_width // 2
    
    for i, (text, color) in enumerate(rules):
        if i < mid_point:
            # Left column
            lx = col1_x + 10
            ly = col1_y + 30 + i * 13
        else:
            # Right column
            lx = col1_x + col_w + 5
            ly = col1_y + 30 + (i - mid_point) * 13
        
        screen.blit(font.render(text, True, color), (lx, ly))
    
    col1_y += h_rules + 10

    # Selected Agent Card (Moved to Col 1 Bottom)
    h_selected = 130
    if selected_agent and selected_agent.alive:
        h_selected = 300 # Expand for Brain view
        
    draw_card_dynamic(col1_x, col1_y, col_width, h_selected, "Selected Agent")
    
    if selected_agent and selected_agent.alive:
        w_name = ['Fists', 'Sword', 'Bow', 'Wand'][selected_agent.weapon]
        k_str = f"S:{selected_agent.kills_by_type[WEAPON_SWORD]} B:{selected_agent.kills_by_type[WEAPON_BOW]} M:{selected_agent.kills_by_type[WEAPON_WAND]}"
        lines = [
            f"ID: {selected_agent.id} | {w_name}",
            f"HP: {selected_agent.hp:.0f}/{selected_agent.max_hp} | Stam: {selected_agent.stamina:.0f}",
            f"STR: {selected_agent.strength} PRC: {selected_agent.precision} MAG: {selected_agent.magic}",
            f"Kills: {selected_agent.kills} [{k_str}]"
        ]
        for i, line in enumerate(lines):
            screen.blit(font.render(line, True, (180, 180, 180)), (col1_x + 10, col1_y + 30 + i * 16))
            
        # Draw Brain (Q-Values)
        if selected_agent.last_q_values is not None:
            q_y = col1_y + 100
            screen.blit(font.render("Brain Activity (Q-Values):", True, (200, 200, 200)), (col1_x + 10, q_y))
            
            actions = ["Up", "Dn", "Lt", "Rt", "Atk", "Wait", "C:D", "C:H", "C:P"]
            q_vals = selected_agent.last_q_values
            
            # Normalize for display
            min_q = np.min(q_vals)
            max_q = np.max(q_vals)
            range_q = max_q - min_q if max_q != min_q else 1.0
            
            bar_w = (col_width - 40) // len(actions)
            
            for i, (act, val) in enumerate(zip(actions, q_vals)):
                bx = col1_x + 20 + i * bar_w
                by = q_y + 100
                bh = 60
                
                norm_h = (val - min_q) / range_q
                h = int(norm_h * bh)
                
                # Color based on value (Red=Low, Green=High)
                c_val = int(norm_h * 255)
                color = (255 - c_val, c_val, 100)
                
                # Highlight max action
                if val == max_q:
                    pygame.draw.rect(screen, (255, 255, 255), (bx, by - h - 2, bar_w - 2, h + 2), 1)
                
                pygame.draw.rect(screen, color, (bx, by - h, bar_w - 2, h))
                
                # Label
                lbl = font.render(act, True, (150, 150, 150))
                screen.blit(lbl, (bx + (bar_w - lbl.get_width())//2, by + 5))
                
    else:
        screen.blit(font.render("Select an agent to inspect", True, (100, 100, 100)), (col1_x + 10, col1_y + 30))
    col1_y += h_selected + 10



    # ==========================
    # COLUMN 2: Stats & Graphs
    # ==========================

    # Loss Graph (Top of Col 2)
    col2_y = draw_graph_dynamic(col2_x, col2_y, col_width, "Avg Loss / Gen", loss_history, (0, 255, 255), "Loss", "Generations")

    # Learning Phase Card (Epsilon)
    h_learning = 100
    draw_card_dynamic(col2_x, col2_y, col_width, h_learning, "Learning Phase")
    
    # Epsilon Bar
    bar_width = col_width - 20
    bar_height = 20
    bar_x = col2_x + 10
    bar_y = col2_y + 35
    
    # Background
    pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y, bar_width, bar_height))
    # Fill
    fill_width = int(epsilon * bar_width)
    # Color gradient from Red (High Eps) to Green (Low Eps)
    # Eps 1.0 -> Red, Eps 0.0 -> Green
    r = int(255 * epsilon)
    g = int(255 * (1 - epsilon))
    bar_color = (r, g, 0)
    pygame.draw.rect(screen, bar_color, (bar_x, bar_y, fill_width, bar_height))
    pygame.draw.rect(screen, (100, 100, 100), (bar_x, bar_y, bar_width, bar_height), 1)
    
    # Text
    phase_text = "Exploration (Chaos)"
    if epsilon < 0.2: phase_text = "Exploitation (Mastery)"
    elif epsilon < 0.5: phase_text = "Balanced Learning"
    
    screen.blit(font.render(f"Epsilon: {epsilon:.4f}", True, (255, 255, 255)), (bar_x, bar_y + 25))
    screen.blit(font.render(phase_text, True, bar_color), (bar_x + 150, bar_y + 25))
    col2_y += h_learning + 10

    # Top Agents (Current Gen)
    h_top = 180  # Reduced height with optimized layout
    draw_card_dynamic(col2_x, col2_y, col_width, h_top, "Current Gen Leaders")
    
    # Sort current agents by reward (descending)
    top_current = sorted([a for a in agents if a.alive], key=lambda x: x.total_reward, reverse=True)[:3]
    
    for i, agent in enumerate(top_current):
        row_y = col2_y + 35 + i * 48  # Reduced spacing from 60 to 48
        
        # Agent Icon/Color
        pygame.draw.circle(screen, agent.color, (col2_x + 25, row_y + 12), 10)
        pygame.draw.circle(screen, (255, 255, 255), (col2_x + 25, row_y + 12), 10, 1)
        
        # Line 1: ID/Weapon + Kills (side by side)
        w_name = ['Fists', 'Sword', 'Bow', 'Wand'][agent.weapon]
        w_color = [(200,200,200), (100,100,255), (100,255,100), (255,100,255)][agent.weapon]
        
        screen.blit(title_font.render(f"#{agent.id}", True, (255, 255, 255)), (col2_x + 45, row_y))
        screen.blit(font.render(w_name, True, w_color), (col2_x + 100, row_y + 2))
        
        # Kills on same line, aligned to right
        k_str = f"Kills: {agent.kills} (S:{agent.kills_by_type[WEAPON_SWORD]} B:{agent.kills_by_type[WEAPON_BOW]} M:{agent.kills_by_type[WEAPON_WAND]})"
        screen.blit(font.render(k_str, True, (200, 200, 200)), (col2_x + 160, row_y + 2))
        
        # Line 2: Stats
        s_str = f"STR:{agent.strength} PRC:{agent.precision} MAG:{agent.magic} HP:{int(agent.hp)}"
        screen.blit(font.render(s_str, True, (150, 150, 150)), (col2_x + 45, row_y + 18))
        
        # Line 3: Reward
        r_str = f"Reward: {agent.total_reward:.1f}"
        screen.blit(font.render(r_str, True, (200, 200, 100)), (col2_x + 45, row_y + 32))
        
    col2_y += h_top + 10

    # Hall of Fame (All-Time)
    h_hof = 180  # Reduced height with optimized layout
    draw_card_dynamic(col2_x, col2_y, col_width, h_hof, "Hall of Fame (All-Time)")
    
    if not hall_of_fame:
        screen.blit(font.render("No Legends yet...", True, (100, 100, 100)), (col2_x + 20, col2_y + 40))
    else:
        for i, data in enumerate(hall_of_fame):
            row_y = col2_y + 35 + i * 48  # Reduced spacing from 60 to 48
            
            # Rank
            rank_color = [(255, 215, 0), (192, 192, 192), (205, 127, 50)][i] # Gold, Silver, Bronze
            screen.blit(title_font.render(f"#{i+1}", True, rank_color), (col2_x + 10, row_y + 5))
            
            # Data extraction (handle dict from JSON/Storage)
            # data is a dict: {'id', 'kills', 'steps', 'weapon', 'kills_by_type', 'stats': {...}}
            aid = data['id']
            kills = data['kills']
            weapon = data['weapon']
            k_type = data['kills_by_type']
            stats = data['stats']
            gen = data.get('gen', '?')
            
            w_name = ['Fists', 'Sword', 'Bow', 'Wand'][weapon]
            w_color = [(200,200,200), (100,100,255), (100,255,100), (255,100,255)][weapon]
            
            # Line 1: ID/Gen/Weapon + Kills (side by side)
            screen.blit(font.render(f"Agent {aid} (Gen {gen})", True, (255, 255, 255)), (col2_x + 45, row_y))
            screen.blit(font.render(w_name, True, w_color), (col2_x + 180, row_y))
            
            # Kills on same line
            k_str = f"K:{kills} (S:{k_type.get(str(WEAPON_SWORD), k_type.get(WEAPON_SWORD, 0))} B:{k_type.get(str(WEAPON_BOW), k_type.get(WEAPON_BOW, 0))} M:{k_type.get(str(WEAPON_WAND), k_type.get(WEAPON_WAND, 0))})"
            screen.blit(font.render(k_str, True, (200, 200, 200)), (col2_x + 245, row_y))
            
            # Line 2: Stats
            s_str = f"STR:{stats['str']} PRC:{stats['prc']} MAG:{stats['mag']} Steps:{data['steps']}"
            screen.blit(font.render(s_str, True, (150, 150, 150)), (col2_x + 45, row_y + 18))
            
            # Line 3: Reward
            reward = data.get('reward', 0)
            r_str = f"Reward: {reward:.1f}"
            screen.blit(font.render(r_str, True, (200, 200, 100)), (col2_x + 45, row_y + 32))

    col2_y += h_hof + 10

    # Action Distribution Card
    h_action_dist = 200  # Increased height for 9 actions
    draw_card_dynamic(col2_x, col2_y, col_width, h_action_dist, "Action Distribution")
    
    # Get latest action distribution
    if action_history:
        latest_dist = action_history[-1]
        action_names = ["Up", "Dn", "Lt", "Rt", "Atk", "Wait", "C:D", "C:H", "C:P"]
        action_colors = [
            (150, 150, 150), (150, 150, 150), (150, 150, 150), (150, 150, 150), # Move
            (255, 50, 50),   # Attack
            (100, 100, 255), # Wait/Shout
            (255, 0, 0),     # Danger
            (0, 255, 0),     # Heal
            (255, 0, 255)    # Potion
        ]
        
        # Draw bars
        bar_height = 15
        max_width = col_width - 80
        for i in range(9):  # NUM_ACTIONS
            percentage = latest_dist.get(i, 0.0)
            y_pos = col2_y + 35 + i * 18
            
            # Label
            screen.blit(font.render(action_names[i], True, (200, 200, 200)), (col2_x + 10, y_pos))
            
            # Background bar
            pygame.draw.rect(screen, (40, 40, 40), (col2_x + 35, y_pos, max_width, bar_height))
            
            # Filled bar
            fill_width = int(percentage * max_width)
            pygame.draw.rect(screen, action_colors[i], (col2_x + 35, y_pos, fill_width, bar_height))
            pygame.draw.rect(screen, (100, 100, 100), (col2_x + 35, y_pos, max_width, bar_height), 1)
            
            # Percentage text
            pct_text = f"{percentage*100:.1f}%"
            screen.blit(font.render(pct_text, True, (180, 180, 180)), (col2_x + 35 + max_width + 5, y_pos))
    else:
        screen.blit(font.render("No data yet...", True, (100, 100, 100)), (col2_x + 20, col2_y + 40))
    
    col2_y += h_action_dist + 10




