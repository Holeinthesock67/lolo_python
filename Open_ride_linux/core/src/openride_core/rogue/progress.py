"""Progression permanente du Cyber-Rogue (lot R9) : châssis, statistiques de runs, coffres et vies.

Module pur. Tout se recalcule depuis le journal des séances : les lignes `rogue_run` (écrites par la
session, lot R8, avec `run_event`) passent par `progression.recompute` comme l'expérience de la série V,
puis `rogue_stats` en tire les statistiques et les déblocages. Seules les pièces dépensées (profil de V4)
ne se recalculent pas.

Un châssis ajoute de petites quantités à des constantes de `RogueBalance` : bouclier maximal, fenêtre de
Perfect Shift, or gagné, adrénaline de départ, seuil de surchauffe. Aucune autre constante n'est
permise, donc ni la pente envoyée au trainer ni la puissance demandée (équité par la FTP) ne bougent.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, fields, replace
from typing import Any

from ..progression import Progress, Table
from .balance import DEFAULT_BALANCE, RogueBalance

BOSS_ID = "chimere_centrale"
DEFAULT_CHASSIS = "standard"
FINISHED = ("victory", "defeat")
UNLOCK_STATS = ("none", "boss_won", "perfect_shifts", "gold_total", "vo2max_runs", "endurance_runs")
BONUS_KEYS = ("shield_max", "ps_window_s", "gold_mult", "adrenaline_start", "overheat_frac")
MAX_RELATIVE_BONUS = 0.10
START_ADRENALINE_MAX = 20.0             # constante nulle au repos : plafond absolu au lieu de 10 %
_CHASSIS_KEYS = {"id": str, "name": str, "text": str, "unlock": str, "threshold": (int, float), "bonus": dict}


class ChassisError(Exception):
    """Table de châssis invalide ou choix refusé ; `code` reprend les codes du contrat."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Chassis:
    id: str
    name: str
    text: str
    unlock: str
    threshold: float
    bonus: dict = field(default_factory=dict)


# --- table ---------------------------------------------------------------------------------

def load_chassis(table: Table, base: RogueBalance = DEFAULT_BALANCE) -> tuple[Chassis, ...]:
    """Section `[[chassis]]` de la table de la série V, vérifiée ; lève `ChassisError` (`table_invalid`)."""
    raw = table.data.get("chassis")
    if not isinstance(raw, list) or not raw:
        raise ChassisError("table_invalid", "[[chassis]] absent ou mal formé")
    out, seen = [], set()
    for i, row in enumerate(raw):
        where = f"[[chassis]] n° {i + 1}"
        if not isinstance(row, dict):
            raise ChassisError("table_invalid", f"{where} : table attendue")
        for key, val in row.items():
            if key not in _CHASSIS_KEYS:
                raise ChassisError("table_invalid", f"{where} {key} : clé inconnue")
            if isinstance(val, bool) or not isinstance(val, _CHASSIS_KEYS[key]):
                raise ChassisError("table_invalid", f"{where} {key} : type inattendu ({val!r})")
        for key in ("id", "name", "unlock", "threshold"):
            if key not in row:
                raise ChassisError("table_invalid", f"{where} {key} : clé manquante")
        if row["id"] in seen:
            raise ChassisError("table_invalid", f"{where} id : « {row['id']} » en double")
        seen.add(row["id"])
        if row["unlock"] not in UNLOCK_STATS:
            raise ChassisError("table_invalid", f"{where} unlock : « {row['unlock']} » inconnu "
                                                f"(attendu : {', '.join(UNLOCK_STATS)})")
        ch = Chassis(row["id"], row["name"], row.get("text", ""), row["unlock"], float(row["threshold"]),
                     dict(row.get("bonus", {})))
        check_bounds(ch, base)
        out.append(ch)
    if out[0].id != DEFAULT_CHASSIS or out[0].unlock != "none" or out[0].bonus:
        raise ChassisError("table_invalid", f"le premier châssis doit être « {DEFAULT_CHASSIS} », sans bonus ni condition")
    return tuple(out)


def check_bounds(chassis: Chassis, base: RogueBalance = DEFAULT_BALANCE) -> None:
    """Refuse une constante hors de la liste permise, ou un bonus de plus de 10 % de la valeur du jeu."""
    for key, delta in chassis.bonus.items():
        where = f"châssis « {chassis.id} » bonus {key}"
        if key not in BONUS_KEYS:
            raise ChassisError("table_invalid", f"{where} : constante non permise (permises : {', '.join(BONUS_KEYS)})")
        if isinstance(delta, bool) or not isinstance(delta, (int, float)) or delta < 0:
            raise ChassisError("table_invalid", f"{where} : nombre positif attendu")
        ref = getattr(base, key)
        if ref == 0:
            if key != "adrenaline_start" or delta > START_ADRENALINE_MAX:
                raise ChassisError("table_invalid", f"{where} : au plus {START_ADRENALINE_MAX:g}")
        elif delta > MAX_RELATIVE_BONUS * ref + 1e-9:
            raise ChassisError("table_invalid", f"{where} : {delta:g} dépasse 10 % de {ref:g}")


def apply_chassis(balance: RogueBalance, chassis: Chassis) -> RogueBalance:
    """Table de valeurs de la run : `balance` plus les bonus du châssis."""
    check_bounds(chassis, balance)
    changes: dict[str, Any] = {}
    for key, delta in chassis.bonus.items():
        value = getattr(balance, key) + delta
        changes[key] = round(value, 6)
    return replace(balance, **changes)


# --- journal et statistiques -----------------------------------------------------------------

def run_event(summary: dict, minutes: float, lives_used: int = 0, chassis: str = DEFAULT_CHASSIS) -> dict:
    """Ligne `rogue_run` du journal : celle que lisent l'expérience, les pièces (V2, V3b) et ces statistiques."""
    return {"kind": "rogue_run", "minutes": round(float(minutes), 2),
            "bosses": [BOSS_ID] if summary["boss"] == "won" else [],
            "objective": summary["objective"], "duration_min": summary["duration_min"],
            "result": summary["result"], "rooms_won": summary["rooms_won"],
            "rooms_total": summary["rooms_total"], "defeats": summary["defeats"],
            "gold": summary["gold"], "perfect_shifts": summary["perfect_shifts"],
            "cards": list(summary["cards"]), "lives_used": lives_used, "chassis": chassis}


@dataclass
class Bucket:
    """Statistiques d'un objectif et d'une durée."""
    runs: int = 0
    finished: int = 0
    abandoned: int = 0
    rooms_won: int = 0
    bosses_won: int = 0
    best_gold: int = 0
    perfect_shifts: int = 0


@dataclass
class RogueStats:
    buckets: dict = field(default_factory=dict)          # "objectif/durée" -> Bucket
    cards: Counter = field(default_factory=Counter)
    gold_total: int = 0
    lives_used: int = 0
    last: dict | None = None             # objectif, durée et châssis de la dernière run (menu de départ, lot R13)

    def add(self, ev: dict) -> None:
        """Ajoute une ligne `rogue_run` ; les lignes sans objectif (anciennes) comptent pour l'expérience seule.

        Les lignes arrivent dans l'ordre des séances : la dernière ajoutée donne `last`.
        """
        if not ev.get("objective"):
            return
        self.last = {"objective": ev["objective"], "duration_min": ev.get("duration_min"),
                     "chassis": ev.get("chassis") or DEFAULT_CHASSIS}
        b = self.buckets.setdefault(f"{ev['objective']}/{ev.get('duration_min')}", Bucket())
        b.runs += 1
        b.finished += 1 if ev.get("result") in FINISHED else 0
        b.abandoned += 1 if ev.get("result") == "abandoned" else 0
        b.rooms_won += int(ev.get("rooms_won") or 0)
        b.bosses_won += len(ev.get("bosses") or [])
        b.best_gold = max(b.best_gold, int(ev.get("gold") or 0))
        b.perfect_shifts += int(ev.get("perfect_shifts") or 0)
        self.cards.update(c for c in ev.get("cards") or [] if isinstance(c, str))
        self.gold_total += int(ev.get("gold") or 0)
        self.lives_used += int(ev.get("lives_used") or 0)

    def total(self, key: str) -> int:
        return sum(getattr(b, key) for b in self.buckets.values())

    def finished_runs(self, objective: str) -> int:
        return sum(b.finished for k, b in self.buckets.items() if k.split("/")[0] == objective)

    def unlock_value(self, unlock: str) -> float:
        return {"none": 0.0, "boss_won": self.total("bosses_won"), "perfect_shifts": self.total("perfect_shifts"),
                "gold_total": self.gold_total, "vo2max_runs": self.finished_runs("vo2max"),
                "endurance_runs": self.finished_runs("endurance")}[unlock]

    @property
    def top_card(self) -> str | None:
        return min(self.cards.items(), key=lambda kv: (-kv[1], kv[0]))[0] if self.cards else None

    def to_dict(self) -> dict:
        return {"buckets": {k: {f.name: getattr(b, f.name) for f in fields(b)} for k, b in sorted(self.buckets.items())},
                "cards": dict(sorted(self.cards.items())), "top_card": self.top_card,
                "gold_total": self.gold_total, "lives_used": self.lives_used, "last": self.last}


def stats_from_events(events: list) -> RogueStats:
    stats = RogueStats()
    for ev in events:
        if ev.get("kind") == "rogue_run":
            stats.add(ev)
    return stats


def rogue_stats(progress: Progress) -> RogueStats:
    """Statistiques recalculées depuis les séances comptées par `progression.recompute`."""
    events = [ev for r in progress.counted for ev in r.facts.events]
    return stats_from_events(events)


# --- déblocages et choix ---------------------------------------------------------------------

def unlocked(chassis: tuple[Chassis, ...], stats: RogueStats) -> list[str]:
    return [c.id for c in chassis if stats.unlock_value(c.unlock) >= c.threshold]


def choose_chassis(chassis: tuple[Chassis, ...], stats: RogueStats, chassis_id: str | None) -> Chassis:
    """Châssis demandé par `start_run` (`None` : le standard) ; `ChassisError` `run_invalid` ou `item_locked`."""
    wanted = chassis_id or DEFAULT_CHASSIS
    for c in chassis:
        if c.id == wanted:
            if wanted not in unlocked(chassis, stats):
                raise ChassisError("item_locked", f"châssis « {c.name} » non débloqué ({c.text})")
            return c
    raise ChassisError("run_invalid", f"châssis inconnu : {wanted!r}")


def config_block(chassis: tuple[Chassis, ...], stats: RogueStats, lives: int) -> dict:
    """Champs `chassis`, `lives` (contrat 1.4) et `last` (révision 1.5) de `hello_ack.config.rogue`.

    Le châssis choisi par défaut est celui de la dernière run s'il est toujours débloqué, sinon le standard ;
    `last` (objectif et durée de la dernière run, `null` avant la première) remplit le menu de départ et dit
    à l'engine que l'avertissement du premier lancement a déjà été accepté.
    """
    open_ids = unlocked(chassis, stats)
    last = stats.last
    selected = last["chassis"] if last and last["chassis"] in open_ids else DEFAULT_CHASSIS
    return {"chassis": {"unlocked": open_ids, "selected": selected}, "lives": lives,
            "last": {"objective": last["objective"], "duration_min": last["duration_min"]} if last else None}
