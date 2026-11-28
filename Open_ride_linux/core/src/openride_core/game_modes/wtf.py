"""Adaptateur du Mode WTF (série WTF) : `wtf.mode.WtfMode`."""

from __future__ import annotations

from .base import GameMode, ModeContext


class WtfGameMode(GameMode):
    id, attr = "wtf", "wtf"

    def fill_frame(self, ctx: ModeContext) -> None:
        st = ctx.state
        wtf = self.obj(ctx)
        if wtf is None or not ctx.running:
            st.wtf = None
            return
        st.wtf = wtf.frame(ctx.t_session, ctx.physics.s)
