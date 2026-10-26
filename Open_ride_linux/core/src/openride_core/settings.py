"""Réglages proposés au menu (lot O3) : liste fermée, lecture, pas au Click, écriture.

Le menu « Réglages » (lot O4) et `openride-core settings` ne changent que les clés de
`SETTINGS`. Les bornes et les choix viennent de `config.py` (`BOUNDS`, `CHOICES`) au moment de
la lecture, jamais recopiés ici ; les thèmes proposés sont `default` puis les dossiers de
`~/OpenRide/Themes/` qui contiennent un `theme.json`, dans l'ordre de `openride-compiler
theme-list` (lot N10). L'écriture passe par `config_writer.py` (fichier gardé tel quel,
`config.toml.bak`, validation avant d'écrire).

Forme d'un réglage (`current`, `settings --json`), stable :

    {"key": "rider.ftp_w", "label": "FTP", "type": "number", "unit": "W",
     "value": 250, "min": 50, "max": 600, "step": 5, "applies": "next_session"}

- `type` : `number` (valeur entre `min` et `max`, pas `step`), `slider` (comme `number`, affiché
  en curseur ; difficulté du trainer, 0 à 100 % par pas de 10) ou `choice` (`choices` : liste
  des valeurs permises, parcourue en boucle ; pas de `min`, `max` ni `step`) ;
- `value` : entier quand la valeur est entière, sinon nombre décimal ; texte pour `choice` ;
- `applies` : `now` (pris en compte tout de suite : thème et qualité du décor du menu) ou
  `next_session` (à la prochaine séance).

`settings --json` écrit `{"config": CHEMIN, "settings": [réglage, …]}` dans l'ordre de `SETTINGS`.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config as config_mod
from . import config_writer

THEMES_DIR = config_mod.OPENRIDE_HOME / "Themes"
APPLIES = ("now", "next_session")


class SettingError(Exception):
    """Réglage inconnu ou valeur refusée ; message lisible qui cite la clé."""


@dataclass(frozen=True)
class Setting:
    key: str          # « section.clé » de config.toml
    label: str        # libellé français du menu
    type: str         # "number", "slider" ou "choice"
    applies: str      # "now" ou "next_session"
    step: float = 0   # pas d'un appui au Click (number, slider)
    unit: str = ""

    @property
    def section_key(self) -> tuple[str, str]:
        section, key = self.key.split(".", 1)
        return section, key

    @property
    def is_int(self) -> bool:
        """Valeur entière dans config.py (braquet) : jamais écrite avec décimale."""
        section, key = self.section_key
        default = getattr(getattr(config_mod.Config(), section), key)
        return isinstance(default, int) and not isinstance(default, bool)


SETTINGS: tuple[Setting, ...] = (
    Setting("rider.ftp_w", "FTP", "number", "next_session", step=5, unit="W"),
    Setting("rider.mass_kg", "Masse du cycliste", "number", "next_session", step=1, unit="kg"),
    Setting("trainer.difficulty_pct", "Difficulté du trainer", "slider", "next_session", step=10, unit="%"),
    Setting("gearing.start_gear", "Braquet de départ", "number", "next_session", step=1),
    Setting("render.quality", "Qualité graphique", "choice", "now"),
    Setting("render.theme", "Thème", "choice", "now"),
)
BY_KEY = {s.key: s for s in SETTINGS}


def get(key: str) -> Setting:
    try:
        return BY_KEY[key]
    except KeyError:
        raise SettingError(f"réglage inconnu {key!r} (réglages possibles : {', '.join(BY_KEY)})") from None


def available_themes(themes_dir: Path | None = None) -> list[str]:
    """`default`, puis les thèmes installés (dossiers avec `theme.json`), triés comme `theme-list`."""
    d = THEMES_DIR if themes_dir is None else themes_dir
    names = ["default"]
    if d.is_dir():
        names += sorted(p.name for p in d.iterdir()
                        if p.is_dir() and not p.name.startswith(".") and p.name != "default"
                        and (p / "theme.json").is_file())
    return names


def bounds(setting: Setting, cfg: config_mod.Config | None = None) -> tuple[float, float]:
    """Bornes lues dans `config.BOUNDS` ; le braquet de départ est aussi borné par `n_gears`."""
    lo, hi = config_mod.BOUNDS[setting.section_key]
    if setting.key == "gearing.start_gear" and cfg is not None:
        hi = min(hi, cfg.gearing.n_gears)
    return lo, hi


def choices(setting: Setting, themes_dir: Path | None = None) -> list[str]:
    if setting.key == "render.theme":
        return available_themes(themes_dir)
    return list(config_mod.CHOICES[setting.section_key])


def _number(value: float) -> int | float:
    return int(value) if float(value).is_integer() else float(value)


def current(cfg: config_mod.Config, themes_dir: Path | None = None) -> list[dict[str, Any]]:
    """Valeur actuelle de chaque réglage, dans l'ordre de `SETTINGS`, prête pour l'IPC (lot O4)."""
    out: list[dict[str, Any]] = []
    for s in SETTINGS:
        section, key = s.section_key
        value = getattr(getattr(cfg, section), key)
        item: dict[str, Any] = {"key": s.key, "label": s.label, "type": s.type, "unit": s.unit}
        if s.type == "choice":
            item.update(value=value, choices=choices(s, themes_dir))
        else:
            lo, hi = bounds(s, cfg)
            item.update(value=_number(value), min=_number(lo), max=_number(hi), step=_number(s.step))
        item["applies"] = s.applies
        out.append(item)
    return out


def step(key: str, value: Any, direction: int, cfg: config_mod.Config | None = None,
         themes_dir: Path | None = None) -> Any:
    """Valeur suivante (`direction` > 0) ou précédente : bornée pour un nombre, en boucle pour un choix."""
    s = get(key)
    d = (direction > 0) - (direction < 0)
    if s.type == "choice":
        options = choices(s, themes_dir)
        i = options.index(value) if value in options else -d   # valeur inconnue : premier ou dernier
        return options[(i + d) % len(options)]
    lo, hi = bounds(s, cfg)
    return _number(min(hi, max(lo, float(value) + d * s.step)))


def parse_value(key: str, text: str) -> Any:
    """Valeur donnée en ligne de commande, convertie dans le type du réglage."""
    s = get(key)
    if s.type == "choice":
        return text
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        raise SettingError(f"{key} : nombre attendu, reçu {text!r}") from None
    if s.is_int:
        if not number.is_integer():
            raise SettingError(f"{key} : entier attendu, reçu {text!r}")
        return int(number)
    return number


def apply(changes: dict[str, Any], path: Path | None = None, themes_dir: Path | None = None) -> list[str]:
    """Valide puis écrit les réglages (`{"rider.ftp_w": 265}`) ; renvoie les lignes changées.

    Lève `SettingError` (clé hors de `SETTINGS`, thème absent, valeur hors bornes) : rien n'est écrit.
    """
    writes: dict[tuple[str, str], object] = {}
    for key, value in changes.items():
        s = get(key)
        if s.key == "render.theme" and value not in (options := available_themes(themes_dir)):
            raise SettingError(f"{key} : thème {value!r} non installé (thèmes : {', '.join(options)})")
        if s.type != "choice" and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise SettingError(f"{key} : nombre attendu, reçu {value!r}")
        writes[s.section_key] = value
    try:
        return config_writer.update_config(writes, path)
    except config_writer.ConfigWriteError as exc:
        raise SettingError(str(exc)) from None


# --- ligne de commande : openride-core settings [--json] | settings set CLÉ VALEUR -------------------

def _format(item: dict[str, Any]) -> str:
    value = f"{item['value']} {item['unit']}".strip()
    if item["type"] == "choice":
        extra = "choix : " + ", ".join(item["choices"])
    else:
        extra = f"{item['min']} à {item['max']}, pas {item['step']}"
    when = "immédiatement" if item["applies"] == "now" else "à la prochaine séance"
    return f"{item['label']:<24} {value:<10} {item['key']:<24} ({extra} ; {when})"


def run(action: str | None, key: str | None, value: str | None, as_json: bool,
        config_path: Path | None) -> int:
    path = config_path or config_mod.DEFAULT_CONFIG_PATH
    if action == "set":
        try:
            if key is None or value is None:
                raise SettingError("usage : openride-core settings set CLÉ VALEUR")
            changed = apply({key: parse_value(key, value)}, path)
        except SettingError as exc:
            print(f"openride-core settings : {exc}", file=sys.stderr)
            return 1
        print(f"{path} : " + ("; ".join(changed) if changed else "inchangé"))
        return 0
    try:
        cfg = config_mod.load(path)
    except config_mod.ConfigError as exc:
        print(f"openride-core settings : {exc}", file=sys.stderr)
        return 1
    items = current(cfg)
    if as_json:
        print(json.dumps({"config": str(path), "settings": items}, ensure_ascii=False, indent=2))
    else:
        print(f"Réglages ({path}) :")
        for item in items:
            print("  " + _format(item))
    return 0
