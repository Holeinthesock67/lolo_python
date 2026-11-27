"""Adaptateur des épreuves de piste (série VD) : `track.TrackEvent`."""

from __future__ import annotations

import time
from typing import Any

from .base import GameMode, ModeContext


class TrackMode(GameMode):
    id, attr = "track", "track_event"
    summary_key = "track"
    elo_modes = ("track",)

    def fill_frame(self, ctx: ModeContext) -> None:
        st = ctx.state
        ev = self.obj(ctx)
        if ev is None or not ctx.running:
            st.track = None
            return
        st.track = ev.frame()

    def end(self, ctx: ModeContext, obj: Any) -> None:
        ctx.state.track = None
        ctx.end_track_choice()
        for bot in ctx.bots:   # lot VD7 : plus de consigne d'épreuve
            if hasattr(bot, "hint"):
                bot.hint, bot.race_view = None, None

    def finish(self, ctx: ModeContext, obj: Any, save: bool) -> Any:
        """Lot VD6 : faits de l'épreuve et bilan au journal, record de la piste ; rend la place du record."""
        if ctx.recording:
            for line in obj.take_journal():
                ctx.game(line)
            ctx.game({"kind": "track_summary", "ts": round(time.time(), 3), **obj.summary()})
        return ctx.track_record(obj, save)

    def summary(self, obj: Any, result: Any) -> dict | None:
        """Lot VD6 : place, temps, tours, record de la piste."""
        return {**obj.summary(), "record_rank": result}

    def ranking(self, obj: Any) -> list[list[str]] | None:
        """Classement complet de l'épreuve finie ; None avant la fin."""
        if not obj.finished:
            return None
        return [[rid] for rid in obj.full_ranking()]
