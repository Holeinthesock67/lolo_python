"""Parcours `.world` synthétiques (manifeste, couche route et couche segments) conformes au Format .world v1.

Sert au parcours de démonstration commun au core et à l'engine, et aux tests.
La ligne de commande est dans `tools/fake_world.py`.
La route est une montée sinueuse synthétique avec un lacet (deux épingles de sens opposés),
qui ne repasse jamais sur elle-même ; les coordonnées
géographiques sont obtenues par une projection locale équirectangulaire (suffisante pour
des données factices, le compilateur utilisera UTM via pyproj).

    python -m openride_core.tools.fake_world --out ../engine/demo --length 8000

Le parcours de démonstration commun au core et à l'engine (identifiant `demo`, 5 000 m, affiché au menu
sous le nom `DEMO_TITLE`, lot O37) est écrit par `write_demo_world` avec une date de création fixe et sa
couche terrain synthétique, pour être identique octet pour octet :
    python -m openride_core.tools.fake_world --demo --out ../engine/demo

Les parcours de démonstration des biomes (lot U19 ; trois dans le jeu de base, le tour gravel en plus pour les recettes, lot O37) et le
circuit en boucle « Circuit des Prés » (lot O38, courses en tours) et la boucle « Volcan en flammes » (lot DB2) sont écrits par `write_biome_demo_worlds`, qui
appelle le générateur du compilateur `openride_compiler.demo_biomes` (lot O37 ; compilateur requis) :
    openride-core demo-biomes [--out DOSSIER] [--recette]

La couche `segments.json` (format 1.3, lot T3) porte les montées et sprints détectés
automatiquement par `segments.py`, sans segment manuel (décision du 27 octobre).
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Callable

from .segments import Profile, detect_segments
from .synthetic_biome import add_biome_layer
from .synthetic_terrain import add_terrain_layer

EARTH_R = 6_371_000.0
DS_M = 10.0

DEMO_NAME = "demo"                 # identifiant de fichier (`demo.world`), inchangé
DEMO_TITLE = "Col du lacet"        # nom affiché au menu (lot O37)
DEMO_LENGTH_M = 5000.0
DEMO_CREATED = "2026-10-23T00:00:00+02:00"   # fixe : le fichier de démo est reproductible
HAIRPIN_GAP_M = 500.0       # distance entre les deux épingles du lacet (au plus 0,15 × longueur)
HAIRPIN_GAP_MIN_M = 250.0


def build_route(length_m: float = 8000.0, origin_lat: float = 45.09, origin_lon: float = 6.06,
                origin_alt: float = 1120.0, grade: Callable[[float], float] | None = None) -> dict:
    """Route synthétique ; `grade(s)` (en %) remplace la pente de la démonstration (parcours d'essai des
    outils, `tools/bots_race.py`)."""
    n = int(length_m // DS_M) + 1
    if (n - 1) * DS_M < length_m:
        n += 1
    s_values = [min(i * DS_M, length_m) for i in range(n)]

    # Cap : dérive lente + virages, avec un lacet : deux épingles de sens opposés (rotation de
    # ~180° sur 150 m chacune), proches l'une de l'autre. La route repart ensuite dans sa direction
    # d'origine, décalée d'environ 190 m : elle ne repasse jamais sur elle-même.
    hairpin_1 = 0.45 * length_m
    hairpin_2 = hairpin_1 + min(HAIRPIN_GAP_M, max(HAIRPIN_GAP_MIN_M, 0.15 * length_m))

    lacet_zone = (hairpin_1 - HAIRPIN_GAP_M, hairpin_2 + HAIRPIN_GAP_M)

    def heading_rate(s: float) -> float:  # degrés par mètre
        rate = 0.0
        if not lacet_zone[0] <= s <= lacet_zone[1]:   # branches du lacet droites et parallèles
            rate = 0.04 * math.sin(s / 700.0) + 0.02 * math.sin(s / 230.0 + 1.0)
        for center, turn in ((hairpin_1, 1.0), (hairpin_2, -1.0)):
            if abs(s - center) < 75.0:
                rate += turn * 180.0 / 150.0
        return rate

    # Pente : montée douce de 1 à 4 % qui ondule (confortable vers 150 W), replat en milieu de parcours.
    def demo_grade(s: float) -> float:
        g = 2.5 + 1.5 * math.sin(s / 900.0) + 0.5 * math.sin(s / 170.0)
        if 0.3 * length_m < s < 0.35 * length_m:
            g = 1.0
        return g

    grade = grade or demo_grade

    xs, zs, alts, grades, headings = [0.0], [0.0], [origin_alt], [grade(0.0)], [45.0]
    h = 45.0
    for i in range(1, n):
        ds = s_values[i] - s_values[i - 1]
        h = (h + heading_rate(s_values[i]) * ds) % 360.0
        rad = math.radians(h)
        # Cap horaire depuis le nord ; x vers l'est, z vers le sud (nord = −z).
        xs.append(xs[-1] + ds * math.sin(rad))
        zs.append(zs[-1] - ds * math.cos(rad))
        g = grade(s_values[i])
        alts.append(alts[-1] + ds * g / 100.0)
        grades.append(g)
        headings.append(h)

    lat0 = math.radians(origin_lat)
    lats = [origin_lat + math.degrees(-z / EARTH_R) for z in zs]
    lons = [origin_lon + math.degrees(x / (EARTH_R * math.cos(lat0))) for x in xs]

    r = lambda v, d: [round(x, d) for x in v]  # noqa: E731
    return {
        "version": "1.0",
        "ds_m": DS_M,
        "n": n,
        "length_m": float(length_m),
        "type": "open",
        "lat": r(lats, 7),
        "lon": r(lons, 7),
        "alt_m": r(alts, 2),
        "x": r(xs, 2),
        "z": r(zs, 2),
        "grade_pct": r(grades, 2),
        "heading_deg": r(headings, 2),
    }


def build_segments(route: dict) -> list[dict]:
    """Segments détectés sur la route (abscisses s_i = i·ds_m, la dernière = length_m)."""
    s = [i * route["ds_m"] for i in range(route["n"] - 1)] + [route["length_m"]]
    return [seg.to_dict() for seg in detect_segments(Profile(s, route["alt_m"], route["grade_pct"]))]


# Version du générateur, portée par le manifeste (`compiler.version`). 0.2.0 (7 novembre 2026) : terrain proche
# dégagé sous la chaussée (`synthetic_terrain.clear_road`) ; 0.3.0 (8 novembre 2026, lot O37) : la
# démonstration porte son nom de parcours `DEMO_TITLE` ; 0.4.0 (12 novembre 2026, lot W17) : couche biome
# synthétique (forêt et alpages, `synthetic_biome.py`). Une démonstration plus ancienne du dossier des
# parcours est remplacée par `ensure_demo_world`.
FAKE_WORLD_NAME = "openride-fake-world"
FAKE_WORLD_VERSION = "0.4.0"


def build_manifest(name: str, route: dict, created: str | None = None,
                   segments: list[dict] | None = None) -> dict:
    segments = build_segments(route) if segments is None else segments
    return {
        "format": "openride-world",
        "format_version": "1.3",
        "name": name,
        "created": created or datetime.now().astimezone().isoformat(timespec="seconds"),
        "compiler": {"name": FAKE_WORLD_NAME, "version": FAKE_WORLD_VERSION},
        "source": {"gpx": None, "gpx_sha256": None},
        "origin": {"lat": route["lat"][0], "lon": route["lon"][0], "alt_m": route["alt_m"][0],
                   "utm_zone": "32T"},
        "projection": "local_equirectangular",
        "route": {"present": True, "version": "1.0", "file": "route.json",
                  "length_m": route["length_m"], "ds_m": route["ds_m"], "n": route["n"],
                  "type": route["type"], "grade_clamped_points": 0},
        "layers": {
            "terrain": {"present": False},
            "buildings": {"present": False},
            "vegetation": {"present": False, "source": "none"},
            "poi": {"present": False},
            "water": {"present": False},
            "segments": {"present": True, "version": "1.0", "file": "segments.json",
                         "count": len(segments), "manual_count": 0},
        },
    }


def write_world(out_dir: Path, name: str, length_m: float, created: str | None = None,
                grade: Callable[[float], float] | None = None, title: str | None = None) -> Path:
    """Écrit `out_dir/<name>.world` ; `title` : nom affiché au menu (défaut : l'identifiant `name`)."""
    route = build_route(length_m, grade=grade)
    world = out_dir / f"{name}.world"
    world.mkdir(parents=True, exist_ok=True)
    segments = build_segments(route)
    (world / "route.json").write_text(json.dumps(route, separators=(",", ":")), encoding="utf-8")
    (world / "segments.json").write_text(
        json.dumps({"version": "1.0", "segments": segments}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (world / "manifest.json").write_text(
        json.dumps(build_manifest(title or name, route, created, segments), indent=2), encoding="utf-8")
    return world


def write_demo_world(out_dir: Path) -> Path:
    """Écrit le parcours de démonstration commun au core et à l'engine, avec sa couche terrain
    synthétique (`synthetic_terrain.py`) : sans elle, l'engine pose un sol plat sous l'altitude la plus
    basse et la route, qui monte de 120 m, semble léviter (constat du 4 novembre 2026). Couche biome
    synthétique depuis le lot W17, comme tout parcours compilé (sinon le biome par défaut partout)."""
    world = write_world(out_dir, DEMO_NAME, DEMO_LENGTH_M, created=DEMO_CREATED, title=DEMO_TITLE)
    return add_biome_layer(add_terrain_layer(world))


def _demo_needs_rewrite(world: Path) -> bool:
    """Vrai si `world` manque, ou si c'est une démonstration écrite ici sans couche terrain ou par une version
    plus ancienne du générateur (terrain qui recouvrait la chaussée au km 1,74 avant la 0.2.0)."""
    try:
        manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    if not isinstance(manifest, dict):
        return True
    compiler = manifest.get("compiler") or {}
    if compiler.get("name") != FAKE_WORLD_NAME:
        return False
    terrain = (manifest.get("layers") or {}).get("terrain") or {}
    return not terrain.get("present", False) or _version(compiler.get("version")) < _version(FAKE_WORLD_VERSION)


def _version(text) -> tuple[int, ...]:
    """« 0.2.0 » -> (0, 2, 0) ; (0,) si illisible (plus ancien que toute version)."""
    try:
        return tuple(int(p) for p in str(text).split("."))
    except ValueError:
        return (0,)


def _bundled_demo_world(engine_dir: Path | None = None) -> Path | None:
    """Démonstration embarquée par l'engine (`engine/demo/demo.world`, identique à `write_demo_world`,
    test_segments.py), si elle porte sa couche terrain."""
    import os

    from .launcher import DEFAULT_ENGINE_DIR

    engine = Path(engine_dir or os.environ.get("OPENRIDE_ENGINE") or DEFAULT_ENGINE_DIR).expanduser()
    world = engine / "demo" / f"{DEMO_NAME}.world"
    return None if _demo_needs_rewrite(world) or not (world / "terrain").is_dir() else world


def ensure_demo_world(routes_root: Path, engine_dir: Path | None = None) -> Path:
    """Crée `<routes_root>/demo.world` s'il manque (ou le réécrit s'il date d'avant sa couche terrain ou d'une
    version plus ancienne du générateur), et renvoie son chemin. Copie la démonstration embarquée par l'engine quand elle est là (quelques
    millisecondes, la séance n'attend pas), sinon l'écrit (environ 2 s pour le terrain). Le manifeste
    est copié en dernier : une copie interrompue est refaite au prochain appel."""
    import shutil

    world = routes_root / f"{DEMO_NAME}.world"
    if not _demo_needs_rewrite(world):
        return world
    bundled = _bundled_demo_world(engine_dir)
    if bundled is None:
        write_demo_world(routes_root)
        return world
    world.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundled / "terrain", world / "terrain", dirs_exist_ok=True)
    if (bundled / "biome").is_dir():
        shutil.copytree(bundled / "biome", world / "biome", dirs_exist_ok=True)
    for name in ("route.json", "segments.json", "manifest.json"):
        shutil.copyfile(bundled / name, world / name)
    return world


def _biome_demo_module():
    """Générateur du compilateur `openride_compiler.demo_biomes` (lots U19 et O37) ; ImportError sans le
    compilateur."""
    from openride_compiler import demo_biomes

    return demo_biomes


def biome_demo_names() -> list[str]:
    """Identifiants des parcours écrits par `write_biome_demo_worlds` (contenus de départ, lot O25)."""
    return list(_biome_demo_module().GAME_DEMOS)


def retired_biome_demo_names() -> list[str]:
    """Démonstrations retirées du jeu de base (lot O37 : le tour gravel), gardées pour les recettes."""
    return list(_biome_demo_module().RETIRED_DEMOS)


def biome_demo_outdated(world: Path) -> bool:
    """Vrai si `world` est une démonstration des biomes écrite avant le lot O37 (générateur
    `make_biome_world` des tests de l'engine : nom technique au menu, lieux « Fictif »)."""
    try:
        manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    compiler = manifest.get("compiler") if isinstance(manifest, dict) else None
    return isinstance(compiler, dict) and compiler.get("name") == "make_biome_world"


def write_biome_demo_worlds(out_dir: Path, recette: bool = False) -> list[dict]:
    """Écrit les parcours de démonstration des biomes (lot U19) dans `out_dir` : tour des six biomes, côte avec
    la mer, alpin, et le circuit en boucle (lot O38). Renvoie le résumé de chacun. `recette` : variante des bancs et des recettes (noms
    techniques, lot O37), avec en plus le tour avec un tiers de gravel ; jamais dans le jeu de base.
    Lève ImportError sans le compilateur."""
    return _biome_demo_module().write_demo_set(Path(out_dir), recette=recette)
