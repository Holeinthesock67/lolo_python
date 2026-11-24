"""Course interrompue écrite pour les bancs (lot RC3) : une Course, un Grand Prix ou un Dernier survivant roulé en
temps accéléré par le vrai core, sans matériel, puis laissé sans fin, comme après un arrêt brutal du PC. Le journal
porte ses instantanés `race_snapshot` (lot RC1) et finit à l'heure de l'appel : au lancement suivant, le menu propose
« Reprendre la course » (moins de 2 h après).

    python -m openride_core.tools.course_interrompue --profil cycliste-a --config config.toml --mode race --secondes 90

Profil d'essai ou HOME temporaire seulement (banc des menus, `menu_scenarios/reprise_course.json`) : rien n'est écrit
ailleurs que dans les dossiers du profil choisi.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

DT = 0.02
POWER_W = 200.0   # puissance fictive du cycliste du banc


def write(cfg_path: Path | None, mode: str, seconds: float, route_id: str = "demo") -> Path:
    """Roule `seconds` secondes de course et rend le journal laissé sans fin."""
    from .. import config as config_mod
    from ..input_providers import NullProvider
    from ..mock_driver import MockDriver
    from ..session import CoreSession

    cfg = config_mod.load(cfg_path) if cfg_path is not None else config_mod.Config()
    cfg.depart.mode = "immediat"   # pas d'engine pour signaler le décor
    s = CoreSession(cfg, driver=MockDriver(base_power_w=POWER_W, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                    config_path=cfg_path)
    errors: list[str] = []
    s.server.send_raw = lambda m, max_size=None: None   # type: ignore[method-assign]
    s.server.send_error = lambda code, msg: errors.append(f"{code} : {msg}")   # type: ignore[method-assign]
    s.server.send_input_event = lambda ev: None   # type: ignore[method-assign]
    real = time.time
    wall = [real() - seconds]
    time.time = lambda: wall[0]   # type: ignore[assignment]   # heures du journal : finies à l'heure de l'appel
    try:
        s._on_command("select_route", {"route_id": route_id}, 1)
        s._on_command("start", {"mode": mode}, 2)
        if errors or s.state.session_state != "RUNNING":
            raise SystemExit(f"course non partie : {errors[-1] if errors else s.state.session_state}")
        for _ in range(int(round(seconds / DT))):
            if s.state.session_state != "RUNNING":
                break
            wall[0] += DT
            s._step(DT, wall[0])
    finally:
        time.time = real   # type: ignore[assignment]
    rec = s._rec
    assert rec is not None
    writer = getattr(rec, "_writer", None)
    if writer is not None:
        writer.close()   # le core « tombe » : ni arrivée, ni fin de séance
    return Path(writer.path) if writer is not None and hasattr(writer, "path") else _newest(s.journal_dir)


def _newest(directory: Path) -> Path:
    return max(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--profil", metavar="ID", help="profil de joueur (défaut : $OPENRIDE_PROFIL)")
    ap.add_argument("--config", type=Path)
    ap.add_argument("--mode", choices=["race", "grandprix", "survivor"], default="race")
    ap.add_argument("--secondes", type=float, default=90.0)
    ap.add_argument("--parcours", default="demo")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)-7s %(name)s %(message)s")
    from .. import profiles

    profiles.activate(profiles.resolve(args.profil))
    path = write(args.config, args.mode, args.secondes, args.parcours)
    print(f"Course interrompue écrite : {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
