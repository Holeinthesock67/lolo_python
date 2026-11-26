"""Copies automatiques d'un profil de joueur et restauration (lot SV1).

Une copie est un dossier complet `~/OpenRide/Sauvegardes/profils/<id>/<AAAAMMJJ-HHMMSS>_<raison>/` : tout le
dossier du profil sauf le verrou et les caches recalculables (`.cache/`). Elle s'écrit dans un dossier `.tmp`
renommé à la fin : une copie coupée en route n'est jamais listée.

Place disque : un fichier inchangé depuis la copie précédente (même taille, même date de modification, ce que
`shutil.copy2` garde) y est un lien dur vers le fichier de cette copie précédente, jamais vers le fichier vivant
du profil (un journal complété en place ne modifie donc aucune copie). Huit copies hebdomadaires prennent ainsi
à peu près la place d'un profil et des séances de la saison, dans un seul dossier.

Raisons (`REASONS`, nombre de copies gardées par raison, les plus anciennes au-delà sont effacées) :
`semaine` (au choix du profil si la dernière a 7 jours ou plus), `mise-a-jour` (`scripts/update.sh`),
`remise-a-zero` (avant la remise à zéro du lot RZ1) et `restauration` (l'état actuel, avant une restauration).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import threading
import tomllib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import profiles

log = logging.getLogger(__name__)

BACKUPS_DIRNAME = "Sauvegardes"   # dans `~/OpenRide/`, à côté de `Profils/` (déjà celui de la migration MJ5)
PROFILE_BACKUPS = "profils"       # sous-dossier des copies de profils, un dossier par profil
MANIFEST = "copie.toml"
WEEKLY = "semaine"
REASONS: dict[str, int] = {WEEKLY: 8, "mise-a-jour": 3, "remise-a-zero": 3, "restauration": 3}
WEEK = timedelta(days=7)
SKIPPED = (profiles.LOCK_NAME, ".cache")   # verrou de la séance, caches recalculés depuis les séances
SHOWN = 16                                  # copies listées au menu (message `profile_backups`)
_ENTRY_RE = re.compile(r"^(?P<stamp>\d{8}-\d{6})_(?P<reason>[a-z-]+)$")
_LOCK = threading.Lock()   # une copie ou une restauration à la fois dans ce processus


class BackupError(profiles.ProfileContextError):
    pass


def _base(ctx: profiles.ProfileContext, base: Path | None) -> Path:
    """Dossier `Profils/` (défaut : le parent du dossier du profil)."""
    return base if base is not None else ctx.root.parent


def folder(ctx: profiles.ProfileContext, base: Path | None = None) -> Path:
    """Dossier des copies du profil `ctx` : `~/OpenRide/Sauvegardes/profils/<id>/`."""
    return _base(ctx, base).parent / BACKUPS_DIRNAME / PROFILE_BACKUPS / str(ctx.id)


def _check(ctx: profiles.ProfileContext) -> None:
    if ctx.id is None:
        raise BackupError("copie impossible sans profil de joueur")
    if ctx.is_trial:
        raise BackupError("le profil d'essai n'a pas de copie (ses séances sont simulées)")


def _dirs(ctx: profiles.ProfileContext, base: Path | None) -> list[tuple[Path, re.Match[str]]]:
    """Copies terminées du profil, les plus récentes d'abord."""
    d = folder(ctx, base)
    if not d.is_dir():
        return []
    out = [(p, m) for p in d.iterdir() if p.is_dir() and (m := _ENTRY_RE.match(p.name)) and m["reason"] in REASONS]
    return sorted(out, key=lambda x: x[1]["stamp"], reverse=True)


def _sessions(root: Path) -> int:
    """Séances d'une copie : fichiers FIT de `Activities/` (journaux et sous-dossiers cachés exclus)."""
    act = root / "Activities"
    return sum(1 for p in act.rglob("*.fit") if ".journal" not in p.parts) if act.is_dir() else 0


def _copy_tree(src: Path, dest: Path, prev: Path | None) -> None:
    """Copie `src` dans `dest`, fichier par fichier (`_copy_tree_file`, liens durs vers `prev`)."""
    dest.mkdir(parents=True, exist_ok=True)
    for entry in sorted(src.iterdir()):
        if entry.name.endswith(".tmp") or entry.is_symlink():
            continue
        target = dest / entry.name
        old = prev / entry.name if prev is not None else None
        if entry.is_dir():
            _copy_tree(entry, target, old if old is not None and old.is_dir() else None)
            continue
        _copy_tree_file(entry, target, old)


def _copy_tree_file(entry: Path, target: Path, old: Path | None) -> None:
    """Copie un fichier ; identique à `old` (taille et date de modification) : lien dur vers `old`."""
    st = entry.stat()
    if old is not None and old.is_file():
        ost = old.stat()
        if ost.st_size == st.st_size and ost.st_mtime_ns == st.st_mtime_ns:
            try:
                os.link(old, target)
                return
            except OSError:   # autre disque, liens durs refusés : copie
                pass
    shutil.copy2(entry, target)


def create(ctx: profiles.ProfileContext, reason: str, base: Path | None = None,
           now: datetime | None = None) -> Path:
    """Copie complète du profil de joueur `ctx` pour la raison `reason` (une de `REASONS`), puis rotation de
    cette raison. Renvoie le dossier de la copie. Lève `BackupError` (profil d'essai, raison inconnue, profil
    absent, erreur disque : la copie partielle est effacée)."""
    _check(ctx)
    if reason not in REASONS:
        raise BackupError(f"raison de copie inconnue : « {reason} »")
    if not ctx.root.is_dir():
        raise BackupError(f"profil « {ctx.id} » introuvable")
    with _LOCK:
        when = now or datetime.now()
        dest = folder(ctx, base) / f"{when:%Y%m%d-%H%M%S}_{reason}"
        if dest.exists():
            raise BackupError("une copie vient d'être faite : réessayer dans une seconde")
        existing = _dirs(ctx, base)
        prev = existing[0][0] if existing else None
        tmp = dest.with_name(dest.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            tmp.mkdir(parents=True)
            for entry in sorted(ctx.root.iterdir()):
                if entry.name in SKIPPED or entry.name.endswith(".tmp") or entry.is_symlink():
                    continue
                old = prev / entry.name if prev is not None else None
                if entry.is_dir():
                    _copy_tree(entry, tmp / entry.name, old if old is not None and old.is_dir() else None)
                else:
                    _copy_tree_file(entry, tmp / entry.name, old)
            manifest = ("# Copie du profil (OpenRide, lot SV1). Restaurable depuis « Gérer : <profil> ».\n"
                        "[copie]\n"
                        f"profil = {profiles._toml_str(ctx.id or '')}\n"
                        f"nom = {profiles._toml_str(ctx.name)}\n"
                        f"raison = {profiles._toml_str(reason)}\n"
                        f"faite = {profiles._toml_str(when.isoformat(timespec='seconds'))}\n"
                        f"seances = {_sessions(tmp)}\n")
            (tmp / MANIFEST).write_text(manifest, encoding="utf-8")
            os.replace(tmp, dest)
        except OSError as exc:
            shutil.rmtree(tmp, ignore_errors=True)
            raise BackupError(f"copie du profil « {ctx.name or ctx.id} » impossible : {exc}") from None
        prune(ctx, reason, base)
    log.info("Copie du profil %s (%s) : %s", ctx.id, reason, dest)
    return dest


def prune(ctx: profiles.ProfileContext, reason: str, base: Path | None = None) -> list[str]:
    """Efface les copies de `reason` au-delà des `REASONS[reason]` plus récentes ; renvoie les noms effacés.
    N'efface que dans le dossier des copies du profil."""
    kept = REASONS[reason]
    same = [p for p, m in _dirs(ctx, base) if m["reason"] == reason]
    gone = same[kept:]
    for p in gone:
        shutil.rmtree(p)
    return [p.name for p in gone]


def _manifest(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads((path / MANIFEST).read_text(encoding="utf-8")).get("copie", {})
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def entries(ctx: profiles.ProfileContext, base: Path | None = None) -> list[dict[str, Any]]:
    """Copies du profil, les plus récentes d'abord : `{id, reason, date, time, sessions}` (`date` AAAA-MM-JJ,
    `time` HH:MM). Vide pour le profil d'essai ou sans profil."""
    if ctx.id is None or ctx.is_trial:
        return []
    out = []
    for p, m in _dirs(ctx, base):
        s = m["stamp"]
        man = _manifest(p)
        sessions = man.get("seances")
        out.append({"id": p.name, "reason": m["reason"], "date": f"{s[:4]}-{s[4:6]}-{s[6:8]}",
                    "time": f"{s[9:11]}:{s[11:13]}",
                    "sessions": sessions if isinstance(sessions, int) else _sessions(p)})
    return out


def weekly_due(ctx: profiles.ProfileContext, base: Path | None = None, now: datetime | None = None) -> bool:
    """Faut-il une copie hebdomadaire ? Oui si le profil de joueur a des fichiers et que sa dernière copie
    `semaine` a 7 jours ou plus (ou n'existe pas)."""
    if ctx.id is None or ctx.is_trial or not ctx.root.is_dir():
        return False
    if not any(e.name not in SKIPPED and e.name != profiles.FILE_NAME for e in ctx.root.iterdir()):
        return False   # profil neuf : rien à protéger encore
    weekly = [m for _, m in _dirs(ctx, base) if m["reason"] == WEEKLY]
    if not weekly:
        return True
    last = datetime.strptime(weekly[0]["stamp"], "%Y%m%d-%H%M%S")
    return (now or datetime.now()) - last >= WEEK


def weekly_if_due(ctx: profiles.ProfileContext, base: Path | None = None,
                  now: datetime | None = None) -> Path | None:
    """Copie `semaine` si elle est due ; None sinon. Une erreur est journalisée, jamais levée (le jeu continue)."""
    try:
        return create(ctx, WEEKLY, base, now) if weekly_due(ctx, base, now) else None
    except (BackupError, OSError) as exc:
        log.warning("Copie hebdomadaire du profil %s impossible : %s", ctx.id, exc)
        return None


def start_weekly(ctx: profiles.ProfileContext, base: Path | None = None) -> threading.Thread | None:
    """Copie hebdomadaire en arrière-plan si elle est due (au choix du profil, au menu) ; renvoie le fil."""
    try:
        due = weekly_due(ctx, base)
    except OSError:
        due = False
    if not due:
        return None
    t = threading.Thread(target=weekly_if_due, args=(ctx, base), name="copie-profil", daemon=True)
    t.start()
    return t


def restore(ctx: profiles.ProfileContext, entry: Any, base: Path | None = None,
            now: datetime | None = None) -> Path:
    """Remet le profil `ctx` dans l'état de la copie `entry` (nom de son dossier). L'état actuel est d'abord
    copié (raison `restauration`, restaurable à son tour), puis tout le dossier du profil, verrou excepté, est
    remplacé par une copie (jamais un lien dur) des fichiers de `entry`, réglages et FTP compris. Le verrou du
    profil doit être tenu par l'appelant. Renvoie la copie de l'état actuel."""
    _check(ctx)
    src = folder(ctx, base) / entry if isinstance(entry, str) and _ENTRY_RE.match(entry) else None
    if src is None or not src.is_dir():
        raise BackupError(f"copie introuvable pour « {ctx.name or ctx.id} » : « {entry} »")
    saved = create(ctx, "restauration", base, now)
    with _LOCK:
        aside = ctx.root / ".avant_restauration.tmp"
        shutil.rmtree(aside, ignore_errors=True)
        aside.mkdir()
        current = [e for e in ctx.root.iterdir() if e.name != profiles.LOCK_NAME and e != aside]
        for e in current:
            os.replace(e, aside / e.name)
        try:
            for e in sorted(src.iterdir()):
                if e.name == MANIFEST or e.name in SKIPPED:
                    continue
                if e.is_dir():
                    shutil.copytree(e, ctx.root / e.name, copy_function=shutil.copy2)
                else:
                    shutil.copy2(e, ctx.root / e.name)
        except OSError as exc:   # remise en place de l'état d'avant
            for e in ctx.root.iterdir():
                if e.name != profiles.LOCK_NAME and e != aside:
                    shutil.rmtree(e) if e.is_dir() else e.unlink()
            for e in aside.iterdir():
                os.replace(e, ctx.root / e.name)
            aside.rmdir()
            raise BackupError(f"restauration impossible : {exc} ; profil laissé tel quel") from None
        shutil.rmtree(aside)
    log.info("Profil %s restauré depuis %s (état d'avant copié dans %s).", ctx.id, src.name, saved)
    return saved
