"""Réglages proposés au menu (lots O3 et O4) : liste fermée, valeurs, pas au Click, écriture.

Chaque réglage est une clé `section.clé` de `config.toml`. Les bornes et les choix viennent de
`config.py` (`BOUNDS`, `CHOICES`), jamais recopiés ici ; les thèmes proposés sont `default` et les
dossiers de `~/OpenRide/Themes/` qui contiennent un `theme.json` (lot N10).

`current(cfg)` donne la liste pour le message IPC `settings` (contrat révision 1.3) et pour
`openride-core settings --json` ; chaque élément :

    {"key": "rider.ftp_w", "label": "FTP", "group": "rider", "type": "int", "value": 250, "min": 50,
     "max": 600, "step": 5, "unit": "W", "applies": "next_session"}

`group` range le réglage dans un sous-écran de « Réglages » (`GROUPS` : cycliste, séance, graphisme,
son, vent) ; l'engine donne les titres. `help` (facultatif) : légende d'un réglage dont les choix ne se
comprennent pas seuls, montrée par l'engine sur la carte de détail (option « gravel », lot U16).

`type` vaut `int` ou `choice` (avec `choices`) ; `applies` vaut `next_session` (prise en compte à
la séance suivante, sans relancer) ou `now` (qualité, niveau des textures, thème, biome, mode d'affichage, courbes,
images/s, jauge d'abri et volumes : l'engine les applique tout de suite ; le lanceur passe aussi la qualité, le
niveau des textures, le thème, le biome, le gravel et le mode d'affichage à l'engine aux lancements suivants).
`apply(cfg, changes, path)` valide, écrit chaque réglage dans son fichier (commentaires et reste du
fichier gardés, copie `.bak`) puis met à jour `cfg` en mémoire.

Portée (série MJ, lot MJ4) : `Setting.scope` vaut `profil` pour les réglages qui suivent le joueur
(`config.PROFILE_KEYS` : cycliste, séance, vent, caméra, courbes) et `machine` pour les autres
(graphisme, affichage, volumes) ; un réglage `profil` s'écrit dans le `profil.toml` du profil en
cours, ou dans `config.toml` sans profil. L'engine n'en sait rien.
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
    group: str
    step: float = 1
    unit: str = ""
    applies: str = "next_session"
    help: str = ""

    @property
    def section(self) -> str:
        return self.key.split(".", 1)[0]

    @property
    def name(self) -> str:
        return self.key.split(".", 1)[1]

    @property
    def scope(self) -> str:
        """« profil » (suit le joueur) ou « machine » ; tiré de `config.PROFILE_KEYS`."""
        return "profil" if config_mod.is_profile_key(self.section, self.name) else "machine"


SETTINGS: tuple[Setting, ...] = (
    # Cycliste
    Setting("rider.ftp_w", "FTP", "rider", 5, "W"),
    Setting("rider.mass_kg", "Poids", "rider", 1, "kg"),
    Setting("rider.hr_max_bpm", "FC max", "rider", 1, "bpm"),
    Setting("bike.mass_kg", "Poids du vélo", "rider", 1, "kg"),
    # Séance ; bonus et niveau des bots du mode classique (série T, lots T7, T10 et T13)
    Setting("trainer.difficulty_pct", "Difficulté en SIM", "ride", 10, "%"),
    Setting("gearing.start_gear", "Braquet de départ", "ride", 1),
    Setting("powerups.mode", "Bonus", "ride"),
    Setting("bots.level_pct", "Niveau des bots", "ride", 5, "%"),   # lot T13
    # Option « gravel » (lot U16, partie gravel) : coupée par défaut, roulement du core et rendu de l'engine
    Setting("gravel.mode", "Chemins de terre (gravel)", "ride",
            help="Coupé : bitume partout. Chemins réels : seules les portions non revêtues du parcours. "
                 "Chemin compact, gravier ou terre : toute la route. Roulement 2 à 3 fois plus dur, "
                 "sous le plafond du vent."),
    # Graphisme
    Setting("render.quality", "Qualité graphique", "graphics", applies="now"),
    Setting("render.texture_level", "Textures du décor", "graphics", applies="now"),   # lot P20
    Setting("render.theme", "Thème", "graphics", applies="now"),
    Setting("render.chart", "Courbes de la séance", "graphics", applies="now"),
    Setting("render.display", "Mode d'affichage", "graphics", applies="now"),
    Setting("render.fps", "Afficher les images/s", "graphics", applies="now"),
    Setting("render.draft_gauge", "Jauge d'abri des bots", "graphics", applies="now"),
    Setting("render.camera", "Vue de caméra", "graphics", applies="now"),
    Setting("render.biome", "Biome du décor", "graphics", applies="now",   # lot U16
            help="Automatique : les biomes du parcours (prairie tempérée sans données). Un autre choix met "
                 "ce biome sur tout le parcours : sol, végétation, faune et ciel."),
    # Son : volumes par catégorie (docs/AUDIO.md, bus audio de l'engine), curseur de 0 à 100 %
    Setting("audio.master_pct", "Volume général", "sound", 10, "%", "now"),
    Setting("audio.ride_pct", "Volume vent et roue libre", "sound", 10, "%", "now"),
    Setting("audio.ambience_pct", "Volume de l'ambiance", "sound", 10, "%", "now"),
    Setting("audio.events_pct", "Volume bips et événements", "sound", 10, "%", "now"),
    Setting("audio.rogue_sfx_pct", "Cyber-Rogue : bruitages", "sound", 10, "%", "now"),   # lot R18
    Setting("audio.rogue_music_pct", "Cyber-Rogue : musique", "sound", 10, "%", "now"),
    # Vent (lot P16, décisions du propriétaire du 25 octobre : coupé par défaut, plafond de 4 points)
    Setting("wind.mode", "Vent", "wind"),
    Setting("wind.speed_kmh", "Force du vent", "wind", 5, "km/h"),
    Setting("wind.from_deg", "Direction du vent", "wind", 45, "°"),
    Setting("wind.gust_pct", "Rafales", "wind", 10, "%"),
    Setting("wind.max_grade_offset_pct", "Plafond du vent", "wind", 1, "pts"),
)
# Sous-écrans de « Réglages », dans l'ordre d'affichage (champ `group` de chaque élément).
GROUPS = ("rider", "ride", "graphics", "sound", "wind")
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
        item: dict[str, Any] = {"key": s.key, "label": s.label, "group": s.group, "value": _value(cfg, s),
                                "applies": s.applies}
        if s.help:
            item["help"] = s.help
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
    """Valide et écrit les réglages, chacun dans le fichier de sa portée ; met `cfg` à jour ;
    renvoie les lignes changées."""
    clean = {k: check(cfg, k, v, themes_dir) for k, v in changes.items()}
    values = [(get(k).section, get(k).name, v) for k, v in clean.items()]
    try:
        changed = config_edit.update_layers(values, path)
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

