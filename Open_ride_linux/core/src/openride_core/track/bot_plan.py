"""Les bots courent l'épreuve (lot VD7, série VD) : consignes de chaque épreuve et course vue par les bots.

Module pur : à chaque pas, `BotPlan.update` lit l'épreuve (`TrackEvent`) et donne à chaque bot sa consigne
(`bots.RaceHint` : sprint vers une ligne, allure de poursuite, relais, derny à ne pas dépasser, repos de
l'américaine, place sur la piste) et la course telle que la voient les bots (`bot_tactics.RaceView`), d'où le
module commun `bot_tactics` tire ses six comportements (plan VD §6.1). Élimination : consignes de survie du
Dernier survivant (`SurvivorRace.survival_hints`, règles de DS sans copie). Aucune règle physique ici : une
consigne ne change que la puissance demandée et la place ; la physique, l'abri et la réserve W′ restent communs.

Plan : `docs/4.0/PLAN_SERIE_VD.md` §6 ; cahier : `docs/lots/LOT_VD7_bots_piste.md`.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..bot_tactics import RaceView, draw
from ..bots import RaceHint
from ..draft import BIKE_LENGTH_M, LANE_MAX_M, LANE_MIN_M
from .base import TrackEvent
from .elimination import Elimination
from .keirin import Keirin
from .madison import Madison
from .mass import MassRace, PointsRace
from .omnium import Omnium
from .points import SPRINT_EVERY, Points
from .pursuit import Pursuit
from .tempo import FROM_LAP, Tempo

POLE_LANE_M = LANE_MAX_M        # à la corde (ligne de mesure) : poursuites et relais en tête
TOP_LANE_M = LANE_MIN_M         # en haut de la piste : repos de l'américaine, coureurs sortis, relayeur qui remonte
EASY_CP = 0.55                  # coureur au repos ou sorti : allure libre
NEUTRAL_CP = 0.75               # tour neutralisé de l'omnium
SPRINT_FROM_M = {"sprinter": (200.0, 280.0), "rouleur": (350.0, 550.0), "climber": (300.0, 450.0),
                 "diesel": (450.0, 650.0)}   # distance de la ligne où part le sprint, tirée par bot et par ligne
SPRINT_MIN_RESERVE_PCT = 25.0   # pas de sprint sous 25 % de réserve
SPRINT_SAVE_RESERVE_PCT = 50.0  # course aux points : sprint intermédiaire seulement au-dessus de 50 % (l'effort se répartit)
TEMPO_CONTENDERS = 3            # tempo : un point au premier, seuls les 3 premiers sur la piste le disputent
POINTS_CONTENDERS = 6           # course aux points : 4 places payées, les 6 premiers les disputent
PURSUIT_START_S = 12.0          # départ arrêté : 12 s à 1,3 × CP, puis allure constante
PURSUIT_START_CP = 1.30
PURSUIT_CP = 1.00               # allure de poursuite calée sur la CP (temps cible : celui de son allure seule)
TEAM_LEAD_CP = 1.10             # meneur d'une poursuite par équipes
TEAM_SPRINT_LEAD_CP = 1.40      # meneur de la vitesse par équipes (un tour à bloc)
SWING_UP_S = 4.0                # le relayeur remonte 4 s en haut de la piste avant de se replacer
KEIRIN_SPRINT_LAPS = (1.0, 1.6)  # derny parti : sprint lancé entre 1 et 1,6 tour de l'arrivée


class BotPlan:
    """Consignes des bots d'une épreuve. `profiles` : id → profil (`bots.PROFILES`) des bots engagés."""

    def __init__(self, ev: TrackEvent, profiles: Mapping[str, str], seed: int = 0) -> None:
        self.ev = ev
        self.profiles = dict(profiles)
        self.seed = int(seed)
        self._swing: dict[str, float] = {}   # relayeur → fin de sa remontée (temps de l'épreuve)
        self._seen_journal = 0
        self._reserve: dict[str, float] = {}

    # --- entrée ---

    def update(self) -> tuple[dict[str, RaceHint | None], RaceView | None, dict[str, Any]]:
        """(consigne de chaque bot, course vue par les bots, consignes de survie de l'élimination)."""
        ev = self._current()
        hints: dict[str, RaceHint | None] = {b: None for b in self.profiles}
        survival: dict[str, Any] = {}
        if ev is None:          # omnium entre deux épreuves : tour neutralisé
            for b in self.profiles:
                hints[b] = RaceHint(power_cp=NEUTRAL_CP)
            return hints, None, survival
        if ev.finished:
            for b in self.profiles:
                hints[b] = RaceHint(power_cp=EASY_CP, lane_m=TOP_LANE_M)
            return hints, None, survival
        view = None
        if isinstance(ev, Pursuit):
            self._pursuit(ev, hints)
        elif isinstance(ev, Elimination):
            survival = ev.race.survival_hints() if ev.race is not None else {}
            view = self._elimination_view(ev)
        elif isinstance(ev, MassRace):
            view = self._mass(ev, hints)
        for rid, r in ev.riders.items():   # sortis (éliminé, déclassé, lâché, écarté) : allure libre en haut
            if rid in hints and r.out is not None:
                hints[rid] = RaceHint(power_cp=EASY_CP, lane_m=TOP_LANE_M)
                survival.pop(rid, None)
        return hints, view, survival

    def _current(self) -> TrackEvent | None:
        ev = self.ev
        if isinstance(ev, Omnium) and not ev.finished:
            return ev.sub
        return ev

    # --- poursuites ---

    def _pursuit(self, ev: Pursuit, hints: dict[str, RaceHint | None]) -> None:
        t = ev.elapsed_s
        for line in ev.journal[self._seen_journal:]:   # relayeur qui vient de passer : il remonte
            if line.get("event") == "relay":
                self._swing[line["rider"]] = t + SWING_UP_S
        self._seen_journal = len(ev.journal)
        for tm in ev.teams.values():
            racing = [i for i in tm.order if ev.riders[i].out is None]
            for k, rid in enumerate(racing):
                if rid not in hints:
                    continue
                if ev.team_size == 1:       # poursuite individuelle : départ arrêté puis allure constante
                    cp = PURSUIT_START_CP if t < PURSUIT_START_S else PURSUIT_CP
                    hints[rid] = RaceHint(power_cp=cp, tactical=True, lane_m=POLE_LANE_M)
                elif k == 0:                # meneur de l'équipe : relais en tête, à la corde
                    cp = TEAM_SPRINT_LEAD_CP if ev.relay_mode == "leave" else TEAM_LEAD_CP
                    if t < PURSUIT_START_S:
                        cp = max(cp, PURSUIT_START_CP)
                    hints[rid] = RaceHint(power_cp=cp, tactical=True, lane_m=POLE_LANE_M)
                elif self._swing.get(rid, -1.0) > t:   # il remonte puis se replace en queue
                    hints[rid] = RaceHint(power_cp=EASY_CP, lane_m=TOP_LANE_M)
                else:                       # dans les roues : la stratégie et la roue suivie font le reste
                    hints[rid] = RaceHint(lane_m=POLE_LANE_M)

    # --- courses en peloton ---

    def _scoring(self, ev: MassRace, k: int) -> bool:
        """Vrai si la ligne `k` rapporte quelque chose : arrivée, sprint (points, américaine), tour du tempo."""
        if k >= ev.laps:
            return True
        if isinstance(ev, Points):          # l'américaine en hérite
            return k % SPRINT_EVERY == 0
        if isinstance(ev, Tempo):
            return k >= FROM_LAP
        return False

    def _next_line(self, ev: MassRace, uid: str) -> int:
        u = ev.units[uid]
        k = min(u.next_mark, ev.laps)
        while not self._scoring(ev, k):
            k += 1
        return k

    def _mass(self, ev: MassRace, hints: dict[str, RaceHint | None]) -> RaceView:
        racing_units = [u for u in ev.units.values() if ev._active(u) and u.finish_t is None]
        road = sorted(racing_units, key=lambda u: -ev.adjusted(u))
        rank = {u.id: i for i, u in enumerate(road)}
        resting: set[str] = set()
        if isinstance(ev, Madison):
            for u in ev.units.values():
                on = ev.racer(u.id)
                resting.update(m for m in u.members if m != on)
        pacer = None
        if isinstance(ev, Keirin) and ev.pacer_on:
            pacer = (ev.origin + ev.pacer_d, ev.pacer_v)
        for uid, u in ev.units.items():
            for rid in u.members:
                if rid not in hints or ev.riders[rid].out is not None:
                    continue
                if rid in resting:            # américaine : au repos en haut de la piste, à allure libre
                    hints[rid] = RaceHint(power_cp=EASY_CP, lane_m=TOP_LANE_M)
                    continue
                if u.finish_t is not None:
                    hints[rid] = RaceHint(power_cp=EASY_CP, lane_m=TOP_LANE_M)
                    continue
                r = ev.riders[rid]
                if pacer is not None:         # keirin : derrière le derny, jamais devant
                    gap = pacer[0] - r.s - BIKE_LENGTH_M
                    hints[rid] = RaceHint(wheel=(max(gap, 0.0), pacer[1]))
                    continue
                k = self._next_line(ev, uid)
                to_line = k * ev.lap_m - ev.adjusted(u)
                hints[rid] = self._sprint_hint(ev, rid, k, to_line, rank.get(uid, len(road)))
        lead = road[0] if road else None
        k = self._next_line(ev, lead.id) if lead is not None else ev.laps
        to_goal = k * ev.lap_m - ev.adjusted(lead) if lead is not None else None
        if pacer is not None:
            to_goal = None
        goal = "finish" if k >= ev.laps else "sprint"
        pts = ev.points()
        score: dict[str, float] = {}
        for u in ev.units.values():
            sc = float(pts.get(u.id, 0)) if pts is not None and isinstance(ev, PointsRace) else -float(rank.get(u.id, len(road)))
            for m in u.members:
                score[m] = sc
        order = tuple(ev.units[u.id].members[0] if not isinstance(ev, Madison) else ev.racer(u.id) for u in road)
        pos = {rid: (r.s, r.v) for rid, r in ev.riders.items() if r.out is None}
        lap, laps = ev.lap_info()
        return RaceView(order=order, pos=pos, score=score, to_goal_m=to_goal, goal=goal, goal_key=k,
                        laps_to_go=None if lap is None or laps is None else max(laps - lap + 1, 0), lap_m=ev.lap_m)

    def _sprint_hint(self, ev: MassRace, rid: str, k: int, to_line: float, road_rank: int) -> RaceHint | None:
        """Sprint vers la ligne `k` : parti à sa distance (tirée par bot et par ligne), s'il la dispute et s'il en
        a la réserve ; None sinon (la stratégie et les comportements de course décident)."""
        prof = self.profiles.get(rid, "rouleur")
        lo, hi = SPRINT_FROM_M.get(prof, SPRINT_FROM_M["rouleur"])
        if isinstance(ev, Keirin):
            lo, hi = KEIRIN_SPRINT_LAPS[0] * ev.lap_m, KEIRIN_SPRINT_LAPS[1] * ev.lap_m
            if prof == "sprinter":
                lo, hi = SPRINT_FROM_M["sprinter"]
        start = lo + (hi - lo) * draw(self.seed, rid, "sprint", k)
        if to_line > start or to_line <= 0:
            return None
        final = k >= ev.laps
        if not final:
            limit = TEMPO_CONTENDERS if isinstance(ev, Tempo) else POINTS_CONTENDERS
            if road_rank >= limit:
                return None
        bot_reserve = self._reserve.get(rid, 100.0)
        need = SPRINT_MIN_RESERVE_PCT if final or isinstance(ev, Tempo) else SPRINT_SAVE_RESERVE_PCT
        if bot_reserve < need:
            return None
        return RaceHint(peak=True, tactical=True, key=("ligne", k))

    def _elimination_view(self, ev: Elimination) -> RaceView | None:
        race = ev.race
        if race is None:
            return None
        f = race.frame()
        alive = list(f["alive"])
        pos = {rid: (ev.riders[rid].s, ev.riders[rid].v) for rid in alive if rid in ev.riders}
        order = tuple(sorted(pos, key=lambda r: -pos[r][0]))
        score = {rid: -float(i) for i, rid in enumerate(order)}
        lap, laps = ev.lap_info()
        to_goal = None
        if pos and race.arch < len(race.arches):
            to_goal = max(race.arches[race.arch] - max(s for s, _ in pos.values()), 0.0)
        return RaceView(order=order, pos=pos, score=score, to_goal_m=to_goal, goal="elimination",
                        goal_key=int(race.arch), laps_to_go=None if lap is None else max(laps - lap + 1, 0),
                        lap_m=ev.lap_m)

    def set_reserves(self, reserves: Mapping[str, float]) -> None:
        """Réserves W′ des bots (%), lues par les sprints (pas de sprint réservoir vide)."""
        self._reserve = dict(reserves)
