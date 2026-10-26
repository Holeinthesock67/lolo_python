"""Compilation au lancement d'OpenRide (Lot N11, SRS §7 et §11).

Vérifie via le catalogue s'il y a des traces GPX à compiler (statut 'to_compile' ou 'outdated').
Si oui, appelle `openride-compiler build-all` dans un sous-processus dont la sortie va au journal,
avec notification desktop (`notify-send`) et délai maximal configurable.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import IO, Callable

DEFAULT_COMPILE_TIMEOUT_S = 300.0


def default_notify(message: str, title: str = "OpenRide") -> None:
    """Notification desktop via notify-send s'il est disponible sur le système."""
    exe = shutil.which("notify-send")
    if exe:
        try:
            subprocess.run(
                [exe, title, message],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass


def find_compiler_cmd() -> list[str] | None:
    """Trouve la commande pour invoquer openride-compiler build-all."""
    if shutil.which("openride-compiler"):
        return ["openride-compiler", "build-all"]
    if importlib.util.find_spec("openride_compiler") is not None:
        return [sys.executable, "-m", "openride_compiler", "build-all"]
    return None


def get_pending_routes(routes_dir: Path | None = None, gpx_dir: Path | None = None) -> list:
    """Retourne la liste des traces nécessitant une compilation (to_compile ou outdated)."""
    from .catalog import list_routes
    from .config import GPX_DIR, ROUTES_DIR

    r_dir = routes_dir if routes_dir is not None else ROUTES_DIR
    g_dir = gpx_dir if gpx_dir is not None else GPX_DIR
    try:
        entries = list_routes(routes_root=r_dir, gpx_dir=g_dir)
        return [e for e in entries if e.status in ("to_compile", "outdated") and e.gpx_path is not None]
    except Exception:
        return []


def run_startup_compilation(
    routes_dir: Path | None = None,
    gpx_dir: Path | None = None,
    timeout_s: float = DEFAULT_COMPILE_TIMEOUT_S,
    compiler_cmd: list[str] | None = None,
    log_file: IO[bytes] | None = None,
    say: Callable[[str], None] | None = None,
    say_warning: Callable[[str], None] | None = None,
    notify: Callable[[str], None] | None = None,
) -> int:
    """Exécute la compilation au lancement si des traces sont en attente.

    Retourne :
        0 si succès (ou rien à compiler, ou compilateur absent)
        1 si erreur de compilation ou délai dépassé
    """
    _say = say if say is not None else (lambda msg: None)
    _say_warn = say_warning if say_warning is not None else _say
    _notify = notify if notify is not None else default_notify

    pending = get_pending_routes(routes_dir, gpx_dir)
    if not pending:
        return 0

    count = len(pending)
    _say(f"compilation de {count} trace{'s' if count > 1 else ''}...")
    _notify(f"Compilation de {count} trace{'s' if count > 1 else ''}…")

    if compiler_cmd is None:
        resolved_cmd = find_compiler_cmd()
    else:
        resolved_cmd = list(compiler_cmd)

    if not resolved_cmd:
        _say("compilateur absent (openride-compiler non installé) : démarrage normal sans compilation.")
        return 0

    cmd = list(resolved_cmd)
    if routes_dir is not None and "--routes-dir" not in cmd:
        cmd.extend(["--routes-dir", str(routes_dir)])
    if gpx_dir is not None and "--gpx-dir" not in cmd:
        cmd.extend(["--gpx-dir", str(gpx_dir)])

    out = log_file if log_file is not None else subprocess.DEVNULL
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
    except OSError as exc:
        _say(f"impossible de lancer le compilateur ({exc}) : démarrage normal.")
        return 0

    try:
        ret = proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _say_warn(f"délai de compilation dépassé ({timeout_s:.0f} s), compilation arrêtée.")
        _notify("Compilation interrompue (délai dépassé), voir le journal")
        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        return 1

    if ret == 0:
        _notify(f"{count} parcours prêt{'s' if count > 1 else ''}")
        _say(f"{count} parcours prêt{'s' if count > 1 else ''}.")
        return 0
    else:
        remaining = get_pending_routes(routes_dir, gpx_dir)
        err_count = len(remaining) if remaining else 1
        _notify(f"{err_count} trace{'s' if err_count > 1 else ''} en erreur, voir le journal")
        _say_warn(f"{err_count} trace{'s' if err_count > 1 else ''} en erreur, voir le journal")
        return 1
