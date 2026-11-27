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
from datetime import date, datetime, timedelta
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
    stats_since: float | None = None   # remise à zéro des statistiques (lot RZ1) : séances comptées à partir de là

    @classmethod
    def for_id(cls, profile_id: str, base: Path | None = None) -> "ProfileContext":
        """Contexte du profil `profile_id` sous `base` (défaut : `~/OpenRide/Profils`)."""
        from . import progression

        root = (base if base is not None else profiles_dir()) / check_id(profile_id)
        desc = read_description(root, profile_id)
        activities = root / "Activities"
        return cls(id=profile_id, root=root, type=desc["type"], name=desc["nom"],
                   counted_sources=tuple(desc["seances_comptees"]), created=desc["cree"],
                   stats_since=read_stats_since(root),
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
    # Revue S5-05 : un profil illisible n'est jamais remplacé en silence par un autre joueur ni par un
    # `principal` neuf. Le dernier choisi (ou, sans joueur lisible, le premier illisible) est rendu tel
    # quel : `ProfileContext.for_id` lève alors `ProfileContextError`, que le lanceur propose de réparer.
    broken = [pid for pid, _ in unreadable(base) if pid != TRIAL_ID]
    if last in broken:
        return last
    if not players and broken:
        return MAIN_ID if MAIN_ID in broken else broken[0]
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
    """Profils du dossier, joueurs triés par nom, puis le profil d'essai. Les illisibles sont sautés ici :
    `unreadable` les liste, le lanceur propose de les réparer et `default_id` ne les remplace pas (S5-05)."""
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


def unreadable(base: Path | None = None) -> list[tuple[str, str]]:
    """Profils sautés par `list_contexts` parce que leur `profil.toml` est illisible (revue S5-05) :
    `(identifiant, raison)`, par identifiant. Les dossiers au nom refusé ne sont pas des profils."""
    base = base if base is not None else profiles_dir()
    out: list[tuple[str, str]] = []
    if not base.is_dir():
        return out
    for d in sorted(base.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        try:
            check_id(d.name)
        except ProfileContextError:
            continue
        try:
            read_description(d, d.name)
        except ProfileContextError as exc:
            out.append((d.name, str(exc)))
    return out


UNREADABLE_SUFFIX = ".illisible-"   # `profil.toml.illisible-AAAAMMJJ-HHMMSS` : ancien fichier mis de côté


def _salvage_profile_section(text: str, profile_id: str) -> dict[str, Any]:
    """Valeurs de `[profil]` gardées une à une si elles sont valides ; les autres prennent leur défaut."""
    desc = default_description(profile_id)
    try:
        section = tomllib.loads(text).get("profil", {})
    except tomllib.TOMLDecodeError:
        section = {}
    if not isinstance(section, dict):
        section = {}
    name = section.get("nom")
    if isinstance(name, str) and name.strip():
        desc["nom"] = name
    if section.get("type") in TYPES:
        desc["type"] = section["type"]
    counted = section.get("seances_comptees")
    if isinstance(counted, list) and counted and all(c in SOURCES for c in counted):
        desc["seances_comptees"] = counted
    created = section.get("cree")
    if isinstance(created, date):
        desc["cree"] = created.isoformat()
    elif isinstance(created, str):
        try:
            desc["cree"] = date.fromisoformat(created).isoformat()
        except ValueError:
            pass
    return desc


def _toml_blocks(text: str) -> list[tuple[str, str]]:
    """Découpe un TOML en blocs `(en-tête, texte)` à chaque ligne `[table]` ou `[[table]]` ; « » avant la première."""
    blocks: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and "]" in stripped and not stripped.startswith("[ ]"):
            blocks.append((stripped.split("]", 1)[0].lstrip("[").strip(), [line]))
        else:
            blocks[-1][1].append(line)
    return [(head, "\n".join(lines) + "\n") for head, lines in blocks if any(x.strip() for x in lines)]


def set_aside_description(root: Path, profile_id: str, now: datetime | None = None) -> tuple[Path, list[str]]:
    """Profil au `profil.toml` illisible (revue S5-05) : l'ancien fichier est MIS DE CÔTÉ (jamais effacé) sous
    `profil.toml.illisible-AAAAMMJJ-HHMMSS`, puis un `profil.toml` lisible est écrit avec tout ce qui se lit
    encore : identité `[profil]` valeur par valeur (identifiant = dossier), et chaque autre table qui se lit
    seule (FTP, poids…). Les séances et le reste du profil ne bougent pas. Renvoie le fichier mis de côté et
    les tables perdues (remises par défaut)."""
    path = root / FILE_NAME
    raw = path.read_text(encoding="utf-8", errors="replace")
    when = now or datetime.now()
    kept = path.with_name(f"{FILE_NAME}{UNREADABLE_SUFFIX}{when:%Y%m%d-%H%M%S}")
    n = 2
    while kept.exists():
        kept = path.with_name(f"{FILE_NAME}{UNREADABLE_SUFFIX}{when:%Y%m%d-%H%M%S}-{n}")
        n += 1
    blocks = _toml_blocks(raw)
    profile_text = "".join(t for head, t in blocks if head == "profil")
    desc = _salvage_profile_section(profile_text, profile_id)
    others: list[tuple[str, str]] = []
    lost: list[str] = []
    for head, block in blocks:
        if head == "profil":
            continue
        try:
            tomllib.loads(block)
            others.append((head, block))
        except tomllib.TOMLDecodeError:
            lost.append(f"[{head}]" if head else "(début du fichier)")
    counted = ", ".join(_toml_str(c) for c in desc["seances_comptees"])
    created = f"cree = {desc['cree']}\n" if desc["cree"] else ""
    head_text = (f"# Profil de joueur OpenRide (série MJ). Réparé le {when:%d/%m/%Y à %H:%M} : "
                 f"l'ancien fichier est gardé sous {kept.name}.\n"
                 "[profil]\n"
                 f"id = {_toml_str(profile_id)}\n"
                 f"nom = {_toml_str(desc['nom'])}\n"
                 f"type = {_toml_str(desc['type'])}\n"
                 f"{created}"
                 f"seances_comptees = [{counted}]\n")
    root_keys = "".join(b for h, b in others if not h)   # clés hors table : avant `[profil]`, sinon elles y entreraient
    text = root_keys + head_text + "".join("\n" + b for h, b in others if h)
    try:
        tomllib.loads(text)   # tables en double ou clés à cheval : on ne garde que l'identité
    except tomllib.TOMLDecodeError:
        lost.extend(f"[{h}]" if h else "(début du fichier)" for h, _ in others)
        text = head_text
    os.replace(path, kept)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    read_description(root, profile_id)   # contrôle : lève si la réparation n'a pas suffi
    return kept, lost


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


# --- remise à zéro des statistiques d'un profil de joueur (lot RZ1) ---------------------------

RESETS_DIRNAME = ".remises_a_zero"   # dans `Profils/` : statistiques mises de côté, une remise par dossier
RESETS_SHOWN = 3                     # remises proposées à l'annulation (message `profiles`)
RESET_MANIFEST = "remise.toml"       # description de la remise, dans son dossier
RESET_KEPT_COPY = "_gardes"          # copie des fichiers gardés au moment de la remise (lecture seule)
STATS_SINCE_FILE = "remise_stats.toml"   # dans le profil : `[remise] depuis` = date de la remise (horodatage)
ELO_NAME = "elo.json"
# Gardés (choix du propriétaire du 22 novembre, « garder coach, FIT et mon Elo ») : description et réglages du
# joueur (nom, FTP, poids, FC max), surcharge de la progression, verrou, derniers choix du menu, plan actif, les
# séances elles-mêmes (`Activities/` : FIT et journaux, l'historique du coach et sa charge des 4 dernières
# semaines), les caches recalculables et le conseil du jour. Les séances d'avant la remise restent sur le disque
# mais ne rapportent plus rien : niveau, expérience, pièces, défis et cartes repartent de la date de la remise
# (`ProfileContext.stats_since`, lue par `progression.recompute`). Mis de côté : records, profil V4 (équipement
# acheté, vies), cartes vues, ligue, segments du monde ouvert et tout fichier ajouté plus tard au profil ; la cote
# Elo garde celle du cycliste (et son nombre de courses), celles des bots repartent de zéro (`ELO_KEEPS_RIDER`).
KEPT_ON_RESET = (FILE_NAME, "progression.toml", LOCK_NAME, "derniers_choix.json", "plan_state.toml",
                 "Activities", ".cache", "conseil.json", STATS_SINCE_FILE)
ELO_KEEPS_RIDER = True


def read_stats_since(root: Path) -> float | None:
    """Date de la dernière remise à zéro du profil (`remise_stats.toml`) ; None sans remise ou fichier illisible."""
    try:
        data = tomllib.loads((root / STATS_SINCE_FILE).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    value = data.get("remise", {}).get("depuis") if isinstance(data.get("remise"), dict) else None
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _write_stats_since(root: Path, when: datetime) -> None:
    path = root / STATS_SINCE_FILE
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("# Remise à zéro des statistiques (OpenRide, lot RZ1) : les séances d'avant ne comptent plus.\n"
                   f"[remise]\ndepuis = {when.timestamp():.0f}   # {when.isoformat(timespec='seconds')}\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def _reset_entries_of(ctx: ProfileContext) -> list[Path]:
    if not ctx.root.is_dir():
        return []
    return [e for e in sorted(ctx.root.iterdir()) if e.name not in KEPT_ON_RESET and not e.name.endswith(".tmp")]


def _check_player(ctx: ProfileContext) -> None:
    if ctx.id is None:
        raise ProfileContextError("remise à zéro impossible sans profil de joueur")
    if ctx.is_trial:
        raise ProfileContextError("le profil d'essai ne se remet pas à zéro : il se vide")


def _stash(ctx: ProfileContext, base: Path, when: datetime, kind: str) -> tuple[Path, list[str]]:
    """Sauvegarde datée : copie des fichiers gardés (`_gardes/`, `remise_stats.toml` compris), puis DÉPLACEMENT
    de tout le reste du profil ; rien n'est effacé."""
    dest = base / RESETS_DIRNAME / f"{ctx.id}_{when:%Y%m%d-%H%M%S}"
    while dest.exists():   # deux sauvegardes dans la même seconde : la seconde prend la suivante
        when += timedelta(seconds=1)
        dest = base / RESETS_DIRNAME / f"{ctx.id}_{when:%Y%m%d-%H%M%S}"
    entries = _reset_entries_of(ctx)
    keep = dest / RESET_KEPT_COPY
    keep.mkdir(parents=True)
    for name in KEPT_ON_RESET:
        src = ctx.root / name
        if name != LOCK_NAME and src.is_file():
            shutil.copy2(src, keep / name)
    moved = [e.name for e in entries]
    since = read_stats_since(ctx.root)
    manifest = ("# Remise à zéro des statistiques (OpenRide, lot RZ1). Annulable depuis « Gérer un profil ».\n"
                "[remise]\n"
                f"profil = {_toml_str(ctx.id)}\n"
                f"nom = {_toml_str(ctx.name)}\n"
                f"faite = {_toml_str(when.isoformat(timespec='seconds'))}\n"
                f"type = {_toml_str(kind)}\n"
                f"stats_depuis_avant = {_toml_str('' if since is None else str(int(since)))}\n"
                f"deplaces = [{', '.join(_toml_str(n) for n in moved)}]\n")
    (dest / RESET_MANIFEST).write_text(manifest, encoding="utf-8")
    for e in entries:
        os.replace(e, dest / e.name)
    return dest, moved


def reset_stats(ctx: ProfileContext, base: Path | None = None, now: datetime | None = None) -> tuple[Path, list[str]]:
    """Remet à zéro les statistiques du profil de joueur `ctx` (voir `KEPT_ON_RESET`) : sauvegarde datée dans
    `Profils/.remises_a_zero/<id>_AAAAMMJJ-HHMMSS/` (fichiers mis de côté DÉPLACÉS, fichiers gardés copiés), puis
    `remise_stats.toml` (date de la remise) et cote Elo du cycliste seule. Refusé pour le profil d'essai (il se
    vide) et hors profil. Le verrou du profil doit être tenu par l'appelant. Renvoie la sauvegarde et les noms
    déplacés."""
    _check_player(ctx)
    base = base if base is not None else ctx.root.parent
    when = now or datetime.now()
    ctx.root.mkdir(parents=True, exist_ok=True)
    dest, moved = _stash(ctx, base, when, "remise")
    _write_stats_since(ctx.root, when)
    if ELO_KEEPS_RIDER and ELO_NAME in moved:
        from . import bot_elo

        old = bot_elo.load(dest / ELO_NAME)
        bot_elo.save(ctx.root / ELO_NAME, bot_elo.EloBook(rating=old.rating, races=old.races))
    return dest, moved


def reset_entries(ctx: ProfileContext, base: Path | None = None, all_kinds: bool = False) -> list[dict[str, str]]:
    """Remises à zéro du profil `ctx`, les plus récentes d'abord : `{id, date, time}` (`id` = dossier de la
    sauvegarde, `date` AAAA-MM-JJ, `time` HH:MM). Les sauvegardes faites par une annulation (fichiers de la période
    d'après la remise) ne sont listées qu'avec `all_kinds` (ligne de commande), pas au menu."""
    if ctx.id is None:
        return []
    folder = (base if base is not None else ctx.root.parent) / RESETS_DIRNAME
    out: list[dict[str, str]] = []
    if not folder.is_dir():
        return out
    for d in sorted(folder.iterdir(), key=lambda p: p.name.rsplit("_", 1)[-1], reverse=True):
        m = _TRASH_RE.match(d.name)
        if not m or m["id"] != ctx.id or not d.is_dir():
            continue
        if not all_kinds and 'type = "annulation"' in _read_text(d / RESET_MANIFEST):
            continue
        s = m["stamp"]
        out.append({"id": d.name, "date": f"{s[:4]}-{s[4:6]}-{s[6:8]}", "time": f"{s[9:11]}:{s[11:13]}"})
    return out


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def undo_reset(ctx: ProfileContext, entry: Any, base: Path | None = None,
               now: datetime | None = None) -> tuple[list[str], Path | None]:
    """Annule une remise à zéro du profil `ctx` : ce qui a été mis de côté depuis (records, Elo… de la période
    d'après) est d'abord sauvegardé à son tour (nouvelle sauvegarde, annulable), puis ce que la remise `entry`
    avait mis de côté revient et la date de départ des statistiques redevient celle d'avant la remise (copie de
    `_gardes/`). Les séances, réglages et FTP ne bougent pas. Le verrou doit être tenu. Renvoie les noms remis et
    la sauvegarde des fichiers d'après la remise (None s'il n'y en avait pas)."""
    _check_player(ctx)
    base = base if base is not None else ctx.root.parent
    m = _TRASH_RE.match(entry) if isinstance(entry, str) else None
    src = base / RESETS_DIRNAME / entry if m and m["id"] == ctx.id else None
    if src is None or not src.is_dir():
        raise ProfileContextError(f"remise à zéro introuvable pour « {ctx.name or ctx.id} » : « {entry} »")
    saved: Path | None = None
    when = now or datetime.now()
    if _reset_entries_of(ctx):
        saved, _ = _stash(ctx, base, when, "annulation")
    back = [e for e in sorted(src.iterdir())
            if e.name not in (RESET_MANIFEST, RESET_KEPT_COPY) and e.name not in KEPT_ON_RESET]
    for e in back:
        os.replace(e, ctx.root / e.name)
    old_since = src / RESET_KEPT_COPY / STATS_SINCE_FILE
    if old_since.is_file():
        shutil.copy2(old_since, ctx.root / STATS_SINCE_FILE)
    else:
        (ctx.root / STATS_SINCE_FILE).unlink(missing_ok=True)
    shutil.rmtree(src)   # ne restent que remise.toml, la copie des fichiers gardés et d'éventuels fichiers gardés
    return [e.name for e in back], saved


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
