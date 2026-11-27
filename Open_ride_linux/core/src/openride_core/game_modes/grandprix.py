"""Adaptateur du Grand Prix des objets et de la Course (séries GP et CR) : `grandprix.GrandPrixMode`."""

from __future__ import annotations

from ..grandprix import ME as GP_ME
from .base import GameMode, ModeContext


class GrandPrixGameMode(GameMode):
    id, attr = "grandprix", "grandprix"

    def fill_frame(self, ctx: ModeContext) -> None:
        """Champ `gp` ; objet en réserve et effets en cours de chaque bot."""
        st = ctx.state
        gp = self.obj(ctx)
        if gp is None or not ctx.running:
            st.gp = None
            return
        st.gp = gp.frame(GP_ME)
        if st.bots:
            st.bots = [{**b, **gp.bot_frame(b["id"])} if b["id"] in gp.racers else b for b in st.bots]
