"""Modification ciblée de `~/OpenRide/config.toml` (lots N12, N14 et O3).

Change quelques clés sans réécrire le fichier : commentaires, ordre, autres sections et clés
inconnues restent tels quels. Une copie `config.toml.bak` est faite avant l'écriture, le
résultat doit passer `config.validate` (sinon rien n'est écrit) et le remplacement est atomique.

`update_layers` (série MJ, lot MJ4) répartit les valeurs entre `config.toml` (la machine) et le
`profil.toml` du profil en cours (clés de `config.PROFILE_KEYS`), mêmes garanties, et valide la
configuration effective des deux fichiers. `remove_keys` (lot MJ5) retire des clés passées au
profil en laissant un commentaire qui dit où elles sont.

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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        raise ConfigEditError(f"{path} : lecture impossible : {exc}") from None


def _parse(path: Path, text: str) -> dict:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigEditError(f"{path} : écriture refusée, TOML invalide : {exc}") from None


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    tmp = path.with_name(path.name + ".tmp")   # même dossier : remplacement atomique
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def update_config(path: Path, values: list[tuple[str, str, object]]) -> list[str]:
    """Écrit les valeurs dans `path` ; renvoie les lignes changées (vide : rien à faire).

    Lève `ConfigEditError` si le fichier final ne passe pas `config.validate` : rien n'est écrit.
    """
    new, changed = plan_text(_read_text(path), values)
    if not changed:
        return []
    try:
        config_mod.from_dict(_parse(path, new), str(path))
    except config_mod.ConfigError as exc:
        raise ConfigEditError(f"écriture refusée : {exc}") from None
    _write(path, new)
    return changed


def remove_keys(path: Path, keys: list[tuple[str, str]], note: str) -> list[str]:
    """Remplace chaque ligne `clé = …` des `(section, clé)` donnés par `# clé : <note>` (copie `.bak`) ;
    renvoie les clés retirées. Le fichier final doit rester un TOML valide, sinon rien n'est écrit."""
    lines = _read_text(path).splitlines()
    wanted = set(keys)
    section = ""
    removed: list[str] = []
    for i, line in enumerate(lines):
        m = SECTION_RE.match(line)
        if m:
            section = m.group(1)
            continue
        km = re.match(r"^\s*([A-Za-z0-9_-]+)\s*=", line)
        if km and (section, km.group(1)) in wanted:
            lines[i] = f"# {km.group(1)} : {note}"
            removed.append(f"[{section}] {km.group(1)}")
    if not removed:
        return []
    new = "\n".join(lines) + "\n"
    try:
        config_mod.from_dict(_parse(path, new), str(path))
    except config_mod.ConfigError as exc:
        raise ConfigEditError(f"écriture refusée : {exc}") from None
    _write(path, new)
    return removed


_ACTIVE = config_mod._ACTIVE


def update_layers(values: list[tuple[str, str, object]], config_path: Path | None = None,
                  profile_path: object = _ACTIVE) -> list[str]:
    """Écrit chaque valeur dans son fichier : `profil.toml` du profil pour une clé joueur, sinon
    `config.toml` ; sans profil (contexte historique), tout va dans `config.toml`.

    La configuration effective des deux fichiers doit passer `config.validate`, sinon rien n'est écrit.
    """
    config_path = config_path or config_mod.DEFAULT_CONFIG_PATH
    if profile_path is _ACTIVE:
        profile_path = config_mod.active_profile_file()
    player = [v for v in values if profile_path is not None and config_mod.is_profile_key(v[0], v[1])]
    machine = [v for v in values if v not in player]
    m_new, m_changed = plan_text(_read_text(config_path), machine)
    p_new, p_changed = (plan_text(_read_text(profile_path), player) if player and profile_path is not None
                        else ("", []))
    if not m_changed and not p_changed:
        return []
    try:
        p_data = _parse(profile_path, p_new) if p_changed else (
            _parse(profile_path, _read_text(profile_path)) if profile_path is not None else {})
        config_mod.from_layers(_parse(config_path, m_new), p_data, str(config_path), str(profile_path))
    except config_mod.ConfigError as exc:
        raise ConfigEditError(f"écriture refusée : {exc}") from None
    if m_changed:
        _write(config_path, m_new)
    if p_changed:
        _write(profile_path, p_new)
    return m_changed + p_changed


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
