"""Pièces de la série V (lot V3b) : gains, état des pièces d'équipement, achats et vies.

Le solde n'est jamais stocké : pièces gagnées d'après les journaux (mêmes séances que
l'expérience, `progression.recompute`) moins pièces dépensées d'après le profil (`profile.py`).
Effacer le profil rend donc les pièces dépensées (aucune perte pour le cycliste).

Gains à l'effort (V-Q10, 27 octobre) : chaque minute rapporte selon la puissance en % de la
FTP (zones de `[coins] effort`), en SIM comme en ERG ; la distance ne compte pas. FTP de la
séance si l'en-tête du journal la donne, sinon celle de `config.toml`.

États d'une pièce : `equipped` (choisie), `owned` (par défaut, achetée ou offerte par un défi
réussi), `buyable` (niveau atteint, achetable), `locked` (niveau non atteint, ou pièce offerte
par un défi seulement et défi non réussi).

Primes de records (27 octobre) : record personnel sur un segment (`pr` des passages de la
série T) et record de puissance moyenne sur 5 s, 1, 5 ou 20 min battu (séances précédentes).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .equipment import Catalogue, Item
from .profile import Profile, ProfileError, record_life_purchase, record_purchase
from .profile import use_life as _profile_use_life
from .progression import POWER_STEP_W, Progress, SessionFacts, Table

_COIN_KEYS = {"effort": list, "per_segment": float, "per_segment_pr": float, "per_power_record": float,
              "per_jersey": float,
              "rogue_boss_default": float, "life_price": int, "rogue_boss": dict}


class CoinsError(Exception):
    """Achat refusé ; `code` reprend les codes d'erreur du contrat (lot V1)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CoinTable:
    effort: tuple[tuple[float, float], ...]   # (seuil en % de la FTP, pièces par minute), croissant
    per_segment: float
    per_segment_pr: float
    per_power_record: float
    per_jersey: float
    rogue_boss_default: float
    life_price: int
    rogue_boss: dict[str, float]
    ftp_w: float = 250.0


def _number(value: Any, where: str, integer: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise CoinsError("table_invalid", f"{where} : nombre positif attendu")
    if integer and int(value) != value:
        raise CoinsError("table_invalid", f"{where} : entier attendu")
    return int(value) if integer else float(value)


def _effort(raw: Any) -> tuple[tuple[float, float], ...]:
    where = "[coins] effort"
    if not isinstance(raw, list) or not raw:
        raise CoinsError("table_invalid", f"{where} : liste de [seuil %FTP, pièces/min] attendue")
    zones = []
    for i, zone in enumerate(raw):
        if not isinstance(zone, list) or len(zone) != 2:
            raise CoinsError("table_invalid", f"{where} : zone {i + 1}, [seuil %FTP, pièces/min] attendu")
        zones.append((_number(zone[0], f"{where} zone {i + 1}"), _number(zone[1], f"{where} zone {i + 1}")))
    if zones[0][0] != 0 or any(b[0] <= a[0] for a, b in zip(zones, zones[1:])):
        raise CoinsError("table_invalid", f"{where} : seuils croissants, le premier à 0")
    return tuple(zones)


def coin_table(table: Table, ftp_w: float = 250.0) -> CoinTable:
    """Section `[coins]` des tables, vérifiée ; lève `CoinsError` (code `table_invalid`).

    `ftp_w` : FTP de `config.toml`, pour les séances dont l'en-tête ne donne pas la sienne.
    """
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
        effort=_effort(raw["effort"]),
        per_segment=_number(raw["per_segment"], "[coins] per_segment"),
        per_segment_pr=_number(raw["per_segment_pr"], "[coins] per_segment_pr"),
        per_power_record=_number(raw["per_power_record"], "[coins] per_power_record"),
        per_jersey=_number(raw["per_jersey"], "[coins] per_jersey"),
        rogue_boss_default=_number(raw["rogue_boss_default"], "[coins] rogue_boss_default"),
        life_price=int(_number(raw["life_price"], "[coins] life_price", integer=True)),
        rogue_boss={k: _number(v, f"[coins.rogue_boss] {k}") for k, v in bosses.items()},
        ftp_w=float(ftp_w),
    )


# --- gains et solde ------------------------------------------------------------------------

def effort_rate(pct_ftp: float, ct: CoinTable) -> float:
    """Pièces par minute à `pct_ftp` % de la FTP (zone dont le seuil est atteint)."""
    rate = ct.effort[0][1]
    for threshold, per_min in ct.effort:
        if pct_ftp >= threshold:
            rate = per_min
    return rate


def effort_coins(facts: SessionFacts, ct: CoinTable) -> float:
    """Pièces de l'effort : minutes passées dans chaque zone de puissance, sans arrondi."""
    ftp = facts.ftp_w or ct.ftp_w
    total = 0.0
    for step, seconds in facts.power_s.items():
        pct = (step + POWER_STEP_W / 2) / ftp * 100.0   # milieu du pas de 10 W
        total += effort_rate(pct, ct) * seconds / 60.0
    return total


def power_records(progress: Progress) -> dict[str, list[int]]:
    """Records de puissance battus, par journal : durées (s) dont la séance bat le meilleur
    des séances comptées précédentes. La première valeur connue d'une durée n'est pas un
    record (rien à battre)."""
    best: dict[int, float] = {}
    out: dict[str, list[int]] = {}
    for r in progress.counted:          # ordre chronologique de `recompute`
        beaten = []
        for d, watts in sorted(r.facts.best_power.items()):
            if d in best and watts > best[d]:
                beaten.append(d)
            best[d] = max(best.get(d, 0.0), watts)
        out[r.facts.journal] = beaten
    return out


def coins_by_session(progress: Progress, ct: CoinTable) -> dict[str, int]:
    """Pièces de chaque séance comptée, primes de records de puissance comprises."""
    records = power_records(progress)
    return {r.facts.journal: session_coins(r.facts, ct, len(records.get(r.facts.journal, ())))
            for r in progress.counted}


def session_coins(facts: SessionFacts, ct: CoinTable, records: int = 0) -> int:
    """Pièces d'une séance (sans contrôle d'éligibilité), arrondies à l'entier inférieur ;
    `records` : nombre de records de puissance battus (voir `power_records`)."""
    total = effort_coins(facts, ct) + ct.per_power_record * records
    for ev in facts.events:
        kind = ev.get("kind")
        if kind == "segment":
            total += ct.per_segment + (ct.per_segment_pr if ev.get("pr") else 0.0)
        elif kind == "jersey":
            total += ct.per_jersey
        elif kind == "rogue_run":
            for boss in ev.get("bosses") or []:
                total += ct.rogue_boss.get(boss, ct.rogue_boss_default)
    return int(math.floor(total + 1e-9))


def earned_coins(progress: Progress, ct: CoinTable) -> int:
    """Pièces gagnées sur toutes les séances comptées par `progression.recompute`."""
    return sum(coins_by_session(progress, ct).values())


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
