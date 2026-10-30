"""Migration du joueur d'avant les profils vers `Profils/principal/` (série MJ, lot MJ5).

Au premier lancement de la version avec profils (plan `docs/2.0/PLAN_SERIE_MJ.md` §5), le lanceur
appelle `migrate()` tant que `Profils/.migration` ne finit pas par `fini`. Étapes, chacune notée
dans `Profils/.migration` une fois faite (une coupure de courant reprend à l'étape suivante, et
chaque étape peut être refaite sans dégât) :

1. `sauvegarde` : archive `Sauvegardes/avant_profils_AAAAMMJJ.tar.gz` de `config.toml`,
   `profile.json`, `records.json`, `plan_state.toml` et `Activities/` ;
2. `instantane` : progression d'avant (`xp --json`, lot X39) dans `Profils/.migration_avant.json` ;
3. `profil` : `Profils/principal/profil.toml`, nom « Cycliste 1 », avec les clés joueur
   (`config.PROFILE_KEYS`) trouvées dans `config.toml` ;
4. `plan` : liste des déplacements écrite d'un coup dans `Profils/.migration_plan.json` ; chaque
   séance suit l'en-tête de son journal (`live`, sans en-tête lisible, et FIT sans journal :
   `principal` ; `simulated`, `replay` : `_essai`) ;
5. `deplacement` : renommages (`os.replace`, même disque) de cette liste ; un fichier déjà à sa
   place est sauté ;
6. `records` : `records.json` de `principal` recalculé depuis ses journaux (parcours introuvable :
   ses anciens records sont gardés) ; l'ancien `records.json` part (il est dans la sauvegarde) ;
7. `caches` : caches d'historique et de puissances d'avant les profils effacés (ils se recalculent) ;
8. `config` : les clés passées au profil sont retirées de `config.toml` (commentaire à leur place) ;
9. `controle` : progression de `principal` comparée à celle d'avant ; un écart annule tout
   (`annulee`, fichiers remis depuis la sauvegarde) et la migration n'est plus retentée seule ;
10. `fini` : le profil par défaut devient `principal` (`profiles.default_id`).

Rien n'est réécrit dans les journaux : ceux sans `profile_id` appartiennent à `principal`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tarfile
import tomllib
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from . import config as config_mod
from . import config_edit, profiles
from .journal import read_journal

log = logging.getLogger(__name__)

STEPS = ("sauvegarde", "instantane", "profil", "plan", "deplacement", "records", "caches", "config",
         "controle", profiles.MIGRATION_DONE)
CANCELLED = "annulee"
MAIN_NAME = "Cycliste 1"
BACKUP_DIR = "Sauvegardes"
SAVED = ("config.toml", "profile.json", "records.json", "plan_state.toml", "Activities")
MOVED_FILES = ("profile.json", "plan_state.toml")
TRIAL_SOURCES = ("simulated", "replay")
CONFIG_NOTE = f"passé dans {profiles.PROFILES_DIRNAME}/{profiles.MAIN_ID}/{profiles.FILE_NAME} (profils de joueurs)"


class MigrationError(Exception):
    """Migration impossible ou annulée ; message lisible."""


class Migration:
    """Migration de `home` (défaut : `~/OpenRide`) ; `stop_after` coupe après une étape (tests)."""

    def __init__(self, home: Path | None = None, today: date | None = None,
                 legacy_caches: tuple[Path, ...] | None = None) -> None:
        self.home = home if home is not None else config_mod.OPENRIDE_HOME
        self.base = self.home / profiles.PROFILES_DIRNAME
        self.today = today or date.today()
        self.config_path = self.home / "config.toml"
        self.main = profiles.ProfileContext.for_id(profiles.MAIN_ID, self.base)
        self.trial = profiles.ProfileContext.for_id(profiles.TRIAL_ID, self.base)
        if legacy_caches is None:
            from .tools import estimate_cp, history
            legacy_caches = (history.CACHE_PATH, estimate_cp.CACHE_PATH)
        self.legacy_caches = legacy_caches

    # --- état ------------------------------------------------------------------------------

    @property
    def journal(self) -> Path:
        return self.base / profiles.MIGRATION_FILE

    @property
    def before_path(self) -> Path:
        return self.base / ".migration_avant.json"

    @property
    def plan_path(self) -> Path:
        return self.base / ".migration_plan.json"

    @property
    def report_path(self) -> Path:
        return self.base / ".migration_ecart.txt"

    def done(self) -> list[str]:
        return profiles.migration_steps(self.base)

    def _mark(self, step: str) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        with self.journal.open("a", encoding="utf-8") as fh:
            fh.write(step + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def legacy(self) -> profiles.ProfileContext:
        """Les dossiers d'avant les profils, sous `home`."""
        from . import progression

        act = self.home / "Activities"
        return profiles.ProfileContext(
            id=None, root=self.home, profile_path=self.home / "profile.json",
            records_path=self.home / "records.json", plan_state_path=self.home / "plan_state.toml",
            activities_dir=act, journal_dir=act / ".journal",
            history_cache=self.legacy_caches[0], mmp_cache=self.legacy_caches[-1],
            shared_table_path=progression.USER_TABLE_PATH)

    # --- déroulé -----------------------------------------------------------------------------

    def run(self, stop_after: str | None = None) -> str:
        """Fait les étapes restantes ; renvoie l'état final (`fini`, `annulee` ou l'étape de coupure)."""
        done = self.done()
        if done and done[-1] in (profiles.MIGRATION_DONE, CANCELLED):
            return done[-1]
        if not done and self.main.root.exists() and any(self.main.root.iterdir()):
            raise MigrationError(f"{self.main.root} existe déjà : migration refusée (rien n'a été touché)")
        actions: dict[str, Callable[[], None]] = {
            "sauvegarde": self.backup, "instantane": self.snapshot_before, "profil": self.write_profile,
            "plan": self.write_plan, "deplacement": self.move, "records": self.rebuild_records,
            "caches": self.clear_caches, "config": self.strip_config, "controle": self.check,
            profiles.MIGRATION_DONE: lambda: None,
        }
        for step in STEPS:
            if step in done:
                continue
            try:
                actions[step]()
            except _Mismatch as exc:
                self.rollback(str(exc))
                return CANCELLED
            self._mark(step)
            log.info("migration des profils : étape %s faite", step)
            if step == stop_after:
                return step
        return profiles.MIGRATION_DONE

    # --- étapes ------------------------------------------------------------------------------

    def backup_path(self) -> Path:
        return self.home / BACKUP_DIR / f"avant_profils_{self.today:%Y%m%d}.tar.gz"

    def backup(self) -> None:
        out = self.backup_path()
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.name + ".tmp")
        with tarfile.open(tmp, "w:gz") as tar:
            for name in SAVED:
                if (self.home / name).exists():
                    tar.add(self.home / name, arcname=name)
        os.replace(tmp, out)   # une sauvegarde du même jour (reprise) est remplacée par l'état d'avant

    def _snapshot(self, ctx: profiles.ProfileContext, profile_file: Path | None) -> dict[str, Any]:
        from .tools.xp import snapshot

        cfg = config_mod.load(self.config_path, profile_file)
        out = snapshot(ctx.journal_dir, ctx, cfg, profile_path=ctx.profile_path)
        out.pop("_progress")
        return out

    def snapshot_before(self) -> None:
        _write_json(self.before_path, self._snapshot(self.legacy(), None))

    def write_profile(self) -> None:
        values = _profile_values(self.config_path)
        lines = ["# Profil de joueur OpenRide (série MJ). Fichier local : jamais versionné.",
                 "# Créé par la migration du joueur d'avant les profils (lot MJ5).",
                 "[profil]",
                 f"id = {config_edit._toml_value(profiles.MAIN_ID)}",
                 f"nom = {config_edit._toml_value(MAIN_NAME)}",
                 'type = "joueur"',
                 f"cree = {self.today.isoformat()}",
                 'seances_comptees = ["live"]']
        for section in dict.fromkeys(s for s, _ in config_mod.PROFILE_KEYS):
            found = [(k, values[(s, k)]) for s, k in config_mod.PROFILE_KEYS if s == section and (s, k) in values]
            if found:
                lines += ["", f"[{section}]", *(f"{k} = {config_edit._toml_value(v)}" for k, v in found)]
        path = self.main.root / profiles.FILE_NAME
        self.main.root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def write_plan(self) -> None:
        moves = plan_moves(self.legacy(), self.main, self.trial)
        _write_json(self.plan_path, [{k: str(Path(v).relative_to(self.home)) for k, v in m.items()} for m in moves])

    def moves(self) -> list[dict[str, str]]:
        """Déplacements du plan, en chemins absolus (le fichier les garde relatifs à `home`)."""
        return [{k: str(self.home / v) for k, v in m.items()}
                for m in json.loads(self.plan_path.read_text(encoding="utf-8"))]

    def move(self) -> None:
        for m in self.moves():
            src, dst = Path(m["from"]), Path(m["to"])
            if not src.exists():
                continue   # déjà déplacé (reprise)
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
        profiles.ensure_description(self.trial)
        act = self.home / "Activities"
        for d in (act / ".journal", act):   # dossiers vidés : retirés
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

    def rebuild_records(self) -> None:
        from .records import RecordBook, RecordsError

        old_path = self.home / "records.json"
        try:
            old = RecordBook.load(old_path)
        except RecordsError as exc:
            log.warning("migration des profils : ancien %s ignoré (%s)", old_path.name, exc)
            old = RecordBook()
        cfg = config_mod.load(self.config_path, self.main.root / profiles.FILE_NAME)
        book = rebuild_from_journals(self.main.journal_dir, old, cfg.rider.mass_kg)
        if book.routes:
            book.save(self.main.records_path)
        old_path.unlink(missing_ok=True)

    def clear_caches(self) -> None:
        for cache in self.legacy_caches:
            if cache.exists():
                cache.unlink()

    def strip_config(self) -> None:
        if not self.config_path.exists():
            return
        keys = [k for k in config_mod.PROFILE_KEYS if k in _profile_values(self.config_path)]
        try:
            config_edit.remove_keys(self.config_path, keys, CONFIG_NOTE)
        except config_edit.ConfigEditError as exc:
            raise MigrationError(str(exc)) from None

    def check(self) -> None:
        from .tools.xp import compare_snapshots, format_diff, has_changes

        before = json.loads(self.before_path.read_text(encoding="utf-8"))
        trial_journals = {Path(m["from"]).name for m in self.moves()
                          if Path(m["to"]).parent == self.trial.journal_dir}
        # Les séances simulées ou rejouées ne comptaient pas avant ; elles sont maintenant à l'essai.
        before["sessions"] = [s for s in before.get("sessions", []) if s.get("journal") not in trial_journals]
        after = self._snapshot(self.main, self.main.root / profiles.FILE_NAME)
        diff = compare_snapshots(before, after, str(self.before_path))
        if has_changes(diff):
            raise _Mismatch(format_diff(diff))

    # --- annulation -------------------------------------------------------------------------

    def rollback(self, reason: str) -> None:
        """Remet les fichiers d'avant (sauvegarde) et retire ce que la migration a créé."""
        log.error("migration des profils annulée : %s", reason)
        self.base.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(f"Migration des profils annulée le {datetime.now():%d/%m/%Y %H:%M}.\n"
                                    f"Écart de progression :\n{reason}\n", encoding="utf-8")
        moves = self.moves() if self.plan_path.is_file() else []
        with tarfile.open(self.backup_path(), "r:gz") as tar:
            tar.extractall(self.home, filter="data")
        for m in moves:   # copies déplacées : les originaux sont revenus de la sauvegarde
            Path(m["to"]).unlink(missing_ok=True)
        shutil.rmtree(self.main.root, ignore_errors=True)
        for p in (self.before_path, self.plan_path):
            p.unlink(missing_ok=True)
        self._mark(CANCELLED)


class _Mismatch(Exception):
    """Écart de progression au contrôle (étape `controle`)."""


# --- fonctions --------------------------------------------------------------------------------

def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _profile_values(config_path: Path) -> dict[tuple[str, str], Any]:
    """Clés joueur (`config.PROFILE_KEYS`) présentes dans `config.toml`."""
    if not config_path.is_file():
        return {}
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise MigrationError(f"{config_path} illisible : {exc}") from None
    out: dict[tuple[str, str], Any] = {}
    for section, key in config_mod.PROFILE_KEYS:
        table = data.get(section)
        if isinstance(table, dict) and key in table:
            out[(section, key)] = table[key]
    return out


def journal_info(path: Path) -> tuple[str | None, str | None, str | None, float | None]:
    """`source`, `profile_id`, `route_id` de l'en-tête et heure du premier relevé ; None si absent."""
    source = profile_id = route_id = None
    try:
        for line in read_journal(path):
            kind = line.get("kind")
            if kind == "header":
                source, profile_id, route_id = line.get("source"), line.get("profile_id"), line.get("route_id")
            elif kind == "record":
                return source, profile_id, route_id, float(line["ts"])
    except (OSError, KeyError, TypeError, ValueError):
        pass
    return source, profile_id, route_id, None


def fit_pattern(route_id: str | None, start_ts: float) -> re.Pattern[str]:
    """Nom du FIT écrit pour ce journal (`fit_export.default_fit_path`, suffixes `_essai` et `_n`)."""
    stamp = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d_%H-%M")
    base = re.escape(f"{stamp}_{route_id or 'seance'}")
    return re.compile(rf"^{base}(_essai)?(_\d+)?\.fit$")


def _free(dst: Path, taken: set[Path]) -> Path:
    """`dst`, ou `dst` suffixé `_2`, `_3`… s'il existe déjà ou est déjà promis."""
    n, out = 1, dst
    while out.exists() or out in taken:
        n += 1
        out = dst.with_name(f"{dst.stem}_{n}{dst.suffix}")
    taken.add(out)
    return out


def plan_moves(legacy: profiles.ProfileContext, main: profiles.ProfileContext,
               trial: profiles.ProfileContext) -> list[dict[str, str]]:
    """Déplacements de la migration, de l'ancien dossier vers `principal` ou `_essai`."""
    moves: list[dict[str, str]] = []
    taken: set[Path] = set()

    def add(src: Path, dst: Path) -> None:
        moves.append({"from": str(src), "to": str(_free(dst, taken))})

    for name in MOVED_FILES:
        if (legacy.root / name).exists():
            add(legacy.root / name, main.root / name)
    to_trial: set[Path] = set()
    fits = sorted(p for p in legacy.activities_dir.glob("*.fit")) if legacy.activities_dir.is_dir() else []
    journals = sorted(legacy.journal_dir.iterdir()) if legacy.journal_dir.is_dir() else []
    for j in journals:
        source, profile_id, route_id, start = (journal_info(j) if j.suffix == ".jsonl"
                                               else (None, None, None, None))
        trial_session = source in TRIAL_SOURCES or profile_id == profiles.TRIAL_ID
        ctx = trial if trial_session else main
        add(j, ctx.journal_dir / j.name)
        if trial_session and start is not None:
            pat = fit_pattern(route_id, start)
            to_trial.update(f for f in fits if pat.match(f.name))
    for f in sorted(to_trial):
        add(f, trial.activities_dir / f.name)
    if legacy.activities_dir.is_dir():
        for entry in sorted(legacy.activities_dir.iterdir()):
            if entry.name != ".journal" and entry not in to_trial:
                add(entry, main.activities_dir / entry.name)   # FIT réels, FIT sans journal, autres
    return moves


def rebuild_from_journals(journal_dir: Path, old: Any, rider_mass_kg: float | None) -> Any:
    """Records recalculés des journaux de `journal_dir`, parcours par parcours ; un parcours
    introuvable garde ses records de `old`."""
    from .records import RecordBook
    from .route import WorldError, find_world, load_world, routes_dir

    journals = sorted(journal_dir.glob("*.jsonl")) if journal_dir.is_dir() else []
    route_ids = sorted({r for j in journals if (r := journal_info(j)[2])})
    book = RecordBook()
    for route_id in route_ids:
        try:
            world = load_world(find_world(route_id, routes_dir()))
        except WorldError as exc:
            log.warning("migration des profils : records de %s gardés (%s)", route_id, exc)
            if route_id in old.routes:
                book.routes[route_id] = old.routes[route_id]
            continue
        book.merge(RecordBook.rebuild(route_id, journals, list(world.segments), world.route.length_m,
                                      world.route.is_loop, rider_mass_kg))
    return book


def needed(home: Path | None = None) -> bool:
    """Vrai tant que la migration n'est ni finie ni annulée."""
    steps = profiles.migration_steps((home if home is not None else config_mod.OPENRIDE_HOME)
                                     / profiles.PROFILES_DIRNAME)
    return not steps or steps[-1] not in (profiles.MIGRATION_DONE, CANCELLED)


def migrate(home: Path | None = None) -> str:
    """Point d'entrée du lanceur : fait la migration si elle reste à faire ; renvoie son état."""
    if not needed(home):
        return profiles.migration_steps((home or config_mod.OPENRIDE_HOME) / profiles.PROFILES_DIRNAME)[-1]
    return Migration(home).run()
