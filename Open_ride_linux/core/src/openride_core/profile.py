"""Profil local de la série V (lot V4) : équipement choisi, achats, vies et avatar.

`~/OpenRide/profile.json` ne garde que ce qui ne se recalcule pas depuis le journal ;
l'expérience, le niveau, les défis et les pièces gagnées viennent de `progression.py` (V2) et
`coins.py` (V3b). Aucune donnée personnelle : ni nom, ni masse, ni taille réelle.

- Lecture tolérante : fichier absent → profil par défaut (rien n'est écrit) ; fichier abîmé →
  copie `profile.json.bak`, sinon défauts, et le fichier abîmé est gardé sous
  `profile.json.corrompu-AAAAMMJJ-HHMMSS`.
- Écriture sûre : fichier temporaire du même dossier, `fsync`, ancien fichier copié en `.bak`,
  puis `os.replace` (jamais de fichier à moitié écrit).
- Migration : sans `version` → version 1 ; version plus récente que le code → lecture seule
  (`ProfileTooNew` à l'écriture), pour ne pas effacer les données d'une version future.

Bornes de l'avatar : celles du contrat (lot V1 §4.4), choisies dans des listes et des
palettes pour se régler au Click.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import OPENRIDE_HOME

log = logging.getLogger(__name__)

PROFILE_PATH = OPENRIDE_HOME / "profile.json"
PROFILE_VERSION = 1

SLOTS = ("frame", "wheels", "helmet", "kit", "socks", "glasses")
DEFAULT_EQUIPPED = {
    "frame": "frame_allround", "wheels": "wheels_standard", "helmet": "helmet_route",
    "kit": "kit_uni", "socks": "socks_blanches", "glasses": "glasses_claires",
}

# Champ -> valeurs permises (liste fermée, ou intervalle entier [min, max]).
AVATAR_CHOICES: dict[str, tuple] = {
    "height": ("S", "M", "L", "XL"),
    "build": ("slim", "medium", "strong"),
}
AVATAR_RANGES: dict[str, tuple[int, int]] = {
    "skin": (0, 7), "hair": (0, 5), "hair_color": (0, 7),
    "kit_primary": (0, 15), "kit_secondary": (0, 15), "number": (0, 999),
}
DEFAULT_AVATAR: dict[str, Any] = {
    "height": "M", "build": "medium", "skin": 2, "hair": 1, "hair_color": 3,
    "kit_primary": 4, "kit_secondary": 0, "number": 1,
}


class ProfileError(Exception):
    """Choix refusé (pièce non possédée, réglage hors bornes, vie absente…)."""


class ProfileTooNew(ProfileError):
    """Profil écrit par une version plus récente d'OpenRide : lecture seule."""


@dataclass
class Profile:
    equipped: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_EQUIPPED))
    purchases: list[dict] = field(default_factory=list)   # {item_id, price, ts}
    lives: dict[str, int] = field(default_factory=lambda: {"bought": 0, "used": 0, "spent": 0})
    avatar: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_AVATAR))
    version: int = PROFILE_VERSION
    read_only: bool = False      # écrit par une version plus récente

    def to_dict(self) -> dict:
        return {"version": PROFILE_VERSION, "equipped": dict(self.equipped),
                "purchases": copy.deepcopy(self.purchases), "lives": dict(self.lives),
                "avatar": dict(self.avatar)}

    @property
    def purchased(self) -> set[str]:
        return {p["item_id"] for p in self.purchases}

    @property
    def spent(self) -> int:
        """Pièces dépensées : équipement et vies (lot V3b)."""
        return sum(int(p.get("price", 0)) for p in self.purchases) + int(self.lives.get("spent", 0))

    @property
    def lives_left(self) -> int:
        return int(self.lives.get("bought", 0)) - int(self.lives.get("used", 0))


# --- validation ---------------------------------------------------------------------------

def check_avatar(avatar: Any) -> dict[str, Any]:
    """Réglages complets et valides, sinon `ProfileError` au premier champ fautif."""
    if not isinstance(avatar, dict):
        raise ProfileError("avatar : objet attendu")
    for key in avatar:
        if key not in AVATAR_CHOICES and key not in AVATAR_RANGES:
            raise ProfileError(f"avatar.{key} : réglage inconnu")
    out = dict(DEFAULT_AVATAR)
    for key, value in avatar.items():
        if key in AVATAR_CHOICES:
            if value not in AVATAR_CHOICES[key]:
                raise ProfileError(f"avatar.{key} : {value!r} hors de {', '.join(AVATAR_CHOICES[key])}")
        else:
            lo, hi = AVATAR_RANGES[key]
            if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
                raise ProfileError(f"avatar.{key} : entier de {lo} à {hi} attendu, reçu {value!r}")
        out[key] = value
    return out


def _from_dict(data: Any, known_items: set[str] | None) -> Profile:
    """Profil depuis le JSON lu ; lève `ValueError` si la forme est fausse (fichier abîmé)."""
    if not isinstance(data, dict):
        raise ValueError("objet JSON attendu")
    version = data.get("version", 0)   # sans version : profil antérieur à la version 1
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise ValueError(f"version invalide : {version!r}")
    prof = Profile()
    if version > PROFILE_VERSION:
        prof.read_only = True
        log.warning("Profil de version %s (code : %s) : lu sans être réécrit.", version, PROFILE_VERSION)
    equipped = data.get("equipped", {})
    if not isinstance(equipped, dict):
        raise ValueError("equipped : objet attendu")
    for slot in SLOTS:
        item = equipped.get(slot)
        if isinstance(item, str) and item and (known_items is None or item in known_items):
            prof.equipped[slot] = item
        elif item is not None:
            log.warning("Profil : %s « %s » inconnu, retour à « %s ».", slot, item, DEFAULT_EQUIPPED[slot])
    purchases = data.get("purchases", [])
    if not isinstance(purchases, list):
        raise ValueError("purchases : liste attendue")
    for p in purchases:
        if not (isinstance(p, dict) and isinstance(p.get("item_id"), str)
                and isinstance(p.get("price", 0), int) and not isinstance(p.get("price", 0), bool)):
            raise ValueError(f"achat mal formé : {p!r}")
        prof.purchases.append({"item_id": p["item_id"], "price": int(p.get("price", 0)),
                               "ts": p.get("ts")})
    lives = data.get("lives", {})
    if not isinstance(lives, dict):
        raise ValueError("lives : objet attendu")
    for key in ("bought", "used", "spent"):
        value = lives.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"lives.{key} : entier positif attendu")
        prof.lives[key] = value
    if "avatar" in data:
        try:
            prof.avatar = check_avatar(data["avatar"])
        except ProfileError as exc:
            log.warning("Profil : %s ; réglages de l'avatar par défaut.", exc)
    prof.version = version
    return prof


# --- lecture et écriture ------------------------------------------------------------------

def _read(path: Path, known_items: set[str] | None) -> Profile:
    with path.open(encoding="utf-8") as fh:
        return _from_dict(json.load(fh), known_items)


def load_profile(path: Path = PROFILE_PATH, known_items: set[str] | None = None) -> Profile:
    """Profil lu, réparé si besoin ; `known_items` (catalogue, V3) remet à zéro les pièces retirées."""
    if not path.exists():
        return Profile()
    try:
        return _read(path, known_items)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        kept = path.with_name(f"{path.name}.corrompu-{stamp}")
        log.warning("Profil illisible (%s) : gardé sous %s.", exc, kept.name)
        try:
            os.replace(path, kept)
        except OSError:
            pass
    backup = path.with_name(path.name + ".bak")
    if backup.exists():
        try:
            prof = _read(backup, known_items)
            log.warning("Profil repris de %s.", backup.name)
            return prof
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            log.warning("Copie %s illisible aussi (%s) : profil par défaut.", backup.name, exc)
    return Profile()


def peek_profile(path: Path = PROFILE_PATH, known_items: set[str] | None = None) -> Profile:
    """Lecture seule, sans réparation (outils comme `openride-core xp`) : défauts si illisible."""
    for candidate in (path, path.with_name(path.name + ".bak")):
        if candidate.exists():
            try:
                return _read(candidate, known_items)
            except (OSError, ValueError, UnicodeDecodeError):
                continue
    return Profile()


def save_profile(profile: Profile, path: Path = PROFILE_PATH) -> None:
    """Écrit le profil sans risque de fichier à moitié écrit ; lève `ProfileTooNew` ou `OSError`."""
    if profile.read_only:
        raise ProfileTooNew("profil écrit par une version plus récente d'OpenRide : non modifié")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(profile.to_dict(), ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    profile.version = PROFILE_VERSION


# --- choix, achats et vies ----------------------------------------------------------------

def equip(profile: Profile, slot: str, item_id: str, owned: set[str]) -> None:
    """Choisit une pièce possédée (`owned` vient du catalogue et des achats, V3 et V3b)."""
    if slot not in SLOTS:
        raise ProfileError(f"emplacement inconnu : {slot!r}")
    if item_id not in owned:
        raise ProfileError(f"« {item_id} » n'est pas possédée")
    profile.equipped[slot] = item_id


def set_avatar(profile: Profile, avatar: dict[str, Any]) -> None:
    """Remplace les réglages de l'avatar ; rien ne change si un champ est invalide."""
    profile.avatar = check_avatar(avatar)


def record_purchase(profile: Profile, item_id: str, price: int, ts: float | None = None) -> None:
    if item_id in profile.purchased:
        raise ProfileError(f"« {item_id} » déjà achetée")
    if isinstance(price, bool) or not isinstance(price, int) or price < 0:
        raise ProfileError(f"prix invalide : {price!r}")
    profile.purchases.append({"item_id": item_id, "price": price,
                              "ts": int(ts if ts is not None else time.time())})


def record_life_purchase(profile: Profile, price: int) -> None:
    if isinstance(price, bool) or not isinstance(price, int) or price < 0:
        raise ProfileError(f"prix invalide : {price!r}")
    profile.lives["bought"] += 1
    profile.lives["spent"] += price


def use_life(profile: Profile) -> None:
    if profile.lives_left <= 0:
        raise ProfileError("aucune vie en réserve")
    profile.lives["used"] += 1
