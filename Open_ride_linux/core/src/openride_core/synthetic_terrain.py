"""Couche terrain synthétique d'un parcours `.world` (lot E1, §4.5 ; Format .world v1, §5).

Tuiles proches et lointaines d'un relief analytique de collines sinusoïdales, d'environ 300 m de
dénivelé, autour de la route. Écrite avec le parcours de démonstration (`demo_world.write_demo_world`)
pour que la route y repose sur un sol qui la suit (le sol plat de l'engine, posé sous l'altitude la
plus basse, laissait la route « léviter » dès qu'elle montait), et par `tools/fake_world.py --terrain`
pour les parcours d'essai. Bibliothèque standard seulement.

Relief synthétique en un point (x, z), `d` étant la distance au bord du ruban (distance à l'axe
moins 3 m) :
- `y_route` : altitude de la route au point le plus proche de l'axe (projection sur le segment) ;
- `y_lisse` : altitude de la route lissée à grande échelle (moyenne pondérée par la distance),
  pour que le relief loin de la route n'ait pas de marche quand le point de route le plus
  proche change ;
- MNT synthétique = `y_route` jusqu'à 25 m, puis passage progressif vers `y_lisse` (25 à 45 m),
  plus les collines, qui montent de 0 à leur pleine amplitude entre 45 et 445 m ;
- fondu du format §5 (simplifié, linéaire) : `y_route − 0,05` jusqu'à 4 m, MNT au-delà de 25 m ;
- garde-fou de la chaussée (`clear_road`, comme le compilateur) : aucun triangle du maillage proche ne
  dépasse la route moins 5 cm, même là où la pente change.
"""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path

TILE_SAMPLES = 101                  # échantillons par côté d'une tuile (format §5)
ROAD_HALF_WIDTH_M = 3.0             # demi-largeur de chaussée
BLEND_START_M = 4.0                 # fondu route → MNT, distance au bord du ruban
BLEND_END_M = 25.0
TERRAIN_BELOW_ROAD_M = 0.05         # le terrain passe 5 cm sous la chaussée
REF_BLEND_END_M = 45.0              # passage de y_route à y_lisse entre 25 et 45 m du bord
HILLS_RAMP_M = 400.0                # les collines atteignent leur amplitude 400 m plus loin

# (dossier, maille, taille de tuile, étendue autour de la route)
NEAR = ("near", 10.0, 1000.0, 400.0)
FAR = ("far", 50.0, 5000.0, 5000.0)

_HASH_CELL_M = 50.0                 # index spatial des segments
_NEAR_SEARCH_M = 60.0               # distance exacte à l'axe calculée jusqu'à 60 m
_DIST_LATTICE_M = 50.0              # grille des distances au-delà
_DIST_MAX_M = 600.0
_SMOOTH_LATTICE_M = 100.0           # grille de y_lisse
_SMOOTH_STEP_PTS = 10               # un point de route sur 10 (100 m) pour y_lisse
_SMOOTH_SCALE_M = 150.0


def _smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def hills(x: float, z: float) -> float:
    """Collines sinusoïdales : environ ± 155 m, soit 300 m de dénivelé."""
    return (100.0 * math.sin(x / 610.0 + 0.3) * math.cos(z / 740.0)
            + 40.0 * math.sin((x + z) / 290.0)
            + 15.0 * math.sin(x / 130.0) * math.sin(z / 170.0))


class SyntheticTerrain:
    """Altitude du relief synthétique autour d'une route (`build_route`)."""

    def __init__(self, route: dict) -> None:
        self.xs: list[float] = route["x"]
        self.zs: list[float] = route["z"]
        self.alts: list[float] = route["alt_m"]
        self.n = len(self.xs)
        self._seg_hash: dict[tuple[int, int], list[int]] = {}
        for i in range(self.n - 1):
            x0, x1 = sorted((self.xs[i], self.xs[i + 1]))
            z0, z1 = sorted((self.zs[i], self.zs[i + 1]))
            for cx in range(math.floor(x0 / _HASH_CELL_M), math.floor(x1 / _HASH_CELL_M) + 1):
                for cz in range(math.floor(z0 / _HASH_CELL_M), math.floor(z1 / _HASH_CELL_M) + 1):
                    self._seg_hash.setdefault((cx, cz), []).append(i)
        self._dist_lattice = self._build_dist_lattice()
        self._smooth_pts = [(self.xs[i], self.zs[i], self.alts[i])
                            for i in range(0, self.n, _SMOOTH_STEP_PTS)]
        self._smooth_cache: dict[tuple[int, int], float] = {}

    # --- distances -----------------------------------------------------------------------

    def nearest_on_axis(self, x: float, z: float) -> tuple[float, float] | None:
        """(distance à l'axe, altitude projetée) du segment le plus proche, s'il est à moins de 60 m."""
        best: tuple[float, float] | None = None
        cx, cz = math.floor(x / _HASH_CELL_M), math.floor(z / _HASH_CELL_M)
        r = math.ceil(_NEAR_SEARCH_M / _HASH_CELL_M)
        seen: set[int] = set()
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                for i in self._seg_hash.get((cx + dx, cz + dz), ()):
                    if i in seen:
                        continue
                    seen.add(i)
                    ax, az = self.xs[i], self.zs[i]
                    vx, vz = self.xs[i + 1] - ax, self.zs[i + 1] - az
                    ll = vx * vx + vz * vz
                    t_raw = 0.0 if ll <= 0.0 else ((x - ax) * vx + (z - az) * vz) / ll
                    t = min(1.0, max(0.0, t_raw))
                    px, pz = ax + t * vx, az + t * vz
                    d = math.hypot(x - px, z - pz)
                    if d <= _NEAR_SEARCH_M and (best is None or d < best[0]):
                        # Au-delà des extrémités, l'altitude prolonge la pente du segment (comme les
                        # points fantômes de la route) : pas de pli que la grille relèverait.
                        t_alt = t
                        if (i == 0 and t_raw < 0.0) or (i == self.n - 2 and t_raw > 1.0):
                            t_alt = t_raw
                        best = (d, self.alts[i] + t_alt * (self.alts[i + 1] - self.alts[i]))
        return best

    def _build_dist_lattice(self) -> dict[tuple[int, int], float]:
        lattice: dict[tuple[int, int], float] = {}
        r = math.ceil(_DIST_MAX_M / _DIST_LATTICE_M)
        for px, pz in zip(self.xs, self.zs):
            ci, cj = round(px / _DIST_LATTICE_M), round(pz / _DIST_LATTICE_M)
            for i in range(ci - r, ci + r + 1):
                for j in range(cj - r, cj + r + 1):
                    d = math.hypot(i * _DIST_LATTICE_M - px, j * _DIST_LATTICE_M - pz)
                    if d < lattice.get((i, j), _DIST_MAX_M):
                        lattice[(i, j)] = d
        return lattice

    def _lattice_distance(self, x: float, z: float) -> float:
        fi, fj = x / _DIST_LATTICE_M, z / _DIST_LATTICE_M
        i, j = math.floor(fi), math.floor(fj)
        u, v = fi - i, fj - j
        g = lambda a, b: self._dist_lattice.get((a, b), _DIST_MAX_M)  # noqa: E731
        return ((1 - u) * (1 - v) * g(i, j) + u * (1 - v) * g(i + 1, j)
                + (1 - u) * v * g(i, j + 1) + u * v * g(i + 1, j + 1))

    def _smooth_node(self, i: int, j: int) -> float:
        key = (i, j)
        val = self._smooth_cache.get(key)
        if val is None:
            x, z = i * _SMOOTH_LATTICE_M, j * _SMOOTH_LATTICE_M
            num = den = 0.0
            for px, pz, pa in self._smooth_pts:
                w = 1.0 / ((x - px) ** 2 + (z - pz) ** 2 + _SMOOTH_SCALE_M ** 2) ** 2
                num += w * pa
                den += w
            val = num / den
            self._smooth_cache[key] = val
        return val

    def smooth_route_alt(self, x: float, z: float) -> float:
        """Altitude de la route lissée à grande échelle (y_lisse), continue partout."""
        fi, fj = x / _SMOOTH_LATTICE_M, z / _SMOOTH_LATTICE_M
        i, j = math.floor(fi), math.floor(fj)
        u, v = fi - i, fj - j
        return ((1 - u) * (1 - v) * self._smooth_node(i, j) + u * (1 - v) * self._smooth_node(i + 1, j)
                + (1 - u) * v * self._smooth_node(i, j + 1) + u * v * self._smooth_node(i + 1, j + 1))

    # --- altitude ------------------------------------------------------------------------

    def height(self, x: float, z: float) -> float:
        near = self.nearest_on_axis(x, z)
        d_axis = near[0] if near is not None else max(self._lattice_distance(x, z), _NEAR_SEARCH_M)
        d_edge = d_axis - ROAD_HALF_WIDTH_M
        y_smooth = self.smooth_route_alt(x, z)
        if near is not None:
            y_route = near[1]
            k = _smoothstep((d_edge - BLEND_END_M) / (REF_BLEND_END_M - BLEND_END_M))
            y_ref = y_route + k * (y_smooth - y_route)
        else:
            y_route = None
            y_ref = y_smooth
        dem = y_ref + hills(x, z) * _smoothstep((d_edge - REF_BLEND_END_M) / HILLS_RAMP_M)
        if y_route is None:
            return dem
        t = min(1.0, max(0.0, (d_edge - BLEND_START_M) / (BLEND_END_M - BLEND_START_M)))
        return (y_route - TERRAIN_BELOW_ROAD_M) * (1.0 - t) + dem * t

    # --- tuiles --------------------------------------------------------------------------

    def tiles_for(self, level: tuple[str, float, float, float]) -> list[tuple[int, int]]:
        """Tuiles dont le carré passe à moins de l'étendue d'un point de la route."""
        _, _, size, extent = level
        tiles: set[tuple[int, int]] = set()
        for px, pz in zip(self.xs, self.zs):
            for ix in range(math.floor((px - extent) / size), math.floor((px + extent) / size) + 1):
                for iz in range(math.floor((pz - extent) / size), math.floor((pz + extent) / size) + 1):
                    if (ix, iz) in tiles:
                        continue
                    dx = max(ix * size - px, 0.0, px - (ix + 1) * size)
                    dz = max(iz * size - pz, 0.0, pz - (iz + 1) * size)
                    if math.hypot(dx, dz) <= extent:
                        tiles.add((ix, iz))
        return sorted(tiles)

    def tile_values(self, level: tuple[str, float, float, float], ix: int, iz: int) -> list[float]:
        """101 × 101 altitudes rangées par ligne : (i, j) à x = ix·T + i·maille, z = iz·T + j·maille."""
        _, cell, size, _ = level
        return [self.height(ix * size + i * cell, iz * size + j * cell)
                for j in range(TILE_SAMPLES) for i in range(TILE_SAMPLES)]


# --- garde-fou de la chaussée -----------------------------------------------------------------
# Les sommets du maillage proche sont posés 5 cm sous la route, mais un triangle de 10 m est plan : là où la
# pente de la route change (de 1 % à 3,5 % au km 1,74 de la démonstration), sa corde passe au-dessus du profil
# de la route et le terrain recouvrait la chaussée (« herbe sur la route », recette du 7 novembre 2026).
# Même règle que le compilateur (`openride_compiler.terrain.clear_road`, 31 octobre) : la chaussée est
# échantillonnée tous les mètres, le long de l'axe et de bord à bord, et les sommets des triangles qui
# dépassent la route moins 5 cm sont abaissés juste ce qu'il faut ; les bords communs des tuiles reçoivent
# ensuite le plus bas des deux.

ROAD_CHECK_STEP_M = 1.0             # pas le long de la route et en travers de la chaussée


def road_samples(route: dict, half_width: float = ROAD_HALF_WIDTH_M,
                 step: float = ROAD_CHECK_STEP_M) -> list[tuple[float, float, float]]:
    """Points (x, z, altitude de la route) de la chaussée tous les `step` mètres le long de l'axe (altitude
    interpolée sur le segment) et en travers, de bord à bord."""
    xs, zs, alts = route["x"], route["z"], route["alt_m"]
    across = [-half_width + k * step for k in range(round(2.0 * half_width / step) + 1)]
    out: list[tuple[float, float, float]] = []
    carry = 0.0                     # abscisse du prochain point dans le segment courant
    for i in range(len(xs) - 1):
        dx, dz = xs[i + 1] - xs[i], zs[i + 1] - zs[i]
        seg = math.hypot(dx, dz)
        if seg <= 0.0:
            continue
        rx, rz = -dz / seg, dx / seg
        d = carry
        while d <= seg + 1e-9:
            f = d / seg
            cx, cz = xs[i] + f * dx, zs[i] + f * dz
            ca = alts[i] + f * (alts[i + 1] - alts[i])
            out.extend((cx + rx * o, cz + rz * o, ca) for o in across)
            d += step
        carry = d - seg
    return out


def clear_road(tiles: dict[tuple[int, int], list[float]], route: dict, cell: float = NEAR[1],
               sink: float = TERRAIN_BELOW_ROAD_M) -> int:
    """Abaisse sur place, juste ce qu'il faut, les sommets des triangles (découpage de terrain_tiles.gd
    `mesh_height_at` : diagonale de (i + 1, j) à (i, j + 1)) qui dépassent la chaussée moins `sink`, puis
    recopie le minimum sur les bords communs des tuiles. Rend le nombre de sommets abaissés."""
    cells = TILE_SAMPLES - 1
    lowered: set[tuple[int, int, int]] = set()
    for px, pz, pa in road_samples(route):
        fx, fz = px / cell, pz / cell
        gi, gj = math.floor(fx), math.floor(fz)
        u, v = fx - gi, fz - gj
        ti, tj = gi // cells, gj // cells
        g = tiles.get((ti, tj))
        if g is None:
            continue
        i, j = gi - ti * cells, gj - tj * cells
        if u + v <= 1.0:
            corners = ((i, j, 1.0 - u - v), (i + 1, j, u), (i, j + 1, v))
        else:
            corners = ((i + 1, j + 1, u + v - 1.0), (i, j + 1, 1.0 - u), (i + 1, j, 1.0 - v))
        idx = [(cj * TILE_SAMPLES + ci, w) for ci, cj, w in corners]
        top = pa - sink
        hp = sum(w * g[k] for k, w in idx)
        if hp <= top + 1e-4:
            continue
        # Chaque coin au-dessus de la limite descend en proportion de son dépassement (les coins déjà sous
        # la route ne bougent pas) ; abaisser ne remonte jamais un autre point : un seul passage suffit.
        lim = top - 1e-3
        over = sum(w * (g[k] - lim) for k, w in idx if g[k] > top)
        alpha = min((hp - lim) / over, 1.0) if over > 0.0 else 1.0
        for k, w in idx:
            if w > 0.0 and g[k] > top:
                g[k] = g[k] - alpha * (g[k] - lim)
                lowered.add((ti, tj, k))
    if lowered:
        _sync_edges(tiles)
    return len(lowered)


def _sync_edges(tiles: dict[tuple[int, int], list[float]]) -> None:
    """Bords communs de deux tuiles voisines ramenés au plus bas des deux (coins compris : deux passes)."""
    last = TILE_SAMPLES - 1
    for _ in range(2):
        for (ix, iz), g in tiles.items():
            e = tiles.get((ix + 1, iz))
            if e is not None:
                for j in range(TILE_SAMPLES):
                    m = min(g[j * TILE_SAMPLES + last], e[j * TILE_SAMPLES])
                    g[j * TILE_SAMPLES + last] = e[j * TILE_SAMPLES] = m
            s_ = tiles.get((ix, iz + 1))
            if s_ is not None:
                for i in range(TILE_SAMPLES):
                    m = min(g[last * TILE_SAMPLES + i], s_[i])
                    g[last * TILE_SAMPLES + i] = s_[i] = m


def build_tiles(route: dict, level: tuple[str, float, float, float],
                terrain: SyntheticTerrain | None = None) -> dict[tuple[int, int], list[float]]:
    """Tuiles d'un niveau, terrain proche dégagé sous la chaussée (`clear_road`). Les valeurs sont arrondies
    en float32 avant le garde-fou, comme dans le fichier, pour que la comparaison porte sur ce qui est écrit."""
    terrain = terrain or SyntheticTerrain(route)
    n = TILE_SAMPLES * TILE_SAMPLES
    tiles = {key: list(struct.unpack(f"<{n}f", struct.pack(f"<{n}f", *terrain.tile_values(level, *key))))
             for key in terrain.tiles_for(level)}
    if level[0] == NEAR[0]:
        clear_road(tiles, route, level[1])
    return tiles


def write_terrain(world: Path, route: dict) -> dict[str, list[list[int]]]:
    """Écrit terrain/near et terrain/far dans `world` ; renvoie les tuiles écrites par niveau."""
    terrain = SyntheticTerrain(route)
    written: dict[str, list[list[int]]] = {}
    for level in (NEAR, FAR):
        folder = world / "terrain" / level[0]
        folder.mkdir(parents=True, exist_ok=True)
        written[level[0]] = []
        for (ix, iz), values in sorted(build_tiles(route, level, terrain).items()):
            data = struct.pack(f"<{TILE_SAMPLES * TILE_SAMPLES}f", *values)
            (folder / f"tile_{ix}_{iz}.f32").write_bytes(data)
            written[level[0]].append([ix, iz])
    return written


def add_terrain_layer(world: Path) -> Path:
    """Ajoute la couche terrain synthétique à un `.world` existant et met le manifeste à jour."""
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    written = write_terrain(world, route)
    manifest_path = world / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["layers"]["terrain"] = {
        "present": True, "version": "1.0", "sources": ["synthetic"],
        "near_cell_m": int(NEAR[1]), "far_cell_m": int(FAR[1]),
        "road_half_width_m": ROAD_HALF_WIDTH_M,
        "tiles": {"near": written["near"], "far": written["far"]},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return world
