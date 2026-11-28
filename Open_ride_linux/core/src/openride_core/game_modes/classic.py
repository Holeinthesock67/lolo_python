"""Adaptateur du mode classique (segments, bonus, maillots, voisins ; lot T7) : `classic.ClassicRace`."""

from __future__ import annotations

from .base import GameMode, ModeContext


class ClassicMode(GameMode):
    id, attr = "classic", "race"

    def fill_frame(self, ctx: ModeContext) -> None:
        """Champs de la révision 1.4 de la série T dans la trame `state`."""
        st = ctx.state
        race = self.obj(ctx)
        if race is None or not ctx.running:
            st.segment = st.powerup = st.jerseys = None
            st.bot_ahead = st.bot_behind = None
            return
        ph = ctx.physics
        f = race.frame(ctx.t_session, ph.s, ph.v, ctx.bots)
        st.segment, st.powerup, st.jerseys = f.get("segment"), f.get("powerup"), f.get("jerseys")
        st.bot_ahead, st.bot_behind = f.get("bot_ahead"), f.get("bot_behind")
        if ph.direction < 0:   # à rebours (lot N17) : ni segment à venir ni voisin dans la course
            st.segment = None
            st.bot_ahead = st.bot_behind = None
        extra = f.get("bots_extra") or {}
        if st.bots:
            st.bots = [{**b, **extra.get(b["id"], {})} for b in st.bots]
