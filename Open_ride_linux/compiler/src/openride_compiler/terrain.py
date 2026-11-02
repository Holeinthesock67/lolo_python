"""Couche terrain : tuiles d'altitude proches (10 m) et lointaines (50 m) (format §5, lot B2 §3.4).

- Tuile `tile_<ix>_<iz>.f32` : 101 × 101 `float32` petit-boutistes rangés par ligne ;
  l'échantillon (i, j) est en x = ix·T + i·maille, z = iz·T + j·maille. Bords partagés.
- Seules les tuiles qui touchent la bande autour de la route sont écrites
  (± 400 m pour le niveau proche, ± 5 km pour le lointain).
- Chaque échantillon est ramené en latitude et longitude (projection inverse du repère),
  puis interrogé par lots auprès du fournisseur d'altitude.
- Niveau proche seulement : fondu avec la route. `d` est la distance à l'axe moins la
  demi-largeur de chaussée ; y = y_route − 0,05 pour d ≤ 4 m, y = y_mnt pour d ≥ 25 m,
  smoothstep entre les deux. Le point de route le plus proche est cherché avec un cKDTree.
- Garde-fou de la chaussée (demande du 31 octobre : « l'herbe ne doit pas passer par-dessus la
  route ») : après le fondu, le maillage proche (triangles de 10 m, même découpage que l'engine)
  est contrôlé en travers de la chaussée tous les mètres ; un triangle qui dépasserait la route
  moins 5 cm a ses sommets abaissés (`clear_road`). Le fondu seul ne suffit pas dans une épingle,
  un aller-retour ou un croisement : un sommet fondu sur une portion de route haute peut tenir un
  triangle qui recouvre la portion basse. Vaut pour tout parcours compilé : trace importée,
  parcours généré (worldgen) ou recette.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from . import constants as C
from .cache import Log, stderr_log
from .elevation import ElevationProvider
from .frame import LocalFrame

N = C.TILE_SAMPLES
TILE_BYTES = N * N * 4
TILES_PER_BATCH = 64
NEIGHBOURS = 4          # sommets de route candidats par échantillon (voisins des épingles compris)


@dataclass(frozen=True)
class Level:
    name: str           # « near » ou « far »
    cell_m: int
    tile_m: int
    band_m: float
    blend: bool


NEAR = Level("near", C.NEAR_CELL_M, C.NEAR_TILE_M, C.NEAR_BAND_M, True)
FAR = Level("far", C.FAR_CELL_M, C.FAR_TILE_M, C.FAR_BAND_M, False)
LEVELS = (NEAR, FAR)


def tile_filename(ix: int, iz: int) -> str:
    return f"tile_{ix}_{iz}.f32"


# --- axe de la route --------------------------------------------------------------------------

class RouteAxis:
    """Distance horizontale à l'axe de la route (polyligne) et altitude au point le plus proche."""

    def __init__(self, x, z, alt) -> None:
        self.x = np.asarray(x, dtype=float)
        self.z = np.asarray(z, dtype=float)
        self.alt = np.asarray(alt, dtype=float)
        self.n = len(self.x)
        self.tree = cKDTree(np.column_stack((self.x, self.z)))

    def nearest(self, px: np.ndarray, pz: np.ndarray, max_dist: float) -> tuple[np.ndarray, np.ndarray]:
        """(distance à l'axe, altitude de la route au point le plus proche) ; inf / NaN au-delà de max_dist."""
        px = np.asarray(px, dtype=float).ravel()
        pz = np.asarray(pz, dtype=float).ravel()
        dist = np.full(px.shape, np.inf)
        y = np.full(px.shape, np.nan)
        # Les sommets sont espacés de 10 m au plus : un point à moins de max_dist de l'axe
        # a un sommet à moins de max_dist + 10 m.
        k = min(NEIGHBOURS, self.n)
        _, idx = self.tree.query(np.column_stack((px, pz)), k=k,
                                 distance_upper_bound=max_dist + C.DS_M)
        idx = idx.reshape(len(px), k)
        for col in range(k):
            j = idx[:, col]
            ok = j < self.n
            if not ok.any():
                continue
            jj = j[ok]
            for a, b in ((np.maximum(jj - 1, 0), jj), (jj, np.minimum(jj + 1, self.n - 1))):
                d, yy = self._segment(px[ok], pz[ok], a, b)
                better = d < dist[ok]
                sel = np.flatnonzero(ok)[better]
                dist[sel] = d[better]
                y[sel] = yy[better]
        far = dist > max_dist
        dist[far] = np.inf
        y[far] = np.nan
        return dist, y

    def _segment(self, px, pz, a, b) -> tuple[np.ndarray, np.ndarray]:
        ax, az, bx, bz = self.x[a], self.z[a], self.x[b], self.z[b]
        vx, vz = bx - ax, bz - az
        ll = vx * vx + vz * vz
        with np.errstate(invalid="ignore", divide="ignore"):
            t = np.where(ll > 0, ((px - ax) * vx + (pz - az) * vz) / np.where(ll > 0, ll, 1.0), 0.0)
        t = np.clip(t, 0.0, 1.0)
        cx, cz = ax + t * vx, az + t * vz
        return np.hypot(px - cx, pz - cz), self.alt[a] + t * (self.alt[b] - self.alt[a])


# --- tuiles -----------------------------------------------------------------------------------

def select_tiles(x, z, level: Level) -> list[tuple[int, int]]:
    """Tuiles dont le rectangle est à moins de `band_m` d'au moins un point de route."""
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    t = level.tile_m
    reach = int(np.ceil(level.band_m / t))
    bx = np.floor(x / t).astype(int)
    bz = np.floor(z / t).astype(int)
    found: set[tuple[int, int]] = set()
    for ox in range(-reach, reach + 1):
        for oz in range(-reach, reach + 1):
            ix, iz = bx + ox, bz + oz
            dx = np.maximum(np.maximum(ix * t - x, 0.0), x - (ix + 1) * t)
            dz = np.maximum(np.maximum(iz * t - z, 0.0), z - (iz + 1) * t)
            near = np.hypot(dx, dz) <= level.band_m
            found.update(zip(ix[near].tolist(), iz[near].tolist()))
    return sorted(found)


def tile_coords(ix: int, iz: int, level: Level) -> tuple[np.ndarray, np.ndarray]:
    """Coordonnées (x, z) des 101 × 101 échantillons, tableau [ligne j, colonne i].

    Calcul en entiers : les bords communs à deux tuiles ont exactement les mêmes coordonnées.
    """
    k = np.arange(N, dtype=np.int64) * level.cell_m
    xs = (ix * level.tile_m + k).astype(float)
    zs = (iz * level.tile_m + k).astype(float)
    gx, gz = np.meshgrid(xs, zs)
    return gx, gz


def blend(y_mnt: np.ndarray, dist_axis: np.ndarray, y_route: np.ndarray,
          half_width: float = C.ROAD_HALF_WIDTH_M) -> np.ndarray:
    """Fondu route / MNT. Sans MNT (NaN) près de la route, l'altitude de la route est gardée."""
    y = np.array(y_mnt, dtype=float, copy=True)
    d = dist_axis - half_width
    near = np.isfinite(dist_axis) & (d < C.BLEND_OUTER_M)
    if not near.any():
        return y
    t = np.clip((d[near] - C.BLEND_INNER_M) / (C.BLEND_OUTER_M - C.BLEND_INNER_M), 0.0, 1.0)
    w = t * t * (3.0 - 2.0 * t)
    road = y_route[near] - C.ROAD_SINK_M
    mnt = y[near]
    y[near] = np.where(np.isfinite(mnt), (1.0 - w) * road + w * mnt, road)
    return y


def build_level(route: dict, frame: LocalFrame, provider: ElevationProvider, level: Level,
                log: Log = stderr_log) -> dict[tuple[int, int], np.ndarray]:
    """Grilles float32 (101 × 101) de toutes les tuiles d'un niveau."""
    x, z = np.asarray(route["x"], float), np.asarray(route["z"], float)
    keys = select_tiles(x, z, level)
    axis = RouteAxis(x, z, route["alt_m"]) if level.blend else None
    log(f"terrain {level.name} : {len(keys)} tuile(s) de {level.tile_m} m, maille {level.cell_m} m")
    out: dict[tuple[int, int], np.ndarray] = {}
    for start in range(0, len(keys), TILES_PER_BATCH):
        batch = keys[start:start + TILES_PER_BATCH]
        grids = [tile_coords(ix, iz, level) for ix, iz in batch]
        gx = np.concatenate([g[0].ravel() for g in grids])
        gz = np.concatenate([g[1].ravel() for g in grids])
        lat, lon = frame.to_latlon(gx, gz)
        y = np.asarray(provider.elevations(lat, lon), dtype=float)
        if axis is not None:
            dist, y_route = axis.nearest(gx, gz, C.ROAD_HALF_WIDTH_M + C.BLEND_OUTER_M)
            y = blend(y, dist, y_route)
        y32 = y.astype("<f4").reshape(len(batch), N, N)
        for k, key in enumerate(batch):
            out[key] = y32[k]
    if level.blend:
        lowered = clear_road(out, x, z, route["alt_m"], level)
        if lowered:
            log(f"terrain {level.name} : {lowered} sommet(s) abaissé(s) sous la chaussée (épingles, croisements)")
    return out


# --- garde-fou de la chaussée -----------------------------------------------------------------

ROAD_CHECK_STEP_M = 1.0     # pas le long de la route et en travers de la chaussée


def road_samples(x, z, alt, half_width: float = C.ROAD_HALF_WIDTH_M,
                 step: float = ROAD_CHECK_STEP_M) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Points de la chaussée (x, z) tous les `step` mètres le long de l'axe et en travers, de bord à
    bord, avec l'altitude de la route à leur hauteur (interpolée le long du segment)."""
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    alt = np.asarray(alt, dtype=float)
    if len(x) < 2:
        return np.empty(0), np.empty(0), np.empty(0)
    seg = np.hypot(np.diff(x), np.diff(z))
    s = np.concatenate(([0.0], np.cumsum(seg)))
    keep = np.concatenate(([True], seg > 0))
    s, x, z, alt = s[keep], x[keep], z[keep], alt[keep]
    if len(s) < 2:
        return np.empty(0), np.empty(0), np.empty(0)
    sv = np.arange(0.0, s[-1] + 1e-9, step)
    cx, cz, ca = np.interp(sv, s, x), np.interp(sv, s, z), np.interp(sv, s, alt)
    k = np.clip(np.searchsorted(s, sv, side="right") - 1, 0, len(s) - 2)
    dx, dz = x[k + 1] - x[k], z[k + 1] - z[k]
    ln = np.hypot(dx, dz)
    rx, rz = -dz / ln, dx / ln          # normale au segment (côté sans importance : bord à bord)
    offs = np.arange(-half_width, half_width + 1e-9, step)
    px = (cx[:, None] + rx[:, None] * offs[None, :]).ravel()
    pz = (cz[:, None] + rz[:, None] * offs[None, :]).ravel()
    pa = np.repeat(ca, len(offs))
    return px, pz, pa


def _triangles(px, pz, level: Level):
    """Tuile, sommets (i, j) des trois coins et poids du triangle du maillage qui contient chaque point
    (découpage de terrain_tiles.gd `mesh_height_at` : diagonale de (i + 1, j) à (i, j + 1))."""
    cells = C.TILE_SAMPLES - 1
    fx = np.asarray(px, dtype=float) / level.cell_m
    fz = np.asarray(pz, dtype=float) / level.cell_m
    gi = np.floor(fx).astype(np.int64)
    gj = np.floor(fz).astype(np.int64)
    u, v = fx - gi, fz - gj
    ti, tj = np.floor_divide(gi, cells), np.floor_divide(gj, cells)
    i, j = gi - ti * cells, gj - tj * cells
    low = u + v <= 1.0
    # coins (di, dj) et poids : bas (a, b, c) ou haut (d, c, b)
    corners = np.where(low[:, None], np.array([[0, 0, 1, 0, 0, 1]]), np.array([[1, 1, 0, 1, 1, 0]]))
    w = np.where(low[:, None], np.column_stack((1.0 - u - v, u, v)),
                 np.column_stack((u + v - 1.0, 1.0 - u, 1.0 - v)))
    return ti, tj, i, j, corners, w


def terrain_excess(tiles: dict[tuple[int, int], np.ndarray], x, z, alt, level: Level = None,
                   sink: float = C.ROAD_SINK_M) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Dépassement (m) du maillage `tiles` au-dessus de la chaussée moins `sink`, aux points de
    `road_samples` couverts par une tuile sans NaN : (excès, x, z). Positif : terrain trop haut."""
    level = level or NEAR
    px, pz, pa = road_samples(x, z, alt)
    if len(px) == 0:
        return np.empty(0), px, pz
    ti, tj, i, j, corners, w = _triangles(px, pz, level)
    h = np.full(len(px), np.nan)
    for key in set(zip(ti.tolist(), tj.tolist())):
        g = tiles.get(key)
        if g is None:
            continue
        sel = np.flatnonzero((ti == key[0]) & (tj == key[1]))
        acc = np.zeros(len(sel))
        for c in range(3):
            acc += w[sel, c] * g[j[sel] + corners[sel, 2 * c + 1], i[sel] + corners[sel, 2 * c]]
        h[sel] = acc
    ok = np.isfinite(h)
    return (h - (pa - sink))[ok], px[ok], pz[ok]


def clear_road(tiles: dict[tuple[int, int], np.ndarray], x, z, alt, level: Level = None,
               sink: float = C.ROAD_SINK_M) -> int:
    """Abaisse (sur place), juste ce qu'il faut, les sommets des triangles qui dépassent la chaussée moins `sink`, puis
    recopie le minimum sur les bords communs des tuiles (bords toujours identiques). Rend le nombre
    de sommets abaissés. Abaisser ne remonte jamais un autre point : un seul passage suffit."""
    level = level or NEAR
    px, pz, pa = road_samples(x, z, alt)
    if len(px) == 0:
        return 0
    ti, tj, i, j, corners, w = _triangles(px, pz, level)
    limit = pa - sink
    lowered: set[tuple[int, int, int, int]] = set()
    for key in set(zip(ti.tolist(), tj.tolist())):
        g = tiles.get(key)
        if g is None:
            continue
        sel = np.flatnonzero((ti == key[0]) & (tj == key[1]))
        h = np.zeros(len(sel))
        for c in range(3):
            h += w[sel, c] * g[j[sel] + corners[sel, 2 * c + 1], i[sel] + corners[sel, 2 * c]]
        bad = sel[np.isfinite(h) & (h > limit[sel] + 1e-4)]
        for p in bad.tolist():
            # Abaissement juste suffisant : chaque coin au-dessus de la limite descend en proportion de
            # son dépassement (les coins déjà sous la route ne bougent pas), recalculé avec les
            # sommets déjà abaissés par les points précédents.
            vs = [(j[p] + corners[p, 2 * c + 1], i[p] + corners[p, 2 * c], w[p, c]) for c in range(3)]
            hp = sum(wc * float(g[vj, vi]) for vj, vi, wc in vs)
            top = float(limit[p])
            lim = top - 1e-3
            if not np.isfinite(hp) or hp <= top + 1e-4:
                continue
            over = sum(wc * (float(g[vj, vi]) - lim) for vj, vi, wc in vs if float(g[vj, vi]) > top)
            alpha = min((hp - lim) / over, 1.0) if over > 0 else 1.0
            for vj, vi, wc in vs:
                gv = float(g[vj, vi])
                if wc > 0 and gv > top:
                    g[vj, vi] = np.float32(gv - alpha * (gv - lim))
                    lowered.add((key[0], key[1], int(vi), int(vj)))
    if lowered:
        _sync_edges(tiles)
    return len(lowered)


def _sync_edges(tiles: dict[tuple[int, int], np.ndarray]) -> None:
    """Bords communs de deux tuiles voisines ramenés au plus bas des deux (coins compris : deux passes)."""
    last = C.TILE_SAMPLES - 1
    for _ in range(2):
        for (ix, iz), g in tiles.items():
            e = tiles.get((ix + 1, iz))
            if e is not None:
                m = np.fmin(g[:, last], e[:, 0])
                g[:, last] = m
                e[:, 0] = m
            s_ = tiles.get((ix, iz + 1))
            if s_ is not None:
                m = np.fmin(g[last, :], s_[0, :])
                g[last, :] = m
                s_[0, :] = m


def build_terrain(route: dict, frame: LocalFrame, provider: ElevationProvider,
                  log: Log = stderr_log) -> dict[str, dict[tuple[int, int], np.ndarray]]:
    return {level.name: build_level(route, frame, provider, level, log) for level in LEVELS}


def terrain_manifest(tiles: dict[str, dict[tuple[int, int], np.ndarray]],
                     provider: ElevationProvider) -> dict:
    """Bloc `layers.terrain` du manifeste (format §5 et §11, ajouts 1.1 : `native_resolution_m`, `tiles`)."""
    return {
        "present": True,
        "version": C.TERRAIN_VERSION,
        "sources": [provider.name],
        "native_resolution_m": provider.native_resolution_m,
        "near_cell_m": C.NEAR_CELL_M,
        "far_cell_m": C.FAR_CELL_M,
        "road_half_width_m": C.ROAD_HALF_WIDTH_M,
        "tiles": {level: [[ix, iz] for ix, iz in sorted(grids)] for level, grids in tiles.items()},
    }


def write_terrain(folder: Path, tiles: dict[str, dict[tuple[int, int], np.ndarray]]) -> None:
    """Écrit `folder/near/…` et `folder/far/…` (folder est le dossier `terrain` ou son temporaire)."""
    for level, grids in tiles.items():
        d = Path(folder) / level
        d.mkdir(parents=True, exist_ok=True)
        for (ix, iz), grid in grids.items():
            (d / tile_filename(ix, iz)).write_bytes(np.ascontiguousarray(grid, dtype="<f4").tobytes())


def read_tile(path: Path) -> np.ndarray:
    return np.frombuffer(Path(path).read_bytes(), dtype="<f4").reshape(N, N)


def replace_terrain_dir(world: Path, tiles: dict[str, dict[tuple[int, int], np.ndarray]]) -> None:
    """Remplace `world/terrain` de façon atomique : dossier temporaire voisin, puis renommage."""
    world = Path(world)
    final = world / "terrain"
    tmp = world / f".terrain.tmp-{os.getpid()}"
    old = world / f".terrain.old-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        write_terrain(tmp, tiles)
        if final.exists():
            final.rename(old)
            try:
                tmp.rename(final)
            except BaseException:
                old.rename(final)
                raise
            shutil.rmtree(old, ignore_errors=True)
        else:
            tmp.rename(final)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
