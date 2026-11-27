"""Adaptateur du Cyber-Rogue (série R) : `rogue.mode.RogueMode`."""

from __future__ import annotations

from .base import GameMode, ModeContext


class RogueGameMode(GameMode):
    id, attr = "rogue", "rogue"

    def fill_frame(self, ctx: ModeContext) -> None:
        """Objet `rogue` : état du dernier pas et événements de tous les pas depuis la trame précédente (lot R23 : la
        boucle tourne à 50 Hz, la trame part à 30 Hz). Champ gardé tel quel quand le mode n'est pas là."""
        rg = self.obj(ctx)
        if rg is None:
            return
        frame = rg.take_frame()
        if frame is not None:
            ctx.state.rogue = frame
