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
    device
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


def draw_grid(screen: pygame.Surface, env: Any, agents: List[Any], 
              particles: List[List], selected_agent: Optional[Any]) -> None:
    """
    Draw the entire game grid with tiles, agents, and visual effects.
    
    Uses optimized rendering by only drawing non-empty tiles. Applies
    the vertical grid offset for proper alignment.
    
    Args:
        screen: Pygame surface to draw on
        env: Environment containing the grid
        agents: List of agent objects
        particles: List of particle effects [x, y, color, radius, max_radius]
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
            
    # Draw Particles
    for p in particles:
        # p[1] is y coordinate in pixels, need to add offset
        pygame.draw.circle(screen, p[2], (int(p[0]), int(p[1] + GRID_OFFSET_Y)), int(p[3]), 2)


def draw_ui(screen: pygame.Surface, font: pygame.font.Font, title_font: pygame.font.Font,
            sliders: List[Any], button: Any, agents: List[Any], selected_agent: Optional[Any],
            generation: int, gen_steps: int, max_steps_per_gen: int, 
            global_kills_by_type: dict, kill_history: List[int], 
            reward_history: List[float], duration_history: List[int],
            cycles_per_hour: float, epsilon: float, hall_of_fame: List[dict],
            action_history: List[dict], btn_reset_epsilon: Any, btn_clear_hof: Any,
            season_buttons: List[Any], current_season: str, auto_season_mode: bool,
            cycle_number: int, season_gens_counter: int, cycle_performance: List[float],
            convergence_info: str) -> None:
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

    # ==========================
    # COLUMN 1: Controls & Info
    # ==========================
    
    # Controls Card
    h_controls = 340  # Increased height to fit all buttons comfortably
    draw_card_dynamic(col1_x, col1_y, col_width, h_controls, "Controls")
    
    # Update Slider 0
    sliders[0].rect.x = col1_x + 10
    sliders[0].rect.y = col1_y + 80
    sliders[0].handle_rect.centery = sliders[0].rect.centery
    sliders[0].update_handle()
    sliders[0].draw(screen, font)
    
    # Update Slider 1
    sliders[1].rect.x = col1_x + 10
    sliders[1].rect.y = col1_y + 120
    sliders[1].handle_rect.centery = sliders[1].rect.centery
    sliders[1].update_handle()
    sliders[1].draw(screen, font)
    
    # Update Slider 2
    sliders[2].rect.x = col1_x + 10
    sliders[2].rect.y = col1_y + 160
    sliders[2].handle_rect.centery = sliders[2].rect.centery
    sliders[2].update_handle()
    sliders[2].draw(screen, font)
    
    # Update Button
    button.rect.x = col1_x + 10
    button.rect.y = col1_y + 200
    button.draw(screen, font)
    
    # New buttons
    btn_reset_epsilon.rect.x = col1_x + 10
    btn_reset_epsilon.rect.y = col1_y + 235
    btn_reset_epsilon.draw(screen, font)
    
    btn_clear_hof.rect.x = col1_x + 10
    btn_clear_hof.rect.y = col1_y + 270
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
    info_text = f"{current_season} | Cycle {cycle_number} | Gen {season_gens_counter}"
    screen.blit(font.render(info_text, True, season_color), (col1_x + 10, col1_y + 100))
    
    # Convergence info on second line
    cv_color = (100, 255, 100) if "OK" in convergence_info else (255, 150, 150)
    screen.blit(font.render(convergence_info, True, cv_color), (col1_x + 10, col1_y + 115))
    
    col1_y += h_seasons + 10

    # Season Explanation Card
    h_explanation = 100
    draw_card_dynamic(col1_x, col1_y, col_width, h_explanation, "Season Effects")
    
    explanation_lines = [
        ("Sp: Balanced (Baseline)", (100, 255, 100)),
        ("Su: Scarce (-67% Wood, -60% Potions)", (255, 200, 50)),
        ("Au: Abundant (+67% Wood, +100% Potions)", (255, 150, 50)),
        ("Wi: Survival (-83% Wood, -47% Time)", (150, 200, 255))
    ]
    
    for i, (text, color) in enumerate(explanation_lines):
        screen.blit(font.render(text, True, color), (col1_x + 10, col1_y + 30 + i * 16))
    
    col1_y += h_explanation + 10

    
    # Legend Card
    h_legend = 130
    draw_card_dynamic(col1_x, col1_y, col_width, h_legend, "Legend")
    legend_items = [
        (COLOR_BG, "Empty"),
        (COLOR_WALL, "Wall"),
        (COLOR_WOOD, "Wood"),
        (COLOR_IRON, "Iron"),
        (COLOR_POTION_HEALTH, "Health"),
        (COLOR_POTION_ENERGY, "Energy"),
        (COLOR_POTION_MAGIC, "Magic")
    ]
    for i, (color, text) in enumerate(legend_items):
        ly = col1_y + 30 + i * 16
        lx = col1_x + 10
        if i >= 4: # Split into 2 columns for potions within legend
             ly = col1_y + 30 + (i-4) * 16
             lx = col1_x + col_width // 2 + 10
             
        if text == "Empty": continue
        
        if text == "Wood": draw_tree(screen, lx//CELL_SIZE, ly//CELL_SIZE) # Hacky preview
        elif text == "Iron": draw_rock(screen, lx//CELL_SIZE, ly//CELL_SIZE)
        elif "Potion" in text: 
            c = COLOR_POTION_HEALTH
            if "Energy" in text: c = COLOR_POTION_ENERGY
            elif "Magic" in text: c = COLOR_POTION_MAGIC
            draw_potion(screen, lx//CELL_SIZE, ly//CELL_SIZE, c)
        else:
            pygame.draw.rect(screen, color, (lx, ly, 12, 12))
            
        screen.blit(font.render(text, True, (180, 180, 180)), (lx + 20, ly - 2))
    col1_y += h_legend + 10

    # Game Rules Card
    h_rules = 320  # Increased height for reward section
    draw_card_dynamic(col1_x, col1_y, col_width, h_rules, "Game Rules")
    rules = [
        ("LOOT & CRAFTING:", (255, 255, 255)),
        ("- Wood -> Arrows (Bow Ammo)", (180, 180, 180)),
        ("- Iron -> Armor (Reduces Dmg)", (180, 180, 180)),
        ("POTIONS:", (255, 255, 255)),
        ("- Red: +20 HP + Magic Bonus", (255, 100, 100)),
        ("- Blue: +30 Stamina", (100, 100, 255)),
        ("- Purple: +1 Magic Power", (200, 100, 200)),
        ("STATS:", (255, 255, 255)),
        ("- STR: Fists/Sword Dmg", (200, 200, 200)),
        ("- PRC: Bow Dmg/Accuracy", (200, 200, 200)),
        ("- MAG: Wand Dmg + Potion Eff.", (200, 200, 200)),
        ("REWARDS:", (255, 255, 0)),
        ("- Survival: +0.1/step", (180, 180, 180)),
        ("- Resources: +5 (Wood/Iron/Magic)", (180, 180, 180)),
        ("- Attack Hit: +10", (180, 180, 180)),
        ("- Kill: +100", (180, 180, 180)),
        ("- Wall hit: -0.1", (180, 180, 180)),
        ("- Death: -100", (180, 180, 180))
    ]
    for i, (text, color) in enumerate(rules):
        screen.blit(font.render(text, True, color), (col1_x + 10, col1_y + 30 + i * 14))
    col1_y += h_rules + 10

    # Selected Agent Card
    h_selected = 130
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
    else:
        screen.blit(font.render("Select an agent", True, (100, 100, 100)), (col1_x + 10, col1_y + 30))
    col1_y += h_selected + 10

    # ==========================
    # COLUMN 2: Stats & Graphs
    # ==========================

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

    # Game Stats Card
    h_stats = 120
    draw_card_dynamic(col2_x, col2_y, col_width, h_stats, "Game Stats")
    alive_count = sum(1 for a in agents if a.alive)
    stats_lines = [
        f"Gen: {generation} | Steps: {gen_steps}/{int(max_steps_per_gen)}",
        f"Speed: {int(cycles_per_hour)} Gen/h",
        f"Alive: {alive_count} | Device: {device.type.upper()}",
        f"Global Kills: S:{global_kills_by_type[WEAPON_SWORD]} B:{global_kills_by_type[WEAPON_BOW]} M:{global_kills_by_type[WEAPON_WAND]} F:{global_kills_by_type[WEAPON_FISTS]}"
    ]
    for i, line in enumerate(stats_lines):
        screen.blit(font.render(line, True, (180, 180, 180)), (col2_x + 10, col2_y + 30 + i * 18))
    col2_y += h_stats + 10

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
    h_action_dist = 140
    draw_card_dynamic(col2_x, col2_y, col_width, h_action_dist, "Action Distribution")
    
    # Get latest action distribution
    if action_history:
        latest_dist = action_history[-1]
        action_names = ["Up", "Down", "Left", "Right", "Attack", "Wait"]
        action_colors = [
            (100, 150, 255),  # Up - Blue
            (100, 150, 255),  # Down - Blue
            (255, 200, 100),  # Left - Orange
            (255, 200, 100),  # Right - Orange
            (255, 100, 100),  # Attack - Red
            (150, 255, 150)   # Wait - Green
        ]
        
        # Draw bars
        bar_height = 15
        max_width = col_width - 80
        for i in range(6):  # NUM_ACTIONS
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

    # Cycle Performance Graph (Always visible)
    h_cycle_perf = 100
    draw_card_dynamic(col2_x, col2_y, col_width, h_cycle_perf, f"Cycle Performance (Avg)")
    
    if len(cycle_performance) > 0:
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
        
        max_val = max(cycle_performance)
        min_val = min(cycle_performance)
        
        # Draw Value Labels
        screen.blit(font.render(f"{max_val:.1f}", True, (150, 150, 150)), (col2_x + 20, col2_y + 25))
        screen.blit(font.render(f"{min_val:.1f}", True, (150, 150, 150)), (col2_x + 20, col2_y + 60))
        
        # Draw points
        points = []
        if max_val > min_val:
            for i, val in enumerate(cycle_performance):
                px = graph_rect.left + (i / max(1, len(cycle_performance)-1)) * graph_rect.width
                norm_val = (val - min_val) / (max_val - min_val)
                py = graph_rect.bottom - norm_val * graph_rect.height
                points.append((px, py))
        else:
            # Flat line
            py = graph_rect.centery
            for i in range(len(cycle_performance)):
                px = graph_rect.left + (i / max(1, len(cycle_performance)-1)) * graph_rect.width
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


