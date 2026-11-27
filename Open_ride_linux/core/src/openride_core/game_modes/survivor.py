"""Adaptateur du Dernier survivant (série DS) : `survivor.SurvivorRace`."""

from __future__ import annotations

from .base import GameMode, ModeContext


class SurvivorMode(GameMode):
    id, attr = "survivor", "survivor"

    def fill_frame(self, ctx: ModeContext) -> None:
        """Champ `survivor` ; puissance pour revenir sur le coureur devant ; champ `out` des bots éliminés."""
        st = ctx.state
        sv = self.obj(ctx)
        if sv is None or not ctx.running:
            st.survivor = None
            return
        st.survivor = sv.frame()
        ahead = st.survivor.get("ahead")
        if ahead is not None:
            ahead["catch_w"] = ctx.survivor_catch_w(ahead["id"])
        if st.bots:
            out = ctx.survivor_out
            st.bots = [{**b, "out": sv.racers[b["id"]].out_arch} if b["id"] in out else b for b in st.bots]
