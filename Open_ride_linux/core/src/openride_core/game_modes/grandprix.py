"""Adaptateur du Grand Prix des objets et de la Course (séries GP et CR) : `grandprix.GrandPrixMode`."""

from __future__ import annotations

import time
from typing import Any

from ..grandprix import ME as GP_ME
from .base import GameMode, ModeContext


class GrandPrixGameMode(GameMode):
    id, attr = "grandprix", "grandprix"
    summary_key = "gp"
    elo_modes = ("grandprix", "race")   # la Course est un Grand Prix sans objet (lot CR1)

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

    def end(self, ctx: ModeContext, obj: Any) -> None:
        """Champ `gp` vidé ; voie du cycliste reprise ; coups, boîtes et bilan au journal (lot GP2), avant les
        lignes des autres modes comme avant le lot IM2."""
        ctx.state.gp = None
        if obj is None:
            return
        ctx.end_grandprix(obj)
        if ctx.recording:
            ctx.game({"kind": "gp_summary", "ts": round(time.time(), 3), **obj.summary()})

    def summary(self, obj: Any, result: Any) -> dict | None:
        """Lot GP2 : place, objets lancés, reçus, esquivés, temps par objet."""
        return obj.summary()

    def ranking(self, obj: Any) -> list[list[str]] | None:
        """Ordre d'arrivée ; None si le cycliste n'a pas passé la ligne."""
        if obj.racers[GP_ME].finished is None:
            return None
        return [[r.id] for r in obj.order()]
