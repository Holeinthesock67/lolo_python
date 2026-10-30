"""Suivi en direct d'un essai guidé, dans sa propre fenêtre qui reste ouverte (lot X45).

Séance du 29 octobre : le banc du trainer tournait sans terminal visible (lancé à distance), et l'écran de
guidage disparaissait à la fin de l'essai. Un outil guidé lancé avec `--fenetre` écrit l'état de son écran
dans `live.json` (module `guide`) ; ce lecteur l'affiche en grand dans une fenêtre de terminal à part :
palier, compte à rebours, puissance, cadence, alertes, relevés, avec les mêmes bips. À la fin, le verdict
reste affiché jusqu'à « Entrée » ou à la fermeture de la fenêtre. Si l'essai ne donne plus de nouvelles
pendant `STALE_S` secondes, la fenêtre le dit.

    python -m openride_core.tools.suivi_direct ~/OpenRide/trainer_steps/2026-10-30_181500
    python -m openride_core.tools.suivi_direct DOSSIER --une-fois    # un seul affichage (tests)

`launch(live_file)` ouvre la fenêtre : `OPENRIDE_TERMINAL` (commande avec `{cmd}`), sinon le premier
terminal trouvé parmi gnome-terminal, x-terminal-emulator, konsole, xfce4-terminal et xterm.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .guide import Guide

LIVE_NAME = "live.json"
STALE_S = 5.0
PERIOD_S = 0.1
TERMINALS = (("gnome-terminal", ["gnome-terminal", "--"]), ("x-terminal-emulator", ["x-terminal-emulator", "-e"]),
             ("konsole", ["konsole", "-e"]), ("xfce4-terminal", ["xfce4-terminal", "-x"]), ("xterm", ["xterm", "-e"]))


def live_path(target: Path) -> Path:
    return target / LIVE_NAME if target.is_dir() or target.suffix != ".json" else target


def read_state(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class Viewer:
    """Rejoue l'état publié sur un `Guide` local : mêmes écrans, mêmes bips, sans journal."""

    def __init__(self, guide: Guide, now: Callable[[], float] = time.time) -> None:
        self.g = guide
        self.now = now
        self._step_key: tuple | None = None
        self._banner = ""
        self._measures = 0
        self._notes = 0
        self.finished = False

    def apply(self, st: dict[str, Any]) -> None:
        g = self.g
        g.title = st.get("title") or g.title
        age = max(0.0, self.now() - float(st.get("updated") or self.now()))
        verdict = st.get("verdict")
        step = st.get("step")
        if verdict is None and step is not None:
            key = (step.get("index"), step.get("text"))
            left = step.get("remaining_s")
            if key != self._step_key:
                self._step_key = key
                g.step(step.get("text", ""), None if left is None else max(0.0, left - age), step.get("detail", ""),
                       index=step.get("index"), total=step.get("total"))
        for text, ok in (st.get("measures") or [])[self._measures:]:
            g.measures.append((text, ok))
        self._measures = len(st.get("measures") or [])
        for text in (st.get("notes") or [])[self._notes:]:
            g.notes.append(text)
        self._notes = len(st.get("notes") or [])
        g.panel, g.panel_ok = list(st.get("panel") or []), st.get("panel_ok")
        banner = st.get("banner") or ""
        if banner and banner != self._banner:
            g.alert(banner, beep=True)
        elif not banner:
            g.banner = ""
        self._banner = banner
        if age > STALE_S and verdict is None:
            g.banner = f"Plus de nouvelles de l'essai depuis {age:.0f} s"
        if verdict is not None and not self.finished:
            self.finished = True
            g.finish(bool(verdict.get("ok")), str(verdict.get("text", "")))
            return
        if not self.finished:
            g.tick(st.get("live") or {})


def follow(path: Path, guide: Guide, once: bool = False, ask: Callable[[str], str] | None = None,
           wait_s: float = 60.0) -> int:
    """Affiche l'essai jusqu'à son verdict, puis garde la fenêtre ouverte jusqu'à « Entrée »."""
    viewer = Viewer(guide)
    start = time.monotonic()
    while True:
        st = read_state(path)
        if st is None:
            if once or time.monotonic() - start > wait_s:
                print(f"Pas d'essai à suivre : {path} introuvable ou illisible.")
                return 1
            guide.banner = f"En attente de l'essai ({path.name})…"
            guide.draw(force=True)
        else:
            viewer.apply(st)
        if once:
            return 0
        if viewer.finished:
            break
        time.sleep(PERIOD_S)
    try:
        (ask or input)("Essai fini : Entrée pour fermer la fenêtre ")
    except (EOFError, KeyboardInterrupt):
        pass
    return 0


def command(live_file: Path) -> list[str]:
    return [sys.executable, "-m", "openride_core.tools.suivi_direct", str(live_file)]


def launch(live_file: Path, which: Callable[[str], str | None] = shutil.which,
           spawn: Callable[[list[str]], Any] | None = None) -> str | None:
    """Ouvre la fenêtre de suivi ; renvoie la commande lancée, ou None (à lancer à la main)."""
    cmd = command(live_file)
    custom = os.environ.get("OPENRIDE_TERMINAL")
    if custom:
        argv = shlex.split(custom.replace("{cmd}", shlex.join(cmd)))
    else:
        found = next((prefix for name, prefix in TERMINALS if which(name)), None)
        if found is None:
            return None
        argv = [*found, *cmd]
    try:
        (spawn or (lambda a: subprocess.Popen(a, stdin=subprocess.DEVNULL, start_new_session=True)))(argv)
    except OSError:
        return None
    return shlex.join(argv)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openride_core.tools.suivi_direct",
                                 description="Suivi en direct d'un essai guidé (lot X45).")
    ap.add_argument("cible", type=Path, help="dossier de l'essai ou fichier live.json")
    ap.add_argument("--une-fois", action="store_true", help="un seul affichage puis quitte")
    ap.add_argument("--muet", action="store_true", help="sans bips")
    a = ap.parse_args(argv)
    guide = Guide("Suivi en direct", sound=False if a.muet or a.une_fois else None)
    return follow(live_path(a.cible), guide, once=a.une_fois)


if __name__ == "__main__":
    sys.exit(main())
