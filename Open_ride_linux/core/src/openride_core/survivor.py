"""Mode « Dernier survivant » : règles de la course à l'élimination (lot DS1, série DS).

Module pur, sans entrée-sortie : la séance (lot DS2) lui donne à chaque pas la position et la
vitesse du cycliste et des bots encore en course, et lit la trame `survivor`, les messages
`elimination`, les lignes de journal et le bilan. Plan : `docs/3.0/PLAN_SERIE_DS.md` §2 et §6 ;
cahier : `docs/lots/LOT_DS1_regles_core.md`.

Règles :
- une arche par adversaire, à `s0 + k × écart` (k = 1 à N), calée sur la fin d'un sprint ou un
  sommet à moins de 300 m, jamais avant 1 km après le départ ; sur un circuit, la distance continue
  au tour suivant ; un parcours qui n'est pas une boucle doit contenir toute la course ;
- instant de passage interpolé entre deux pas ;
- dès que tous les coureurs en course sauf un ont passé l'arche, le dernier est éliminé, même loin
  derrière ; égalité (écart sous 1 ms) : un bot avant le cycliste, puis le niveau le plus bas, puis
  l'identifiant le plus grand ;
- éliminé à l'arche k avec N bots, un coureur finit (N + 2 − k)e ; le dernier en course gagne.

Lot DS3 : `survival_hints` donne à chaque bot en course sa situation avant l'arche (menacé, à l'abri)
et la distance où il lance son sprint de survie ; `ProfileBot` en tire sa puissance (`bots.py`).
Aucun élastique : un bot ne ralentit jamais à cause de l'écart avec le cycliste en tant que tel.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Iterable, Mapping

ME = "me"                                    # le cycliste, comme dans `jerseys` (contrat 1.4)
SPACINGS_KM = (1, 2, 3)                      # réglage « Écart entre arches »
SPREADS = {"tight": 3.0, "normal": 8.0, "wide": 15.0}   # réglage « Écart de niveau » : ± points de FTP
AFTER_OUT = ("ride", "end")                  # réglage « Après élimination »
PROFILE_ORDER = ("climber", "rouleur", "sprinter", "diesel")
MIN_OPPONENTS = 2
MAX_OPPONENTS = 11                           # 4 tant que le core limite les bots à 4 (lot DS8)
FIRST_ARCH_MIN_M = 1000.0                    # aucune arche dans le premier kilomètre
SNAP_M = 300.0                               # calage sur une ligne de sprint ou un sommet
TIE_S = 0.001                                # écart de passage sous lequel deux coureurs sont à égalité
RESULT_REPEAT = 3                            # message `elimination` répété 3 fois, à 1 s d'intervalle
V_FLOOR = 1.0                                # m/s : vitesse plancher pour les écarts en temps
# Lot DS3 : tactique de survie des bots
DANGER_LAST = 2                              # menacé : parmi les deux derniers en course…
DANGER_GAP_S = 2.0                           # … ou à moins de 2 s du dernier
SAFE_GAP_S = 5.0                             # à l'abri : à plus de 5 s du dernier
SPRINT_FROM_M = (250.0, 400.0)               # distance de l'arche où part le sprint, tirée par arche et par bot


class SurvivorError(ValueError):
    """Réglage refusé ou parcours trop court pour la course."""


# --- préparation ------------------------------------------------------------------------------

def course_length_m(opponents: int, spacing_km: float) -> float:
    """Longueur de la course : une arche par adversaire."""
    return opponents * spacing_km * 1000.0


def check_settings(opponents: int, spacing_km: float, spread: str, after_out: str,
                   max_opponents: int = MAX_OPPONENTS) -> None:
    if isinstance(opponents, bool) or not isinstance(opponents, int) \
            or not MIN_OPPONENTS <= opponents <= max_opponents:
        raise SurvivorError(f"adversaires : {opponents!r} refusé ({MIN_OPPONENTS} à {max_opponents})")
    if spacing_km not in SPACINGS_KM:
        raise SurvivorError(f"écart entre arches : {spacing_km!r} refusé ({', '.join(map(str, SPACINGS_KM))} km)")
    if spread not in SPREADS:
        raise SurvivorError(f"écart de niveau : {spread!r} refusé ({', '.join(SPREADS)})")
    if after_out not in AFTER_OUT:
        raise SurvivorError(f"après élimination : {after_out!r} refusé ({', '.join(AFTER_OUT)})")


def fits(opponents: int, spacing_km: float, length_m: float | None, loop: bool, s0: float = 0.0) -> bool:
    """Vrai si la course tient sur le parcours (toujours sur un circuit ou en monde ouvert : length_m None)."""
    if loop or length_m is None:
        return True
    return s0 + course_length_m(opponents, spacing_km) <= length_m + 1e-6


def _lines(segments: Iterable, length_m: float | None, loop: bool, upto: float) -> list[float]:
    """Lignes de sprint et sommets (fin de chaque segment), répétées à chaque tour sur un circuit."""
    ends = sorted(float(seg.s_end) for seg in segments)
    if not ends:
        return []
    if not loop or not length_m:
        return ends
    out: list[float] = []
    lap = 0
    while lap * length_m <= upto:
        out.extend(lap * length_m + e for e in ends)
        lap += 1
    return out


def arch_positions(opponents: int, spacing_km: float, s0: float = 0.0, segments: Iterable = (),
                   length_m: float | None = None, loop: bool = False) -> list[float]:
    """Abscisses des arches (cumulées sur un circuit). Lève SurvivorError si la course ne tient pas."""
    if not fits(opponents, spacing_km, length_m, loop, s0):
        raise SurvivorError(f"parcours trop court : {course_length_m(opponents, spacing_km) / 1000:g} km "
                            f"de course pour {max((length_m or 0.0) - s0, 0.0) / 1000:.1f} km restants")
    spacing = spacing_km * 1000.0
    end = s0 + course_length_m(opponents, spacing_km)
    lines = _lines(segments, length_m, loop, end + SNAP_M)
    out: list[float] = []
    for k in range(1, opponents + 1):
        nominal = s0 + k * spacing
        pos = nominal
        near = [x for x in lines if abs(x - nominal) <= SNAP_M]
        if near:
            cand = min(near, key=lambda x: (abs(x - nominal), x))
            low = max(s0 + FIRST_ARCH_MIN_M, (out[-1] + spacing / 2) if out else s0)
            limit = length_m if (length_m is not None and not loop) else None
            if cand >= low and (limit is None or cand <= limit):
                pos = cand
        out.append(pos)
    return out


def plan_field(opponents: int, level_pct: float, spread: str,
               bounds: tuple[float, float] = (50.0, 150.0)) -> list[tuple[str, float]]:
    """Plateau du mode : (profil, niveau en % de la FTP) pour chaque bot.

    Profils dans l'ordre grimpeur, rouleur, sprinteur, diesel ; niveaux étalés régulièrement de
    `level_pct + écart` à `level_pct − écart`, dans les bornes du réglage `bots.level_pct`."""
    if spread not in SPREADS:
        raise SurvivorError(f"écart de niveau : {spread!r} refusé ({', '.join(SPREADS)})")
    half = SPREADS[spread]
    lo, hi = bounds
    out = []
    for i in range(opponents):
        frac = 0.0 if opponents == 1 else 1.0 - 2.0 * i / (opponents - 1)
        level = min(max(level_pct + frac * half, lo), hi)
        out.append((PROFILE_ORDER[i % len(PROFILE_ORDER)], round(level, 1)))
    return out


# --- course -----------------------------------------------------------------------------------

@dataclass
class Racer:
    id: str
    name: str
    level: float = 100.0          # % de la FTP (égalités) ; le cycliste n'en a pas besoin
    out_arch: int | None = None   # arche (1 à N) de l'élimination
    place: int | None = None
    gap_s: float | None = None    # retard sur l'avant-dernier à l'élimination


@dataclass
class _Pending:
    msg: dict
    at: float
    left: int


@dataclass
class SurvivorRace:
    """Course à l'élimination d'une séance. `bots` : (id, nom, niveau) de chaque adversaire."""

    arches: list[float]
    bots: list[tuple[str, str, float]]
    spacing_km: float = 2.0
    seed: int = 0
    journal: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.arches) != len(self.bots):
            raise SurvivorError("une arche par adversaire")
        if any(b > a for a, b in zip(self.arches[1:], self.arches)):
            raise SurvivorError("arches dans le désordre")
        self.racers: dict[str, Racer] = {ME: Racer(ME, "Toi")}
        for bot_id, name, level in self.bots:
            if bot_id in self.racers:
                raise SurvivorError(f"identifiant en double : {bot_id}")
            self.racers[bot_id] = Racer(bot_id, name, float(level))
        self.arch = 0                                   # index de l'arche à départager
        self.crossings: list[dict[str, float]] = [{} for _ in self.arches]
        self._prev: dict[str, tuple[float, float]] = {}  # id → (t, s) au pas précédent
        self._pos: dict[str, tuple[float, float]] = {}   # id → (s, v) au dernier pas
        self._pending: list[_Pending] = []
        self.winner: str | None = None

    # --- état ---

    @property
    def alive(self) -> list[str]:
        return [r.id for r in self.racers.values() if r.out_arch is None]

    @property
    def finished(self) -> bool:
        return self.winner is not None

    def is_out(self, rider_id: str) -> bool:
        r = self.racers.get(rider_id)
        return r is not None and r.out_arch is not None

    # --- pas ---

    def start(self, t: float, positions: Mapping[str, tuple[float, float]]) -> None:
        """Positions de départ : `positions` = id → (s, v), le cycliste sous l'id `me`."""
        for rid, (s, v) in positions.items():
            if rid in self.racers:
                self._prev[rid] = (t, float(s))
                self._pos[rid] = (float(s), float(v))

    def step(self, t: float, positions: Mapping[str, tuple[float, float]]) -> list[str]:
        """Un pas de séance (RUNNING seulement). Rend les identifiants éliminés pendant ce pas."""
        if self.finished:
            return []
        for rid, (s, v) in positions.items():
            r = self.racers.get(rid)
            if r is None or r.out_arch is not None:
                continue
            s = float(s)
            t0, s0 = self._prev.get(rid, (t, s))
            if s > s0:
                for i in range(self.arch, len(self.arches)):
                    a = self.arches[i]
                    if a > s:
                        break
                    if a > s0 and rid not in self.crossings[i]:
                        self.crossings[i][rid] = t0 + (a - s0) / (s - s0) * (t - t0)
            self._prev[rid] = (t, s)
            self._pos[rid] = (s, float(v))
        out: list[str] = []
        while not self.finished:
            gone = self._resolve(t)
            if gone is None:
                break
            out.append(gone)
        return out

    def _tie_key(self, rid: str) -> tuple:
        """Ordre d'élimination à égalité : bot avant cycliste, niveau le plus bas, identifiant le plus grand."""
        r = self.racers[rid]
        return (rid != ME, -r.level, rid)

    def _resolve(self, t: float) -> str | None:
        """Élimine le dernier de l'arche en cours si elle est départagée."""
        alive = self.alive
        passed = {rid: tc for rid, tc in self.crossings[self.arch].items() if rid in alive}
        if len(passed) < len(alive) - 1:
            return None
        behind = [rid for rid in alive if rid not in passed]
        if behind:
            loser = behind[0]
            second_last = max(passed.values())
            pos = self._pos.get(loser)
            # retard estimé : temps pour rejoindre l'arche à sa vitesse du moment
            if pos is not None:
                gap = (t - second_last) + max(self.arches[self.arch] - pos[0], 0.0) / max(pos[1], V_FLOOR)
            else:
                gap = t - second_last
            if gap < TIE_S:
                return None   # possible égalité : on attend son passage, départagé au pas suivant
        else:
            last_t = max(passed.values())
            group = [rid for rid, tc in passed.items() if last_t - tc < TIE_S]
            loser = max(group, key=self._tie_key)
            others = [tc for rid, tc in passed.items() if rid != loser]
            gap = passed[loser] - max(others) if others else 0.0
        self._eliminate(loser, max(gap, 0.0), t)
        return loser

    def _eliminate(self, rid: str, gap_s: float, t: float) -> None:
        k = self.arch + 1
        n = len(self.arches)
        r = self.racers[rid]
        r.out_arch, r.place, r.gap_s = k, n + 2 - k, round(gap_s, 2)
        alive = self.alive
        msg = {"type": "elimination", "v": 1, "arch": k, "rider": rid, "name": r.name[:16],
               "place": r.place, "gap_s": r.gap_s, "alive": len(alive)}
        self._pending.append(_Pending(msg, t, RESULT_REPEAT))
        self.journal.append({"kind": "survivor", "ts": round(time.time(), 3), "arch": k, "rider": rid,
                             "place": r.place, "gap_s": r.gap_s})
        self.arch += 1
        if self.arch >= n and len(alive) == 1:
            win = self.racers[alive[0]]
            win.place = 1
            self.winner = win.id
            self.journal.append({"kind": "survivor", "ts": round(time.time(), 3), "arch": n,
                                 "rider": win.id, "place": 1, "gap_s": None})

    def due_results(self, t: float) -> list[dict]:
        """Messages `elimination` à envoyer maintenant (3 fois, à une seconde d'intervalle)."""
        out: list[dict] = []
        for item in self._pending:
            if t >= item.at:
                out.append(item.msg)
                item.left -= 1
                item.at = t + 1.0
        self._pending = [i for i in self._pending if i.left > 0]
        return out

    # --- tactique des bots (lot DS3) ---

    def sprint_from_m(self, rider_id: str, arch: int) -> float:
        """Distance de l'arche `arch` (index) où `rider_id` lance son sprint : tirée, rejouable."""
        rnd = random.Random(f"{self.seed}:{rider_id}:{arch}")
        return rnd.uniform(*SPRINT_FROM_M)

    def survival_hints(self) -> dict[str, tuple[float, bool, bool, float]]:
        """Pour chaque bot en course : (distance à sa prochaine arche, menacé, à l'abri, début du sprint).

        Un bot qui a déjà passé l'arche en cours vise la suivante ; son classement est celui de la route.
        Menacé : parmi les deux derniers en course ou à moins de 2 s du dernier ; à l'abri : à plus de 5 s
        du dernier. Le cycliste compte comme un coureur parmi les autres (pas d'élastique)."""
        if self.finished:
            return {}
        order = self._order()
        last = order[-1] if order else None
        s_last = self._pos.get(last, (0.0, 0.0))[0] if last else 0.0
        out: dict[str, tuple[float, bool, bool, float]] = {}
        for rank, rid in enumerate(order):
            if rid == ME or rid not in self._pos:
                continue
            s, v = self._pos[rid]
            nxt = self.arch
            while nxt < len(self.arches) - 1 and rid in self.crossings[nxt]:
                nxt += 1
            if rid in self.crossings[nxt]:
                continue   # a passé la dernière arche : plus rien à défendre
            d_m = max(self.arches[nxt] - s, 0.0)
            gap_s = (s - s_last) / max(v, V_FLOOR)
            danger = rank >= len(order) - DANGER_LAST or gap_s < DANGER_GAP_S
            safe = not danger and gap_s > SAFE_GAP_S
            out[rid] = (round(d_m, 2), danger, safe, self.sprint_from_m(rid, nxt))
        return out

    # --- trame, journal, bilan ---

    def _order(self) -> list[str]:
        """Coureurs en course, du premier au dernier sur la route."""
        alive = self.alive
        return sorted(alive, key=lambda rid: (-self._pos.get(rid, (0.0, 0.0))[0], rid != ME, rid))

    def frame(self) -> dict:
        """Objet `survivor` de la trame `state` (plan §6)."""
        order = self._order()
        me = self.racers[ME]
        out: dict = {"arch": min(self.arch + 1, len(self.arches)), "arches": len(self.arches),
                     "d_m": None, "alive": order, "last": order[-1] if order else None,
                     "gap_last_s": None,
                     "out": [[r.id, r.out_arch] for r in sorted(self.racers.values(),
                                                                key=lambda r: (r.out_arch or 0, r.id))
                             if r.out_arch is not None and r.id != ME],
                     "me_out": me.out_arch, "winner": self.winner}
        if me.out_arch is None and not self.finished and ME in self._pos:
            s_me, v_me = self._pos[ME]
            out["d_m"] = round(max(self.arches[self.arch] - s_me, 0.0), 1)
            if len(order) >= 2:
                # écart avec le dernier ; si le cycliste est dernier, avec celui qui le précède
                other = order[-2] if order[-1] == ME else order[-1]
                s_o, v_o = self._pos[other]
                behind_v = v_me if order[-1] == ME else v_o
                out["gap_last_s"] = round(abs(s_me - s_o) / max(behind_v, V_FLOOR), 1)
        return out

    def take_journal(self) -> list[dict]:
        lines, self.journal = self.journal, []
        return lines

    def summary(self) -> dict:
        """`summary.survivor` : place du cycliste, éliminations arche par arche, vainqueur."""
        me = self.racers[ME]
        elim = sorted((r for r in self.racers.values() if r.out_arch is not None), key=lambda r: r.out_arch)
        return {"place": me.place, "of": len(self.racers), "arches": len(self.arches),
                "spacing_km": self.spacing_km,
                "eliminated": [[r.out_arch, r.id, r.name[:16], r.gap_s] for r in elim],
                "winner": self.winner}
