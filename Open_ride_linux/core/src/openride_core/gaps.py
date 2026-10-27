"""Écarts en temps de passage entre le cycliste et les bots (lot T16, série T).

Module pur, appelé une fois par trame par la séance (règle « le core est le maître ») :
l'engine affiche `gap_s`, `bot_ahead` et `bot_behind` tels quels. Cahier :
`docs/lots/LOT_T16_ecarts_temps_passage.md`.

Calcul comme en course (plan de la série T §3.4) :
- bot devant : temps écoulé depuis son passage au point où se trouve le cycliste ;
- bot derrière : temps écoulé depuis le passage du cycliste au point où se trouve le bot
  (écart négatif) ;
- repli distance ÷ vitesse (estimation du lot O7) quand le passage n'est pas dans l'historique
  (au départ, ou après plus de `HISTORY_S` secondes d'écart) ;
- boucle : le voisin est cherché sur le tour en cours, c'est-à-dire sur le circuit (écart de
  position ramené dans ]−L/2, L/2]) ; un bot qui a un tour d'avance et roule juste derrière
  est donc « derrière ».

Les positions `s` sont les distances cumulées (`RiderPhysics.s`, sans rebouclage) ; le temps
`t` est le temps chronométré de la séance (figé en pause pour tous les coureurs).
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

HISTORY_S = 300.0        # passages gardés : les 5 dernières minutes
SAMPLE_EVERY_S = 0.1     # un passage noté tous les 0,1 s au plus (50 Hz → 10 Hz)
MIN_SPEED_MPS = 1.0      # vitesse plancher du repli distance ÷ vitesse
RIDER_ID = "rider"


@dataclass(frozen=True)
class Gap:
    id: str
    gap_s: float             # positif si le bot est devant
    distance_m: float        # positif si le bot est devant (sur le circuit pour une boucle)
    estimated: bool          # True : repli distance ÷ vitesse


@dataclass(frozen=True)
class GapReport:
    gaps: dict[str, Gap]
    bot_ahead: str | None
    bot_behind: str | None


class _Track:
    """Passages (t, s) d'un coureur, s croissant."""

    def __init__(self) -> None:
        self.t: list[float] = []
        self.s: list[float] = []

    def add(self, t: float, s: float) -> None:
        if self.t and (t - self.t[-1] < SAMPLE_EVERY_S or s < self.s[-1]):
            return
        self.t.append(t)
        self.s.append(s)
        cut = bisect.bisect_left(self.t, t - HISTORY_S)
        if cut > 64:         # purge par paquets
            del self.t[:cut]
            del self.s[:cut]

    def time_at(self, s: float) -> float | None:
        """Instant interpolé du passage en `s`, None s'il n'est pas dans l'historique."""
        if not self.s or s < self.s[0] or s > self.s[-1]:
            return None
        i = bisect.bisect_left(self.s, s)
        if i == 0:
            return self.t[0]
        s0, s1 = self.s[i - 1], self.s[i]
        t0, t1 = self.t[i - 1], self.t[i]
        if s1 <= s0:
            return t1
        return t0 + (t1 - t0) * (s - s0) / (s1 - s0)


class GapTracker:
    """Historique des passages de chaque coureur et écarts par trame."""

    def __init__(self, length_m: float | None = None, loop: bool = False) -> None:
        if loop and not (length_m and length_m > 0):
            raise ValueError("une boucle demande sa longueur")
        self.length_m = length_m
        self.loop = loop
        self._tracks: dict[str, _Track] = {}

    def record(self, t: float, positions: dict[str, float]) -> None:
        """Note les positions cumulées de chaque coureur (cycliste sous `RIDER_ID`)."""
        for rid, s in positions.items():
            if math.isfinite(s):
                self._tracks.setdefault(rid, _Track()).add(t, s)

    def _circuit_delta(self, s_bot: float, s_me: float) -> float:
        d = s_bot - s_me
        if self.loop:
            L = self.length_m
            d = (d + L / 2.0) % L - L / 2.0
            if d == -L / 2.0:
                d = L / 2.0
        return d

    def report(self, t: float, me: tuple[float, float],
               bots: dict[str, tuple[float, float]]) -> GapReport:
        """`me` = (s, v) du cycliste, `bots` = {id: (s, v)} ; positions cumulées."""
        s_me, v_me = me
        mine = self._tracks.get(RIDER_ID)
        gaps: dict[str, Gap] = {}
        for bid, (s_bot, v_bot) in bots.items():
            d = self._circuit_delta(s_bot, s_me)
            gap: float | None = None
            if d > 0:
                track = self._tracks.get(bid)
                # Point du cycliste exprimé dans les distances cumulées du bot.
                passed = track.time_at(s_bot - d) if track else None
                if passed is not None:
                    gap = t - passed
                else:
                    gap = d / max(v_me, MIN_SPEED_MPS)
            elif d < 0:
                passed = mine.time_at(s_me + d) if mine else None
                if passed is not None:
                    gap = -(t - passed)
                else:
                    gap = d / max(v_bot, MIN_SPEED_MPS)
            else:
                gap = 0.0
                passed = t
            gaps[bid] = Gap(bid, gap, d, passed is None)

        ahead = [g for g in gaps.values() if g.distance_m > 0]
        behind = [g for g in gaps.values() if g.distance_m <= 0]
        bot_ahead = min(ahead, key=lambda g: g.distance_m).id if ahead else None
        bot_behind = max(behind, key=lambda g: g.distance_m).id if behind else None
        return GapReport(gaps, bot_ahead, bot_behind)

    def step(self, t: float, me: tuple[float, float],
             bots: dict[str, tuple[float, float]]) -> GapReport:
        """Note les positions du pas puis rend les écarts (un appel par trame)."""
        self.record(t, {RIDER_ID: me[0], **{k: v[0] for k, v in bots.items()}})
        return self.report(t, me, bots)
