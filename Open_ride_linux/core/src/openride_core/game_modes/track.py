"""Adaptateur des épreuves de piste (série VD) : `track.TrackEvent`."""

from __future__ import annotations

from .base import GameMode, ModeContext


class TrackMode(GameMode):
    id, attr = "track", "track_event"

    def fill_frame(self, ctx: ModeContext) -> None:
        st = ctx.state
        ev = self.obj(ctx)
        if ev is None or not ctx.running:
            st.track = None
            return
        st.track = ev.frame()
