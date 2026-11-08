"""Tactique des bots à profil (lot Y10) : relais, attaques, réponses, fatigue de longue durée, forme du jour.

Module commun, pur et testable, appelé par `ProfileBot` à chaque pas (`Tactics.adjust`) et par la séance une
fois par pas pour le groupe (`update_field`). Il ne change que la **puissance demandée** et l'envie de garder
ou de quitter une roue : la physique, l'abri (`draft.py`) et la réserve W′bal (`rogue/wbal.py`) restent ceux
du cycliste ; une puissance au-dessus de la CP vide la réserve comme pour lui (pas de triche physique).

Chaque mode de jeu choisit ses comportements dans `MODE_TACTICS` (table, pas de code propre au mode).

Lot VD7 (`docs/4.0/PLAN_SERIE_VD.md` §6.1) : six comportements de course écrits une seule fois ici, sans rien
savoir des épreuves (le module n'importe pas le paquet `track/`) : coalitions, marquage, bluff, gestion du
classement, fatigue visible et personnalités. Le mode décrit la course dans une `RaceView` (ordre, classement,
prochain objectif : sprint, arrivée ou élimination) et appelle `race_update` à chaque pas ; chaque bot en tire
une intention (`RaceIntent`) que `Tactics.race_power` applique à sa puissance demandée et à sa place (`lane.home`).
Le réglage « Tactique des bots : aucune, simple, complète » choisit la ligne de la table (`track_mode`).

Tirages : tous viennent de la graine de la séance (`draw`), jamais de l'heure ni d'un générateur partagé ; à
graine égale, même course (tests et rejeu). Cahier : `docs/lots/LOT_Y10_comportement_bots_core.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import zlib
from typing import Any, Callable, Iterable

from .draft import LANE_MIN_M

# --- valeurs du cahier Y10 (§4) -------------------------------------------------------------------------

GROUP_GAP_S = 2.0              # des coureurs à moins de 2 s les uns des autres forment un groupe
FLAT_MAX_GRADE_PCT = 2.0       # relais seulement sous 2 % de pente
RELAY_S = (30.0, 60.0)         # durée d'un relais en tête, selon la réserve (30 % → 30 s, 100 % → 60 s)
RELAY_MIN_RESERVE_PCT = 30.0   # sous 30 % de réserve, pas de relais
DROP_FACTOR = 0.85             # en fin de relais, puissance −15 %...
DROP_S = 5.0                   # ... pendant 5 s : il se décale et glisse en queue
DROP_MAX_S = 15.0              # (le temps d'être doublé : 5 s ne suffisent pas à 15 % de moins, 15 s au plus)
REST_S = 20.0                  # puis il ne reprend pas la tête avant 20 s s'il y est encore
RELAY_SHIFT_M = 1.0            # il se décale de 1 m vers l'axe (place de repos du placement, lot AS2)
ATTACK_FACTOR = (1.15, 1.30)   # attaque : 1,15 à 1,30 × CP...
ATTACK_S = (20.0, 60.0)        # ... pendant 20 à 60 s
ATTACK_MIN_RESERVE_PCT = 50.0  # pas d'attaque sous 50 % de réserve
ATTACK_STOP_RESERVE_PCT = 10.0  # attaque arrêtée quand la réserve passe sous 10 %
SPRINT_ATTACK_M = 1000.0       # attaque possible au dernier kilomètre d'un sprint, avant le pic du sprinteur
RESPONSE_MIN_RESERVE_PCT = 40.0   # pas de réponse sous 40 % de réserve
# Départ d'un coureur : son écart grandit de plus de 0,5 s en 3 s (le cahier écrit « 0,5 s par seconde pendant
# 3 s » ; à 1,25 × CP, l'écart d'une vraie attaque grandit d'environ 0,2 s par seconde : la lettre ne verrait
# aucune attaque). Relevé toutes les TICK_S secondes, les RESPONSE_WINDOW_S dernières secondes.
RESPONSE_GAIN_S = 0.5
RESPONSE_WINDOW_S = 3.0
RESPONSE_FACTOR = 1.25         # le bot qui suit roule à 1,25 × CP...
RESPONSE_MAX_S = 60.0          # ... au plus 60 s...
RESPONSE_CAUGHT_S = 0.3        # ... ou jusqu'à revenir à 0,3 s (la roue suivie du lot AS1 prend le relais)
RESPONSE_STOP_RESERVE_PCT = 20.0
RESPONSE_WHEEL_M = 1.0         # en chasse, une roue à moins de 1 m devant : on la suit, le placement fait doubler
RESPONSE_START_S = 30.0        # aucun départ jugé dans les 30 premières secondes (mise en route)
RESPONSE_COOLDOWN_S = 30.0     # un même départ n'est jugé qu'une fois en 30 s
DURABILITY_START_S = 3600.0    # fatigue de longue durée au-delà de 60 min de séance
DURABILITY_FLOOR = 0.70        # jamais moins de 70 % de la CP (séance de plusieurs heures)
FORM_RANGE = (0.97, 1.03)      # jour avec, jour sans : facteur de forme sur la CP
TICK_S = 0.5                   # le groupe (relais, départs) est relu deux fois par seconde
RIDER_ID = "rider"


@dataclass(frozen=True)
class Behaviours:
    """Comportements actifs d'un mode (une ligne de `MODE_TACTICS`)."""

    relays: bool = False
    attacks: bool = False
    responses: bool = False
    durability: bool = False
    form: bool = False
    # lot VD7 (§6.1 du plan VD) : comportements de course, lus dans une `RaceView` donnée par le mode
    coalitions: bool = False
    marking: bool = False
    bluff: bool = False
    standings: bool = False
    fatigue: bool = False          # fatigue visible : réserve vide, il se relève et monte en haut

    @property
    def racing(self) -> bool:
        """Vrai si un comportement de course est actif (les personnalités en règlent alors la fréquence)."""
        return self.coalitions or self.marking or self.bluff or self.standings or self.fatigue


NONE = Behaviours()
FULL = Behaviours(relays=True, attacks=True, responses=True, durability=True, form=True)
RACE_SIMPLE = Behaviours(durability=True, marking=True, standings=True, fatigue=True)
RACE_FULL = Behaviours(relays=True, responses=True, durability=True, form=True, coalitions=True, marking=True,
                       bluff=True, standings=True, fatigue=True)

# Table des modes. Les modes qui n'ont pas encore branché la table (Dernier survivant, WTF, monde ouvert,
# vélodrome) restent à `none` jusqu'à leur propre lot. `essai` : le banc `bots_race` (lot X27), qui juge
# chaque bot à ± 2 % du cycliste, sans le facteur de forme qui l'en écarterait à dessein.
MODE_TACTICS: dict[str, Behaviours] = {
    "none": NONE,
    "classic": FULL,
    "essai": Behaviours(relays=True, attacks=True, responses=True, durability=True, form=False),
    "calibration": Behaviours(attacks=True, durability=True),   # lot T13 : bot seul, sans groupe ni forme
    # lot VD7 : réglage « Tactique des bots » des épreuves de piste (pas d'attaque de montée sur une piste plate)
    "track_none": NONE,
    "track_simple": RACE_SIMPLE,
    "track_full": RACE_FULL,
    # poursuites (individuelle et par équipes) : allure et relais de l'épreuve, seule la fatigue se voit
    "track_paced": Behaviours(durability=True, fatigue=True),
}

LEVELS = ("none", "simple", "full")   # réglage « Tactique des bots : aucune, simple, complète »


def track_mode(level: str, paced: bool = False) -> str:
    """Ligne de `MODE_TACTICS` du réglage « Tactique des bots » d'une épreuve de piste ; `paced` : épreuve à
    allure imposée (poursuites), où l'épreuve règle les relais et l'allure (pas de coalition ni de bluff)."""
    if level not in LEVELS:
        raise ValueError(f"tactique des bots : {level!r} ({', '.join(LEVELS)})")
    if paced and level != "none":
        return "track_paced"
    return f"track_{level}"


# --- comportements de course (lot VD7, plan VD §6.1) ------------------------------------------------------

PERSONALITIES = ("attacker", "follower", "opportunist")
# Fréquence de chaque comportement selon le caractère (chance tirée de la graine à chaque occasion).
RATES: dict[str, dict[str, float]] = {
    "attacker":    {"coalition": 0.8, "mark": 0.4, "bluff": 0.6, "all_in": 0.9},
    "follower":    {"coalition": 0.2, "mark": 0.9, "bluff": 0.1, "all_in": 0.3},
    "opportunist": {"coalition": 0.5, "mark": 0.6, "bluff": 0.4, "all_in": 0.6},
}
COALITION_FACTOR = 1.12        # coalition : 1,12 × CP à tour de rôle pour prendre un tour ou creuser l'écart
COALITION_SIZE = (2, 3)
COALITION_MIN_RESERVE_PCT = 60.0   # pour s'unir, réserve au-dessus de 60 %...
COALITION_STOP_RESERVE_PCT = 35.0  # ... et la coalition se défait sous 35 %
COALITION_GAP_S = 2.0          # coureurs voisins sur la piste (moins de 2 s) seulement
COALITION_GOAL_M = 1.5         # en tours : à moins d'un tour et demi d'un objectif, ils redeviennent rivaux
COALITION_COOLDOWN_S = 60.0    # une coalition au plus à la fois, et 60 s entre deux
MARK_GAP_S = 4.0               # marquage : le coureur le plus dangereux, à moins de 4 s...
MARK_RELEASE_S = 6.0           # ... qu'on laisse partir au-delà de 6 s
MARK_HOLD_S = 0.6              # derrière lui, à plus de 0,6 s : on revient sur sa roue...
MARK_FACTOR = 1.25             # ... à 1,25 × CP
MARK_MIN_RESERVE_PCT = 20.0
BLUFF_WINDOW_M = (250.0, 450.0)    # bluff : fausse attaque entre 450 et 250 m de l'objectif...
BLUFF_FACTOR = 1.35            # ... à 1,35 × CP...
BLUFF_S = (3.0, 5.0)           # ... pendant 3 à 5 s...
SIT_UP_FACTOR = 0.80           # ... puis il se relève (0,8 × CP)...
SIT_UP_S = 5.0                 # ... pendant 5 s
BLUFF_MIN_RESERVE_PCT = 50.0
FINAL_LAPS = 3                 # gestion du classement : dans les 3 derniers tours...
WATCH_CAP = 0.95               # ... le leader surveille (plafond 0,95 × CP) et marque son dauphin...
ALL_IN_FACTOR = 1.20           # ... ceux de derrière tentent le tout pour le tout (1,2 × CP)...
ALL_IN_STOP_RESERVE_PCT = 15.0  # ... jusqu'à 15 % de réserve
TIRED_RESERVE_PCT = 8.0        # fatigue visible : réserve sous 8 %, il se relève...
TIRED_CAP = 0.75               # ... (0,75 × CP au plus), décroche et monte en haut de la piste...
TIRED_LANE_M = LANE_MIN_M      # ... (`lane.home` au plus loin de la corde : haut de la piste sur un vélodrome)
RECOVERED_RESERVE_PCT = 25.0   # ... jusqu'à 25 % de réserve


def personality_of(name: str) -> str:
    """Caractère d'un bot, tiré de son nom et non de la graine : même nom, même caractère d'une course à
    l'autre (plan VD §6.1)."""
    return PERSONALITIES[zlib.crc32(f"tempérament:{name}".encode()) % len(PERSONALITIES)]


@dataclass(frozen=True)
class RaceView:
    """La course vue par les bots, écrite par le mode à chaque pas (aucune règle d'épreuve ici).

    `order` : coureurs en course, du premier au dernier sur la piste (le cycliste sous `RIDER_ID`) ;
    `pos` : id → (distance déroulée, vitesse) ; `score` : classement de l'épreuve (plus grand = mieux ; les
    points, ou l'opposé de la place) ; `to_goal_m` : distance de la tête au prochain objectif (`goal` :
    sprint, finish, elimination ; None : aucun) et `goal_key` son numéro (une occasion par objectif) ;
    `laps_to_go` : tours restants ; `lap_m` : longueur du tour."""

    order: tuple[str, ...]
    pos: dict[str, tuple[float, float]]
    score: dict[str, float]
    to_goal_m: float | None = None
    goal: str = "none"
    goal_key: int = 0
    laps_to_go: int | None = None
    lap_m: float = 250.0

    def gap_s(self, a: str, b: str) -> float:
        """Avance de `a` sur `b`, en secondes (positif : `a` devant)."""
        sa, va = self.pos[a]
        sb, vb = self.pos[b]
        return (sa - sb) / max(vb, va, 1.0)

    @property
    def final(self) -> bool:
        return self.laps_to_go is not None and self.laps_to_go <= FINAL_LAPS


@dataclass
class RaceIntent:
    """Intention de course d'un bot, posée par `race_update`, appliquée par `Tactics.race_power`."""

    coalition: tuple[str, ...] = ()    # membres de sa coalition (lui compris), vide : aucune
    mark: str | None = None            # coureur marqué
    bluff_until: float = -1.0          # fin de la fausse attaque (temps du champ)
    sit_up_until: float = -1.0         # fin du relâchement qui la suit
    watch: bool = False                # leader qui surveille
    all_in: bool = False               # tout pour le tout
    tired: bool = False                # réserve vide : il se relève et le montre
    _bluffed: tuple = ()               # objectifs déjà joués (bluff)
    _all_in_done: bool = False


class RaceField:
    """État des comportements de course d'une épreuve : coalition en cours, horloge, faits comptés (tests)."""

    def __init__(self, seed: int = 0) -> None:
        self.seed = int(seed)
        self.t = 0.0
        self.coalition: tuple[str, ...] = ()
        self.coalition_since = -1.0
        self._last_coalition = -1e9
        self.counts = {"coalition": 0, "mark": 0, "bluff": 0, "all_in": 0, "watch": 0, "tired": 0}


def _rate(bot: Any, key: str) -> float:
    return RATES[bot.tactics.personality][key]


def race_update(field: RaceField, bots: list[Any], view: RaceView, dt: float) -> None:
    """Intentions de course des bots à profil d'après la `view` du mode (un appel par pas, avant leur pas).
    Ne change que `tactics.race` : la puissance et la place se lisent ensuite dans `Tactics.race_power`."""
    field.t += dt
    t = field.t
    by_id = {b.id: b for b in bots if getattr(b, "tactics", None) is not None}
    racing = [by_id[i] for i in view.order if i in by_id and by_id[i].tactics.on.racing]
    ranked = sorted(view.score, key=lambda k: (-view.score[k], k))
    for b in racing:
        on, it = b.tactics.on, b.tactics.race
        reserve = b.wbal_pct
        # fatigue visible : passe avant tout
        if on.fatigue:
            if not it.tired and reserve < TIRED_RESERVE_PCT:
                it.tired = True
                field.counts["tired"] += 1
            elif it.tired and reserve >= RECOVERED_RESERVE_PCT:
                it.tired = False
        else:
            it.tired = False
        # gestion du classement (dernier tiers : les 3 derniers tours)
        it.watch = False
        if on.standings and view.final and b.id in view.score:
            rank = ranked.index(b.id)
            if rank == 0 and len(ranked) > 1 and view.score[b.id] > view.score[ranked[1]]:
                it.watch = True
                field.counts["watch"] += it.mark != ranked[1]
                it.mark = ranked[1]    # il surveille son dauphin
            elif rank > 0 and not it._all_in_done:
                it._all_in_done = True
                if reserve > 2 * ALL_IN_STOP_RESERVE_PCT and draw(field.seed, b.id, "tout") < _rate(b, "all_in"):
                    it.all_in = True
                    field.counts["all_in"] += 1
        if it.all_in and reserve <= ALL_IN_STOP_RESERVE_PCT:
            it.all_in = False
        # marquage du coureur le plus dangereux au classement
        if on.marking and not it.watch:
            danger = next((k for k in ranked if k != b.id and k in view.pos), None)
            if it.mark is not None and (it.mark not in view.pos
                                        or abs(view.gap_s(it.mark, b.id)) > MARK_RELEASE_S):
                it.mark = None             # trop loin : on le laisse partir
            if (it.mark is None and danger is not None and abs(view.gap_s(danger, b.id)) <= MARK_GAP_S
                    and draw(field.seed, b.id, "marque", danger) < _rate(b, "mark")):
                it.mark = danger
                field.counts["mark"] += 1
        elif not on.marking:
            it.mark = None
        # bluff à l'approche d'un objectif
        if (on.bluff and view.to_goal_m is not None and view.goal in ("sprint", "finish", "elimination")
                and BLUFF_WINDOW_M[0] <= view.to_goal_m <= BLUFF_WINDOW_M[1] and view.goal_key not in it._bluffed):
            it._bluffed += (view.goal_key,)
            if reserve > BLUFF_MIN_RESERVE_PCT and draw(field.seed, b.id, "bluff", view.goal_key) < _rate(b, "bluff"):
                it.bluff_until = t + _between(BLUFF_S, draw(field.seed, b.id, "bluff_s", view.goal_key))
                it.sit_up_until = it.bluff_until + SIT_UP_S
                field.counts["bluff"] += 1
    _coalitions(field, racing, view, t)


def _coalitions(field: RaceField, racing: list[Any], view: RaceView, t: float) -> None:
    """Une coalition de 2 ou 3 voisins loin de tout objectif ; défaite à l'approche du suivant (ils redeviennent
    rivaux), quand un membre tombe sous 35 % de réserve ou n'est plus en course."""
    near_goal = view.to_goal_m is not None and view.to_goal_m <= COALITION_GOAL_M * view.lap_m
    if field.coalition:
        members = [b for b in racing if b.id in field.coalition]
        if (near_goal or view.final or len(members) < len(field.coalition)
                or any(b.wbal_pct < COALITION_STOP_RESERVE_PCT for b in members)):
            for b in racing:
                b.tactics.race.coalition = ()
            field.coalition = ()
            field._last_coalition = t
        return
    if near_goal or view.final or t - field._last_coalition < COALITION_COOLDOWN_S:
        return
    able = [b for b in racing if b.tactics.on.coalitions and not b.tactics.race.tired
            and b.wbal_pct > COALITION_MIN_RESERVE_PCT]
    tick = int(t // COALITION_COOLDOWN_S)
    for i, b in enumerate(able):
        if draw(field.seed, b.id, "coalition", tick) >= _rate(b, "coalition"):
            continue
        size = COALITION_SIZE[int(draw(field.seed, b.id, "taille", tick) * 2) % 2]
        group = [b]
        for o in able[i + 1:]:
            if len(group) >= size:
                break
            if abs(view.gap_s(group[-1].id, o.id)) <= COALITION_GAP_S:
                group.append(o)
        if len(group) >= COALITION_SIZE[0]:
            field.coalition = tuple(g.id for g in group)
            field.coalition_since = t
            for g in group:
                g.tactics.race.coalition = field.coalition
            field.counts["coalition"] += 1
            return


@dataclass(frozen=True)
class Character:
    """Caractère tactique d'un profil (table des profils du lot T12, `bots.PROFILES`)."""

    attack_chance: float = 0.0          # chance d'attaquer une montée
    attack_window: tuple[float, float] = (0.3, 0.8)   # moment de l'attaque, en part de la montée
    sprint_attack_chance: float = 0.0   # chance d'attaquer au dernier kilomètre d'un sprint
    follow_climb: float = 0.5           # chance de suivre un départ en montée
    follow_flat: float = 0.5            # ... sur le plat
    relays: bool = True                 # prend des relais (pas le sprinteur)
    durability_pct_per_h: float = 3.0   # CP perdue par heure au-delà de 60 min


def draw(seed: int, *keys: Any) -> float:
    """Tirage dans [0, 1) fixé par la graine et les clés (bot, montée, tour…) : même graine, même tirage."""
    text = ":".join(str(k) for k in (seed,) + keys)
    return zlib.crc32(text.encode()) / 4294967296.0


def _between(lo_hi: tuple[float, float], u: float) -> float:
    return lo_hi[0] + (lo_hi[1] - lo_hi[0]) * u


def durability_factor(t_s: float, pct_per_h: float) -> float:
    """Part de la CP gardée après `t_s` secondes de séance (1 jusqu'à 60 min, puis −`pct_per_h` % par heure)."""
    over = t_s - DURABILITY_START_S
    if over <= 0.0:
        return 1.0
    return max(1.0 - pct_per_h / 100.0 * over / 3600.0, DURABILITY_FLOOR)


def relay_duration_s(reserve_pct: float) -> float:
    """Durée d'un relais : 30 s à 30 % de réserve, 60 s réserve pleine."""
    u = min(max((reserve_pct - RELAY_MIN_RESERVE_PCT) / (100.0 - RELAY_MIN_RESERVE_PCT), 0.0), 1.0)
    return _between(RELAY_S, u)


class Tactics:
    """État tactique d'un bot à profil : son attaque en cours, son relais, sa réponse à un départ.

    `role` est posé par `update_field` (groupe) : "" (rien), "relay" (en tête), "drop" (fin de relais, il
    glisse en queue), "take" (il passe prendre la tête), "pass" (il double celui qui se relève)."""

    def __init__(self, bot_id: str, character: Character, seed: int = 0, mode: str = "none",
                 name: str | None = None) -> None:
        self.bot_id = bot_id
        self.character = character
        self.personality = personality_of(name if name is not None else bot_id)   # lot VD7
        self.start(seed, mode)

    def start(self, seed: int, mode: str) -> None:
        """Départ de séance : comportements du mode, facteur de forme tiré de la graine, état remis à zéro."""
        if mode not in MODE_TACTICS:
            raise ValueError(f"mode de tactique inconnu : {mode!r} ({', '.join(MODE_TACTICS)})")
        self.seed = int(seed)
        self.mode = mode
        self.on = MODE_TACTICS[mode]
        self.form = _between(FORM_RANGE, draw(self.seed, self.bot_id, "forme")) if self.on.form else 1.0
        self.reset()

    def reset(self) -> None:
        self.attack_until = -1.0           # fin de l'attaque en cours (temps du bot), -1 : pas d'attaque
        self.attack_factor = 0.0
        self.attacks = 0                   # attaques lancées depuis le départ
        self._attack_done: set[tuple] = set()   # montées et sprints (id, tour) déjà jugés
        self._triggers: dict[tuple, float] = {}  # point de déclenchement tiré pour chaque montée et sprint
        self.role = ""
        self.role_until = -1.0
        self._home: float | None = None    # place de repos d'avant le décalage de fin de relais
        self.relay_started = -1.0          # début de la fin de relais (temps du champ)
        self.respond_to: str | None = None
        self.respond_until = -1.0
        self.responses = 0                 # départs suivis depuis le départ
        self._gaps: dict[str, list[float]] = {}   # écarts (s) relevés des coureurs devant, dernier en fin
        self._judged: dict[str, float] = {}       # dernier départ jugé de chaque coureur (temps du champ)
        self.race = RaceIntent()                  # lot VD7 : intention de course (`race_update`)
        self.race_t = 0.0                         # temps du champ de course au dernier `race_update`

    # --- capacité du jour ------------------------------------------------------------------------------

    def cp_factor(self, t_s: float) -> float:
        """Forme du jour × fatigue de longue durée (part de la CP calibrée)."""
        f = self.form
        if self.on.durability:
            f *= durability_factor(t_s, self.character.durability_pct_per_h)
        return f

    # --- attaque (pas du bot) --------------------------------------------------------------------------

    def _attack_zone(self, pos: float, lap: int, segments: Iterable[Any], sprint_last_m: float,
                     peak: bool) -> tuple[tuple, float] | None:
        """(clé du segment, point de déclenchement) de la montée, ou du dernier kilomètre de sprint, où se
        trouve `pos` ; None ailleurs ou si le caractère du bot n'y attaque pas."""
        ch = self.character
        for seg in segments:
            if seg.type == "climb":
                if ch.attack_chance > 0.0 and seg.s_start <= pos < seg.s_end:
                    key = (seg.id, lap)
                    at = self._triggers.get(key)
                    if at is None:
                        u = _between(ch.attack_window, draw(self.seed, self.bot_id, "moment", *key))
                        at = self._triggers[key] = seg.s_start + u * (seg.s_end - seg.s_start)
                    return key, at
            elif seg.type == "sprint" and ch.sprint_attack_chance > 0.0 and not peak:
                lo, hi = seg.s_end - SPRINT_ATTACK_M, seg.s_end - sprint_last_m
                if lo <= pos < hi:
                    key = (seg.id, lap, "sprint")
                    at = self._triggers.get(key)
                    if at is None:
                        at = self._triggers[key] = lo + draw(self.seed, self.bot_id, "moment", *key) * (hi - lo)
                    return key, at
        return None

    def attack_triggers(self, segments: Iterable[Any], sprint_last_m: float, peak: bool) -> list[float]:
        """Points de déclenchement (sur le premier tour, triés) des attaques possibles de ce bot : un seul appel
        de `adjust` y suffit hors attaque en cours (simulation du calibrage, lot T13)."""
        if not self.on.attacks:
            return []
        out = []
        for seg in segments:
            start = seg.s_start if seg.type == "climb" else seg.s_end - SPRINT_ATTACK_M
            zone = self._attack_zone(start, 0, (seg,), sprint_last_m, peak)
            if zone is not None:
                out.append(zone[1])
        return sorted(out)

    def _attack(self, bot: Any, pos: float, lap: int, t: float, reserve: float) -> float | None:
        """Puissance de l'attaque en cours ou qui part maintenant ; None sans attaque."""
        if self.attack_until > t:
            if reserve > ATTACK_STOP_RESERVE_PCT:
                return self.attack_factor * bot.cp_w
            self.attack_until = -1.0
            return None
        zone = self._attack_zone(pos, lap, bot.segments, bot.spec.sprint_last_m, bot.peak_w > 0)
        if zone is None:
            return None
        key, trigger = zone
        if pos < trigger or key in self._attack_done:
            return None
        self._attack_done.add(key)   # une fois par montée au plus, même si la réserve ne le permet pas
        chance = self.character.sprint_attack_chance if key[-1] == "sprint" else self.character.attack_chance
        if reserve <= ATTACK_MIN_RESERVE_PCT or draw(self.seed, self.bot_id, "attaque", *key) >= chance:
            return None
        self.attack_factor = _between(ATTACK_FACTOR, draw(self.seed, self.bot_id, "force", *key))
        self.attack_until = t + _between(ATTACK_S, draw(self.seed, self.bot_id, "durée", *key))
        self.attacks += 1
        return self.attack_factor * bot.cp_w

    def adjust(self, bot: Any, power_w: float, tactical: bool, t: float, s: float, length_m: float = 0.0,
               is_loop: bool = False, reserve_pct: float | None = None) -> tuple[float, bool]:
        """Puissance de la stratégie du lot T12 corrigée par la tactique, et vrai quand le bot doit quitter
        (ou ignorer) la roue qu'il suit (attaque, réponse, relais à prendre). `t` : temps de séance du bot ;
        `s` : position du bot ; `reserve_pct` : réserve à prendre en compte (celle du bot sinon ; simulation du
        calibrage)."""
        on = self.on
        if not (on.attacks or on.responses or on.relays):
            return power_w, tactical
        reserve = bot.wbal_pct if reserve_pct is None else reserve_pct
        pos, lap = s, 0
        if is_loop and length_m > 0:
            lap, pos = int(s // length_m), s % length_m
        if on.attacks and not (bot.peak_w > 0 and power_w == bot.peak_w):   # le pic du sprint (T12) garde la main
            p = self._attack(bot, pos, lap, t, reserve)
            if p is not None:
                return max(p, power_w), True
        if self.respond_to is not None:
            if t < self.respond_until and reserve > RESPONSE_STOP_RESERVE_PCT:
                wheel = getattr(bot, "wheel", None)
                if wheel is not None and wheel[0] < RESPONSE_WHEEL_M:
                    return power_w, False   # roue à moins de 1 m : il la suit (lot AS1) au lieu de foncer dedans
                return max(RESPONSE_FACTOR * bot.cp_w, power_w), True
            self.respond_to = None
        if tactical:   # sprint ou attaque de la stratégie du T12 : les rôles du groupe n'y touchent pas
            return power_w, True
        if self.role == "drop":
            return DROP_FACTOR * power_w, True
        if self.role in ("take", "pass"):
            return power_w, True
        return power_w, tactical

    # --- comportements de course (lot VD7) ----------------------------------------------------------------

    def race_power(self, bot: Any, power_w: float, tactical: bool, t: float,
                   view: RaceView | None = None) -> tuple[float, bool, float | None]:
        """Puissance demandée corrigée par l'intention de course, vrai pour quitter la roue suivie, et place
        voulue (`lane.home`, None : inchangée). `t` : temps du champ de course ; `view` : la course (marquage).
        Rien d'autre ne change : la réserve se vide ou se remplit par le modèle W′bal du bot."""
        on, it = self.on, self.race
        if not on.racing:
            return power_w, tactical, None
        cp = bot.cp_w
        if it.tired:
            return min(power_w, TIRED_CAP * cp), False, TIRED_LANE_M
        if t < it.bluff_until:
            return max(power_w, BLUFF_FACTOR * cp), True, None
        if t < it.sit_up_until:
            return min(power_w, SIT_UP_FACTOR * cp), False, None
        if tactical:          # sprint ou consigne de l'épreuve : la stratégie garde la main
            return power_w, True, None
        if it.all_in:
            return max(power_w, ALL_IN_FACTOR * cp), True, None
        if it.mark is not None and view is not None and it.mark in view.pos and self.bot_id in view.pos:
            ahead = view.gap_s(it.mark, self.bot_id)
            if MARK_HOLD_S < ahead <= MARK_RELEASE_S and bot.wbal_pct > MARK_MIN_RESERVE_PCT:
                return max(power_w, MARK_FACTOR * cp), True, None   # il revient sur la roue du marqué
            if it.watch:
                return min(power_w, WATCH_CAP * cp), False, None
            return power_w, False, None
        if it.watch:
            return min(power_w, WATCH_CAP * cp), False, None
        if it.coalition:
            return max(power_w, COALITION_FACTOR * cp), False, None
        return power_w, tactical, None

    # --- groupe (pas du champ) -------------------------------------------------------------------------

    def _watch(self, runner_id: str, gap_s: float, t: float, reserve: float, climbing: bool) -> None:
        """Relève l'écart d'un coureur devant ; décide de le suivre s'il part (§4 : réponse)."""
        hist = self._gaps.setdefault(runner_id, [])
        hist.append(gap_s)
        n = int(round(RESPONSE_WINDOW_S / TICK_S)) + 1
        if len(hist) > n:
            del hist[0]
        if len(hist) < n or hist[0] > GROUP_GAP_S or gap_s - hist[0] <= RESPONSE_GAIN_S:
            return
        if any(b <= a for a, b in zip(hist, hist[1:])):   # l'écart doit grandir à chaque relevé
            return
        if t - self._judged.get(runner_id, -1e9) < RESPONSE_COOLDOWN_S or self.respond_to is not None:
            return
        self._judged[runner_id] = t
        chance = self.character.follow_climb if climbing else self.character.follow_flat
        if reserve > RESPONSE_MIN_RESERVE_PCT and draw(self.seed, self.bot_id, "suit", runner_id,
                                                       int(t / TICK_S)) < chance:
            self.respond_to = runner_id
            self.respond_until = self._now_bot + RESPONSE_MAX_S
            self.responses += 1

    _now_bot = 0.0   # temps du bot au dernier relevé du champ (les réponses se comptent en temps du bot)


class Field:
    """État du champ de la séance : horloge des relevés et changements de tête comptés (essais, journal)."""

    def __init__(self) -> None:
        self.t = 0.0
        self._acc = 0.0
        self.lead_changes = 0          # relais passés (fins de relais et bots qui laissent passer)


def _runners(bots: list[Any], rider: tuple[float, float] | None, length_m: float | None,
             is_loop: bool) -> list[tuple[float, float, str, Any]]:
    """(position déroulée, vitesse, id, bot ou None) du cycliste et des bots, du premier au dernier."""
    ref = rider[0] if rider is not None else (bots[0].s if bots else 0.0)
    out = []
    if rider is not None:
        out.append((rider[0], rider[1], RIDER_ID, None))
    for b in bots:
        if getattr(b, "kind", "constant") != "constant":
            continue   # le fantôme n'est pas dans la course
        d = b.s - ref
        if is_loop and length_m:
            d %= length_m
            if d > length_m / 2.0:
                d -= length_m
        out.append((ref + d, b.v, b.id, b))
    out.sort(key=lambda r: -r[0])
    return out


def groups(runners: list[tuple[float, float, str, Any]]) -> list[list[tuple[float, float, str, Any]]]:
    """Coureurs triés du premier au dernier, coupés là où l'écart dépasse `GROUP_GAP_S`."""
    out: list[list] = []
    for r in runners:
        if out:
            prev = out[-1][-1]
            if (prev[0] - r[0]) / max(r[1], 1.0) <= GROUP_GAP_S:
                out[-1].append(r)
                continue
        out.append([r])
    return out


def update_field(field: Field, bots: list[Any], rider: tuple[float, float] | None, dt: float,
                 grade_at: Callable[[float], float] | None = None, length_m: float | None = None,
                 is_loop: bool = False) -> None:
    """Groupes, relais et réponses aux départs (§4), relus toutes les `TICK_S` secondes sur les positions
    du pas précédent ; appelé par la séance avant le pas des bots. `rider` : (s, v) du cycliste, None sans
    lui ; `grade_at(s)` : pente (%) à la position s."""
    field.t += dt
    field._acc += dt
    if field._acc + 1e-9 < TICK_S:
        return
    field._acc = 0.0
    t = field.t
    runners = _runners(bots, rider, length_m, is_loop)
    pos = {id(r[3]): r[0] for r in runners if r[3] is not None}   # positions déroulées des bots
    for grp in groups(runners):
        tacticians = [r for r in grp if r[3] is not None and getattr(r[3], "tactics", None) is not None]
        if not tacticians:
            continue
        # --- réponses : chacun surveille les coureurs devant lui dans son groupe et ceux qui en sortent
        for _, v, rid, b in tacticians:
            tac = b.tactics
            tac._now_bot = b.t
            if not tac.on.responses or t < RESPONSE_START_S:   # départ arrêté : les écarts se font tout seuls
                continue
            climbing = grade_at is not None and grade_at(b.s) >= FLAT_MAX_GRADE_PCT
            seen = set()
            for o_s, _, o_id, _ in runners:
                gap = (o_s - pos[id(b)]) / max(v, 1.0)
                if gap <= 0.0 or gap > GROUP_GAP_S + 2 * RESPONSE_WINDOW_S:
                    continue
                seen.add(o_id)
                tac._watch(o_id, gap, t, b.wbal_pct, climbing)
            for gone in [k for k in tac._gaps if k not in seen]:
                del tac._gaps[gone]
            if tac.respond_to is not None:
                target = next((r for r in runners if r[2] == tac.respond_to), None)
                if target is None or (target[0] - pos[id(b)]) / max(v, 1.0) <= RESPONSE_CAUGHT_S:
                    tac.respond_to = None
        _relays(field, grp, t, grade_at)


def _eligible(b: Any) -> bool:
    tac = getattr(b, "tactics", None) if b is not None else None
    return (tac is not None and tac.on.relays and tac.character.relays
            and b.wbal_pct >= RELAY_MIN_RESERVE_PCT)


def _relays(field: Field, grp: list[tuple[float, float, str, Any]], t: float,
            grade_at: Callable[[float], float] | None) -> None:
    """Relais d'un groupe sur le plat : le premier roule `relay_duration_s`, puis se relève (−15 % pendant
    5 s) ; le suivant passe prendre la tête et les autres doublent celui qui se relève. Pas de relais en
    montée, ni par un sprinteur ou un bot sous 30 % de réserve (il laisse passer s'il est devant)."""
    members = [r[3] for r in grp]
    head_s, _, _, head = grp[0]
    for b in members:   # rôles échus ; seul le premier est en relais
        tac = getattr(b, "tactics", None) if b is not None else None
        if tac is None:
            continue
        if tac.role == "drop" and ((t >= tac.role_until and b is not head) or t >= tac.relay_started + DROP_MAX_S):
            tac.role, tac.role_until = "rest", t + REST_S   # doublé (5 s au moins), ou au bout de 15 s
        elif tac.role in ("take", "pass") and (t >= tac.role_until or not any(
                getattr(m, "tactics", None) is not None and m.tactics.role == "drop" for m in members)):
            tac.role = ""   # celui qui se relevait est doublé (ou sorti du groupe)
        elif (tac.role == "rest" and (t >= tac.role_until or b is not head)) or (tac.role == "relay" and b is not head):
            tac.role = ""
        if tac.role not in ("drop", "rest"):
            _shift(b, False)
    flat = grade_at is None or grade_at(head_s) < FLAT_MAX_GRADE_PCT
    if len(grp) < 2 or not flat:
        for b in members:
            tac = getattr(b, "tactics", None) if b is not None else None
            if tac is not None and tac.role == "relay":
                tac.role = ""
        return
    if head is None or getattr(head, "tactics", None) is None or not head.tactics.on.relays:
        return   # le cycliste (ou un bot sans tactique) mène : on suit sa roue
    tac = head.tactics
    if tac.role in ("drop", "rest"):
        return
    behind = [r[3] for r in grp[1:]]
    next_up = next((b for b in behind if _eligible(b)), None)
    if not _eligible(head):
        if next_up is not None:   # sprinteur ou bot vide devant : il se range et laisse passer
            _hand_over(head, next_up, behind, t)
            field.lead_changes += 1
        return
    if tac.role != "relay":
        tac.role = "relay"
        tac.role_until = t + relay_duration_s(head.wbal_pct)
        return
    if t >= tac.role_until and next_up is not None:
        _hand_over(head, next_up, behind, t)
        field.lead_changes += 1


def _shift(bot: Any, aside: bool) -> None:
    """Place de repos du bot (`lane.home`, lot AS2) décalée de `RELAY_SHIFT_M` vers l'axe quand il se relève :
    ceux qui le suivaient passent sans sortir de leur ligne ; remise à sa place ensuite."""
    lane, tac = getattr(bot, "lane", None), bot.tactics
    if lane is None:
        return
    if aside and tac._home is None:
        tac._home = lane.home
        lane.home = max(lane.home - RELAY_SHIFT_M, LANE_MIN_M)
    elif not aside and tac._home is not None:
        lane.home, tac._home = tac._home, None


def _hand_over(head: Any, next_up: Any, behind: list[Any], t: float) -> None:
    head.tactics.role, head.tactics.role_until = "drop", t + DROP_S
    head.tactics.relay_started = t   # début de la fin de relais
    _shift(head, True)
    for b in behind:
        tac = getattr(b, "tactics", None) if b is not None else None
        if tac is None or tac.role in ("drop", "rest") or not _eligible(b):
            continue   # sprinteur ou bot vide : il reste dans les roues
        tac.role = "take" if b is next_up else "pass"
        tac.role_until = t + DROP_MAX_S


def start_race(bots: Iterable[Any], seed: int, mode: str) -> None:
    """Départ de séance : graine et comportements du mode donnés aux bots à profil (après leur calibrage)."""
    for b in bots:
        tac = getattr(b, "tactics", None)
        if tac is not None:
            tac.start(seed, mode)
            b.apply_form()


def seed_from(value: float) -> int:
    """Graine de séance sur 32 bits (par exemple `time.time()`)."""
    return int(math.floor(value)) & 0xFFFFFFFF
