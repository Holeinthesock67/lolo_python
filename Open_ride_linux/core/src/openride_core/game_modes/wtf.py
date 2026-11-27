"""Adaptateur du Mode WTF (série WTF) : `wtf.mode.WtfMode`."""

from __future__ import annotations

import time
from typing import Any

from .base import GameMode, ModeContext


class WtfGameMode(GameMode):
    id, attr = "wtf", "wtf"
    summary_key = "wtf"

    def fill_frame(self, ctx: ModeContext) -> None:
        st = ctx.state
        wtf = self.obj(ctx)
        if wtf is None or not ctx.running:
            st.wtf = None
            return
        st.wtf = wtf.frame(ctx.t_session, ctx.physics.s)

    def end(self, ctx: ModeContext, obj: Any) -> None:
        ctx.state.wtf = None

    def finish(self, ctx: ModeContext, obj: Any, save: bool) -> Any:
        if ctx.recording:
            for line in obj.take_journal():
                ctx.game({**line, "ts": round(time.time(), 3)})
            ctx.game({"kind": "wtf_summary", "ts": round(time.time(), 3), **obj.summary()})
            ctx.reset_physics()
        return None

    def summary(self, obj: Any, result: Any) -> dict | None:
        """Lot WTF2 : points et événements joués."""
        return obj.summary()
