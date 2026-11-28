"""Adaptateur du Dernier survivant (série DS) : `survivor.SurvivorRace`."""

from __future__ import annotations

import time
from typing import Any

from .. import bot_elo
from .base import GameMode, ModeContext


class SurvivorMode(GameMode):
    id, attr = "survivor", "survivor"
    summary_key = "survivor"
    elo_modes = ("survivor",)

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

    def end(self, ctx: ModeContext, obj: Any) -> None:
        ctx.state.survivor = None
        ctx.end_survivor_bots()

    def finish(self, ctx: ModeContext, obj: Any, save: bool) -> Any:
        if ctx.recording:   # lot DS2 : éliminations et bilan au journal
            for line in obj.take_journal():
                ctx.game(line)
            ctx.game({"kind": "survivor_summary", "ts": round(time.time(), 3), **obj.summary()})
            for bot in ctx.bots:
                if hasattr(bot, "power_factor"):
                    bot.power_factor = 1.0
        return None

    def summary(self, obj: Any, result: Any) -> dict | None:
        """Lot DS2 : place, éliminations, vainqueur."""
        return obj.summary()

    def ranking(self, obj: Any) -> list[list[str]] | None:
        """Places d'élimination, les non éliminés ex aequo en tête ; None tant que le cycliste n'est pas classé."""
        if obj.racers[bot_elo.ME].place is None:
            return None
        return bot_elo.order_from_places(((r.id, r.place) for r in obj.racers.values()), unplaced_first=True)
