"""Isolation des suites de tests : HOME temporaire, pas de fenêtre, garde-fou d'écriture, une suite à la fois.

Chargé tout en haut de `core/tests/conftest.py` et de `compiler/tests/conftest.py`, avant tout
import d'openride_core (les chemins du type `~/OpenRide/Activities` sont calculés à l'import) :

- `isoler_environnement()` : HOME, XDG_CONFIG_HOME, XDG_DATA_HOME, XDG_CACHE_HOME et XDG_STATE_HOME
  pointent vers un dossier temporaire neuf ; zenity, kdialog et notify-send sont remplacés, en tête
  du PATH, par des programmes muets. Les sous-processus en héritent.
- `GardeEcriture` : un crochet d'audit (`sys.addaudithook`) relève toute écriture, création,
  suppression ou renommage hors du dossier temporaire du système, ou dans le HOME temporaire
  (un test écrit dans son `tmp_path`, jamais dans le HOME) ; après chaque test, le HOME temporaire
  est aussi comparé à son état d'avant, pour les écritures des sous-processus. Le test échoue.
- `verrou_suite()` : une seule suite de tests OpenRide à la fois sur la machine ; une deuxième
  attend la fin de la première (les mesures de performance ne sont plus faussées par une suite
  lancée en parallèle). `OPENRIDE_TESTS_VERROU` marque les sous-processus d'une suite qui le tient.

Bibliothèque standard seulement : sert aussi à `scripts/recette_pc.py` et aux bancs de l'engine.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
import sysconfig
import tempfile
import time
import traceback
from pathlib import Path

_BIBLIOTHEQUE = (sysconfig.get_paths()["stdlib"], sysconfig.get_paths()["platstdlib"])
DIALOGUES = ("zenity", "kdialog", "notify-send")
VARIABLE_VERROU = "OPENRIDE_TESTS_VERROU"
_ECRITURE = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
# événement d'audit → (position du chemin, position de son dir_fd ou None), pour chaque chemin écrit
_EVENEMENTS = {"os.mkdir": ((0, 2),), "os.remove": ((0, 1),), "os.rmdir": ((0, 1),),
               "os.rename": ((0, 2), (1, 3)), "os.symlink": ((1, 2),), "os.link": ((1, 3),),
               "os.truncate": ((0, None),), "shutil.rmtree": ((0, 1),)}


def _chemin(chemin, dir_fd) -> str:
    """Chemin absolu, relatif au dossier `dir_fd` s'il est donné (Linux : /proc/self/fd)."""
    chemin = os.fsdecode(chemin)
    if isinstance(dir_fd, int) and not os.path.isabs(chemin):
        with contextlib.suppress(OSError):
            return os.path.join(os.readlink(f"/proc/self/fd/{dir_fd}"), chemin)
    return os.path.abspath(chemin)


def isoler_environnement() -> tuple[Path, Path]:
    """HOME et XDG dans un dossier temporaire neuf, fenêtres de bureau muettes ; renvoie le HOME et
    le dossier des programmes muets."""
    home = Path(tempfile.mkdtemp(prefix="openride-tests-home-")).resolve()
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_STATE_HOME", ".local/state")):
        os.environ[var] = str(home / sub)
    os.environ["HOME"] = str(home)
    muets = Path(tempfile.mkdtemp(prefix="openride-tests-bin-"))
    for nom in DIALOGUES:
        prog = muets / nom
        # Une question (réparer la configuration, lot O34) reçoit « Non » ; le reste réussit sans rien afficher.
        prog.write_text('#!/bin/sh\ncase "$*" in *--question*|*--yesno*) exit 1;; esac\nexit 0\n', encoding="utf-8")
        prog.chmod(0o755)
    os.environ["PATH"] = f"{muets}{os.pathsep}{os.environ.get('PATH', '')}"
    return home, muets


def nettoyer_environnement(*dossiers: Path) -> None:
    """Supprime le HOME temporaire et le dossier des programmes muets (pas ceux d'une suite parente)."""
    for d in dossiers:
        shutil.rmtree(d, ignore_errors=True)


def _etat(home: Path) -> dict[str, tuple[int, int]]:
    etat = {}
    for racine, dossiers, fichiers in os.walk(home):
        for nom in dossiers + fichiers:
            p = os.path.join(racine, nom)
            with contextlib.suppress(OSError):
                st = os.lstat(p)
                etat[os.path.relpath(p, home)] = (st.st_mtime_ns, st.st_size)
    return etat


class GardeEcriture:
    """Relève les écritures d'un test hors du dossier temporaire du système ou dans le HOME temporaire."""

    def __init__(self, home: Path) -> None:
        self.home = str(home)
        tmp = tempfile.gettempdir()
        self.permis = {os.path.abspath(tmp), os.path.realpath(tmp)}
        self.actif = False
        self.releves: list[str] = []
        self._avant: dict[str, tuple[int, int]] = {}
        sys.addaudithook(self._crochet)

    def _interdit(self, p: str) -> bool:
        if "__pycache__" in p or p.startswith(("/dev/", "/proc/")):
            return False
        if p == self.home or p.startswith(self.home + os.sep):
            return True
        if p in self.permis:        # le dossier temporaire lui-même : fichier anonyme (O_TMPFILE) de tempfile et de multiprocessing
            return False
        return not any(p.startswith(r + os.sep) for r in self.permis)

    def _crochet(self, evenement: str, args: tuple) -> None:
        if not self.actif:
            return
        if evenement == "open":
            chemin, _mode, flags = args
            cibles = [(chemin, None)] if isinstance(flags, int) and flags & _ECRITURE else []
        elif evenement in _EVENEMENTS:
            cibles = [(args[i], args[j] if j is not None and j < len(args) else None)
                      for i, j in _EVENEMENTS[evenement] if i < len(args)]
        else:
            return
        for c, dir_fd in cibles:
            if not isinstance(c, (str, bytes, os.PathLike)):
                continue
            c = _chemin(c, dir_fd)
            if self._interdit(c):
                self.actif = False      # pas de relevé récursif pendant la mise en forme
                try:
                    pile = traceback.extract_stack(limit=30)[:-1]
                    lieu = next((f"{f.filename}:{f.lineno}" for f in reversed(pile)
                                 if not f.filename.startswith(_BIBLIOTHEQUE)
                                 and "isolation_tests" not in f.filename), "?")
                    self.releves.append(f"{evenement} {c} (depuis {lieu})")
                finally:
                    self.actif = True

    def debut(self) -> None:
        self.releves.clear()
        self._avant = _etat(Path(self.home))
        self.actif = True

    def fin(self) -> list[str]:
        """Arrête le relevé ; renvoie les écritures interdites, HOME temporaire remis à l'état d'avant."""
        self.actif = False
        home = Path(self.home)
        apres = _etat(home)
        changes = sorted(k for k in apres if apres[k] != self._avant.get(k))
        releves = list(dict.fromkeys(self.releves))
        releves += [f"écrit dans le HOME (sous-processus ?) : ~/{k}" for k in changes
                    if not any(f"{self.home}/{k}" in r for r in releves)]
        if changes:     # le test suivant repart d'un HOME propre
            for k in sorted(changes, key=len):
                p = home / k
                if p.is_dir() and not p.is_symlink():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    with contextlib.suppress(OSError):
                        p.unlink()
        self.releves.clear()
        return releves


def message_garde(releves: list[str]) -> str:
    return ("écriture hors du dossier temporaire du test (utiliser tmp_path, ou passer le dossier "
            "en paramètre) :\n  " + "\n  ".join(releves[:20]))


@contextlib.contextmanager
def verrou_suite(nom: str, attente_max_s: float = 3 * 3600):
    """Une seule suite de tests OpenRide à la fois ; attend la fin de celle en cours."""
    if os.environ.get(VARIABLE_VERROU):
        yield
        return
    import fcntl

    chemin = Path(tempfile.gettempdir()) / f"openride-tests-{os.getuid()}.lock"
    with open(chemin, "a+", encoding="utf-8") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            f.seek(0)
            autre = f.read().strip() or "?"
            print(f"[openride] une autre suite de tests tourne ({autre}) : {nom} attend sa fin…",
                  file=sys.stderr, flush=True)
            fin = time.monotonic() + attente_max_s
            while True:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() > fin:
                        raise TimeoutError(f"suite {autre} toujours en cours après {attente_max_s:.0f} s")
                    time.sleep(1.0)
        f.seek(0)
        f.truncate()
        f.write(f"{nom}, pid {os.getpid()}\n")
        f.flush()
        os.environ[VARIABLE_VERROU] = str(os.getpid())
        try:
            yield
        finally:
            os.environ.pop(VARIABLE_VERROU, None)
            f.seek(0)
            f.truncate()
            fcntl.flock(f, fcntl.LOCK_UN)


# --- Branchement pytest ---------------------------------------------------------------------------

def brancher_pytest() -> dict:
    """Isole l'environnement et renvoie les crochets pytest, à mettre dans le conftest.py :

        globals().update(brancher_pytest())     # avant tout import d'openride_core
    """
    import pytest

    home, muets = isoler_environnement()
    garde = GardeEcriture(home)
    verrou = contextlib.ExitStack()

    def pytest_configure(config) -> None:
        verrou.enter_context(verrou_suite(f"pytest {config.rootpath.name}"))

    def pytest_unconfigure(config) -> None:
        verrou.close()
        nettoyer_environnement(home, muets)

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(item) -> None:
        garde.debut()

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(item):
        try:
            return (yield)
        finally:
            releves = garde.fin()
            garde.debut()
            if releves:
                pytest.fail(message_garde(releves), pytrace=False)

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_teardown(item, nextitem):
        try:
            return (yield)
        finally:
            releves = garde.fin()
            if releves:
                pytest.fail(message_garde(releves), pytrace=False)

    return {f.__name__: f for f in (pytest_configure, pytest_unconfigure, pytest_runtest_setup,
                                    pytest_runtest_call, pytest_runtest_teardown)}
