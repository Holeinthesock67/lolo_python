"""Profils de joueurs (série MJ, lot MJ1) : contexte des dossiers du joueur en cours.

Un profil est un dossier `~/OpenRide/Profils/<id>/` qui contient tout ce qui appartient à un
joueur : profil de la série V (`profile.json`), records (`records.json`), plan actif
(`plan_state.toml`), séances (`Activities/` et ses journaux), caches de l'historique et des
puissances. Le reste de `~/OpenRide/` est à la machine (plan MJ §2.1).

Les modules du core ne gardent aucun chemin de joueur figé : ils demandent `current()` au moment
de l'appel. Sans profil choisi (`--profil` absent, `OPENRIDE_PROFIL` vide), le contexte
« historique » reprend les chemins d'avant la série MJ, lus dans les constantes des modules au
moment de l'appel (les tests qui les redirigent continuent de marcher) : aucun changement visible.

Lot MJ2 : `profil.toml` décrit le profil (`[profil] id, nom, type, cree, seances_comptees`). Le profil
d'essai `_essai` est un profil comme les autres, de type `essai`, où les séances simulées comptent
(`seances_comptees = ["live", "simulated"]`) ; ses journaux portent `profile_id` et ne comptent
jamais ailleurs. Un profil sans `profil.toml`, et le contexte historique, valent `joueur`, `["live"]`.
"""

from __future__ import annotations

import fcntl
import os
import re
import shutil
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import IO, Any

ENV_VAR = "OPENRIDE_PROFIL"
PROFILES_DIRNAME = "Profils"
LOCK_NAME = ".verrou"
FILE_NAME = "profil.toml"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
TYPES = ("joueur", "essai")
SOURCES = ("live", "simulated", "replay")   # valeurs `source` de l'en-tête du journal (lot V2)
TRIAL_ID = "_essai"
# Description par défaut d'un profil sans `profil.toml` : tout est donnée, aucun cas particulier
# dans le code (le profil d'essai ne diffère que par ces valeurs).
DEFAULTS: dict[str, dict[str, Any]] = {
    TRIAL_ID: {"nom": "Profil d'essai", "type": "essai", "seances_comptees": ["live", "simulated"]},
}
PLAYER_DEFAULTS: dict[str, Any] = {"type": "joueur", "seances_comptees": ["live"]}
RESERVED_IDS = frozenset(DEFAULTS)


class ProfileContextError(ValueError):
    """Identifiant de profil refusé, `profil.toml` illisible, ou profil déjà utilisé par une autre séance."""


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
    type: str = "joueur"          # « joueur » ou « essai » (lot MJ2)
    name: str = ""
    counted_sources: tuple[str, ...] = ("live",)   # sources du journal qui rapportent expérience et pièces
    created: str = ""

    @classmethod
    def for_id(cls, profile_id: str, base: Path | None = None) -> "ProfileContext":
        """Contexte du profil `profile_id` sous `base` (défaut : `~/OpenRide/Profils`)."""
        from . import progression

        root = (base if base is not None else profiles_dir()) / check_id(profile_id)
        desc = read_description(root, profile_id)
        activities = root / "Activities"
        return cls(id=profile_id, root=root, type=desc["type"], name=desc["nom"],
                   counted_sources=tuple(desc["seances_comptees"]), created=desc["cree"],
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

    @property
    def is_trial(self) -> bool:
        return self.type == "essai"

    def owns(self, journal_profile_id: str | None) -> bool:
        """Le journal marqué `journal_profile_id` est-il de ce profil ?

        Un journal sans `profile_id` (séances d'avant la série MJ, contexte historique) appartient
        aux profils de type `joueur`, jamais au profil d'essai.
        """
        if journal_profile_id is None:
            return not self.is_trial
        return journal_profile_id == self.id

    def journal_header(self) -> dict[str, str] | None:
        """`profile_id` et `profile_type` de l'en-tête du journal ; None en contexte historique."""
        if self.id is None:
            return None
        return {"profile_id": self.id, "profile_type": self.type}

    def fit_suffix(self) -> str:
        """Suffixe du nom des FIT : `_essai` pour le profil d'essai (lot MJ2)."""
        return "_essai" if self.is_trial else ""


def default_description(profile_id: str) -> dict[str, Any]:
    desc = {"id": profile_id, "nom": profile_id, "cree": "", **PLAYER_DEFAULTS}
    desc.update(DEFAULTS.get(profile_id, {}))
    return desc


def read_description(root: Path, profile_id: str) -> dict[str, Any]:
    """`[profil]` de `<root>/profil.toml`, complété par les valeurs par défaut ; lève `ProfileContextError`."""
    desc = default_description(profile_id)
    path = root / FILE_NAME
    if not path.is_file():
        return desc
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ProfileContextError(f"{path} illisible : {exc}") from None
    section = data.get("profil", {})
    if not isinstance(section, dict):
        raise ProfileContextError(f"{path} : [profil] doit être une table")
    for key, value in section.items():
        desc[key] = value.isoformat() if isinstance(value, date) else value
    if desc["id"] != profile_id:
        raise ProfileContextError(f"{path} : id « {desc['id']} » différent du dossier « {profile_id} »")
    if desc["type"] not in TYPES:
        raise ProfileContextError(f"{path} : type « {desc['type']} » inconnu ({', '.join(TYPES)})")
    counted = desc["seances_comptees"]
    if not isinstance(counted, list) or any(s not in SOURCES for s in counted):
        raise ProfileContextError(f"{path} : seances_comptees doit être une liste parmi {', '.join(SOURCES)}")
    if not isinstance(desc["nom"], str):
        raise ProfileContextError(f"{path} : nom doit être un texte")
    return desc


def _toml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ensure_description(ctx: ProfileContext, today: date | None = None) -> Path:
    """Écrit `profil.toml` s'il manque (première utilisation du profil) ; renvoie son chemin."""
    path = ctx.root / FILE_NAME
    if ctx.id is None or path.is_file():
        return path
    ctx.root.mkdir(parents=True, exist_ok=True)
    counted = ", ".join(_toml_str(s) for s in ctx.counted_sources)
    created = ctx.created or (today or date.today()).isoformat()
    text = ("# Profil de joueur OpenRide (série MJ). Fichier local : jamais versionné.\n"
            "[profil]\n"
            f"id = {_toml_str(ctx.id)}\n"
            f"nom = {_toml_str(ctx.name)}\n"
            f"type = {_toml_str(ctx.type)}\n"
            f"cree = {created}\n"
            f"seances_comptees = [{counted}]\n")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


KEPT_ON_CLEAR = (FILE_NAME, "progression.toml", LOCK_NAME)


def clear(ctx: ProfileContext) -> list[str]:
    """Vide un profil d'essai (séances, records, plan, profil V4, caches) ; garde sa description
    et sa surcharge de progression. Refusé pour un profil de joueur. Renvoie les noms effacés."""
    if not ctx.is_trial:
        raise ProfileContextError(f"seul le profil d'essai se vide (profil « {ctx.label} » de type {ctx.type})")
    removed: list[str] = []
    if not ctx.root.is_dir():
        return removed
    for entry in sorted(ctx.root.iterdir()):
        if entry.name in KEPT_ON_CLEAR:
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
        removed.append(entry.name)
    return removed


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
