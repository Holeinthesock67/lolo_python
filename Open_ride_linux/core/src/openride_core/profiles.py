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

Lot MJ5 : une fois la migration du joueur d'avant les profils finie (`Profils/.migration`, module
`migration_profils`), le profil par défaut est `principal` et le contexte historique ne sert plus.

Lot MJ7 : liste, création (identifiant tiré du nom), renommage et mise à la corbeille des profils ;
profil par défaut `[profils] dernier` de `config.toml` (profil `joueur` seulement), sinon le seul
profil joueur, sinon `principal` ; `~/OpenRide/.profil_actif` dit au lanceur quel profil relancer
après un plantage du core.

Lot O33 : le profil d'essai se vide et un profil de la corbeille se restaure depuis le menu
(`clear`, `trash_entries`, `restore`).
"""

from __future__ import annotations

import dataclasses
import fcntl
import os
import re
import shutil
import tomllib
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
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
MAIN_ID = "principal"          # joueur d'avant les profils, après la migration (lot MJ5)
MIGRATION_FILE = ".migration"  # étapes de la migration, dans `Profils/` (lot MJ5)
MIGRATION_DONE = "fini"
TRASH_DIRNAME = ".corbeille"   # profils supprimés, restaurables depuis « Gérer un profil » (lots MJ7, O33)
ACTIVE_FILE = ".profil_actif"  # dans `~/OpenRide/` : profil de la séance en cours (lot MJ7)
MAX_PROFILES = 8               # profils de joueur au plus (message `profiles` d'un datagramme)
NAME_MAX = 16
# Description par défaut d'un profil sans `profil.toml` : tout est donnée, aucun cas particulier
# dans le code (le profil d'essai ne diffère que par ces valeurs).
DEFAULTS: dict[str, dict[str, Any]] = {
    TRIAL_ID: {"nom": "Profil d'essai", "type": "essai", "seances_comptees": ["live", "simulated"]},
}
PLAYER_DEFAULTS: dict[str, Any] = {"type": "joueur", "seances_comptees": ["live"]}
RESERVED_IDS = frozenset(DEFAULTS)


class ProfileContextError(ValueError):
    """Identifiant de profil refusé, `profil.toml` illisible, ou profil déjà utilisé par une autre séance."""


class ProfileNameError(ProfileContextError):
    """Nom de profil refusé (code `name_invalid` du contrat, lot MJ6)."""


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


def migration_steps(base: Path | None = None) -> list[str]:
    """Étapes déjà faites de la migration (lot MJ5), dans l'ordre ; vide si elle n'a pas commencé."""
    path = (base if base is not None else profiles_dir()) / MIGRATION_FILE
    try:
        return [s for s in path.read_text(encoding="utf-8").split() if s]
    except (OSError, UnicodeDecodeError):
        return []


def default_id(base: Path | None = None, config_path: Path | None = None) -> str | None:
    """Profil choisi sans `--profil` ni `OPENRIDE_PROFIL`, une fois la migration finie :
    `[profils] dernier` de `config.toml` s'il existe encore, sinon le seul profil joueur, sinon
    `principal`, sinon le premier par nom ; None avant la migration (contexte historique)."""
    base = base if base is not None else profiles_dir()
    steps = migration_steps(base)
    if not steps or steps[-1] != MIGRATION_DONE:
        return None
    players = [c.id for c in list_contexts(base) if not c.is_trial]
    last = last_player(config_path if config_path is not None else base.parent / "config.toml")
    if last in players:
        return last
    if len(players) == 1 or (players and MAIN_ID not in players):
        return players[0]   # le seul, ou le premier par nom sans `principal`
    return MAIN_ID


def last_player(config_path: Path) -> str | None:
    """`[profils] dernier` de `config.toml` (None si absent ou illisible)."""
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    section = data.get("profils")
    value = section.get("dernier") if isinstance(section, dict) else None
    return value if isinstance(value, str) and value else None


# --- liste, création, renommage, suppression (lot MJ7) ---------------------------------------

def list_contexts(base: Path | None = None) -> list[ProfileContext]:
    """Profils du dossier (les illisibles sont sautés), joueurs triés par nom, puis le profil d'essai."""
    base = base if base is not None else profiles_dir()
    out: list[ProfileContext] = []
    if base.is_dir():
        for d in sorted(base.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            try:
                out.append(ProfileContext.for_id(d.name, base))
            except ProfileContextError:
                continue
    return sorted(out, key=lambda c: (c.is_trial, c.name.casefold(), c.id or ""))


def check_name(name: Any, others: list[ProfileContext], own_id: str | None = None) -> str:
    """Nom affiché : 1 à 16 caractères, lettres (accents compris), chiffres, espace, tiret ; unique."""
    if not isinstance(name, str):
        raise ProfileNameError("nom attendu (texte)")
    clean = " ".join(name.split())
    if not 1 <= len(clean) <= NAME_MAX:
        raise ProfileNameError(f"nom de 1 à {NAME_MAX} caractères (reçu {len(clean)})")
    bad = sorted({c for c in clean if not (c.isalpha() or c.isdigit() or c in " -")})
    if bad:
        raise ProfileNameError(f"caractère refusé : {' '.join(bad)} (lettres, chiffres, espace et tiret)")
    if any(c.name.casefold() == clean.casefold() and c.id != own_id for c in others):
        raise ProfileNameError(f"le nom « {clean} » est déjà pris")
    return clean


def id_from_name(name: str, taken: set[str]) -> str:
    """Identifiant de dossier tiré du nom (« Thérèse B » → `therese-b`), suffixé `-2`… s'il est pris."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    base_id = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")[:28] or "joueur"
    out, n = base_id, 1
    while out in taken or out in RESERVED_IDS:
        n += 1
        out = f"{base_id}-{n}"
    return out


def create(name: Any, base: Path | None = None, today: date | None = None) -> ProfileContext:
    """Nouveau profil de joueur ; lève `ProfileNameError` ou `ProfileContextError` (huit profils au plus)."""
    base = base if base is not None else profiles_dir()
    existing = list_contexts(base)
    clean = check_name(name, existing)
    if sum(not c.is_trial for c in existing) >= MAX_PROFILES:
        raise ProfileContextError(f"{MAX_PROFILES} profils au plus")
    taken = {c.id for c in existing if c.id} | ({d.name for d in base.iterdir()} if base.is_dir() else set())
    new_id = id_from_name(clean, taken)
    ctx = ProfileContext.for_id(new_id, base)
    ensure_description(dataclasses.replace(ctx, name=clean), today)
    return ProfileContext.for_id(new_id, base)


def rename(profile_id: str, name: Any, base: Path | None = None) -> ProfileContext:
    """Change le nom affiché (l'identifiant ne change pas)."""
    base = base if base is not None else profiles_dir()
    existing = list_contexts(base)
    ctx = _existing(profile_id, existing)
    clean = check_name(name, existing, own_id=profile_id)
    ensure_description(ctx)
    path = ctx.root / FILE_NAME
    lines = path.read_text(encoding="utf-8").splitlines()
    section = ""
    for i, line in enumerate(lines):
        m = re.match(r"^\s*\[\s*([A-Za-z0-9_.-]+)\s*\]", line)
        if m:
            section = m.group(1)
        elif section == "profil" and re.match(r"^\s*nom\s*=", line):
            lines[i] = f"nom = {_toml_str(clean)}"
            break
    else:
        raise ProfileContextError(f"{path} : clé nom introuvable dans [profil]")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return ProfileContext.for_id(profile_id, base)


def delete(profile_id: str, active_id: str | None, base: Path | None = None,
           now: datetime | None = None) -> Path:
    """Met le profil à la corbeille (`Profils/.corbeille/<id>_AAAAMMJJ-HHMMSS`) ; refusé pour le
    profil en cours, le profil d'essai et le dernier profil joueur. Renvoie le dossier à la corbeille."""
    base = base if base is not None else profiles_dir()
    existing = list_contexts(base)
    ctx = _existing(profile_id, existing)
    if ctx.is_trial:
        raise ProfileContextError("le profil d'essai ne se supprime pas (il se vide)")
    if profile_id == active_id:
        raise ProfileContextError(f"« {ctx.name} » est le profil en cours : changer de profil d'abord")
    if sum(not c.is_trial for c in existing) <= 1:
        raise ProfileContextError("le dernier profil de joueur ne se supprime pas")
    with ProfileLock(ctx):   # pas pendant une séance de ce profil
        pass
    dest = base / TRASH_DIRNAME / f"{profile_id}_{(now or datetime.now()):%Y%m%d-%H%M%S}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(ctx.root, dest)
    return dest


TRASH_SHOWN = 5   # profils de la corbeille proposés à la restauration (message `profiles`, lot O33)
_TRASH_RE = re.compile(r"^(?P<id>[a-z0-9][a-z0-9-]{0,31})_(?P<stamp>\d{8}-\d{6})$")


def trash_entries(base: Path | None = None) -> list[dict[str, str]]:
    """Profils de la corbeille, les plus récents d'abord : `{id, name, deleted}` (`id` = dossier de la
    corbeille, `deleted` = date de la suppression `AAAA-MM-JJ`) ; les dossiers illisibles sont sautés."""
    trash = (base if base is not None else profiles_dir()) / TRASH_DIRNAME
    out: list[dict[str, str]] = []
    if not trash.is_dir():
        return out
    for d in sorted(trash.iterdir(), key=lambda p: p.name.rsplit("_", 1)[-1], reverse=True):
        m = _TRASH_RE.match(d.name)
        if not m or not d.is_dir():
            continue
        try:
            desc = read_description(d, m["id"])
        except ProfileContextError:
            continue
        stamp = m["stamp"]
        out.append({"id": d.name, "name": str(desc["nom"]),
                    "deleted": f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"})
    return out


def restore(entry: Any, base: Path | None = None) -> ProfileContext:
    """Remet un profil de la corbeille (lot O33) ; refusé si son identifiant ou son nom est repris
    entre-temps, ou au-delà de huit profils. Lève `ProfileContextError`."""
    base = base if base is not None else profiles_dir()
    m = _TRASH_RE.match(entry) if isinstance(entry, str) else None
    src = base / TRASH_DIRNAME / entry if m else None
    if src is None or not src.is_dir():
        raise ProfileContextError(f"profil introuvable dans la corbeille : « {entry} »")
    profile_id = m["id"]
    name = str(read_description(src, profile_id)["nom"])
    existing = list_contexts(base)
    if (base / profile_id).exists():
        raise ProfileContextError(f"un profil « {profile_id} » existe déjà : renommer ou supprimer l'autre d'abord")
    if any(c.name.casefold() == name.casefold() for c in existing):
        raise ProfileContextError(f"le nom « {name} » est déjà pris : renommer l'autre profil d'abord")
    if sum(not c.is_trial for c in existing) >= MAX_PROFILES:
        raise ProfileContextError(f"{MAX_PROFILES} profils au plus : en supprimer un d'abord")
    os.replace(src, base / profile_id)
    return ProfileContext.for_id(profile_id, base)


def _existing(profile_id: Any, existing: list[ProfileContext]) -> ProfileContext:
    for c in existing:
        if c.id == profile_id:
            return c
    raise ProfileContextError(f"profil inconnu : « {profile_id} »")


def active_file() -> Path:
    from . import config as config_mod

    return config_mod.OPENRIDE_HOME / ACTIVE_FILE


def write_active(ctx: ProfileContext, path: Path | None = None) -> None:
    """Note le profil de la séance pour le lanceur (relance après un plantage) ; rien sans profil."""
    path = path or active_file()
    if ctx.id is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(ctx.id + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_active(path: Path | None = None) -> str | None:
    """Profil noté par le core ; None si absent, illisible ou refusé."""
    try:
        value = (path or active_file()).read_text(encoding="utf-8").strip()
        return check_id(value)
    except (OSError, UnicodeDecodeError, ProfileContextError):
        return None


def resolve(profile_id: str | None, env: dict[str, str] | None = None) -> ProfileContext | None:
    """Profil demandé par `--profil`, sinon par `OPENRIDE_PROFIL`, sinon le profil par défaut
    (`default_id`) ; None : contexte historique."""
    env = os.environ if env is None else env
    wanted = profile_id or env.get(ENV_VAR, "") or default_id()
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
