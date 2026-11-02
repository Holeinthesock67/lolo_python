"""Configuration invalide réparable depuis le lanceur (lot O34), sans éditer de fichier à la main.

Une valeur refusée par `config.load` (`ConfigError` avec `section` et `key`) se remet à sa valeur par
défaut : sa ligne est mise en commentaire dans le fichier qui la contient (`config.toml` ou `profil.toml`
du profil en cours), après une copie `<fichier>.bak`. Un fichier qui n'est plus du TOML (`ConfigError`
avec `path`) repart du modèle de `config.toml`, ou vide pour un `profil.toml` (son identité `[profil]`
est gardée), l'ancien restant dans `<fichier>.bak`. Le lanceur pose la question dans une fenêtre et
recommence la lecture : plusieurs valeurs fautives se réparent l'une après l'autre.
"""

from __future__ import annotations

import os
import re
import shutil
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from .config import ConfigError

SECTION_RE = re.compile(r"^\s*\[\s*([A-Za-z0-9_.-]+)\s*\]")
KEY_RE = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=")
MAX_REPAIRS = 10   # valeurs réparées au plus par lancement (au-delà : message d'erreur habituel)


@dataclass
class Repair:
    question: str               # texte de la fenêtre, réponse oui ou non
    apply: Callable[[], str]    # répare ; renvoie ce qui a été fait (journal du lanceur)


def _backup(path: Path) -> Path:
    bak = path.with_name(path.name + ".bak")
    shutil.copy2(path, bak)
    return bak


def _write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def key_lines(text: str, section: str, key: str) -> list[int]:
    """Numéros des lignes `key = …` de la section `section` (table `[section]` du TOML)."""
    current = ""
    found = []
    for i, line in enumerate(text.splitlines()):
        m = SECTION_RE.match(line)
        if m:
            current = m.group(1)
            continue
        km = KEY_RE.match(line)
        if km and current == section and km.group(1) == key:
            found.append(i)
    return found


def reset_key(path: Path, section: str, key: str, today: date | None = None) -> bool:
    """Met en commentaire `[section] key` dans `path` (copie `.bak`) ; faux si la clé n'y est pas."""
    text = path.read_text(encoding="utf-8")
    found = key_lines(text, section, key)
    if not found:
        return False
    lines = text.splitlines()
    stamp = (today or date.today()).strftime("%d/%m/%Y")
    for i in found:
        lines[i] = f"# {lines[i].strip()}   # valeur invalide, remise par défaut le {stamp}"
    _backup(path)
    _write(path, "\n".join(lines) + "\n")
    return True


def reset_file(path: Path, template: Path | None) -> None:
    """Fichier TOML illisible : repart du modèle (`config.toml`) ou de son seul `[profil]` (`profil.toml`)."""
    _backup(path)
    if template is not None:
        text = template.read_text(encoding="utf-8") if template.is_file() else "# Configuration OpenRide\n"
    else:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        keep, inside = [], False
        for line in lines:   # identité du profil : bloc [profil] recopié tel quel
            m = SECTION_RE.match(line)
            if m:
                inside = m.group(1) == "profil"
            if inside:
                keep.append(line)
        text = "\n".join(keep) + "\n" if keep else ""
        try:
            tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            text = ""
    _write(path, text)


def _holds(path: Path | None, section: str, key: str) -> bool:
    try:
        return path is not None and path.is_file() and bool(key_lines(path.read_text(encoding="utf-8"), section, key))
    except (OSError, UnicodeDecodeError):
        return False


def proposal(exc: ConfigError, config_path: Path, profile_path: Path | None,
             template: Path | None) -> Repair | None:
    """Réparation proposée pour `exc`, ou None si la faute n'est pas localisée (message seul)."""
    if exc.path is not None and Path(exc.path).is_file():
        path = Path(exc.path)
        is_config = path == config_path
        what = "la configuration du PC" if is_config else "les réglages du profil"
        return Repair(
            question=(f"OpenRide ne peut pas lire {what} ({path.name}) :\n{exc}\n\n"
                      f"Repartir d'un fichier neuf ? L'ancien est gardé dans {path.name}.bak."),
            apply=lambda: (reset_file(path, template if is_config else None),
                           f"{path} remis à neuf (copie {path.name}.bak)")[1])
    if exc.section is None or exc.key is None:
        return None
    files = [p for p in (profile_path, config_path) if _holds(p, exc.section, exc.key)]
    if not files:
        return None
    section, key = exc.section, exc.key

    def apply() -> str:
        done = [str(p) for p in files if reset_key(p, section, key)]
        return f"[{section}] {key} remis par défaut dans {', '.join(done)} (copie .bak)"

    names = " et ".join(p.name for p in files)
    return Repair(
        question=(f"Un réglage d'OpenRide est invalide :\n{exc}\n\n"
                  f"Remettre « [{section}] {key} » à sa valeur par défaut ? "
                  f"La version actuelle de {names} est gardée dans une copie .bak."),
        apply=apply)
