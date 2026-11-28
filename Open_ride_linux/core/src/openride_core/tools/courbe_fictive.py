"""Séances fabriquées d'un cycliste fictif (FTP 250 W) pour l'écran « Ma puissance » (série PP, lot PP3).

    python -m openride_core.tools.courbe_fictive DOSSIER_JOURNAUX [--now TS]

Écrit dans DOSSIER_JOURNAUX une dizaine de journaux `.jsonl` à 1 Hz répartis sur 5 mois : sprints du Grand
Prix, élimination, col, longue sortie, séance de seuil en ERG et course de 20 min, d'après le modèle à deux
paramètres CP = 250 W, W' = 20 kJ (plus des pointes de sprint). Sert au banc des menus, aux maquettes et
aux tests : aucune donnée réelle, rien n'est lu dans le dossier personnel. Les séances sont datées par
rapport à `--now` (défaut : maintenant), pour que les fenêtres de 6 mois et 6 semaines aient toujours de quoi
montrer.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

CP_W, WPRIME_J = 250.0, 20000.0
DAY = 86400.0


def model_w(seconds: float) -> float:
    """Puissance tenable sur `seconds` selon le modèle CP / W' du cycliste fictif."""
    return CP_W + WPRIME_J / seconds


# (nom, jours avant maintenant, parcours, entraînement, blocs [(durée s, watts, ERG)])
SESSIONS = (
    ("gp_sprints", 150, "gp-ligne", None, [(600, 160, False), (5, 880, False), (300, 150, False), (15, 720, False),
                                           (600, 170, False), (30, 560, False), (600, 160, False)]),
    ("col_long", 120, "demo", None, [(900, 170, False), (1200, model_w(1200) - 3, False), (600, 150, False)]),
    ("velodrome", 95, "velodrome-250", None, [(600, 160, False), (60, 430, False), (300, 140, False),
                                              (120, model_w(120) - 20, False), (600, 150, False)]),
    ("seuil_erg", 70, "demo", "seuil_3x15", [(600, 150, True), (900, 255, True), (300, 150, True),
                                             (900, 255, True), (300, 150, True), (900, 255, True), (300, 120, True)]),
    ("route_longue", 60, "demo", None, [(3600, 220, False), (300, 150, False)]),
    ("col_5min", 35, "demo", None, [(900, 165, False), (300, model_w(300) - 8, False), (900, 160, False),
                                    (180, model_w(180) - 12, False), (600, 150, False)]),
    ("cotes", 25, "demo", None, [(900, 165, False), (480, model_w(480) - 6, False), (900, 160, False),
                                 (720, model_w(720) - 5, False), (60, 150, False)]),
    ("course_20", 8, "demo", None, [(900, 165, False), (1200, model_w(1200) - 2, False), (600, 150, False)]),
    ("sprint_court", 4, "gp-ligne", None, [(600, 160, False), (5, 820, False), (300, 150, False),
                                           (60, 400, False), (600, 150, False)]),
)


def write_sessions(journal_dir: Path, now: float | None = None) -> list[Path]:
    """Écrit les séances fabriquées dans `journal_dir` ; renvoie leurs chemins."""
    now = time.time() if now is None else now
    journal_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for name, ago, route, workout, blocks in SESSIONS:
        start = round(now - ago * DAY)
        stamp = time.strftime("%Y-%m-%d_%H-%M", time.localtime(start))
        lines = [{"kind": "header", "version": 1, "route_id": route, "workout_id": workout, "source": "live",
                  "ftp_w": 250},
                 {"kind": "event", "event": "start", "ts": float(start)}]
        t = float(start)
        for i, (dur, w, erg) in enumerate(blocks):
            for k in range(int(dur)):
                wave = 3 if dur >= 60 else 0     # petite ondulation des longs blocs, moyenne exacte par paire
                p = round(w + (wave if (k + i) % 2 else -wave), 1)
                rec = {"kind": "record", "ts": t, "t": t - start, "power": p, "cadence": 90, "speed": 8.0,
                       "distance": 0.0, "mode": "ERG" if erg else "SIM"}
                if erg:
                    rec["target_w"] = float(w)
                lines.append(rec)
                t += 1.0
        lines.append({"kind": "event", "event": "stop", "ts": t})
        path = journal_dir / f"{stamp}_{route}_{name}.jsonl"
        path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
        out.append(path)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openride_core.tools.courbe_fictive",
                                 description="Séances fabriquées d'un cycliste fictif (FTP 250 W).")
    ap.add_argument("journal_dir", type=Path)
    ap.add_argument("--now", type=float, help="heure Unix de référence (défaut : maintenant)")
    a = ap.parse_args(argv)
    for p in write_sessions(a.journal_dir, a.now):
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
