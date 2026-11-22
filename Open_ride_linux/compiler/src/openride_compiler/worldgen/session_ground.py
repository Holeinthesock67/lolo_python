"""Sol des tuiles de la balade réglé sur la route engagée (règle sol / route, 21 novembre 2026).

Le carré du cache règle son sol sur chacune de ses arêtes (`squares.square_relief`), mais l'engine dessine la route de
la balade : les arêtes mises bout à bout et rééchantillonnées tous les 10 m (`edge_profile.concat`), avec les virages
pris aux carrefours, le départ au milieu d'une arête et les boucles de retournement des impasses, que le carré ne
connaît pas. La balade a donc ses propres tuiles proches : copie de la tuile du carré, puis la même règle
(`road_ground.py`) appliquée à la route engagée telle que l'engine la dessine, avant que l'engine ne lise la tuile.

- Une tuile se règle quand elle arrive (avant d'être publiée), puis de nouveau dès que la route engagée change près
  d'elle, même si l'engine l'affiche déjà (22/11) : l'engine relit une tuile proche dont le fichier a changé et
  remplace son maillage quand le nouveau est prêt (`world_streamer.gd`, empreinte du fichier lu). Avant, une tuile à
  moins de 2 km du cycliste attendait qu'il s'éloigne ; il roulait dessus avec le sol de l'ancienne route (banc du lac
  d'Annecy : talus sans appui jusqu'à 3,2 m).
- Chaque réglage repart de la tuile du carré : un choix de carrefour qui retire une route rend aussi son sol.
- Un sommet partagé avec une tuile voisine qui n'est pas réglée en même temps garde la valeur de la voisine (bords
  communs identiques, pas de fente) ; les autres sommets compensent.
- Contrôle : après chaque réglage, sol au-dessus de la chaussée et pieds de talus sans appui comptés sur la route
  engagée, sur tous les points des tuiles réglées, bords figés compris (rendus par `road_ground.fit`, `check` relit les
  tuiles écrites, comme `controle_sol_route`), dans les statistiques de la séance et le
  journal.

Repère de la séance (x vers l'est, z vers le sud, tuile (ix, iz) de [1000 ix ; 1000 (ix + 1)] × [1000 iz ; …]).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import numpy as np

from .. import constants as C
from .. import road_ground as RG

TILE_M = 1000.0
REACH_M = RG.FOOT_OFFSET_M + 2 * TILE_M / (C.TILE_SAMPLES - 1)   # points de la règle qui touchent une tuile
Key = tuple[int, int]


def route_spans(legs: Iterable, edges: dict) -> list[tuple[float, float, str]]:
    """Ponts et tunnels de la route engagée, en abscisse de la route. Une étape (`process.Leg`) parcourt son arête
    dans un sens, éventuellement à partir du milieu (départ) ou précédée d'une boucle de retournement : dans les
    deux cas son profil est plus court ou plus long que l'arête du même écart, au début."""
    out = []
    for leg in legs:
        e = edges.get(leg.edge_id)
        if e is None or not e.spans:
            continue
        le, lp = float(e.length_m), float(leg.profile.length_m)
        shift = lp - le
        for a, b, kind in e.spans:
            lo, hi = (a, b) if leg.forward else (le - b, le - a)
            lo, hi = max(lo + shift, 0.0), min(hi + shift, lp)
            if hi > lo:
                out.append((leg.s0 + lo, leg.s0 + hi, kind))
    return out


def route_corridor(route: dict, spans: list[tuple[float, float, str]]):
    """Points de la règle (chaussée, pieds de talus) de la route engagée (colonnes de `process._route_columns`)."""
    upper, lower = RG.corridor_s(route["x"], route["z"], route["alt_m"], route["heading_deg"],
                                 s=np.asarray(route["s"], float),
                                 open_spans=[sp for sp in spans if sp[2] == "tunnel"], ground_spans=spans)
    return upper[:3], RG.drop_covered_feet(upper, lower, upper[3], lower[3])


def _near(points, keys: Iterable[Key], margin: float = REACH_M):
    px, pz, lim = (np.asarray(a, float) for a in points)
    sel = np.zeros(len(px), bool)
    for ix, iz in keys:
        sel |= ((px >= ix * TILE_M - margin) & (px <= (ix + 1) * TILE_M + margin)
                & (pz >= iz * TILE_M - margin) & (pz <= (iz + 1) * TILE_M + margin))
    return px[sel], pz[sel], lim[sel]


def touched_tiles(points) -> set[Key]:
    """Tuiles dont un sommet porte un point de la règle (chaussée ou pied de talus)."""
    out: set[Key] = set()
    for px, pz, _ in points:
        px, pz = np.asarray(px, float), np.asarray(pz, float)
        for d in (-REACH_M, REACH_M):
            for e in (-REACH_M, REACH_M):
                out |= set(zip(np.floor((px + d) / TILE_M).astype(int).tolist(),
                               np.floor((pz + e) / TILE_M).astype(int).tolist()))
    return out


def tile_distance(key: Key, x: float, z: float) -> float:
    ix, iz = key
    dx = max(ix * TILE_M - x, 0.0, x - (ix + 1) * TILE_M)
    dz = max(iz * TILE_M - z, 0.0, z - (iz + 1) * TILE_M)
    return float(np.hypot(dx, dz))


def _read(path: Path) -> np.ndarray:
    n = C.TILE_SAMPLES
    return np.fromfile(path, dtype="<f4").reshape(n, n).astype(float)


def _write(path: Path, y: np.ndarray) -> None:
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_bytes(np.ascontiguousarray(y, dtype="<f4").tobytes())
    os.replace(tmp, path)      # remplace aussi le lien vers le cache : la tuile du carré n'est jamais touchée


class SessionGround:
    """Tuiles proches de la balade : source (tuile du carré, cache) et copie réglée (dossier de la séance)."""

    def __init__(self, session_dir: Path) -> None:
        self.dir = Path(session_dir) / "terrain" / "near"
        self.sources: dict[Key, Path] = {}

    def path(self, key: Key) -> Path:
        return self.dir / f"tile_{key[0]}_{key[1]}.f32"

    def add(self, key: Key, source: Path) -> None:
        self.sources[key] = Path(source)

    def fit(self, todo: Iterable[Key], upper, lower) -> dict:
        """Règle les tuiles `todo` (connues) à partir de leur source ; bords communs avec les autres tuiles gardés."""
        todo = {k for k in todo if k in self.sources}
        if not todo:
            return {"tiles": 0, "lowered": 0, "raised": 0, "left_low": 0, "over": 0, "over_max_m": 0.0, "short": 0, "short_max_m": 0.0}
        tiles: dict[Key, np.ndarray] = {}
        frozen: set[Key] = set()
        pristine = {}
        for k in todo:
            tiles[k] = _read(self.sources[k])
            pristine[k] = tiles[k].copy()
        for ix, iz in todo:
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    n = (ix + dx, iz + dz)
                    if n in tiles or n not in self.sources or not self.path(n).is_file():
                        continue
                    tiles[n] = _read(self.path(n))
                    frozen.add(n)
        cells = C.TILE_SAMPLES - 1
        for (ix, iz) in todo:                       # bords communs : valeur de la voisine déjà en place
            y = tiles[(ix, iz)]
            for (nx, nz) in frozen:
                dx, dz = nx - ix, nz - iz
                if max(abs(dx), abs(dz)) != 1:
                    continue
                g = tiles[(nx, nz)]
                cols = {-1: (0, cells), 0: (slice(None), slice(None)), 1: (cells, 0)}[dx]
                rows = {-1: (0, cells), 0: (slice(None), slice(None)), 1: (cells, 0)}[dz]
                y[rows[0], cols[0]] = g[rows[1], cols[1]]
        gather, scatter, step = RG.tiles_access(tiles, TILE_M)

        def fixed(gi, gj):
            ti, tj = gi // cells, gj // cells
            li, lj = gi - ti * cells, gj - tj * cells
            out = np.zeros(len(gi), bool)
            for k in frozen:            # sommet d'une tuile figée, bord commun compris
                kx, kz = k
                out |= ((ti == kx) | ((li == 0) & (ti - 1 == kx))) & ((tj == kz) | ((lj == 0) & (tj - 1 == kz)))
            return out

        res = RG.fit(gather, scatter, step, _near(upper, todo), _near(lower, todo), fixed=fixed if frozen else None,
                     rounds=RG.TILE_ROUNDS)
        written = 0
        for k in todo:      # tuile inchangée : le lien vers le carré du cache reste (ou revient)
            p = self.path(k)
            if np.array_equal(tiles[k], pristine[k]):
                if not p.is_symlink():
                    tmp = p.with_name(f".{p.name}.lien-{os.getpid()}")
                    tmp.unlink(missing_ok=True)
                    tmp.symlink_to(self.sources[k])
                    os.replace(tmp, p)
                continue
            _write(p, tiles[k])
            written += 1
        return {"tiles": written, **res}

    def check(self, upper, lower, keys: Iterable[Key] | None = None) -> dict:
        """Contrôle des tuiles de la séance (toutes, ou `keys`) contre la route engagée (`RG.residual`)."""
        keys = [k for k in (self.sources if keys is None else keys) if self.path(k).is_file()]
        tiles = {k: _read(self.path(k)) for k in keys}
        gather, _, step = RG.tiles_access(tiles, TILE_M)
        return RG.residual(gather, step, _near(upper, keys, 0.0), _near(lower, keys, 0.0))
