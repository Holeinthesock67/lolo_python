"""Plans d'entraînement sur plusieurs semaines (lot O11) : `openride-core plan …`.

Un plan (`~/OpenRide/Plans/<id>.toml`, format décrit dans `docs/contracts/plan_format_v1.md`)
range par semaine et par jour des entraînements de la bibliothèque (`~/OpenRide/Workouts/`,
`.zwo`, `.erg`, `.mrc`) ou des tests de FTP (`ftp_test:ramp`, lot O10).

- Jours : `lundi` à `dimanche` (calendrier) ou `jour1` à `jour7` (plan sans calendrier). La
  semaine 1 est la semaine du lundi au dimanche qui contient la date de début ; les séances de
  la semaine 1 placées avant la date de début ne comptent pas. Avec `jourN`, la séance tombe
  N − 1 jours après le début de sa semaine de plan (date de début + 7 × (semaine − 1)).
- Plan actif : `~/OpenRide/plan_state.toml` (hors du dépôt), écrit par `start_plan`.
- Une séance prévue est **faite** si une séance de l'historique du même jour, ou rattrapée dans
  les `CATCH_UP_DAYS` jours suivants, porte le même entraînement (`workout_id` du journal) et a
  duré au moins `DONE_RATIO` de la durée prévue. Chaque séance de l'historique ne compte qu'une fois.
- Le journal d'une séance roulée pendant un plan actif porte `plan` = {id, week, day} (en-tête,
  champ facultatif) quand l'entraînement est celui du jour ou une séance en retard rattrapable.
"""

from __future__ import annotations

import re
import shutil
import sys
import tomllib
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from . import config as config_mod
from .workout import WORKOUT_SUFFIXES, WorkoutError, load_workout, workout_path

PLANS_DIR = config_mod.PLANS_DIR
STATE_PATH = config_mod.OPENRIDE_HOME / "plan_state.toml"
BUILTIN_PLANS_DIR = Path(__file__).resolve().parents[2] / "plans"
BUILTIN_WORKOUTS_DIR = Path(__file__).resolve().parents[2] / "workouts"

WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
GENERIC_DAYS = tuple(f"jour{i}" for i in range(1, 8))
FTP_TESTS = ("ftp_test:ramp",)
CATCH_UP_DAYS = 3
DONE_RATIO = 0.8
PLAN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class PlanError(Exception):
    """Plan invalide ou commande refusée ; message lisible."""


@dataclass(frozen=True)
class PlanDay:
    week: int          # à partir de 1
    day: str           # « mardi » ou « jour2 »
    workout: str       # identifiant de la bibliothèque ou ftp_test:…


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    description: str
    days_per_week: int
    focus: tuple[str, ...]          # thème de chaque semaine
    days: tuple[PlanDay, ...]
    durations_s: dict[str, float] = field(default_factory=dict, compare=False)   # durée prévue par entraînement

    @property
    def weeks(self) -> int:
        return len(self.focus)


@dataclass(frozen=True)
class PlanInfo:
    id: str
    name: str
    weeks: int
    sessions: int
    error: str | None = None


@dataclass(frozen=True)
class PlanState:
    plan_id: str
    start: date


@dataclass(frozen=True)
class DoneSession:
    """Séance de l'historique, réduite à ce qui sert au suivi d'un plan."""
    day: date
    workout_id: str | None
    duration_s: float


# --- lecture et validation -----------------------------------------------------------------

def normalize_id(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "plan"


def ftp_tests_available() -> bool:
    try:
        from . import ftp_test  # noqa: F401  (lot O10)
    except ImportError:
        return False
    return True


def workout_duration(workout: str, workouts_dir: Path) -> float:
    """Durée prévue d'une séance ; lève `PlanError` si l'entraînement est absent ou invalide."""
    if workout in FTP_TESTS:
        if not ftp_tests_available():
            raise PlanError(f"« {workout} » : test de FTP pas encore disponible (lot O10)")
        from . import ftp_test

        return float(ftp_test.planned_duration_s(workout.split(":", 1)[1]))
    if workout.startswith("ftp_test:"):
        raise PlanError(f"« {workout} » : test de FTP inconnu (attendu {', '.join(FTP_TESTS)})")
    try:
        return load_workout(workout_path(workouts_dir, workout)).duration_s
    except WorkoutError as exc:
        raise PlanError(f"entraînement « {workout} » : {exc}") from None


def parse_plan(data: dict[str, Any], plan_id: str, workouts_dir: Path) -> Plan:
    head = data.get("plan")
    if not isinstance(head, dict) or not isinstance(head.get("name"), str) or not head["name"].strip():
        raise PlanError("section [plan] absente ou sans « name »")
    weeks = data.get("week")
    if not isinstance(weeks, list) or not weeks:
        raise PlanError("aucune semaine ([[week]])")
    dpw = head.get("days_per_week", 0)
    if isinstance(dpw, bool) or not isinstance(dpw, int) or not 1 <= dpw <= 7:
        raise PlanError("plan.days_per_week : entier de 1 à 7 attendu")
    days: list[PlanDay] = []
    focus: list[str] = []
    durations: dict[str, float] = {}
    for w_index, week in enumerate(weeks, start=1):
        if not isinstance(week, dict) or not isinstance(week.get("days"), list):
            raise PlanError(f"semaine {w_index} : liste « days » attendue")
        focus.append(str(week.get("focus", "")))
        seen: set[str] = set()
        for item in week["days"]:
            if not isinstance(item, dict):
                raise PlanError(f"semaine {w_index} : jour mal formé {item!r}")
            day, workout = item.get("day"), item.get("workout")
            if day not in WEEKDAYS + GENERIC_DAYS:
                raise PlanError(f"semaine {w_index} : jour {day!r} inconnu (lundi à dimanche ou jour1 à jour7)")
            if day in seen:
                raise PlanError(f"semaine {w_index} : {day} cité deux fois")
            seen.add(day)
            if not isinstance(workout, str) or not workout.strip():
                raise PlanError(f"semaine {w_index}, {day} : « workout » manquant")
            if workout not in durations:
                durations[workout] = workout_duration(workout, workouts_dir)
            days.append(PlanDay(w_index, day, workout))
    kinds = {d.day in WEEKDAYS for d in days}
    if len(kinds) > 1:
        raise PlanError("jours de la semaine et jour1 à jour7 mélangés dans le même plan")
    return Plan(plan_id, head["name"].strip(), str(head.get("description", "")), dpw, tuple(focus),
                tuple(days), durations)


def load_plan(plan_id: str, plans_dir: Path | None = None, workouts_dir: Path | None = None) -> Plan:
    plans_dir = PLANS_DIR if plans_dir is None else plans_dir
    workouts_dir = config_mod.WORKOUTS_DIR if workouts_dir is None else workouts_dir
    if not PLAN_ID_RE.match(plan_id):
        raise PlanError(f"identifiant de plan invalide : {plan_id!r}")
    path = plans_dir / f"{plan_id}.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PlanError(f"plan « {plan_id} » introuvable dans {plans_dir}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise PlanError(f"{path.name} : lecture impossible : {exc}") from None
    except tomllib.TOMLDecodeError as exc:
        raise PlanError(f"{path.name} : TOML invalide : {exc}") from None
    try:
        return parse_plan(data, plan_id, workouts_dir)
    except PlanError as exc:
        raise PlanError(f"{path.name} : {exc}") from None


def list_plans(plans_dir: Path | None = None, workouts_dir: Path | None = None) -> list[PlanInfo]:
    """Plans du dossier, triés ; un plan invalide est listé avec son erreur."""
    plans_dir = PLANS_DIR if plans_dir is None else plans_dir
    if not plans_dir.is_dir():
        return []
    out: list[PlanInfo] = []
    for path in sorted(plans_dir.glob("*.toml")):
        try:
            p = load_plan(path.stem, plans_dir, workouts_dir)
        except PlanError as exc:
            out.append(PlanInfo(path.stem, path.stem, 0, 0, str(exc)))
        else:
            out.append(PlanInfo(p.id, p.name, p.weeks, len(p.days)))
    return out


# --- calendrier et suivi -----------------------------------------------------------------------

def scheduled_date(entry: PlanDay, start: date) -> date:
    if entry.day in WEEKDAYS:
        monday = start - timedelta(days=start.weekday())
        return monday + timedelta(weeks=entry.week - 1, days=WEEKDAYS.index(entry.day))
    return start + timedelta(weeks=entry.week - 1, days=GENERIC_DAYS.index(entry.day))


def schedule(plan: Plan, start: date) -> list[tuple[PlanDay, date]]:
    """Séances du plan avec leur date, dans l'ordre ; celles placées avant le début sont omises."""
    out = [(d, scheduled_date(d, start)) for d in plan.days]
    return sorted(((d, when) for d, when in out if when >= start), key=lambda dw: (dw[1], dw[0].week))


def match_done(plan: Plan, start: date, history: Iterable[DoneSession]) -> dict[int, DoneSession]:
    """Index dans `schedule()` → séance de l'historique qui la valide."""
    sched = schedule(plan, start)
    pool = sorted((h for h in history if h.workout_id), key=lambda h: h.day)
    used: set[int] = set()
    done: dict[int, DoneSession] = {}
    for i, (entry, when) in enumerate(sched):
        need = DONE_RATIO * plan.durations_s.get(entry.workout, 0.0)
        for k, h in enumerate(pool):
            if k in used or h.workout_id != entry.workout:
                continue
            if when <= h.day <= when + timedelta(days=CATCH_UP_DAYS) and h.duration_s >= need:
                used.add(k)
                done[i] = h
                break
    return done


def _entry_dict(entry: PlanDay, when: date, plan: Plan, done: DoneSession | None) -> dict[str, Any]:
    return {"week": entry.week, "day": entry.day, "date": when.isoformat(), "workout": entry.workout,
            "duration_s": round(plan.durations_s.get(entry.workout, 0.0), 1), "done": done is not None,
            "done_on": done.day.isoformat() if done else None}


def today(plan: Plan, start: date, history: Iterable[DoneSession], on: date | None = None) -> dict[str, Any]:
    """Séance du jour, séances en retard, semaine en cours et pourcentage fait."""
    on = date.today() if on is None else on
    sched = schedule(plan, start)
    done = match_done(plan, start, history)
    todays = [_entry_dict(e, w, plan, done.get(i)) for i, (e, w) in enumerate(sched) if w == on]
    late = []
    for i, (e, w) in enumerate(sched):
        if w < on and i not in done:
            item = _entry_dict(e, w, plan, None)
            item["catch_up"] = on <= w + timedelta(days=CATCH_UP_DAYS)
            late.append(item)
    monday = start - timedelta(days=start.weekday())
    week = (on - (monday if plan.days and plan.days[0].day in WEEKDAYS else start)).days // 7 + 1
    upcoming = [_entry_dict(e, w, plan, None) for i, (e, w) in enumerate(sched) if w > on][:1]
    return {
        "plan": plan.id, "name": plan.name, "start": start.isoformat(), "date": on.isoformat(),
        "week": week if 1 <= week <= plan.weeks else None, "weeks": plan.weeks,
        "finished": on > (sched[-1][1] + timedelta(days=CATCH_UP_DAYS)) if sched else True,
        "today": todays, "late": late, "next": upcoming[0] if upcoming else None,
        "done": len(done), "total": len(sched),
        "done_pct": round(100.0 * len(done) / len(sched), 1) if sched else 0.0,
    }


def plan_tag(plan: Plan, start: date, workout_id: str, on: date | None = None) -> dict[str, Any] | None:
    """`{id, week, day}` de la séance prévue que cet entraînement réalise aujourd'hui (ou rattrape)."""
    on = date.today() if on is None else on
    candidates = [(when, e) for e, when in schedule(plan, start)
                  if e.workout == workout_id and when <= on <= when + timedelta(days=CATCH_UP_DAYS)]
    if not candidates:
        return None
    when, entry = max(candidates, key=lambda c: c[0])   # la plus récente : celle du jour d'abord
    return {"id": plan.id, "week": entry.week, "day": entry.day}


def plan_summary(plan: Plan, ftp_w: float, workouts_dir: Path | None = None) -> list[dict[str, Any]]:
    """Durée, TSS et nombre de séances par semaine (`estimate_metrics` des outils d'entraînements)."""
    from .tools.workouts import estimate_metrics

    workouts_dir = config_mod.WORKOUTS_DIR if workouts_dir is None else workouts_dir
    tss_cache: dict[str, float] = {}
    out = []
    for w in range(1, plan.weeks + 1):
        entries = [d for d in plan.days if d.week == w]
        tss = 0.0
        for d in entries:
            if d.workout not in tss_cache:
                if d.workout in FTP_TESTS:
                    from . import ftp_test

                    planned = ftp_test.planned_workout(d.workout.split(":", 1)[1], ftp_w)
                    tss_cache[d.workout] = estimate_metrics(planned, ftp_w)["tss"]
                else:
                    tss_cache[d.workout] = estimate_metrics(load_workout(workout_path(workouts_dir, d.workout)),
                                                            ftp_w)["tss"]
            tss += tss_cache[d.workout]
        out.append({"week": w, "focus": plan.focus[w - 1], "sessions": len(entries),
                    "duration_s": round(sum(plan.durations_s[d.workout] for d in entries), 1),
                    "tss": round(tss, 1),
                    "days": [{"day": d.day, "workout": d.workout} for d in entries]})
    return out


# --- plan actif --------------------------------------------------------------------------------

def _state_path(state_path: Path | None) -> Path:
    """Chemin donné, sinon le plan actif du profil de joueur en cours (série MJ, lot MJ1)."""
    if state_path is not None:
        return state_path
    from . import profiles
    return profiles.current().plan_state_path


def load_state(state_path: Path | None = None) -> PlanState | None:
    path = _state_path(state_path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        active = data["active"]
        return PlanState(str(active["plan"]), date.fromisoformat(str(active["start"])))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError, ValueError):
        return None


def start_plan(plan_id: str, start: date | None = None, plans_dir: Path | None = None,
               workouts_dir: Path | None = None, state_path: Path | None = None) -> PlanState:
    """Rend le plan actif ; refuse un plan invalide (rien n'est écrit)."""
    load_plan(plan_id, plans_dir, workouts_dir)
    st = PlanState(plan_id, date.today() if start is None else start)
    path = _state_path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Plan d'entraînement actif (openride-core plan start), lot O11\n"
                    f'[active]\nplan = "{st.plan_id}"\nstart = "{st.start.isoformat()}"\n', encoding="utf-8")
    return st


def stop_plan(state_path: Path | None = None) -> bool:
    path = _state_path(state_path)
    if path.exists():
        path.unlink()
        return True
    return False


def active_tag(workout_id: str | None, on: date | None = None, state_path: Path | None = None,
               plans_dir: Path | None = None, workouts_dir: Path | None = None) -> dict[str, Any] | None:
    """Champ `plan` du journal pour la séance qui commence (None sans plan actif ou hors plan).

    Ne lève jamais : un plan abîmé ne doit pas empêcher de rouler.
    """
    if not workout_id:
        return None
    try:
        st = load_state(state_path)
        if st is None:
            return None
        return plan_tag(load_plan(st.plan_id, plans_dir, workouts_dir), st.start, workout_id, on)
    except Exception:
        return None


def history_sessions(activities_dir: Path | None = None, ftp_w: float = 250.0) -> list[DoneSession]:
    """Séances de l'historique (`openride-core history`) réduites au jour, à l'entraînement et à la durée."""
    from datetime import datetime

    from .tools.history import compute_history

    result = compute_history(activities_dir, ftp_w, weeks=520)
    out = []
    for s in result["sessions"]:
        if s.get("status") == "error" or s.get("start_ts") is None:
            continue
        out.append(DoneSession(datetime.fromtimestamp(s["start_ts"]).date(), s.get("workout"),
                               float(s.get("duration_s") or 0.0)))
    return out


# --- import d'un dossier et plans de référence ------------------------------------------------

def natural_key(text: str) -> list[Any]:
    """`w1d2` < `w1d10` ; « semaine 10 » après « semaine 9 »."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def _toml_str(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def plan_toml(name: str, description: str, days_per_week: int, weeks: list[tuple[str, list[tuple[str, str]]]]) -> str:
    lines = ["# Plan d'entraînement OpenRide (docs/contracts/plan_format_v1.md)", "[plan]",
             f"name = {_toml_str(name)}", f"description = {_toml_str(description)}",
             f"days_per_week = {days_per_week}"]
    for focus, days in weeks:
        lines += ["", "[[week]]", f"focus = {_toml_str(focus)}", "days = ["]
        lines += [f"  {{ day = {_toml_str(d)}, workout = {_toml_str(w)} }}," for d, w in days]
        lines.append("]")
    return "\n".join(lines) + "\n"


def import_folder(src: Path, name: str, days: list[str], plans_dir: Path | None = None,
                  workouts_dir: Path | None = None) -> tuple[Plan, list[str]]:
    """Crée un plan depuis un dossier d'entraînements numérotés ; renvoie le plan et les fichiers copiés.

    Les entraînements sont copiés dans la bibliothèque sous `<id du plan>_<nom>` ; un fichier
    existant de contenu différent n'est jamais écrasé (import refusé, rien n'est copié).
    """
    plans_dir = PLANS_DIR if plans_dir is None else plans_dir
    workouts_dir = config_mod.WORKOUTS_DIR if workouts_dir is None else workouts_dir
    if not days or any(d not in WEEKDAYS + GENERIC_DAYS for d in days) or len(set(days)) != len(days):
        raise PlanError("--days : jours distincts parmi lundi à dimanche ou jour1 à jour7")
    if not src.is_dir():
        raise PlanError(f"{src} : dossier introuvable")
    files = sorted((p for p in src.iterdir() if p.is_file() and p.suffix.lower() in WORKOUT_SUFFIXES),
                   key=lambda p: natural_key(p.name))
    if not files:
        raise PlanError(f"{src} : aucun entraînement .zwo, .erg ou .mrc")
    plan_id = normalize_id(name)
    target = plans_dir / f"{plan_id}.toml"
    if target.exists():
        raise PlanError(f"le plan « {plan_id} » existe déjà ({target})")
    copies: list[tuple[Path, Path]] = []
    for p in files:
        dst = workouts_dir / f"{plan_id}_{normalize_id(p.stem)}{p.suffix.lower()}"
        if dst.exists() and dst.read_bytes() != p.read_bytes():
            raise PlanError(f"{dst.name} existe déjà dans la bibliothèque avec un autre contenu : import refusé")
        try:
            load_workout(p)
        except WorkoutError as exc:
            raise PlanError(f"{p.name} : {exc}") from None
        copies.append((p, dst))
    weeks = []
    for i in range(0, len(copies), len(days)):
        chunk = copies[i:i + len(days)]
        weeks.append(("", [(days[k], dst.stem) for k, (_, dst) in enumerate(chunk)]))
    workouts_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for p, dst in copies:
        if not dst.exists():
            shutil.copy2(p, dst)
            copied.append(dst.name)
    plans_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(plan_toml(name, f"Importé de {src.name}", len(days), weeks), encoding="utf-8")
    return load_plan(plan_id, plans_dir, workouts_dir), copied


def install_builtin(plans_dir: Path | None = None, workouts_dir: Path | None = None) -> tuple[list[str], list[str]]:
    """Copie les plans de référence (`core/plans/`) et les entraînements de référence qu'ils citent,
    sans rien écraser ; renvoie `(copiés, conservés)`."""
    plans_dir = PLANS_DIR if plans_dir is None else plans_dir
    workouts_dir = config_mod.WORKOUTS_DIR if workouts_dir is None else workouts_dir
    copied: list[str] = []
    kept: list[str] = []
    workouts_dir.mkdir(parents=True, exist_ok=True)
    plans_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(BUILTIN_PLANS_DIR.glob("*.toml")):
        data = tomllib.loads(src.read_text(encoding="utf-8"))
        for week in data.get("week", []):
            for item in week.get("days", []):
                wid = item.get("workout", "")
                if wid in FTP_TESTS:
                    continue
                for builtin in BUILTIN_WORKOUTS_DIR.glob(f"{wid}.*"):
                    if builtin.suffix.lower() not in WORKOUT_SUFFIXES:
                        continue
                    dst = workouts_dir / builtin.name
                    if dst.exists():
                        if dst.name not in kept and dst.name not in copied:
                            kept.append(dst.name)
                    else:
                        shutil.copy2(builtin, dst)
                        copied.append(dst.name)
        dst = plans_dir / src.name
        if dst.exists():
            kept.append(dst.name)
        else:
            shutil.copy2(src, dst)
            copied.append(dst.name)
    return copied, kept


# --- ligne de commande -----------------------------------------------------------------------

def _hms(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"


def run(args: Any) -> int:
    """`openride-core plan list|show ID|start ID [--date]|stop|today|import|install`."""
    import json

    cfg_path = getattr(args, "config", None)
    try:
        cfg = config_mod.load(cfg_path)
    except config_mod.ConfigError as exc:
        print(f"openride-core plan : {exc}", file=sys.stderr)
        return 1
    plans_dir = args.plans_dir or PLANS_DIR
    workouts_dir = args.workouts_dir or config_mod.WORKOUTS_DIR
    state_path = _state_path(args.state)
    try:
        if args.action == "list":
            infos = list_plans(plans_dir, workouts_dir)
            st = load_state(state_path)
            if args.json:
                print(json.dumps([vars(i) for i in infos], ensure_ascii=False, indent=2))
                return 0
            if not infos:
                print(f"Aucun plan dans {plans_dir} (openride-core plan install pour les plans de référence).")
            for i in infos:
                mark = "*" if st and st.plan_id == i.id else " "
                state = f"erreur : {i.error}" if i.error else f"{i.weeks} semaine(s), {i.sessions} séance(s)"
                print(f"{mark} {i.id:<28} {i.name:<36} {state}")
            return 0
        if args.action == "show":
            plan = load_plan(_need(args.plan_id), plans_dir, workouts_dir)
            weeks = plan_summary(plan, cfg.rider.ftp_w, workouts_dir)
            if args.json:
                print(json.dumps({"id": plan.id, "name": plan.name, "weeks": weeks}, ensure_ascii=False, indent=2))
                return 0
            print(f"{plan.name} ({plan.id}) : {plan.weeks} semaine(s), FTP {cfg.rider.ftp_w:.0f} W")
            if plan.description:
                print(f"  {plan.description}")
            for w in weeks:
                focus = f" – {w['focus']}" if w["focus"] else ""
                print(f"Semaine {w['week']}{focus} : {w['sessions']} séance(s), {_hms(w['duration_s'])}, TSS {w['tss']:.1f}")
                for d in w["days"]:
                    print(f"    {d['day']:<9} {d['workout']}")
            return 0
        if args.action == "start":
            start = date.fromisoformat(args.date) if args.date else None
            st = start_plan(_need(args.plan_id), start, plans_dir, workouts_dir, state_path)
            print(f"Plan « {st.plan_id} » actif depuis le {st.start.isoformat()}.")
            return 0
        if args.action == "stop":
            print("Plan arrêté." if stop_plan(state_path) else "Aucun plan actif.")
            return 0
        if args.action == "today":
            st = load_state(state_path)
            if st is None:
                print("Aucun plan actif (openride-core plan start ID).")
                return 0
            plan = load_plan(st.plan_id, plans_dir, workouts_dir)
            res = today(plan, st.start, history_sessions(args.activities_dir, cfg.rider.ftp_w))
            if args.json:
                print(json.dumps(res, ensure_ascii=False, indent=2))
                return 0
            week = f"semaine {res['week']}/{res['weeks']}" if res["week"] else "hors des semaines du plan"
            print(f"{res['name']} : {week}, {res['done']}/{res['total']} séances faites ({res['done_pct']:.0f} %)")
            for t in res["today"]:
                print(f"  Aujourd'hui : {t['workout']} ({_hms(t['duration_s'])})" + (" – faite" if t["done"] else ""))
            if not res["today"]:
                nxt = res["next"]
                print("  Repos aujourd'hui." + (f" Prochaine : {nxt['workout']} le {nxt['date']}." if nxt else ""))
            for t in res["late"]:
                when = "à rattraper" if t["catch_up"] else "manquée"
                print(f"  En retard ({when}) : {t['workout']}, prévue le {t['date']}")
            return 0
        if args.action == "import":
            if not args.name or not args.days:
                raise PlanError("usage : openride-core plan import DOSSIER --name NOM --days mardi,jeudi,samedi")
            plan, copied = import_folder(Path(_need(args.plan_id)), args.name,
                                         [d.strip() for d in args.days.split(",") if d.strip()],
                                         plans_dir, workouts_dir)
            print(f"Plan « {plan.id} » créé : {plan.weeks} semaine(s), {len(plan.days)} séance(s) ; "
                  f"{len(copied)} entraînement(s) copié(s) dans {workouts_dir}.")
            return 0
        if args.action == "install":
            copied, kept = install_builtin(plans_dir, workouts_dir)
            print(f"{len(copied)} fichier(s) copié(s) ({', '.join(copied) or 'aucun'}), "
                  f"{len(kept)} conservé(s) sans écrasement ({', '.join(kept) or 'aucun'}).")
            return 0
    except (PlanError, ValueError) as exc:
        print(f"openride-core plan : {exc}", file=sys.stderr)
        return 1
    print(f"openride-core plan : action inconnue {args.action!r}", file=sys.stderr)
    return 2


def _need(value: str | None) -> str:
    if not value:
        raise PlanError("argument manquant (identifiant du plan ou dossier)")
    return value
