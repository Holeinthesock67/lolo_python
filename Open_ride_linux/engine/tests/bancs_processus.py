"""Processus des bancs de l'engine : arrêt complet, signaux d'arrêt, HOME temporaire (revue de code vague 5, lot RC21).

- `descendants(pid)` : descendants d'un processus, lus dans /proc, les plus profonds d'abord.
- `arreter_descendants(pid)` : SIGTERM puis SIGKILL aux descendants. `xvfb-run` est un script sh qui ne
  transmet pas SIGTERM à Godot (piège `EXIT` seul) : sans cela, Godot et Xvfb survivent au banc (O3-05).
- `signaux_en_exception()` : SIGTERM et SIGHUP (fermeture du terminal, `timeout`) lèvent `ArretDemande`,
  pour que les blocs `finally` des bancs arrêtent le core et Godot comme à la fin normale (O3-08).
- `home_temporaire()` : HOME et dossiers XDG dans un dossier temporaire neuf, pour un Godot lancé par un banc :
  l'engine ne lit plus `~/OpenRide/powerups.toml`, les consignes d'essai ni les sons du joueur, et son cache de
  shaders ne s'écrit plus dans le vrai profil (O3-09).

Bibliothèque standard seulement.
"""

from __future__ import annotations

import contextlib
import os
import signal
import tempfile
import time
from pathlib import Path


class ArretDemande(SystemExit):
    """Signal d'arrêt reçu par le banc : code 128 + numéro du signal, nettoyage par les `finally`."""

    def __init__(self, signum: int) -> None:
        super().__init__(128 + signum)
        self.signum = signum


def descendants(pid: int) -> list[int]:
    """Processus descendants de `pid` (lus dans /proc), les plus profonds d'abord."""
    children: dict[int, list[int]] = {}
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        children.setdefault(int(fields[1]), []).append(int(stat.parent.name))
    out: list[int] = []
    todo = [pid]
    while todo:
        for child in children.get(todo.pop(), []):
            out.append(child)
            todo.append(child)
    return out[::-1]


def _vivant(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:    # zombie : mort, en attente de son parent
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return False


def arreter_descendants(pid: int, delai_s: float = 5.0) -> list[int]:
    """SIGTERM aux descendants de `pid`, puis SIGKILL à ceux encore vivants après `delai_s` ; renvoie les
    processus visés. À appeler avant d'arrêter `pid` lui-même (après, ses enfants n'ont plus de parent connu)."""
    pids = descendants(pid)
    for p in pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(p, signal.SIGTERM)
    fin = time.monotonic() + delai_s
    while time.monotonic() < fin and any(_vivant(p) for p in pids):
        time.sleep(0.1)
    for p in pids:
        if _vivant(p):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(p, signal.SIGKILL)
    return pids


def signaux_en_exception(signaux: tuple[int, ...] = (signal.SIGTERM, signal.SIGHUP)) -> None:
    """Fait de SIGTERM et SIGHUP une exception `ArretDemande` dans le fil principal (une seule fois par
    signal : un second signal pendant le nettoyage n'interrompt pas les `finally`)."""

    def gestionnaire(signum, _frame) -> None:
        for s in signaux:
            signal.signal(s, signal.SIG_IGN)
        print(f"[banc] signal {signal.Signals(signum).name} reçu : arrêt propre du core et de Godot", flush=True)
        raise ArretDemande(signum)

    for s in signaux:
        signal.signal(s, gestionnaire)


def home_temporaire(prefixe: str = "openride-banc-home-") -> tuple[Path, dict[str, str]]:
    """Dossier temporaire neuf et variables HOME / XDG_* qui y pointent, à ajouter à l'environnement de Godot."""
    home = Path(tempfile.mkdtemp(prefix=prefixe)).resolve()
    env = {"HOME": str(home)}
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_STATE_HOME", ".local/state")):
        env[var] = str(home / sub)
    return home, env
