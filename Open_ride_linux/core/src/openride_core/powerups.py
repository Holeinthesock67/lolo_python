"""Bonus : un seul modèle de bonus décrit par des données (lot TT2, série TT ; lot T6 pour le cadre).

Module pur. Un bonus est obtenu au hasard à la fin de chaque segment et sous une arche tous
les 5 km ; un seul est gardé en réserve (un nouveau remplace l'ancien). Il s'active par le
bouton Z du Click (appui court) et agit pendant quelques secondes sur les paramètres de la
physique (`PhysicsParams`) ou sur la puissance prise en compte, donc sur la vitesse virtuelle
seulement : la résistance du trainer, la puissance du FIT, du journal et du bilan restent
celles mesurées. En ERG, les bonus sont coupés (ERG d'une session libre compris, T-Q2), la réserve
est gardée. Cahiers : `docs/lots/LOT_T6_bonus.md`, `docs/lots/LOT_TT2_modele_unique_bonus.md` ;
plan `docs/4.0/PLAN_SERIE_TT.md`.

**Un bonus = une ligne de `DEFAULT_TABLE`** : identifiant du contrat (révision 1.13), effet
(`EffectSpec` : effet, facteur, durée), jeux où il est tiré (`classiques`, `tactiques`), conditions
de tirage (`draw_if`), conditions d'activation avec la raison du refus (`refuse_unless`), seuil de
suspension. Aucun bonus n'a de branche de code à lui : `params`, `power` et `CONDITIONS` ne lisent
que l'effet et les noms de conditions. Les effets du Grand Prix (lot GP1 : `kick`, `slip`,
`speed_floor`, `cap`, `immune`, `wind`) sont des lignes du même `EffectSpec` ; `grandprix/effects.py`
les applique (un seul système, plan GP §5).

Les valeurs se modifient dans `~/OpenRide/powerups.toml` (facultatif), une section par bonus :

    [feather]              # Plume : masse totale × factor ([lightweight], nom de la 2.0, accepté)
    factor = 0.90
    duration_s = 20
    [aero]                 # Casque aéro : CdA × factor
    factor = 0.75
    duration_s = 15
    [power]                # Puissance prise en compte par la physique × factor
    factor = 1.10
    duration_s = 15
    [anvil]                # Enclume : masse × factor, en descente seulement
    factor = 1.6
    duration_s = 15
    [obtain]
    arch_every_m = 5000    # 0 : pas d'arche
    per_segment = true
"""

from __future__ import annotations

import math
import random
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

from .config import OPENRIDE_HOME
from .physics import PhysicsParams

POWERUPS_FILE = OPENRIDE_HOME / "powerups.toml"

# --- effets : une seule liste pour les bonus et les objets du Grand Prix ----------------------

BONUS_EFFECTS = ("mass", "cda", "power", "draft", "crr", "breakaway")   # série TT (plan §2)
# Grand Prix (lot GP1), déplacés de `grandprix/effects.py` sans changement :
IMPULSES = ("kick", "slip")
DURATIONS = ("speed_floor", "cap", "immune", "wind", "breakaway")
MULTIPLIERS = ("kick", "slip", "speed_floor", "cap")   # facteurs sans unité, comparés à 1
HITS = ("slip", "cap", "wind")                         # effets subis : arrêtés par `immune`
EFFECTS = tuple(dict.fromkeys(BONUS_EFFECTS + IMPULSES + DURATIONS))


@dataclass(frozen=True)
class EffectSpec:
    """Ligne d'effet : (effet, facteur, durée). Bonus de la série TT et objets du Grand Prix."""

    effect: str
    factor: float
    duration_s: float = 0.0

    def __post_init__(self) -> None:
        if self.effect not in EFFECTS:
            raise ValueError(f"effet inconnu : {self.effect!r}")

    def scaled(self, chaos: float) -> EffectSpec:
        """Force multipliée par le chaos : l'écart à 1 d'un facteur, la valeur du vent ; durée inchangée."""
        if self.effect in MULTIPLIERS:
            return replace(self, factor=1.0 + (self.factor - 1.0) * chaos)
        if self.effect == "wind":
            return replace(self, factor=self.factor * chaos)
        return self


# --- conditions : noms lus dans la table, évalués sur le contexte du pas ---------------------

DESCENT_GRADE_PCT = -1.5        # Enclume : activation refusée au-dessus (plan §2)
DESCENT_HOLD_PCT = -0.5         # Enclume : masse en plus suspendue au-dessus, le temps continue
DESCENT_MIN_M = 300.0           # tirage : au moins 300 m d'affilée sous −1,5 %…
LOOK_AHEAD_M = 5000.0           # … dans les 5 km devant (plan §3)
LOOK_STEP_M = 25.0
UNPAVED_MIN_M = 1000.0         # Rouleau compresseur : au moins 1 km non revêtu dans les 5 km devant
ROLLER_BLEND_M = 20.0          # Rouleau : transitions de 20 m, comme le fondu des surfaces du lot U21
NEAR_FINISH_M = 400.0          # Échappée : refusée à moins de 400 m de l'arrivée ou de la fin d'un sprint
DRAFT_PLUS_CAP = 0.55          # Aspiration + : plafond du cœur de groupe de la série AS (AS4)
DRAFT_PLUS_REACH_M = 25.0      # Aspiration + : portée de l'abri (15 m sans bonus)
REFUSED_SHOW_S = 2.0            # raison du refus affichée 2 s (contrat 1.13, `powerup.refused`)

MODES = ("off", "classiques", "tactiques")      # réglage `powerups.mode` (contrat 1.13)
SETS = ("classiques", "tactiques")
REASONS = ("no_bots", "no_descent", "near_finish", "no_gravel", "erg")


@dataclass
class Context:
    """Ce que le terrain et la séance disent au moment d'un tirage, d'un appui ou d'un pas."""

    grade_pct: float = 0.0
    has_bots: bool = False
    near_finish: bool = False                         # à moins de 400 m de l'arrivée ou de la fin d'un sprint
    ds_m: float = 0.0                                 # distance roulée pendant le pas (fondu du Rouleau, TT5)
    descent_ahead: Callable[[], bool] = lambda: False   # calcul paresseux : seulement au tirage
    gravel_ahead: Callable[[], bool] = lambda: False    # idem : gravel actif et 1 km non revêtu devant (TT5)


CONDITIONS: dict[str, Callable[[Context], bool]] = {
    "descending": lambda c: c.grade_pct <= DESCENT_GRADE_PCT,
    "descent_ahead": lambda c: c.descent_ahead(),
    "bots": lambda c: c.has_bots,
    "far_from_finish": lambda c: not c.near_finish,
    "gravel_ahead": lambda c: c.gravel_ahead(),
}


def unpaved_ahead(surface_at: Callable[[float], str], s: float, length_m: float | None = None) -> bool:
    """Vrai s'il y a au moins `UNPAVED_MIN_M` non revêtus dans les 5 km devant (`surface_at` : surface
    effective, option gravel comprise) ; `length_m` : fin d'un parcours ouvert, None pour une boucle."""
    end = LOOK_AHEAD_M if length_m is None else min(LOOK_AHEAD_M, length_m - s)
    total, d = 0.0, LOOK_STEP_M / 2.0
    while d < end:
        if surface_at(s + d) != "paved":
            total += LOOK_STEP_M
            if total >= UNPAVED_MIN_M - 1e-9:
                return True
        d += LOOK_STEP_M
    return False


def descent_ahead(grade_at: Callable[[float], float], s: float, length_m: float | None = None) -> bool:
    """Vrai s'il y a au moins `DESCENT_MIN_M` d'affilée sous `DESCENT_GRADE_PCT` dans les 5 km devant.

    `length_m` : fin d'un parcours ouvert (rien n'est cherché au-delà) ; None pour une boucle."""
    run, d = 0.0, LOOK_STEP_M
    end = LOOK_AHEAD_M if length_m is None else min(LOOK_AHEAD_M, length_m - s)
    while d <= end + 1e-9:
        run = run + LOOK_STEP_M if grade_at(s + d) <= DESCENT_GRADE_PCT else 0.0
        if run >= DESCENT_MIN_M - 1e-9:
            return True
        d += LOOK_STEP_M
    return False


# --- table des bonus ----------------------------------------------------------------------

class PowerUpError(ValueError):
    """Fichier de valeurs invalide."""


@dataclass(frozen=True)
class PowerUpSpec:
    kind: str                                   # identifiant du contrat (révision 1.13)
    effect: str                                 # un de `BONUS_EFFECTS`
    factor: float
    duration_s: float
    label: str
    sets: tuple[str, ...] = SETS
    factor_bounds: tuple[float, float] = (0.5, 1.5)
    draw_if: tuple[str, ...] = ()               # conditions de tirage (noms de `CONDITIONS`)
    refuse_unless: tuple[tuple[str, str], ...] = ()   # (condition, raison du refus)
    hold_above_grade_pct: float | None = None   # effet suspendu au-dessus de cette pente
    cap: float | None = None                    # effet `draft` : plafond de l'abri (TT3)
    reach_m: float | None = None                # effet `draft` : portée de l'abri (TT3)

    def __post_init__(self) -> None:
        EffectSpec(self.effect, self.factor, self.duration_s)   # effet connu
        if self.effect not in BONUS_EFFECTS:
            raise ValueError(f"{self.kind} : effet {self.effect!r} réservé au Grand Prix")
        names = set(self.draw_if) | {c for c, _ in self.refuse_unless}
        if names - set(CONDITIONS) or {r for _, r in self.refuse_unless} - set(REASONS):
            raise ValueError(f"{self.kind} : condition ou raison inconnue")

    @property
    def effect_spec(self) -> EffectSpec:
        return EffectSpec(self.effect, self.factor, self.duration_s)


@dataclass(frozen=True)
class PowerUpTable:
    specs: dict[str, PowerUpSpec]
    arch_every_m: float = 5000.0
    per_segment: bool = True

    def kinds(self, set_name: str) -> tuple[str, ...]:
        return tuple(k for k, s in self.specs.items() if set_name in s.sets)


# L'ordre des lignes est celui du tirage : Plume, Casque, Puissance d'abord, comme la 2.0
# (`lightweight`, `aero`, `power`), pour que le jeu `classiques` tire les mêmes bonus.
DEFAULT_TABLE = PowerUpTable(specs={
    "feather": PowerUpSpec("feather", "mass", 0.90, 20.0, "Plume", factor_bounds=(0.5, 1.0)),
    "aero": PowerUpSpec("aero", "cda", 0.75, 15.0, "Casque aéro", factor_bounds=(0.5, 1.0)),
    "power": PowerUpSpec("power", "power", 1.10, 15.0, "Puissance", factor_bounds=(1.0, 1.5)),
    "anvil": PowerUpSpec("anvil", "mass", 1.6, 15.0, "Enclume", sets=("tactiques",), factor_bounds=(1.0, 2.5),
                         draw_if=("descent_ahead",), refuse_unless=(("descending", "no_descent"),),
                         hold_above_grade_pct=DESCENT_HOLD_PCT),
    # Durées de l'Aspiration +, de l'Échappée et du Rouleau ajustées au banc du lot TT8 (40, 20 et 30 s avant ;
# `tools/bonus_bench.py`, rapport `docs/4.0/RAPPORT_EQUILIBRAGE_TT8.md`).
# Aspiration + (lot TT3) : abri × 1,5 plafonné au cœur de groupe d'AS4, portée 15 → 25 m.
    "draft_plus": PowerUpSpec("draft_plus", "draft", 1.5, 35.0, "Aspiration +", sets=("tactiques",),
                              factor_bounds=(1.0, 2.0), draw_if=("bots",), refuse_unless=(("bots", "no_bots"),),
                              cap=DRAFT_PLUS_CAP, reach_m=DRAFT_PLUS_REACH_M),
    # Échappée (lot TT4, Burrito et Fantôme fusionnés) : les bots derrière ne reçoivent plus ton abri et
    # ne répondent pas à ton attaque. Même ligne d'effet que le Furtif du Grand Prix (GP4).
    "breakaway": PowerUpSpec("breakaway", "breakaway", 1.0, 30.0, "Échappée", sets=("tactiques",),
                             factor_bounds=(1.0, 1.0), draw_if=("bots",),
                             refuse_unless=(("bots", "no_bots"), ("far_from_finish", "near_finish"))),
    # Rouleau compresseur (lot TT5) : roulement du bitume sur le non revêtu ; `factor` = part du roulement
    # en plus du gravel qui disparaît (1 : tout), atteinte et perdue sur 20 m.
    "roller": PowerUpSpec("roller", "crr", 1.0, 25.0, "Rouleau compresseur", sets=("tactiques",),
                          factor_bounds=(0.0, 1.0), draw_if=("gravel_ahead",),
                          refuse_unless=(("gravel_ahead", "no_gravel"),)),
})
KINDS = tuple(DEFAULT_TABLE.specs)
LABELS = {k: s.label for k, s in DEFAULT_TABLE.specs.items()}
ALIASES = {"lightweight": "feather"}   # sections de `powerups.toml` écrites pour la 2.0
SOURCES = ("segment", "arch")

DURATION_MIN_S, DURATION_MAX_S = 1.0, 120.0
ARCH_EVERY_MIN_M = 500.0


def _number(section: dict, key: str, default: float, lo: float, hi: float, where: str) -> float:
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PowerUpError(f"{where}.{key} doit être un nombre")
    if not lo <= value <= hi:
        raise PowerUpError(f"{where}.{key} = {value} hors de [{lo}, {hi}]")
    return float(value)


def load_table(path: Path | None = None) -> PowerUpTable:
    """Valeurs des bonus : défauts du plan, remplacés par ceux du fichier s'il existe."""
    path = path or POWERUPS_FILE
    if not path.is_file():
        return DEFAULT_TABLE
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PowerUpError(f"{path} illisible : {exc}") from exc
    for old, new in ALIASES.items():
        if old in data:
            if new in data:
                raise PowerUpError(f"[{old}] et [{new}] : la même section deux fois")
            data[new] = data.pop(old)
    unknown = set(data) - set(KINDS) - {"obtain"}
    if unknown:
        raise PowerUpError(f"sections inconnues dans {path.name} : {', '.join(sorted(unknown))}")
    specs = {}
    for kind, base in DEFAULT_TABLE.specs.items():
        sec = data.get(kind, {})
        if not isinstance(sec, dict):
            raise PowerUpError(f"[{kind}] doit être une section")
        specs[kind] = replace(
            base,
            factor=_number(sec, "factor", base.factor, *base.factor_bounds, kind),
            duration_s=_number(sec, "duration_s", base.duration_s, DURATION_MIN_S, DURATION_MAX_S, kind))
    obtain = data.get("obtain", {})
    if not isinstance(obtain, dict):
        raise PowerUpError("[obtain] doit être une section")
    every = _number(obtain, "arch_every_m", DEFAULT_TABLE.arch_every_m, 0.0, 1e6, "obtain")
    if 0.0 < every < ARCH_EVERY_MIN_M:
        raise PowerUpError(f"obtain.arch_every_m = {every} : 0 ou au moins {ARCH_EVERY_MIN_M:.0f} m")
    per_segment = obtain.get("per_segment", DEFAULT_TABLE.per_segment)
    if not isinstance(per_segment, bool):
        raise PowerUpError("obtain.per_segment doit valoir true ou false")
    return PowerUpTable(specs=specs, arch_every_m=every, per_segment=per_segment)


class ArchSchedule:
    """Arches de bonus à position fixe sur la route (tous les `every_m`, répétées à chaque tour)."""

    def __init__(self, every_m: float, length_m: float, loop: bool = False) -> None:
        self.length_m = float(length_m)
        self.loop = loop
        self.positions: list[float] = []
        self.every_m = float(every_m)
        self.endless = math.isinf(self.length_m) and not loop   # monde ouvert (lot W21) : une arche tous les every_m
        if every_m > 0 and not self.endless:
            k = 1
            while k * every_m < self.length_m - 1e-6:
                self.positions.append(k * every_m)
                k += 1

    def crossed(self, s_prev: float, s: float) -> int:
        """Nombre d'arches franchies entre deux positions cumulées (`s_prev` exclu, `s` inclus)."""
        if self.endless and self.every_m > 0:
            return max(0, math.floor(s / self.every_m) - math.floor(max(s_prev, 0.0) / self.every_m)) if s > s_prev else 0
        if s <= s_prev or not self.positions:
            return 0
        if not self.loop:
            return sum(1 for p in self.positions if s_prev < p <= s)
        L = self.length_m
        count = 0
        for p in self.positions:
            # Nombre de k tels que s_prev < k·L + p <= s.
            count += math.floor((s - p) / L) - math.floor((s_prev - p) / L)
        return count


@dataclass(frozen=True)
class PowerUpUse:
    kind: str
    t_start: float           # temps chronométré de la séance à l'activation
    duration_s: float

    def to_dict(self) -> dict:
        return {"kind": self.kind, "t_start": round(self.t_start, 2),
                "duration_s": round(self.duration_s, 2)}


@dataclass(frozen=True)
class DraftBoost:
    """Abri du cycliste × `factor`, plafonné à `cap`, sources comptées jusqu'à `reach_m` (lot TT3)."""
    factor: float
    cap: float
    reach_m: float


@dataclass(frozen=True)
class Refusal:
    kind: str
    reason: str
    t: float


@dataclass
class PowerUps:
    """Réserve, bonus actif et effets ; `step` n'est appelé que pendant `RUNNING`."""

    table: PowerUpTable = DEFAULT_TABLE
    seed: int | None = None
    set_name: str = "classiques"
    erg: bool = False
    reserve: str | None = None
    active: str | None = None
    remaining_s: float = 0.0
    held: bool = False                     # effet suspendu (Enclume hors descente), le temps continue
    refused: Refusal | None = None
    refused_left_s: float = 0.0
    uses: list[PowerUpUse] = field(default_factory=list)
    refusals: list[Refusal] = field(default_factory=list)
    roll_w: float = 0.0                    # part du Rouleau appliquée (0 à 1, fondu de 20 m)

    def __post_init__(self) -> None:
        if self.set_name not in SETS:
            raise ValueError(f"jeu de bonus inconnu : {self.set_name}")
        self._rng = random.Random(self.seed)
        self._kinds = self.table.kinds(self.set_name)

    # --- obtention et activation ---------------------------------------------------------

    def award(self, source: str, ctx: Context | None = None) -> str | None:
        """Bonus tiré parmi ceux du jeu qui servent ici (remplace l'ancien) ; None en ERG, source coupée
        ou rien d'utile. Sans condition de tirage, le tirage est celui de la 2.0 (même suite aléatoire)."""
        if source not in SOURCES:
            raise ValueError(f"source de bonus inconnue : {source}")
        if self.erg or (source == "segment" and not self.table.per_segment):
            return None
        ctx = ctx or Context()
        specs = self.table.specs
        kinds = [k for k in self._kinds if all(CONDITIONS[c](ctx) for c in specs[k].draw_if)]
        if not kinds:
            return None
        self.reserve = self._rng.choice(kinds)
        return self.reserve

    def activate(self, t: float, ctx: Context | None = None) -> bool:
        """Appui court sur Z : active la réserve s'il n'y a pas déjà un bonus actif. Un bonus dont la
        condition manque (ou tout bonus en ERG) est refusé : réserve gardée, raison dans `refused`."""
        if self.reserve is None or self.active is not None:
            return False
        spec = self.table.specs[self.reserve]
        ctx = ctx or Context()
        reason = "erg" if self.erg else next(
            (r for c, r in spec.refuse_unless if not CONDITIONS[c](ctx)), None)
        if reason is not None:
            self.refused = Refusal(spec.kind, reason, t)
            self.refused_left_s = REFUSED_SHOW_S
            self.refusals.append(self.refused)
            return False
        self.active, self.reserve = self.reserve, None
        self.remaining_s = spec.duration_s
        self.refused, self.refused_left_s = None, 0.0
        self.held = self._held(spec, ctx)
        self.uses.append(PowerUpUse(spec.kind, t, spec.duration_s))
        return True

    @staticmethod
    def _held(spec: PowerUpSpec, ctx: Context) -> bool:
        return spec.hold_above_grade_pct is not None and ctx.grade_pct > spec.hold_above_grade_pct

    def step(self, dt: float, ctx: Context | None = None) -> None:
        if ctx is not None and ctx.ds_m > 0.0:   # fondu de l'effet `crr` sur la distance roulée (TT5)
            spec = self._effect()
            up = ctx.ds_m / ROLLER_BLEND_M
            self.roll_w = min(1.0, self.roll_w + up) if spec is not None and spec.effect == "crr" \
                else max(0.0, self.roll_w - up)
        if self.refused is not None:
            self.refused_left_s -= dt
            if self.refused_left_s <= 1e-9:
                self.refused, self.refused_left_s = None, 0.0
        if self.active is None:
            return
        self.remaining_s -= dt
        if self.remaining_s <= 1e-9:
            self.active, self.remaining_s, self.held = None, 0.0, False
        elif ctx is not None:
            self.held = self._held(self.table.specs[self.active], ctx)

    def set_erg(self, on: bool) -> None:
        """ERG : bonus actif arrêté, obtention et activation refusées ; la réserve est gardée."""
        self.erg = bool(on)
        if self.erg and self.active is not None:
            self.active, self.remaining_s, self.held = None, 0.0, False

    # --- effets --------------------------------------------------------------------------

    def _effect(self) -> PowerUpSpec | None:
        if self.active is None or self.held:
            return None
        return self.table.specs[self.active]

    def params(self, base: PhysicsParams) -> PhysicsParams:
        """Paramètres de la physique pendant le bonus (masse, CdA ou roulement) ; `base` sinon."""
        spec = self._effect()
        if spec is None:
            return base
        if spec.effect == "mass":
            return replace(base, mass_kg=base.mass_kg * spec.factor)
        if spec.effect == "cda":
            return replace(base, cda_m2=base.cda_m2 * spec.factor)
        return base

    def surface_factor(self, gravel_factor: float) -> float:
        """Facteur de roulement du gravel (lot U21) pendant le Rouleau compresseur (lot TT5) : ramené vers 1
        (bitume) selon le fondu ; le supplément de pente SIM du gravel, calculé dessus, disparaît aussi."""
        if self.roll_w <= 0.0:
            return gravel_factor
        spec = self.table.specs.get("roller")
        share = spec.factor if spec is not None else 1.0
        return 1.0 + (gravel_factor - 1.0) * (1.0 - share * self.roll_w)

    def draft_boost(self) -> DraftBoost | None:
        """Abri renforcé pendant un bonus `draft` (Aspiration +, lot TT3) ; None sinon."""
        spec = self._effect()
        if spec is None or spec.effect != "draft":
            return None
        return DraftBoost(spec.factor, spec.cap if spec.cap is not None else 1.0,
                          spec.reach_m if spec.reach_m is not None else 0.0)

    def unseen(self) -> bool:
        """Vrai pendant un effet `breakaway` (Échappée, lot TT4) : ni abri donné, ni attaque vue."""
        spec = self._effect()
        return spec is not None and spec.effect == "breakaway"

    def feel_params(self, p: PhysicsParams, base: PhysicsParams) -> PhysicsParams:
        """Paramètres du supplément de pente SIM : masse de base (Plume et Enclume ne se sentent pas au
        trainer, T-Q3), CdA et roulement du bonus (l'abri, le vent et le gravel suivent le bonus)."""
        spec = self._effect()
        if spec is not None and spec.effect == "mass":
            return replace(p, mass_kg=base.mass_kg)
        return p

    def power(self, measured_w: float) -> float:
        """Puissance prise en compte par la physique (jamais écrite au journal ni au FIT)."""
        spec = self._effect()
        if spec is not None and spec.effect == "power":
            return measured_w * spec.factor
        return measured_w

    def state_dict(self) -> dict:
        """État interne (tests et outils) ; la trame `state` est écrite par `classic.ClassicRace.frame`."""
        return {"reserve": self.reserve, "active": self.active,
                "remaining_s": round(self.remaining_s, 1) if self.active else 0.0}

    def contract(self) -> dict:
        """Objet `powerup` de la trame `state` (contrat IPC 1.13)."""
        out: dict = {"held": self.reserve, "active": self.active,
                     "remaining_s": round(self.remaining_s, 1) if self.active else 0.0}
        if self.refused is not None:
            out["refused"] = {"kind": self.refused.kind, "reason": self.refused.reason}
        return out
