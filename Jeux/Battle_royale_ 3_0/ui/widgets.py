"""
UI Widgets for Arena of Life game.
"""
import pygame
from typing import Tuple, Callable
from config.constants import COLOR_TEXT


class Slider:
    """
    Interactive slider widget for adjusting numeric values.
    """
    def __init__(self, x: int, y: int, w: int, h: int, 
                 min_val: float, max_val: float, initial_val: float, label: str) -> None:
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.val = initial_val
        self.label = label
        self.dragging = False
        self.handle_rect = pygame.Rect(x, y - 5, 10, h + 10)
        self.update_handle()

    def update_handle(self) -> None:
        """Update handle position based on current value"""
        ratio = (self.val - self.min_val) / (self.max_val - self.min_val)
        self.handle_rect.centerx = self.rect.x + int(self.rect.width * ratio)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle mouse events for slider interaction"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.handle_rect.collidepoint(event.pos):
                self.dragging = True
            elif self.rect.collidepoint(event.pos):
                self.dragging = True
                self.update_val_from_pos(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                self.update_val_from_pos(event.pos[0])

    def update_val_from_pos(self, x: int) -> None:
        """Update value based on mouse x position"""
        x = max(self.rect.left, min(x, self.rect.right))
        ratio = (x - self.rect.left) / self.rect.width
        self.val = self.min_val + ratio * (self.max_val - self.min_val)
        self.update_handle()

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw the slider on screen"""
        label_surf = font.render(f"{self.label}: {self.val:.5f}", True, COLOR_TEXT)
        screen.blit(label_surf, (self.rect.x, self.rect.y - 20))
        pygame.draw.rect(screen, (100, 100, 100), self.rect)
        pygame.draw.rect(screen, (200, 200, 200), self.handle_rect)


class Button:
    """
    Interactive button widget.
    """
    def __init__(self, x: int, y: int, w: int, h: int, 
                 text: str, callback: Callable, color=None) -> None:
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.callback = callback
        self.hovered = False
        self.color = color  # Custom color override

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle mouse events for button interaction"""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.hovered:
                self.callback()

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw the button on screen"""
        from config.constants import COLOR_BTN, COLOR_BTN_HOVER
        
        # Determine base color
        if self.color:
            base_color = self.color
        else:
            base_color = COLOR_BTN
            
        # Apply hover effect (simple brightening or just swapping to hover color if no custom color)
        if self.hovered:
            if self.color:
                # Simple way to make it look "hovered" if custom color is set: make it slightly brighter or keep same
                # For now, let's just use the custom color but maybe add a white border or similar.
                # Or just use the standard hover color if we want consistent hover behavior?
                # User asked for "Green when ON". Let's stick to the requested color.
                # We can blend it with white to make it lighter for hover.
                r, g, b = base_color
                color = (min(r + 30, 255), min(g + 30, 255), min(b + 30, 255))
            else:
                color = COLOR_BTN_HOVER
        else:
            color = base_color

        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, (200, 200, 200), self.rect, 1)
        text_surf = font.render(self.text, True, COLOR_TEXT)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)
