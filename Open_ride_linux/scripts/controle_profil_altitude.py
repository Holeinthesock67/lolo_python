#!/usr/bin/env python3
"""Contrôle du profil d'altitude des balades du monde ouvert sur le PC (21 novembre 2026, garde-fou d'altitude).

Demande du propriétaire : protéger le monde ouvert contre les défauts des sources d'altitude (rampes brutales, pics,
trous, marches). Le garde-fou (`compiler/src/openride_compiler/worldgen/altitude_guard.py`) corrige le profil des
arêtes à la génération ; ce script relit la route engagée telle que le jeu l'a roulée (`route/part_*.json` des
balades `ow-*.world`) et liste :

- les **défauts graves** : pente au-delà de ± 15 % sur un pas de 10 m, changement de pente de plus de
  `GRAVE_CURVE_PCT` (2 × 4 %) d'un pas au suivant (le constat du banc `ea1_lac` : 0 → 21 % en 10 m), altitude
  absente ; **saut** de la route (plus de `JUMP_TOL_M` de géométrie de plus que le pas en s : arête courte fondue
  dans un carrefour et sautée, constat du banc de #961 du 22 novembre) ;
- les **écarts** à la règle stricte (changement de pente de 4 % à 8 %) : attendus seulement dans les carrefours où
  la route tourne sur un flanc (deux arêtes de directions différentes), comptés pour information.

    python3 scripts/controle_profil_altitude.py --out DOSSIER --seances DOSSIER [--dernieres N] [MONDE.world ...]

Bancs : `--seances` est le dossier `seances/` du cache **séparé** du banc, jamais `~/OpenRide/Cache/monde`. Écrit
`DOSSIER/resume.txt` (une ligne par balade, pires points avec s en m). Code de sortie : 0 si aucun défaut grave,
1 sinon, 2 si rien à contrôler. Lecture seule.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "compiler" / "src"))

import numpy as np  # noqa: E402

from openride_compiler.worldgen import altitude_guard as AG  # noqa: E402

GRAVE_CURVE_PCT = 2.0 * AG.CURVE_MAX_PCT
WORST_SHOWN = 8
JUMP_TOL_M = 0.5


def route_profile(world: Path) -> tuple[np.ndarray, np.ndarray]:
    """(s, alt) de la route engagée, parties mises bout à bout (bord commun non doublé)."""
    s, alt, _x, _z = route_columns(world)
    return s, alt


def route_columns(world: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(s, alt, x, z) de la route engagée (x, z en NaN si une partie ne les donne pas)."""
    parts = sorted((world / "route").glob("part_*.json"), key=lambda p: int(p.stem.split("_")[1]))
    s_all: list[float] = []
    a_all: list[float] = []
    x_all: list[float] = []
    z_all: list[float] = []
    for p in parts:
        d = json.loads(p.read_text(encoding="utf-8"))
        alt = [float("nan") if v is None else float(v) for v in d["alt_m"]]
        n = len(alt)
        s0, ds, length = float(d.get("s0_m", 0.0)), float(d.get("ds_m", 10.0)), float(d["length_m"])
        s = [s0 + min(i * ds, length) for i in range(n)]
        start = 1 if s_all and abs(s[0] - s_all[-1]) < 1e-6 else 0
        s_all += s[start:]
        a_all += alt[start:]
        x_all += [float(v) for v in d.get("x", [float("nan")] * n)][start:]
        z_all += [float(v) for v in d.get("z", [float("nan")] * n)][start:]
    return np.asarray(s_all), np.asarray(a_all), np.asarray(x_all), np.asarray(z_all)


def jumps(s: np.ndarray, x: np.ndarray, z: np.ndarray) -> list:
    """Sauts de la route : pas dont la géométrie dépasse l'avancée en s (une corde est toujours plus courte)."""
    if len(s) < 2:
        return []
    extra = np.hypot(np.diff(x), np.diff(z)) - np.diff(s)
    return [(float(s[k]), "saut", float(extra[k])) for k in np.flatnonzero(extra > JUMP_TOL_M)]


def classify(s: np.ndarray, alt: np.ndarray) -> tuple[list, list]:
    """(défauts graves, écarts à la règle stricte), chacun en (s, nature, valeur %)."""
    strict = AG.check(alt, s)
    grave = [d for d in strict if d[1] in ("trou", "pente") or (d[1] == "cassure" and abs(d[2]) > GRAVE_CURVE_PCT)]
    minor = [d for d in strict if d not in grave]
    return grave, minor


def latest_sessions(seances: Path, n: int) -> list[Path]:
    if n <= 0 or not seances.is_dir():
        return []
    found = [p for p in seances.glob("ow-*.world") if any((p / "route").glob("part_*.json"))]
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found[:n]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mondes", nargs="*", type=Path, help="balades ow-*.world à contrôler")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seances", type=Path, help="dossier seances/ du cache séparé du banc")
    ap.add_argument("--dernieres", type=int, default=3)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    worlds = list(a.mondes) or (latest_sessions(a.seances, a.dernieres) if a.seances else [])
    if not worlds:
        why = f"rien à contrôler : aucune balade ow-*.world avec route/part_*.json dans {a.seances}"
        (a.out / "resume.txt").write_text(why + "\n", encoding="utf-8")
        print(why, file=sys.stderr)
        return 2
    lines = [f"règle : pente ≤ {AG.GRADE_MAX_PCT:.0f} %, changement de pente ≤ {AG.CURVE_MAX_PCT:.0f} % par 10 m "
             f"(grave au-delà de {GRAVE_CURVE_PCT:.0f} %)"]
    graves = 0
    for w in worlds:
        s, alt, x, z = route_columns(w)
        grave, minor = classify(s, alt)
        grave += jumps(s, x, z)
        graves += len(grave)
        g = 100.0 * np.diff(alt) / np.maximum(np.diff(s), 1e-6)
        worst = float(np.nanmax(np.abs(np.diff(g)))) if len(g) > 1 else 0.0
        lines.append(f"{w.name} : {s[-1] / 1000:.1f} km, {len(grave)} défaut(s) grave(s), {len(minor)} écart(s), "
                     f"pire changement de pente {worst:.1f} % en 10 m")
        for d in sorted(grave, key=lambda d: -abs(d[2]) if np.isfinite(d[2]) else 0)[:WORST_SHOWN]:
            unit = "m" if d[1] == "saut" else "%"
            lines.append(f"  [GRAVE] s = {d[0]:.0f} m : {d[1]} {d[2]:+.1f} {unit}")
        for d in sorted(minor, key=lambda d: -abs(d[2]))[:3]:
            lines.append(f"  [écart] s = {d[0]:.0f} m : {d[1]} {d[2]:+.1f} %")
    lines.append(f"résultat : {len(worlds)} balade(s), {graves} défaut(s) grave(s)")
    (a.out / "resume.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if graves else 0


if __name__ == "__main__":
    sys.exit(main())
