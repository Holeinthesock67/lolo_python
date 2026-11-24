#!/usr/bin/env python3
"""Lance le core avec une horloge murale décalée, pour l'essai d'endurance (lot EN1, `essai_endurance.py`).

    horloge_decalee.py openride_core FICHIER_HORLOGE run --config … --trainer sim …

Le premier argument est le nom du module lancé (`openride_core`) : il reste dans la ligne de commande du processus,
pour que la sonde de performance (`perf_probe.PROCESSES`) retrouve le core. `FICHIER_HORLOGE` est un petit JSON
`{"decalage_s": 604800.0}` relu chaque seconde : le banc l'écrit pour faire passer la ligue d'une semaine à la
suivante sans relancer le core. Seule `time.time()` est décalée (jour de la ligue, horodatage du journal et des
fichiers) ; `time.monotonic()`, qui cadence la boucle de la séance, ne bouge pas : un saut d'une semaine ne fait pas
un pas de physique d'une semaine.

Variable facultative `OPENRIDE_ESSAI_MANCHE_S` : durée visée d'une manche de la ligue (`league.RACE_TARGET_S`,
environ 27 min par défaut), raccourcie pour l'essai à blanc (`essai_endurance.py --court`). Rien du jeu n'est
modifié sur le disque : le décalage ne vit que dans ce processus.
"""

from __future__ import annotations

import json
import os
import runpy
import sys
import threading
import time
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage : horloge_decalee.py openride_core FICHIER_HORLOGE ARGUMENTS_DU_CORE…")
    module, clock_file = sys.argv[1], Path(sys.argv[2])
    real_time = time.time
    offset = [0.0]

    def read_offset() -> None:
        try:
            offset[0] = float(json.loads(clock_file.read_text(encoding="utf-8")).get("decalage_s", 0.0))
        except (OSError, ValueError, TypeError, AttributeError):
            pass   # fichier en cours d'écriture : on garde le décalage précédent

    def follow() -> None:
        while True:
            time.sleep(1.0)
            read_offset()

    read_offset()
    threading.Thread(target=follow, name="horloge_decalee", daemon=True).start()
    time.time = lambda: real_time() + offset[0]   # type: ignore[assignment]
    target = os.environ.get("OPENRIDE_ESSAI_MANCHE_S")
    if target:
        try:
            from openride_core import league   # type: ignore[import-not-found]
            league.RACE_TARGET_S = float(target)
        except ImportError:
            print("[essai] ligue absente de cette version du core : OPENRIDE_ESSAI_MANCHE_S ignorée", flush=True)
    sys.argv = [module, *sys.argv[3:]]
    runpy.run_module(module, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
