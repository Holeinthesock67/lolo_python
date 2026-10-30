"""La surprise du chef (lot WTF1, module pur) : la règle inventée pour le mode WTF.

Un chef en toque rattrape le cycliste en tandem (`arrive`, 4 s) et soulève sa cloche : le plat
est montré pendant 5 s (`reveal`), pendant lesquelles Z court le refuse (« Non merci, chef ! »).
Un chef vexé revient la fois suivante avec le plat le plus piquant. Sinon le plat se mange
pendant 45 s (`eat`) :

- `spaghetti` : la route ondule de ± 1,5 point toutes les 8 s (physique et trainer) ;
- `jelly` : route en gelée, ça colle (résistance au roulement × 1,5 et + 1 point ressenti) ;
- `musette` : bal musette, l'accordéoniste annonce une cadence qui change toutes les 15 s ;
  chaque seconde à ± 4 rpm fait danser la foule (2 points par seconde) ;
- `souffle` : un soufflé au fromage sur le guidon monte quand la puissance est régulière et
  retombe à chaque à-coup ; réussi s'il dépasse 80 % de sa hauteur à la fin ;
- `chili` : piment, la vitesse virtuelle part à + 25 % pendant 25 s, puis « ça brûle » à − 15 %.

Seule la vitesse virtuelle et, pour deux plats, une pente ressentie bornée changent.
"""

from __future__ import annotations

from .events import Effects, Event, sinus

DISHES = ("spaghetti", "jelly", "musette", "souffle", "chili")
SPICIEST = "chili"
ARRIVE_S, REVEAL_S, EAT_S = 4.0, 5.0, 45.0
MUSETTE_TEMPI = (80.0, 95.0, 70.0)
MUSETTE_STEP_S = 15.0


class Chef(Event):
    id = "chef"
    duration_s = ARRIVE_S + REVEAL_S + EAT_S

    def __init__(self, rng, ctx, inp, vexed: bool = False) -> None:
        super().__init__(rng, ctx, inp)
        self.dish = SPICIEST if vexed else rng.choice(DISHES)
        self.phase = "arrive"
        self.phase_left = ARRIVE_S
        self.refused = False
        self.eat_t = 0.0
        self.souffle = 0.5
        self._prev_w: float | None = None
        self._w_acc = self._w_t = 0.0

    def press(self, event: str) -> bool:
        if self.phase == "reveal" and event == "Z_SHORT":
            self.refused = True
            self.finish("refused", 0)
            return True
        return False

    def step(self, inp) -> None:
        self.left_s = max(self.left_s - inp.dt, 0.0)
        self.phase_left -= inp.dt
        if self.phase == "arrive" and self.phase_left <= 0.0:
            self.phase, self.phase_left = "reveal", REVEAL_S
        elif self.phase == "reveal" and self.phase_left <= 0.0:
            self.phase, self.phase_left = "eat", EAT_S
        elif self.phase == "eat":
            self.eat_t += inp.dt
            self._eat(inp)
            if self.phase_left <= 0.0:
                self._served()

    def _eat(self, inp) -> None:
        if self.dish == "musette" and abs(inp.cadence_rpm - self.tempo) <= 4.0:
            self._w_acc += inp.dt
            if self._w_acc >= 1.0:   # une seconde en rythme : la foule danse
                self._w_acc -= 1.0
                self.points += 2
        elif self.dish == "souffle":
            self._w_t += inp.dt
            self._w_acc += inp.power_w * inp.dt
            if self._w_t >= 1.0:
                avg = self._w_acc / self._w_t
                if self._prev_w is not None and inp.measures_ok:
                    jerk = abs(avg - self._prev_w) / max(self.ctx.ftp_w, 1.0)
                    # Régulier : monte de 3 % par seconde ; à-coup : retombe d'autant plus qu'il est fort.
                    self.souffle += 0.03 if jerk < 0.10 else -min(jerk, 0.5)
                    self.souffle = min(max(self.souffle, 0.0), 1.0)
                self._prev_w = avg if inp.measures_ok else None
                self._w_acc = self._w_t = 0.0

    def _served(self) -> None:
        if self.dish == "souffle":
            self.finish("success" if self.souffle >= 0.8 else "flop", 120 if self.souffle >= 0.8 else 10)
        elif self.dish == "musette":
            self.finish("danced", 0)
        else:
            self.finish("eaten", 50)

    @property
    def tempo(self) -> float:
        return MUSETTE_TEMPI[int(self.eat_t // MUSETTE_STEP_S) % len(MUSETTE_TEMPI)]

    def apply(self, eff: Effects) -> None:
        if self.phase != "eat":
            return
        if self.dish == "spaghetti":
            eff.grade_add_pct += 1.5 * sinus(self.eat_t, 8.0)
        elif self.dish == "jelly":
            eff.crr_factor *= 1.5
            eff.feel_offset_pct += 1.0
        elif self.dish == "chili":
            eff.power_factor *= 1.25 if self.eat_t < 25.0 else 0.85

    def data(self) -> dict:
        out = {"phase": self.phase, "dish": self.dish if self.phase != "arrive" else None,
               "phase_left_s": round(max(self.phase_left, 0.0), 1)}
        if self.phase == "eat":
            if self.dish == "musette":
                out["tempo_rpm"] = self.tempo
            elif self.dish == "souffle":
                out["souffle"] = round(self.souffle, 2)
            elif self.dish == "chili":
                out["burning"] = self.eat_t >= 25.0
        return out
