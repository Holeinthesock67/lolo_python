"""Réglages proposés au menu (lots O3 et O4) : liste fermée, valeurs, pas au Click, écriture.

Chaque réglage est une clé `section.clé` de `config.toml`. Les bornes et les choix viennent de
`config.py` (`BOUNDS`, `CHOICES`), jamais recopiés ici ; les thèmes proposés sont `default` et les
dossiers de `~/OpenRide/Themes/` qui contiennent un `theme.json` (lot N10).

`current(cfg)` donne la liste pour le message IPC `settings` (contrat révision 1.3) et pour
`openride-core settings --json` ; chaque élément :

    {"key": "rider.ftp_w", "label": "FTP", "group": "rider", "type": "int", "value": 250, "min": 50,
     "max": 600, "step": 5, "unit": "W", "applies": "next_session"}

`group` range le réglage dans un sous-écran de « Réglages » (`GROUPS` : cycliste, séance, graphisme,
son, vent, avancé) ; l'engine donne les titres. Le message est envoyé en parties comme `routes` (lot O27).

`type` vaut `int` ou `choice` (avec `choices`) ; `applies` vaut `next_session` (prise en compte à
la séance suivante, sans relancer), `now` (qualité, niveau des textures, thème, mode d'affichage, courbes, images/s,
jauge d'abri et volumes : l'engine les applique tout de suite ; le lanceur passe aussi la qualité, le niveau des
textures, le thème et le mode d'affichage à l'engine aux lancements suivants) ou `relaunch` (décor vivant, relief :
passés par le lanceur à l'engine ;
progression : lue au démarrage du core ; pris au prochain lancement, l'engine propose de relancer, lot O26).

Deux règles de forme valent pour toutes les clés (lot O26) : un booléen du fichier est un choix `on` /
`off` au menu ; `Setting.scale` multiplie un nombre du fichier pour l'afficher en entier au menu (relief
2,5 affiché 250 %), et le divise à l'écriture.
`apply(cfg, changes, path)` valide, écrit chaque réglage dans son fichier (commentaires et reste du
fichier gardés, copie `.bak`) puis met à jour `cfg` en mémoire.

Portée (série MJ, lot MJ4) : `Setting.scope` vaut `profil` pour les réglages qui suivent le joueur
(`config.PROFILE_KEYS` : cycliste, séance, vent, caméra, courbes) et `machine` pour les autres
(graphisme, affichage, volumes) ; un réglage `profil` s'écrit dans le `profil.toml` du profil en
cours, ou dans `config.toml` sans profil. L'engine n'en sait rien.
"""

from __future__ import annotations

import json
import math
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
    scale: float = 1   # valeur du menu = valeur du fichier × scale (lot O26)

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
    # Graphisme
    Setting("render.quality", "Qualité graphique", "graphics", applies="now"),
    Setting("render.texture_level", "Textures du décor", "graphics", applies="now"),   # lot P20
    Setting("render.theme", "Thème", "graphics", applies="now"),
    Setting("render.chart", "Courbes de la séance", "graphics", applies="now"),
    Setting("render.display", "Mode d'affichage", "graphics", applies="now"),
    Setting("render.fps", "Afficher les images/s", "graphics", applies="now"),
    Setting("render.draft_gauge", "Jauge d'abri des bots", "graphics", applies="now"),
    Setting("render.camera", "Vue de caméra", "graphics", applies="now"),
    Setting("render.living", "Décor vivant", "graphics", applies="relaunch"),   # lot O26
    Setting("render.visual_grade_scale", "Relief exagéré", "graphics", 25, "%", "relaunch", 100),
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
    Setting("wind.max_grade_offset_pct", "Plafond du vent", "wind", 1, "pts de pente"),
    Setting("wind.feel", "Ressenti du vent", "wind"),   # lot O26
    # Avancé (lot O27) : monde ouvert hors ligne, plafonds de disque, progression du Garage
    Setting("open_world.network", "Télécharger les cartes", "advanced"),
    Setting("open_world.cache_max_gb", "Cache du monde", "advanced", 1, "Go"),
    Setting("render.theme_library_gb", "Place pour les thèmes", "advanced", 1, "Go"),
    Setting("progression.enabled", "Progression et Garage", "advanced", applies="relaunch"),
)
BOOL_CHOICES = ("on", "off")
# Sous-écrans de « Réglages », dans l'ordre d'affichage (champ `group` de chaque élément).
GROUPS = ("rider", "ride", "graphics", "sound", "wind", "advanced")
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


def _is_bool(s: Setting) -> bool:
    return isinstance(getattr(config_mod.Config(), s.section).__dict__[s.name], bool)


def choices(s: Setting, themes_dir: Path | None = None) -> list[str] | None:
    if s.key == "render.theme":
        return installed_themes(themes_dir)
    if _is_bool(s):
        return list(BOOL_CHOICES)
    found = config_mod.CHOICES.get((s.section, s.name))
    return list(found) if found else None


def bounds(s: Setting, cfg: config_mod.Config) -> tuple[float, float] | None:
    if s.key == "gearing.start_gear":
        return (1, cfg.gearing.n_gears)
    found = config_mod.BOUNDS.get((s.section, s.name))
    return (found[0] * s.scale, found[1] * s.scale) if found else None


def _value(cfg: config_mod.Config, s: Setting) -> Any:
    v = getattr(getattr(cfg, s.section), s.name)
    if isinstance(v, bool):
        return BOOL_CHOICES[0] if v else BOOL_CHOICES[1]
    return int(round(v * s.scale)) if isinstance(v, float) else v


def _to_file(s: Setting, value: Any) -> Any:
    """Valeur du menu vers la valeur du fichier : booléen pour `on` / `off`, division par `scale`."""
    if _is_bool(s):
        return value == BOOL_CHOICES[0]
    if s.scale != 1:
        return value / s.scale
    return value


def current(cfg: config_mod.Config, themes_dir: Path | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in SETTINGS:
        item: dict[str, Any] = {"key": s.key, "label": s.label, "group": s.group, "value": _value(cfg, s),
                                "applies": s.applies}
        ch = choices(s, themes_dir)
        if ch is not None:
            item.update(type="choice", choices=ch)
        else:
            lo, hi = bounds(s, cfg) or (0, 0)
            item.update(type="int", min=math.ceil(lo), max=math.floor(hi), step=int(s.step), unit=s.unit)
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
    clean = {k: _to_file(get(k), check(cfg, k, v, themes_dir)) for k, v in changes.items()}
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
        when = {"next_session": "séance suivante", "now": "tout de suite", "relaunch": "prochain lancement"}[it["applies"]]
        print(f"{it['key']:<24} {it['label']:<20} {it['value']}{unit}  ({when})")
    return 0

