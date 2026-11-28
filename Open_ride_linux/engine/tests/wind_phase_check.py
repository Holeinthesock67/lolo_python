#!/usr/bin/env python3
"""Vitesse de la phase du vent sur une longue séance (lot EC10, revue E12-51).

Lit les colonnes `wind_phase`, `wind_strength` et `wind_gust` de la sonde de l'engine (`moteur.csv`, écrit avec
`--perf-probe`, scénario `vent_duree` de `sim_bench.py --probe`) et vérifie :

- que la phase avance à la vitesse prévue par le vent du moment (`wind_model.gd`, `phase_rate`), sans dérive entre
  le début et la fin de la séance ;
- qu'elle reste sous la vitesse maximale (2,0 × 1,6 s par s).

Affiche aussi, pour comparaison, la fréquence apparente des touffes d'herbe (0,9 Hz) avec l'ancienne formule des
shaders (`phase × fréquence × (1 + 0,6 × rafale)`) : c'est elle qui s'emballait avec la durée.

Usage : python engine/tests/wind_phase_check.py DOSSIER_OU_moteur.csv [--min-s 600]
Code de sortie 0 si tout est bon, 1 sinon (2 : pas de données).
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

RATE_MIN, RATE_MAX, GUST_GAIN = 0.4, 2.0, 0.6   # wind_model.gd
GRASS_HZ = 0.9                                  # grass_tufts.gd


def phase_rate(strength: float, gust: float) -> float:
    s = min(max(strength, 0.0), 1.0)
    g = min(max(gust, 0.0), 1.0)
    return (RATE_MIN + (RATE_MAX - RATE_MIN) * s) * (1.0 + GUST_GAIN * g)


def read_rows(path: Path) -> list[dict[str, float]]:
    files = [path] if path.is_file() else sorted(path.rglob("moteur.csv"))
    rows: list[dict[str, float]] = []
    for f in files:
        with f.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh, delimiter=";"):
                try:
                    rows.append({k: float(r[k]) for k in ("t_s", "wind_phase", "wind_strength", "wind_gust")})
                except (KeyError, TypeError, ValueError):
                    continue
        if rows:
            break
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path)
    ap.add_argument("--min-s", type=float, default=600.0, help="durée minimale mesurée (défaut 600 s)")
    a = ap.parse_args(argv)
    rows = read_rows(a.source)
    if len(rows) < 3:
        print("Pas de colonnes wind_phase dans la sonde (moteur.csv introuvable ou engine sans le lot EC10).")
        return 2
    samples = []   # (t, vitesse mesurée, vitesse prévue, fréquence apparente de l'herbe avec l'ancienne formule)
    for p, q in zip(rows, rows[1:]):
        dt = q["t_s"] - p["t_s"]
        if dt <= 0.2 or q["wind_phase"] < p["wind_phase"] - 1e-6:
            continue
        rate = (q["wind_phase"] - p["wind_phase"]) / dt
        expected = phase_rate(0.5 * (p["wind_strength"] + q["wind_strength"]), 0.5 * (p["wind_gust"] + q["wind_gust"]))
        old = GRASS_HZ * ((q["wind_phase"] * (1 + 0.6 * q["wind_gust"])) - (p["wind_phase"] * (1 + 0.6 * p["wind_gust"]))) / dt
        samples.append((q["t_s"], rate, expected, abs(old)))
    span = samples[-1][0] - samples[0][0] if samples else 0.0
    ok = True
    print(f"Séance mesurée : {span:.0f} s, {len(samples)} relevés")
    if span < a.min_s:
        print(f"[ÉCHEC] durée mesurée {span:.0f} s < {a.min_s:.0f} s")
        ok = False
    bound = RATE_MAX * (1 + GUST_GAIN)
    worst = max(s[1] for s in samples)
    print(f"[{'OK' if worst <= bound * 1.05 else 'ÉCHEC'}] avance maximale de la phase {worst:.2f} s/s (≤ {bound:.2f})")
    ok = ok and worst <= bound * 1.05
    t0 = samples[0][0]
    first = [s for s in samples if s[0] - t0 <= 120]
    last = [s for s in samples if samples[-1][0] - s[0] <= 120]
    for label, part in (("2 premières minutes", first), ("2 dernières minutes", last)):
        ratio = statistics.median(s[1] / s[2] for s in part if s[2] > 0)
        old_hz = statistics.median(s[3] for s in part)
        good = 0.8 <= ratio <= 1.25
        ok = ok and good
        print(f"[{'OK' if good else 'ÉCHEC'}] {label} : phase à {ratio:.2f} × la vitesse prévue par le vent ; "
              f"herbe avec l'ancienne formule : {old_hz:.1f} Hz (comparaison)")
    print("=== PHASE DU VENT CORRECTE" if ok else "=== PHASE DU VENT À REVOIR")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
