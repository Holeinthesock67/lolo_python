"""Remplacement atomique et durable d'un dossier ou d'un fichier (revue de code K4-07 et K4-08).

Règle commune aux écritures d'un `.world` et de ses couches :

- le contenu s'écrit dans un voisin caché `.<nom>.tmp-<pid>`, puis remplace l'original par renommage
  (l'ancien passe un instant par `.<nom>.old-<pid>`) ;
- avant le renommage, chaque fichier et chaque dossier du temporaire passe par `fsync` : après une
  coupure de courant, on retrouve l'ancien contenu ou le nouveau, jamais un `route.json` vide
  (K4-08) ;
- les voisins `.tmp-<pid>` et `.old-<pid>` laissés par un processus tué (SIGTERM ou SIGKILL du lanceur
  au-delà du délai, le `finally` ne passe pas) sont effacés au prochain remplacement du même nom
  (K4-07). Un `.old-<pid>` orphelin sans original est le contenu précédent, arrêté entre les deux
  renommages : il est remis en place au lieu d'être effacé.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Callable


def pid_alive(pid: int) -> bool:
    """Vrai si le processus `pid` existe (même s'il appartient à un autre utilisateur)."""
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True   # dans le doute, on garde
    return True


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def clean_stale(final: Path) -> list[Path]:
    """Efface les voisins `.<nom>.tmp-<pid>` et `.<nom>.old-<pid>` des processus disparus.

    Un `.old-<pid>` orphelin alors que `final` manque est remis à la place de `final` (le plus récent
    s'il y en a plusieurs). Rend la liste des chemins effacés ou remis en place."""
    final = Path(final)
    parent = final.parent
    if not parent.is_dir():
        return []
    pattern = re.compile(rf"\.{re.escape(final.name)}\.(tmp|old)-(\d+)")
    stale: list[tuple[str, Path]] = []
    for p in parent.iterdir():
        m = pattern.fullmatch(p.name)
        if m and not pid_alive(int(m.group(2))):
            stale.append((m.group(1), p))
    touched: list[Path] = []
    olds = sorted((p for kind, p in stale if kind == "old"), key=_mtime, reverse=True)
    if olds and not final.exists() and not final.is_symlink():
        try:
            olds[0].rename(final)
            touched.append(olds.pop(0))
        except OSError:
            pass
    for kind, p in stale:
        if p in touched:
            continue
        _remove(p)
        touched.append(p)
    return touched


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def fsync_path(path: Path) -> None:
    """`fsync` d'un fichier ou d'un dossier (entrées du dossier) ; sans effet si non pris en charge."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) if Path(path).is_dir() else os.O_RDONLY
    try:
        fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def fsync_tree(folder: Path) -> None:
    """`fsync` de tous les fichiers d'un dossier, puis des dossiers eux-mêmes, du plus profond au haut."""
    folder = Path(folder)
    for root, dirs, files in os.walk(folder, topdown=False):
        for name in files:
            p = Path(root) / name
            if not p.is_symlink():
                fsync_path(p)
        fsync_path(Path(root))


def replace_dir(final: Path, fill: Callable[[Path], None]) -> Path:
    """Remplace le dossier `final` par celui que `fill(tmp)` écrit, de façon atomique et durable.

    `fill` reçoit un chemin qui n'existe pas encore et peut le créer ; s'il ne le crée pas, un dossier
    vide est posé. En cas d'erreur, `final` reste tel qu'il était."""
    final = Path(final)
    parent = final.parent
    parent.mkdir(parents=True, exist_ok=True)
    clean_stale(final)
    tmp = parent / f".{final.name}.tmp-{os.getpid()}"
    old = parent / f".{final.name}.old-{os.getpid()}"
    _remove(tmp)
    try:
        fill(tmp)
        tmp.mkdir(exist_ok=True)
        fsync_tree(tmp)
        if final.exists():
            _remove(old)
            final.rename(old)
            try:
                tmp.rename(final)
            except BaseException:
                old.rename(final)
                raise
            fsync_path(parent)
            shutil.rmtree(old, ignore_errors=True)
        else:
            tmp.rename(final)
            fsync_path(parent)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return final


def replace_file_text(final: Path, text: str) -> None:
    """Réécrit un fichier texte UTF-8 de façon atomique et durable (temporaire, `fsync`, `os.replace`)."""
    final = Path(final)
    clean_stale(final)
    tmp = final.parent / f".{final.name}.tmp-{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, final)
        fsync_path(final.parent)
    finally:
        tmp.unlink(missing_ok=True)
