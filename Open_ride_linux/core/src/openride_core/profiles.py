"""Profils de joueurs (série MJ, lot MJ1) : contexte des dossiers du joueur en cours.

Un profil est un dossier `~/OpenRide/Profils/<id>/` qui contient tout ce qui appartient à un
joueur : profil de la série V (`profile.json`), records (`records.json`), plan actif
(`plan_state.toml`), séances (`Activities/` et ses journaux), caches de l'historique et des
puissances. Le reste de `~/OpenRide/` est à la machine (plan MJ §2.1).

Les modules du core ne gardent aucun chemin de joueur figé : ils demandent `current()` au moment
de l'appel. Sans profil choisi (`--profil` absent, `OPENRIDE_PROFIL` vide), le contexte
« historique » reprend les chemins d'avant la série MJ, lus dans les constantes des modules au
moment de l'appel (les tests qui les redirigent continuent de marcher) : aucun changement visible.
"""

from __future__ import annotations

import fcntl
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import IO

ENV_VAR = "OPENRIDE_PROFIL"
PROFILES_DIRNAME = "Profils"
LOCK_NAME = ".verrou"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
RESERVED_IDS = frozenset({"_essai"})   # profil d'essai (lot MJ2)


class ProfileContextError(ValueError):
    """Identifiant de profil refusé, ou profil déjà utilisé par une autre séance."""


def check_id(profile_id: str) -> str:
    """Identifiant de dossier : minuscules, chiffres et tirets (1 à 32), ou un identifiant réservé."""
    if profile_id in RESERVED_IDS or _ID_RE.match(profile_id or ""):
        return profile_id
    raise ProfileContextError(f"identifiant de profil refusé : « {profile_id} » "
                              "(minuscules, chiffres et tirets, 1 à 32 caractères)")


def profiles_dir() -> Path:
    from . import config as config_mod

    return config_mod.OPENRIDE_HOME / PROFILES_DIRNAME


@dataclass(frozen=True)
class ProfileContext:
    """Où sont les fichiers du joueur en cours ; `id` vaut None pour le contexte historique."""

    id: str | None
    root: Path
    profile_path: Path
    records_path: Path
    plan_state_path: Path
    activities_dir: Path
    journal_dir: Path
    history_cache: Path
    mmp_cache: Path
    shared_table_path: Path       # surcharge `progression.toml` commune à la machine

    @classmethod
    def for_id(cls, profile_id: str, base: Path | None = None) -> "ProfileContext":
        """Contexte du profil `profile_id` sous `base` (défaut : `~/OpenRide/Profils`)."""
        from . import progression

        root = (base if base is not None else profiles_dir()) / check_id(profile_id)
        activities = root / "Activities"
        return cls(id=profile_id, root=root,
                   profile_path=root / "profile.json",
                   records_path=root / "records.json",
                   plan_state_path=root / "plan_state.toml",
                   activities_dir=activities,
                   journal_dir=activities / ".journal",
                   history_cache=root / ".cache" / "history.json",
                   mmp_cache=root / ".cache" / "mmp.json",
                   shared_table_path=progression.USER_TABLE_PATH)

    @classmethod
    def legacy(cls) -> "ProfileContext":
        """Contexte historique : les chemins d'avant la série MJ, lus à l'appel."""
        from . import config as config_mod
        from . import fit_export, journal, plans, profile, progression, records
        from .tools import estimate_cp, history

        return cls(id=None, root=config_mod.OPENRIDE_HOME,
                   profile_path=profile.PROFILE_PATH,
                   records_path=records.RECORDS_FILE,
                   plan_state_path=plans.STATE_PATH,
                   activities_dir=fit_export.ACTIVITIES_DIR,
                   journal_dir=journal.JOURNAL_DIR,
                   history_cache=history.CACHE_PATH,
                   mmp_cache=estimate_cp.CACHE_PATH,
                   shared_table_path=progression.USER_TABLE_PATH)

    @property
    def lock_path(self) -> Path:
        return self.root / LOCK_NAME

    @property
    def table_path(self) -> Path:
        """Surcharge de la progression : celle du profil si elle existe, sinon celle de la machine."""
        own = self.root / "progression.toml"
        return own if self.id is not None and own.is_file() else self.shared_table_path

    @property
    def label(self) -> str:
        return self.id if self.id is not None else "(sans profil)"


_active: ProfileContext | None = None


def current() -> ProfileContext:
    """Contexte du joueur en cours : celui activé, sinon le contexte historique."""
    return _active if _active is not None else ProfileContext.legacy()


def activate(ctx: ProfileContext | None) -> None:
    """Rend `ctx` actif pour tout le processus (None : retour au contexte historique)."""
    global _active
    _active = ctx


def resolve(profile_id: str | None, env: dict[str, str] | None = None) -> ProfileContext | None:
    """Profil demandé par `--profil`, sinon par `OPENRIDE_PROFIL` ; None sans demande."""
    env = os.environ if env is None else env
    wanted = profile_id if profile_id else env.get(ENV_VAR, "")
    return ProfileContext.for_id(wanted) if wanted else None


class ProfileLock:
    """Verrou `<profil>/.verrou` : une seule séance écrit un profil (rendu à la mort du processus)."""

    def __init__(self, ctx: ProfileContext) -> None:
        self.ctx = ctx
        self._fh: IO[str] | None = None

    def acquire(self) -> None:
        self.ctx.root.mkdir(parents=True, exist_ok=True)
        fh = self.ctx.lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            raise ProfileContextError(f"le profil « {self.ctx.label} » est déjà utilisé par une autre séance "
                                      f"({self.ctx.lock_path})") from None
        fh.seek(0)
        fh.truncate()
        fh.write(f"{os.getpid()}\n")
        fh.flush()
        self._fh = fh

    def release(self) -> None:
        if self._fh is not None:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "ProfileLock":
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
