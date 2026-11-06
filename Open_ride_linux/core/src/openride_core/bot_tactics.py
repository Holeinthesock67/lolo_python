"""Tactique des bots à profil (lot Y10) : relais, attaques, réponses, fatigue de longue durée, forme du jour.

Module commun, pur et testable, appelé par `ProfileBot` à chaque pas (`Tactics.adjust`) et par la séance une
fois par pas pour le groupe (`update_field`). Il ne change que la **puissance demandée** et l'envie de garder
ou de quitter une roue : la physique, l'abri (`draft.py`) et la réserve W′bal (`rogue/wbal.py`) restent ceux
du cycliste ; une puissance au-dessus de la CP vide la réserve comme pour lui (pas de triche physique).

Chaque mode de jeu choisit ses comportements dans `MODE_TACTICS` (table, pas de code propre au mode). Le
vélodrome (lot VD7, `docs/4.0/PLAN_SERIE_VD.md` §6.1) prolonge ce module avec ses propres comportements
(coalitions, marquage, bluff, gestion du classement, fatigue visible, personnalités) et le réglage « Tactique
des bots : aucune, simple, complète » : ils s'ajoutent comme champs de `Behaviours` et lignes de la table.

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


NONE = Behaviours()
FULL = Behaviours(relays=True, attacks=True, responses=True, durability=True, form=True)

# Table des modes. Les modes qui n'ont pas encore branché la table (Dernier survivant, WTF, monde ouvert,
# vélodrome) restent à `none` jusqu'à leur propre lot. `essai` : le banc `bots_race` (lot X27), qui juge
# chaque bot à ± 2 % du cycliste, sans le facteur de forme qui l'en écarterait à dessein.
MODE_TACTICS: dict[str, Behaviours] = {
    "none": NONE,
    "classic": FULL,
    "essai": Behaviours(relays=True, attacks=True, responses=True, durability=True, form=False),
    "calibration": Behaviours(attacks=True, durability=True),   # lot T13 : bot seul, sans groupe ni forme
}


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

    def __init__(self, bot_id: str, character: Character, seed: int = 0, mode: str = "none") -> None:
        self.bot_id = bot_id
        self.character = character
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

    def attack_spans(self, segments: Iterable[Any], sprint_last_m: float, peak: bool) -> list[tuple[float, float]]:
        """Intervalles (début, fin, sur un tour) où ce bot peut attaquer : les montées, le dernier kilomètre des
        sprints ; pour sauter `adjust` ailleurs (simulation du calibrage, lot T13)."""
        ch, out = self.character, []
        if not self.on.attacks:
            return out
        for seg in segments:
            if seg.type == "climb" and ch.attack_chance > 0.0:
                out.append((seg.s_start, seg.s_end))
            elif seg.type == "sprint" and ch.sprint_attack_chance > 0.0 and not peak:
                out.append((seg.s_end - SPRINT_ATTACK_M, seg.s_end - sprint_last_m))
        return out

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
