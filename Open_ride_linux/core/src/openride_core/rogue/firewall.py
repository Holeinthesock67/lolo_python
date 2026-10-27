"""Firewall : cycliste virtuel qui poursuit le joueur dans une salle (lot R4).

Il roule le profil de la salle (lu à la position du joueur) à la puissance du `firewall_plan` (fraction
de la FTP) avec la physique du joueur, sans décalage de braquet, vent ni aspiration. Module pur ; les dégâts du contact sont
appliqués par le combat (R5).
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass

from ..physics import RiderPhysics
from .balance import DEFAULT_BALANCE, RogueBalance
from .rooms import Room, RoomRider


@dataclass(frozen=True)
class FirewallState:
    s: float            # position du mur dans la salle (m, négative avant l'entrée)
    v: float            # vitesse (m/s)
    gap_m: float        # joueur − mur (m)
    contact: bool       # le mur a rattrapé le joueur


class Firewall:
    def __init__(self, room: Room, rider: RoomRider, balance: RogueBalance = DEFAULT_BALANCE,
                 player_s: float = 0.0) -> None:
        self.room, self.rider, self.b = room, rider, balance
        self._xs = [p[0] for p in room.profile]
        self._gs = [p[1] for p in room.profile]
        self._starts = [t.s0_m for t in room.firewall_plan]
        self.body = RiderPhysics(rider.params, s=player_s - balance.start_gap_m, v=0.0)
        self._prev_player_s = player_s
        self.state = FirewallState(self.body.s, 0.0, balance.start_gap_m, False)

    def grade_at(self, s: float) -> float:
        xs, gs = self._xs, self._gs
        if s <= xs[0]:
            return gs[0]
        if s >= xs[-1]:
            return gs[-1]
        i = bisect.bisect_right(xs, s) - 1
        u = (s - xs[i]) / (xs[i + 1] - xs[i])
        return gs[i] + (gs[i + 1] - gs[i]) * u

    def frac_at(self, s: float) -> float:
        i = min(max(bisect.bisect_right(self._starts, s) - 1, 0), len(self._starts) - 1)
        return self.room.firewall_plan[i].frac

    def step(self, dt: float, player_s: float, paused: bool = False,
             input_lost: bool = False) -> FirewallState:
        """Avance le mur de `dt` ; arrêté en pause et tant que le Click est perdu."""
        player_v = (player_s - self._prev_player_s) / dt if dt > 0 else 0.0
        self._prev_player_s = player_s
        if not (paused or input_lost) and dt > 0:
            # Le mur lit le profil et le plan à la position du joueur : même terrain, même instant,
            # donc à puissance égale l'écart reste constant et les salves tombent en même temps.
            ref = max(player_s, 0.0)
            self.body.step(self.frac_at(ref) * self.rider.ftp_w, self.grade_at(ref), 0.0, dt)
            gap = player_s - self.body.s
            if gap <= 0.0:                                  # contact : collé au joueur
                self.body.s, self.body.v = player_s, max(min(self.body.v, player_v), 0.0)
            elif gap > self.b.max_gap_m:                    # plafond : suit le joueur à distance fixe
                self.body.s, self.body.v = player_s - self.b.max_gap_m, max(player_v, 0.0)
        gap = player_s - self.body.s
        self.state = FirewallState(self.body.s, self.body.v, gap, gap <= 0.0)
        return self.state
