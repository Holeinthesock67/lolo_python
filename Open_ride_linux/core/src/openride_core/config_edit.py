"""Modification ciblée de `~/OpenRide/config.toml` (lots N12, N14 et O3).

Change quelques clés sans réécrire le fichier : commentaires, ordre, autres sections et clés
inconnues restent tels quels. Une copie `config.toml.bak` est faite avant l'écriture, le
résultat doit passer `config.validate` (sinon rien n'est écrit) et le remplacement est atomique.

En ligne de commande (utilisé par `scripts/install.sh`) :
    python -m openride_core.config_edit FICHIER SECTION CLÉ VALEUR
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tomllib
from pathlib import Path

from . import config as config_mod

SECTION_RE = re.compile(r"^\s*\[\s*([A-Za-z0-9_.-]+)\s*\]\s*(#.*)?$")
VALUE_LINE_RE = re.compile(r"""^(\s*[A-Za-z0-9_-]+\s*=\s*(?:"[^"]*"|'[^']*'|[^#]*?))\s*(#.*)?$""")


class ConfigEditError(Exception):
    """Écriture refusée (valeur invalide, fichier illisible) ; message lisible."""


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_value(value: object) -> str:
    """Valeur TOML : texte entre guillemets, booléen, entier ou nombre (réglages du lot O3)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return _toml_string(str(value))


def _set_key(lines: list[str], section: str, key: str, value: object) -> str | None:
    """Remplace ou ajoute `key = valeur` dans `[section]` ; renvoie la ligne écrite si elle change."""
    new_line = f"{key} = {_toml_value(value)}"
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*=")
    start = end = None
    for i, line in enumerate(lines):
        m = SECTION_RE.match(line)
        if m:
            if start is not None and end is None:
                end = i
            if m.group(1) == section:
                start, end = i, None
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([f"[{section}]", new_line])
        return new_line
    end = len(lines) if end is None else end
    for i in range(start + 1, end):
        if key_re.match(lines[i]):
            m = VALUE_LINE_RE.match(lines[i])
            current, comment = (m.group(1).strip(), m.group(2)) if m else (lines[i].strip(), None)
            if current == new_line:
                return None
            lines[i] = new_line + (f"   {comment}" if comment else "")   # commentaire de fin gardé
            return new_line
    insert = end
    while insert > start + 1 and not lines[insert - 1].strip():
        insert -= 1   # avant les lignes vides qui séparent de la section suivante
    lines.insert(insert, new_line)
    return new_line


def plan_text(text: str, values: list[tuple[str, str, object]]) -> tuple[str, list[str]]:
    """Texte final et lignes changées pour les `(section, clé, valeur)` donnés."""
    lines = text.splitlines()
    changed: list[str] = []
    for section, key, value in values:
        line = _set_key(lines, section, key, value)
        if line is not None:
            changed.append(f"[{section}] {line}")
    return "\n".join(lines) + "\n", changed


def update_config(path: Path, values: list[tuple[str, str, object]]) -> list[str]:
    """Écrit les valeurs dans `path` ; renvoie les lignes changées (vide : rien à faire).

    Lève `ConfigEditError` si le fichier final ne passe pas `config.validate` : rien n'est écrit.
    """
    try:
        old = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        raise ConfigEditError(f"{path} : lecture impossible : {exc}") from None
    new, changed = plan_text(old, values)
    if not changed:
        return []
    try:
        config_mod.from_dict(tomllib.loads(new), str(path))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigEditError(f"{path} : écriture refusée, TOML invalide : {exc}") from None
    except config_mod.ConfigError as exc:
        raise ConfigEditError(f"écriture refusée : {exc}") from None
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    tmp = path.with_name(path.name + ".tmp")   # même dossier : remplacement atomique
    tmp.write_text(new, encoding="utf-8")
    os.replace(tmp, path)
    return changed


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 4:
        print("usage : python -m openride_core.config_edit FICHIER SECTION CLÉ VALEUR", file=sys.stderr)
        return 2
    path, section, key, value = Path(args[0]).expanduser(), args[1], args[2], args[3]
    try:
        changed = update_config(path, [(section, key, value)])
    except ConfigEditError as exc:
        print(f"config_edit : {exc}", file=sys.stderr)
        return 1
    print(f"{path} : " + ("; ".join(changed) if changed else "inchangé"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
