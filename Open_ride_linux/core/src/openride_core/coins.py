"""Pièces de la série V (lot V3b) : gains, état des pièces d'équipement, achats et vies.

Le solde n'est jamais stocké : pièces gagnées d'après les journaux (mêmes séances que
l'expérience, `progression.recompute`) moins pièces dépensées d'après le profil (`profile.py`).
Effacer le profil rend donc les pièces dépensées (aucune perte pour le cycliste).

États d'une pièce : `equipped` (choisie), `owned` (par défaut, achetée ou offerte par un défi
réussi), `buyable` (niveau atteint, achetable), `locked` (niveau non atteint, ou pièce offerte
par un défi seulement et défi non réussi).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .equipment import Catalogue, Item
from .profile import Profile, ProfileError, record_life_purchase, record_purchase
from .profile import use_life as _profile_use_life
from .progression import Progress, SessionFacts, Table

_COIN_KEYS = {"per_km": float, "per_erg_min": float, "per_segment": float, "per_jersey": float,
              "rogue_boss_default": float, "life_price": int, "rogue_boss": dict}


class CoinsError(Exception):
    """Achat refusé ; `code` reprend les codes d'erreur du contrat (lot V1)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CoinTable:
    per_km: float
    per_erg_min: float
    per_segment: float
    per_jersey: float
    rogue_boss_default: float
    life_price: int
    rogue_boss: dict[str, float]
    erg_replaces_distance: bool


def _number(value: Any, where: str, integer: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise CoinsError("table_invalid", f"{where} : nombre positif attendu")
    if integer and int(value) != value:
        raise CoinsError("table_invalid", f"{where} : entier attendu")
    return int(value) if integer else float(value)


def coin_table(table: Table) -> CoinTable:
    """Section `[coins]` des tables, vérifiée ; lève `CoinsError` (code `table_invalid`)."""
    raw = table.data.get("coins")
    if not isinstance(raw, dict):
        raise CoinsError("table_invalid", "section [coins] absente ou mal formée")
    for key in raw:
        if key not in _COIN_KEYS:
            raise CoinsError("table_invalid", f"[coins] {key} : clé inconnue")
    for key in _COIN_KEYS:
        if key not in raw and key != "rogue_boss":
            raise CoinsError("table_invalid", f"[coins] {key} : clé manquante")
    bosses = raw.get("rogue_boss", {})
    if not isinstance(bosses, dict):
        raise CoinsError("table_invalid", "[coins.rogue_boss] : table attendue")
    return CoinTable(
        per_km=_number(raw["per_km"], "[coins] per_km"),
        per_erg_min=_number(raw["per_erg_min"], "[coins] per_erg_min"),
        per_segment=_number(raw["per_segment"], "[coins] per_segment"),
        per_jersey=_number(raw["per_jersey"], "[coins] per_jersey"),
        rogue_boss_default=_number(raw["rogue_boss_default"], "[coins] rogue_boss_default"),
        life_price=int(_number(raw["life_price"], "[coins] life_price", integer=True)),
        rogue_boss={k: _number(v, f"[coins.rogue_boss] {k}") for k, v in bosses.items()},
        erg_replaces_distance=bool(table.rule("erg_replaces_distance")),
    )


# --- gains et solde ------------------------------------------------------------------------

def session_coins(facts: SessionFacts, ct: CoinTable) -> int:
    """Pièces d'une séance (sans contrôle d'éligibilité), arrondies à l'entier inférieur."""
    total = 0.0
    erg = facts.erg_s > 0
    if not (erg and ct.erg_replaces_distance):
        total += ct.per_km * facts.distance_m / 1000.0
    if erg:
        total += ct.per_erg_min * facts.erg_s / 60.0
    for ev in facts.events:
        kind = ev.get("kind")
        if kind == "segment":
            total += ct.per_segment
        elif kind == "jersey":
            total += ct.per_jersey
        elif kind == "rogue_run":
            for boss in ev.get("bosses") or []:
                total += ct.rogue_boss.get(boss, ct.rogue_boss_default)
    return int(math.floor(total + 1e-9))


def earned_coins(progress: Progress, ct: CoinTable) -> int:
    """Pièces gagnées sur toutes les séances comptées par `progression.recompute`."""
    return sum(session_coins(r.facts, ct) for r in progress.counted)


def raw_balance(progress: Progress, profile: Profile, ct: CoinTable) -> int:
    """Gagnées − dépensées ; peut être négatif si le fichier de données a baissé les gains."""
    return earned_coins(progress, ct) - profile.spent


def balance(progress: Progress, profile: Profile, ct: CoinTable) -> int:
    """Solde affiché : jamais négatif (un solde négatif bloque les achats sans rien retirer)."""
    return max(raw_balance(progress, profile, ct), 0)


# --- état des pièces ------------------------------------------------------------------------

def challenge_rewards(progress: Progress) -> set[str]:
    return {c.reward for c in progress.challenges if c.reward}


def owned_items(progress: Progress, profile: Profile, catalogue: Catalogue) -> set[str]:
    """Pièces possédées : par défaut, achetées, offertes par un défi réussi (passé à `profile.equip`)."""
    owned = {i.id for i in catalogue.items.values() if i.default}
    owned |= {i for i in profile.purchased if i in catalogue}
    owned |= {i for i in challenge_rewards(progress) if i in catalogue}
    return owned


def item_state(item: Item, progress: Progress, profile: Profile, catalogue: Catalogue) -> str:
    if profile.equipped.get(item.slot) == item.id:
        return "equipped"
    if item.id in owned_items(progress, profile, catalogue):
        return "owned"
    if item.buyable and progress.level.level >= item.level:
        return "buyable"
    return "locked"


# --- achats et vies -------------------------------------------------------------------------

def buy(item_id: str, progress: Progress, profile: Profile, catalogue: Catalogue, ct: CoinTable,
        ts: float | None = None) -> int:
    """Achète une pièce et l'enregistre dans le profil (à écrire par l'appelant) ; nouveau solde.

    Refus (`CoinsError.code`) : `item_unknown`, `already_owned`, `item_locked`, `not_enough_coins`.
    """
    if item_id not in catalogue:
        raise CoinsError("item_unknown", f"pièce inconnue : {item_id!r}")
    item = catalogue[item_id]
    if item.id in owned_items(progress, profile, catalogue):
        raise CoinsError("already_owned", f"« {item.name} » est déjà possédée")
    if not item.buyable:
        raise CoinsError("item_locked", f"« {item.name} » s'obtient par un défi")
    if progress.level.level < item.level:
        raise CoinsError("item_locked", f"« {item.name} » demande le niveau {item.level}")
    solde = raw_balance(progress, profile, ct)
    if solde < item.price:
        raise CoinsError("not_enough_coins", f"« {item.name} » coûte {item.price} pièces, solde {max(solde, 0)}")
    record_purchase(profile, item.id, item.price, ts)
    return solde - item.price


def buy_life(progress: Progress, profile: Profile, ct: CoinTable) -> int:
    """Achète une vie du mode Cyber-Rogue (lot R9 décide quand elle sert) ; nouveau solde."""
    solde = raw_balance(progress, profile, ct)
    if solde < ct.life_price:
        raise CoinsError("not_enough_coins", f"une vie coûte {ct.life_price} pièces, solde {max(solde, 0)}")
    record_life_purchase(profile, ct.life_price)
    return solde - ct.life_price


def use_life(profile: Profile) -> None:
    """Utilise une vie en réserve ; `CoinsError` (`no_life`) s'il n'y en a pas."""
    try:
        _profile_use_life(profile)
    except ProfileError as exc:
        raise CoinsError("no_life", str(exc)) from None
