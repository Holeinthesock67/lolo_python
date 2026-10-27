"""Réglages proposés au menu (lots O3 et O4) : liste fermée, valeurs, pas au Click, écriture.

Chaque réglage est une clé `section.clé` de `config.toml`. Les bornes et les choix viennent de
`config.py` (`BOUNDS`, `CHOICES`), jamais recopiés ici ; les thèmes proposés sont `default` et les
dossiers de `~/OpenRide/Themes/` qui contiennent un `theme.json` (lot N10).

`current(cfg)` donne la liste pour le message IPC `settings` (contrat révision 1.3) et pour
`openride-core settings --json` ; chaque élément :

    {"key": "rider.ftp_w", "label": "FTP", "type": "int", "value": 250, "min": 50, "max": 600,
     "step": 5, "unit": "W", "applies": "next_session"}

`type` vaut `int` ou `choice` (avec `choices`) ; `applies` vaut `next_session` (prise en compte à
la séance suivante, sans relancer) ou `now` (qualité et thème : l'engine les applique tout de suite
au décor ; le lanceur les passe aussi à l'engine aux lancements suivants).
`apply(cfg, changes, path)` valide, écrit dans `config.toml` (commentaires et reste du fichier
gardés, copie `.bak`) puis met à jour `cfg` en mémoire.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config as config_mod
from . import config_edit

THEMES_DIR = Path.home() / "OpenRide" / "Themes"


@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    step: float = 1
    unit: str = ""
    applies: str = "next_session"

    @property
    def section(self) -> str:
        return self.key.split(".", 1)[0]

    @property
    def name(self) -> str:
        return self.key.split(".", 1)[1]


SETTINGS: tuple[Setting, ...] = (
    Setting("rider.ftp_w", "FTP", 5, "W"),
    Setting("rider.mass_kg", "Poids", 1, "kg"),
    Setting("trainer.difficulty_pct", "Difficulté en SIM", 10, "%"),
    Setting("gearing.start_gear", "Braquet de départ", 1),
    Setting("render.quality", "Qualité graphique", applies="now"),
    Setting("render.theme", "Thème", applies="now"),
    Setting("render.chart", "Courbes de la séance", applies="now"),
    # Vent (lot P16, décisions du propriétaire du 25 octobre : coupé par défaut, plafond de 4 points)
    Setting("wind.mode", "Vent"),
    Setting("wind.speed_kmh", "Force du vent", 5, "km/h"),
    Setting("wind.max_grade_offset_pct", "Plafond du vent", 1, "pts"),
    # Bonus du mode classique (série T, lots T7 et T10)
    Setting("powerups.mode", "Bonus"),
)
KEYS = tuple(s.key for s in SETTINGS)


class SettingError(Exception):
    """Réglage inconnu ou valeur refusée ; message lisible qui cite la clé et les bornes."""


def get(key: str) -> Setting:
    for s in SETTINGS:
        if s.key == key:
            return s
    raise SettingError(f"réglage inconnu : {key} (réglages : {', '.join(KEYS)})")


def installed_themes(themes_dir: Path | None = None) -> list[str]:
    base = THEMES_DIR if themes_dir is None else themes_dir
    names = ["default"]
    if base.is_dir():
        names += sorted(d.name for d in base.iterdir()
                        if d.is_dir() and d.name != "default" and (d / "theme.json").is_file())
    return names


def choices(s: Setting, themes_dir: Path | None = None) -> list[str] | None:
    if s.key == "render.theme":
        return installed_themes(themes_dir)
    found = config_mod.CHOICES.get((s.section, s.name))
    return list(found) if found else None


def bounds(s: Setting, cfg: config_mod.Config) -> tuple[float, float] | None:
    if s.key == "gearing.start_gear":
        return (1, cfg.gearing.n_gears)
    return config_mod.BOUNDS.get((s.section, s.name))


def _value(cfg: config_mod.Config, s: Setting) -> Any:
    v = getattr(getattr(cfg, s.section), s.name)
    return int(round(v)) if isinstance(v, float) else v


def current(cfg: config_mod.Config, themes_dir: Path | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in SETTINGS:
        item: dict[str, Any] = {"key": s.key, "label": s.label, "value": _value(cfg, s), "applies": s.applies}
        ch = choices(s, themes_dir)
        if ch is not None:
            item.update(type="choice", choices=ch)
        else:
            lo, hi = bounds(s, cfg) or (0, 0)
            item.update(type="int", min=int(lo), max=int(hi), step=int(s.step), unit=s.unit)
        out.append(item)
    return out


def step(cfg: config_mod.Config, key: str, value: Any, direction: int, themes_dir: Path | None = None) -> Any:
    """Valeur suivante (direction +1) ou précédente (−1) : bornée pour un nombre, en boucle pour un choix."""
    s = get(key)
    ch = choices(s, themes_dir)
    if ch is not None:
        i = ch.index(value) if value in ch else 0
        return ch[(i + (1 if direction > 0 else -1)) % len(ch)]
    lo, hi = bounds(s, cfg) or (float("-inf"), float("inf"))
    return int(max(lo, min(hi, value + (s.step if direction > 0 else -s.step))))


def check(cfg: config_mod.Config, key: str, value: Any, themes_dir: Path | None = None) -> Any:
    """Valeur validée (entier pour un nombre) ; `SettingError` sinon."""
    s = get(key)
    ch = choices(s, themes_dir)
    if ch is not None:
        if not isinstance(value, str) or value not in ch:
            raise SettingError(f"{key} : « {value} » refusé (choix : {', '.join(ch)})")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        try:
            value = float(str(value).replace(",", "."))
        except ValueError:
            raise SettingError(f"{key} : nombre attendu, reçu « {value} »") from None
    lo, hi = bounds(s, cfg) or (float("-inf"), float("inf"))
    if not lo <= value <= hi:
        raise SettingError(f"{key} : {value:g} hors bornes ({lo:g} à {hi:g})")
    return int(round(value))


def apply(cfg: config_mod.Config, changes: dict[str, Any], path: Path | None = None,
          themes_dir: Path | None = None) -> list[str]:
    """Valide et écrit les réglages ; met `cfg` à jour ; renvoie les lignes changées."""
    clean = {k: check(cfg, k, v, themes_dir) for k, v in changes.items()}
    values = [(get(k).section, get(k).name, v) for k, v in clean.items()]
    try:
        changed = config_edit.update_config(path or config_mod.DEFAULT_CONFIG_PATH, values)
    except config_edit.ConfigEditError as exc:
        raise SettingError(str(exc)) from None
    for k, v in clean.items():
        s = get(k)
        section = getattr(cfg, s.section)
        old = getattr(section, s.name)
        setattr(section, s.name, float(v) if isinstance(old, float) else v)
    return changed


def run(as_json: bool, config_path: Path | None, set_args: list[str] | None = None) -> int:
    """`openride-core settings [--json]` et `openride-core settings set CLÉ VALEUR`."""
    try:
        cfg = config_mod.load(config_path)
    except config_mod.ConfigError as exc:
        print(f"openride-core settings : configuration invalide : {exc}")
        return 1
    if set_args:
        key, raw = set_args
        try:
            changed = apply(cfg, {key: raw}, config_path)   # texte converti en nombre par check()
        except SettingError as exc:
            print(f"openride-core settings : {exc}")
            return 1
        print("; ".join(changed) if changed else "inchangé")
        return 0
    items = current(cfg)
    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    for it in items:
        unit = f" {it['unit']}" if it.get("unit") else ""
        when = "séance suivante" if it["applies"] == "next_session" else "tout de suite"
        print(f"{it['key']:<24} {it['label']:<20} {it['value']}{unit}  ({when})")
    return 0

