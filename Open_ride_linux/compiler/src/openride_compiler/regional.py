"""Variante régionale par tuile (champ `variant` de la couche biome, Format .world v1 §8 quater ; lot U4).

Sans entrée-sortie hors la lecture de la table embarquée `data/regional_variants.toml`.

Une variante est un objet `{"ground": …, "roofs": …, "landscape": …}` (roches et terres, architecture, paysage
du lot U25 : canyons, fjords, îles volcaniques, rizières, appliqué par l'engine aux seuls biomes de base du
paysage, section `landscapes` du thème) ; chaque membre se choisit séparément : la plus petite zone de la table qui contient le point et qui donne ce membre, puis la
première règle générale qui s'applique (part de biomes, latitude) et qui le donne, puis la variante neutre ;
sinon le membre reste `null` (l'engine garde ce que donne le biome, lot U23 pour les bâtiments).

La table travaille à grosse maille : bornes en degrés entiers, zone de 1° × 1° au moins, aucune coordonnée
plus fine. Une zone contient les points de `lat_min <= lat < lat_max` et `lon_min <= lon < lon_max`.

Tuiles : une variante par tuile proche (au centre de la tuile, parts de biomes de la tuile) ; une tuile
lointaine prend la variante majoritaire des tuiles proches qu'elle contient, ou, sans tuile proche, celle de
son propre centre.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import numpy as np
import tomllib

# Énumération fermée du contrat (U1 §4.3, Format .world v1 §8 quater), étendue seulement par ajout.
GROUNDS = ("gres_rose", "calcaire_blanc", "granite_gris", "schiste_sombre", "basalte", "laterite_rouge", "craie")
ROOFS = ("tuile_ronde", "ardoise", "tuile_plate", "pierre_seche", "toit_plat_blanc", "bois", "kawara", "bois_peint")
LANDSCAPES = ("canyon", "fjord", "ile_volcanique", "rizieres", "volcan_actif")
MEMBERS = {"ground": GROUNDS, "roofs": ROOFS, "landscape": LANDSCAPES}
# Membres toujours présents dans une tuile ; `landscape` (lot U25) est facultatif : absent = null (tuiles
# écrites avant le lot U25).
REQUIRED_MEMBERS = ("ground", "roofs")

ZONE_KEYS = {"name", "lat", "lon", *MEMBERS}
RULE_KEYS = {"name", "biomes", "min_share", "abs_lat_min", "abs_lat_max", *MEMBERS}
NEUTRAL_KEYS = set(MEMBERS)
TABLE_KEYS = {"neutral", "rule", "zone"}


@dataclass(frozen=True)
class Zone:
    name: str
    lat: tuple[int, int]
    lon: tuple[int, int]
    values: dict[str, str]

    @property
    def area(self) -> int:
        return (self.lat[1] - self.lat[0]) * (self.lon[1] - self.lon[0])

    def contains(self, lat: float, lon: float) -> bool:
        return self.lat[0] <= lat < self.lat[1] and self.lon[0] <= lon < self.lon[1]


@dataclass(frozen=True)
class Rule:
    name: str
    values: dict[str, str]
    biomes: tuple[str, ...] = ()
    min_share: float = 0.0
    abs_lat_min: int | None = None
    abs_lat_max: int | None = None

    def applies(self, lat: float, biome_shares: Mapping[str, float]) -> bool:
        if self.biomes and sum(float(biome_shares.get(b, 0.0)) for b in self.biomes) < self.min_share:
            return False
        if self.abs_lat_min is not None and abs(lat) < self.abs_lat_min:
            return False
        if self.abs_lat_max is not None and abs(lat) > self.abs_lat_max:
            return False
        return True


@dataclass(frozen=True)
class Table:
    zones: tuple[Zone, ...]
    rules: tuple[Rule, ...]
    neutral: dict[str, str]


def _check_keys(where: str, data: Mapping, allowed: set[str]) -> None:
    extra = set(data) - allowed
    if extra:
        raise ValueError(f"{where} : clé(s) inconnue(s) {', '.join(sorted(extra))}")


def _values(where: str, data: Mapping) -> dict[str, str]:
    out = {}
    for member, ids in MEMBERS.items():
        if member in data:
            value = data[member]
            if value not in ids:
                raise ValueError(f"{where} : {member} {value!r} inconnu (possibles : {', '.join(ids)})")
            out[member] = value
    return out


def _degrees(where: str, pair) -> tuple[int, int]:
    if (not isinstance(pair, list) or len(pair) != 2
            or not all(isinstance(v, int) and not isinstance(v, bool) for v in pair)):
        raise ValueError(f"{where} : bornes attendues en degrés entiers [min, max], reçu {pair!r}")
    if pair[0] >= pair[1]:
        raise ValueError(f"{where} : borne min {pair[0]} pas sous la borne max {pair[1]}")
    return int(pair[0]), int(pair[1])


def parse_table(data: Mapping) -> Table:
    """Table de variantes d'après le contenu TOML déjà lu (erreurs explicites, sans valeur par défaut cachée)."""
    _check_keys("table", data, TABLE_KEYS)
    zones = []
    for k, z in enumerate(data.get("zone", [])):
        where = f"zone {z.get('name', k)}"
        _check_keys(where, z, ZONE_KEYS)
        lat = _degrees(where + " lat", z.get("lat"))
        lon = _degrees(where + " lon", z.get("lon"))
        if not (-90 <= lat[0] and lat[1] <= 90 and -180 <= lon[0] and lon[1] <= 180):
            raise ValueError(f"{where} : hors du globe")
        values = _values(where, z)
        if not values:
            raise ValueError(f"{where} : aucun membre ({', '.join(MEMBERS)})")
        zones.append(Zone(name=str(z.get("name", k)), lat=lat, lon=lon, values=values))
    names = [z.name for z in zones]
    if len(set(names)) != len(names):
        raise ValueError("zones : noms en double")
    rules = []
    for k, r in enumerate(data.get("rule", [])):
        where = f"règle {r.get('name', k)}"
        _check_keys(where, r, RULE_KEYS)
        values = _values(where, r)
        if not values:
            raise ValueError(f"{where} : aucun membre ({', '.join(MEMBERS)})")
        for key in ("abs_lat_min", "abs_lat_max"):
            if key in r and (not isinstance(r[key], int) or isinstance(r[key], bool)):
                raise ValueError(f"{where} : {key} attendu en degrés entiers")
        biomes = tuple(r.get("biomes", ()))
        if biomes and "min_share" not in r:
            raise ValueError(f"{where} : biomes sans min_share")
        if not biomes and "abs_lat_min" not in r and "abs_lat_max" not in r:
            raise ValueError(f"{where} : aucune condition")
        rules.append(Rule(name=str(r.get("name", k)), values=values, biomes=biomes,
                          min_share=float(r.get("min_share", 0.0)),
                          abs_lat_min=r.get("abs_lat_min"), abs_lat_max=r.get("abs_lat_max")))
    neutral = data.get("neutral", {})
    _check_keys("neutral", neutral, NEUTRAL_KEYS)
    return Table(zones=tuple(sorted(zones, key=lambda z: (z.area, z.name))), rules=tuple(rules),
                 neutral=_values("neutral", neutral))


def load_table(path: Path | None = None) -> Table:
    """Table embarquée (`data/regional_variants.toml`) ou fichier donné."""
    if path is None:
        text = resources.files("openride_compiler").joinpath("data/regional_variants.toml").read_text("utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")
    return parse_table(tomllib.loads(text))


_DEFAULT: Table | None = None


def default_table() -> Table:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = load_table()
    return _DEFAULT


def variant_for(lat: float, lon: float, biome_shares: Mapping[str, float],
                table: Table | None = None) -> dict[str, str | None]:
    """Variante `{"ground", "roofs", "landscape"}` d'un point (membre `None` si rien ne le donne)."""
    table = table or default_table()
    out: dict[str, str | None] = {}
    zones = [z for z in table.zones if z.contains(lat, lon)]          # déjà triées, la plus petite d'abord
    rules = [r for r in table.rules if r.applies(lat, biome_shares)]
    for member in MEMBERS:
        value = next((z.values[member] for z in zones if member in z.values), None)
        if value is None:
            value = next((r.values[member] for r in rules if member in r.values), None)
        if value is None:
            value = table.neutral.get(member)
        out[member] = value
    return out


def parse_forced(text: str) -> dict[str, str | None]:
    """`--variant GROUND,ROOFS[,LANDSCAPE]` ; un membre vide ou omis reste `null` (par exemple `basalte,`)."""
    parts = text.split(",")
    if not len(REQUIRED_MEMBERS) <= len(parts) <= len(MEMBERS):
        raise ValueError(f"variante attendue GROUND,ROOFS[,LANDSCAPE], reçu {text!r}")
    parts += [""] * (len(MEMBERS) - len(parts))
    out: dict[str, str | None] = {}
    for (member, ids), value in zip(MEMBERS.items(), parts):
        value = value.strip()
        if value and value not in ids:
            raise ValueError(f"{member} {value!r} inconnu (possibles : {', '.join(ids)})")
        out[member] = value or None
    if all(v is None for v in out.values()):
        raise ValueError("variante vide : donner au moins GROUND, ROOFS ou LANDSCAPE")
    return out


def tile_shares(tile: Mapping) -> dict[str, float]:
    """Part (0 à 1) de chaque biome d'une tuile de biome, moyenne des 289 poids."""
    return {name: float(np.mean(grid)) / 255.0 for name, grid in zip(tile["biomes"], tile["weights"])}


def _key(variant: Mapping[str, str | None]) -> tuple[str, ...]:
    return tuple(variant.get(m) or "" for m in MEMBERS)


def assign_variants(tiles: dict[str, dict[tuple[int, int], dict]], tile_m: Mapping[str, float],
                    to_latlon: Callable[[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]] | None,
                    forced: Mapping[str, str | None] | None = None, table: Table | None = None,
                    near: str = "near", far: str = "far") -> None:
    """Pose `variant` dans chaque tuile (proches puis lointaines), sur place.

    `forced` (option `--variant`) : même couple partout. Sinon `to_latlon` donne le centre des tuiles.
    """
    if forced is not None:
        for level in tiles.values():
            for tile in level.values():
                tile["variant"] = dict(forced)
        return
    assert to_latlon is not None
    table = table or default_table()

    def at_centers(level: str, keys: Sequence[tuple[int, int]]) -> None:
        if not keys:
            return
        size = tile_m[level]
        cx = np.array([(ix + 0.5) * size for ix, _ in keys], dtype=float)
        cz = np.array([(iz + 0.5) * size for _, iz in keys], dtype=float)
        lat, lon = to_latlon(cx, cz)
        lat, lon = np.atleast_1d(np.asarray(lat, dtype=float)), np.atleast_1d(np.asarray(lon, dtype=float))
        for k, key in enumerate(keys):
            tile = tiles[level][key]
            tile["variant"] = variant_for(float(lat[k]), float(lon[k]), tile_shares(tile), table)

    near_tiles = tiles.get(near, {})
    at_centers(near, sorted(near_tiles))
    far_tiles = tiles.get(far, {})
    if not far_tiles:
        return
    ratio = tile_m[far] / tile_m[near]
    votes: dict[tuple[int, int], Counter] = {}
    examples: dict[tuple[str, ...], dict] = {}
    for (ix, iz), tile in near_tiles.items():
        cx, cz = (ix + 0.5) / ratio, (iz + 0.5) / ratio     # centre de la tuile proche, en tuiles lointaines
        owner = (int(np.floor(cx)), int(np.floor(cz)))
        if owner in far_tiles:
            k = _key(tile["variant"])
            votes.setdefault(owner, Counter())[k] += 1
            examples.setdefault(k, tile["variant"])
    alone = []
    for key in sorted(far_tiles):
        if key in votes:
            # Majorité ; à égalité, le plus petit couple d'identifiants (déterministe).
            best = min(votes[key].items(), key=lambda kv: (-kv[1], kv[0]))[0]
            far_tiles[key]["variant"] = dict(examples[best])
        else:
            alone.append(key)
    at_centers(far, alone)


def summary(tiles: Mapping[tuple[int, int], Mapping]) -> str:
    """Rapport court des variantes d'un niveau : « calcaire_blanc/tuile_ronde/— 12, gres_rose/—/canyon 3 »."""
    count = Counter(_key(t.get("variant") or {}) for t in tiles.values())
    parts = ["/".join(v or "—" for v in k) + f" {n}" for k, n in sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))]
    return ", ".join(parts) if parts else "aucune tuile"
