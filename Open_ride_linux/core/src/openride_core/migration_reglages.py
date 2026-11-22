"""Réglages retirés du menu (lot NI2, audit des éléments inutiles du 21 novembre 2026) : migration des fichiers.

Un réglage retiré du menu ne doit plus agir en silence avec une valeur choisie avant son retrait : au lancement,
sa ligne est mise en commentaire dans `~/OpenRide/config.toml` et dans le `profil.toml` de chaque profil, après
une copie `<fichier>.bak`, et la valeur par défaut de `config.py` reprend. Le reste du fichier (commentaires,
autres clés) est gardé. Une ligne déjà en commentaire n'est plus lue : la migration se fait une fois, sans
marque à part, et une clé remise à la main est de nouveau commentée au lancement suivant.

`RETIRED` : (section, clé, raison écrite dans le commentaire). La clé reste connue de `config.py` (bancs et
arguments du lanceur), seule la valeur des fichiers du joueur est retirée.
"""

from __future__ import annotations

import os
import shutil
from datetime import date
from pathlib import Path

from . import config as config_mod
from .config_repair import key_lines

RETIRED: tuple[tuple[str, str, str], ...] = (
    # R5 : « Textures du décor » ; « auto » suit la Qualité graphique (basses et moyennes avaient la même taille)
    ("render", "texture_level", "réglage retiré du menu (lot NI2), suit la Qualité graphique"),
)


def files(home: Path | None = None) -> list[Path]:
    """Fichiers de réglages du joueur : `config.toml` puis le `profil.toml` de chaque profil."""
    base = home or config_mod.OPENRIDE_HOME
    out = [base / "config.toml"]
    profils = base / "Profils"
    if profils.is_dir():
        out += sorted(p / "profil.toml" for p in profils.iterdir() if p.is_dir() and not p.name.startswith("."))
    return [p for p in out if p.is_file()]


def migrate_file(path: Path, today: date | None = None) -> list[str]:
    """Met en commentaire les clés retirées de `path` (copie `.bak` si quelque chose change) ; renvoie les
    clés retirées (« section.clé »)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    lines = text.splitlines()
    stamp = (today or date.today()).strftime("%d/%m/%Y")
    done: list[str] = []
    for section, key, why in RETIRED:
        found = key_lines(text, section, key)
        for i in found:
            lines[i] = f"# {lines[i].strip()}   # {why}, le {stamp}"
        if found:
            done.append(f"{section}.{key}")
    if done:
        shutil.copy2(path, path.with_name(path.name + ".bak"))
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    return done


def migrate(home: Path | None = None, today: date | None = None) -> list[str]:
    """Migration de tous les fichiers ; renvoie une ligne par fichier changé (journal du lanceur)."""
    out = []
    for path in files(home):
        keys = migrate_file(path, today)
        if keys:
            out.append(f"{path} : {', '.join(keys)} retiré du menu, valeur par défaut reprise (copie {path.name}.bak)")
    return out
