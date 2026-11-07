"""Séance conseillée (série CO, lot CO1) : besoin du jour et sa raison, calculés depuis l'historique.

    openride-core coach [--date AAAA-MM-JJ] [--objectif endurance|courses|grimpeur] [--temps MIN]
                        [--montre TYPE[:MIN[:W]]] [--prochaine-course AAAA-MM-JJ] [--dir DOSSIER]
                        [--ftp W] [--json] [--config FICHIER]

Plan et règles : `docs/5.0/PLAN_SERIE_CO.md`. Toutes les valeurs (zones de chaque besoin, cibles par
objectif, seuils des règles) viennent de la table `data/coach.toml` ; zones, NP, TSS et meilleures
puissances viennent de `tools/session_summary.py` (aucune seconde formule).

Trois besoins : `light` (aérobie léger, Z1–Z2), `intense` (aérobie intense, Z3–Z5), `anaerobic`
(anaérobie, Z6–Z7) ; et trois conseils à part : `recovery` (récupération), `ftp_test` (test de FTP),
`rest` (repos, seulement sur suggestion de la montre). Règles lues dans l'ordre, la première qui
s'applique décide : RG (suggestion de la montre Garmin saisie aujourd'hui), R0 (pas assez de séances),
R1 (course hier ou forme très basse), R2 (course dans 1 à 2 jours), R3 (fatigue), R4 (FTP ancienne),
R5 (séance du plan actif), R6 (plus grand retard sur la cible, avec garde-fous), R7 (départage de R6).

Séances lues : celles du profil en cours (`~/OpenRide/Profils/<id>/Activities/` et `.journal/`) des
`history_days` derniers jours. Une séance présente en `.fit` et en `.jsonl` (± 60 s) n'est comptée
qu'une fois, depuis le journal, qui porte sa source et ses tests de FTP. Les séances rejouées ne
comptent jamais ; les séances simulées seulement sur un profil qui les compte (profil d'essai).
Faits de chaque séance mis en cache dans `.cache/coach.json` du profil (clé : chemin, taille,
`mtime_ns`, FTP). Rien d'autre n'est écrit.

Les entrées de la course hier, de la prochaine course (lot CO6) et de la suggestion de la montre
(lot CO8) sont des paramètres de `recommend` ; CO1 les reçoit de la ligne de commande seulement.

Clés de la sortie `--json` (stables) : date, need, need_label, rule, reason, duration_min, notes
(liste de textes), alternatives (besoins proposés en second), details {objective, targets_pct,
shares_pct, deficits_pts, sessions_28d, duration_28d_s, ctl, atl, form, days_since_hard,
hard_last_7d, ftp_w, ftp_test_date, ftp_age_days, profile ({fenêtre: multiple de la FTP} ou null),
profile_weak (besoin ou null), last_by_need ({besoin: date ou null}), plan (null ou {plan, name,
week, workout}), watch (null ou {type, need, duration_min, target_w}), next_race (null ou date)}.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

TABLE_PATH = Path(__file__).resolve().parent / "data" / "coach.toml"
NEEDS = ("light", "intense", "anaerobic")
LABELS = {
    "light": "aérobie léger", "intense": "aérobie intense", "anaerobic": "anaérobie",
    "recovery": "récupération", "ftp_test": "test de FTP", "rest": "repos",
}
OBJECTIVES = ("endurance", "courses", "grimpeur")
MATCH_TOLERANCE_S = 60.0


class CoachError(ValueError):
    """Table invalide ou entrée refusée ; message lisible."""


# --- table ----------------------------------------------------------------------------------------

def load_table(path: Path | None = None) -> dict[str, Any]:
    p = TABLE_PATH if path is None else Path(path)
    try:
        table = tomllib.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise CoachError(f"table du conseil illisible ({p}) : {exc}") from exc
    for key in ("needs", "window", "hard", "targets", "rules", "profile", "durations", "watch"):
        if key not in table:
            raise CoachError(f"table du conseil : section [{key}] absente")
    return table


# --- faits d'une séance (pur) ---------------------------------------------------------------------

@dataclass(frozen=True)
class SessionFacts:
    """Ce que le conseil retient d'une séance."""
    start_ts: float
    duration_s: float
    tss: float
    need_s: dict[str, float]                 # secondes dans les zones de chaque besoin
    hard: bool
    best_w: dict[str, float | None]          # meilleures puissances du bilan (5s, 1min, 5min, 20min)
    ftp_test_w: float | None = None          # FTP calculée par un test de FTP de la séance
    source: str = ""                         # live, simulated, replay ou "" (FIT sans journal)

    @property
    def day(self) -> date:
        return datetime.fromtimestamp(self.start_ts).date()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SessionFacts":
        return cls(float(d["start_ts"]), float(d["duration_s"]), float(d["tss"]),
                   {k: float(v) for k, v in d["need_s"].items()}, bool(d["hard"]),
                   dict(d["best_w"]), d.get("ftp_test_w"), str(d.get("source") or ""))


def _efforts(powers: list[float], floor_w: float, min_s: int) -> int:
    """Nombre de suites d'au moins `min_s` secondes au-dessus de `floor_w`."""
    count = run = 0
    for p in powers + [0.0]:
        if p >= floor_w:
            run += 1
        else:
            if run >= min_s:
                count += 1
            run = 0
    return count


def session_facts(session: Any, ftp_w: float, table: dict[str, Any], source: str = "") -> SessionFacts:
    """Faits d'une séance chargée par `session_summary.load_session`."""
    from .tools.session_summary import compute_summary, running_records

    s = compute_summary(session, ftp_w)
    zone_s = {z["zone"]: float(z["seconds"]) for z in s["zones"]}
    need_s = {n: sum(zone_s.get(z, 0.0) for z in table["needs"][n]) for n in NEEDS}
    hard_cfg = table["hard"]
    threshold_s = sum(zone_s.get(z, 0.0) for z in hard_cfg["threshold_zones"])
    recs = running_records(session.records, session.events)
    powers = [max(0.0, float(r["power"])) if r.get("power") is not None else 0.0 for r in recs]
    efforts = _efforts(powers, ftp_w * hard_cfg["effort_pct"] / 100.0, int(hard_cfg["effort_min_s"]))
    hard = threshold_s >= hard_cfg["threshold_min_s"] or efforts >= hard_cfg["effort_count"]
    test_w = None
    for t in getattr(session, "ftp_tests", []) or []:
        if isinstance(t.get("ftp_w"), (int, float)) and t["ftp_w"] > 0:
            test_w = float(t["ftp_w"])
    return SessionFacts(float(s["start_ts"]), float(s["duration_s"]), float(s["tss"]), need_s, hard,
                        dict(s["best_power_w"]), test_w, source)


# --- signaux (pur) --------------------------------------------------------------------------------

def _ewma(daily: list[float], days: int) -> float:
    value = 0.0
    for tss in daily:
        value += (tss - value) / days
    return value


def build_signals(facts: Iterable[SessionFacts], ftp_w: float, today: date, table: dict[str, Any]) -> dict[str, Any]:
    """Signaux S1 à S4 et S7 au jour `today` (séances de `today` comprises)."""
    win, hard_cfg = table["window"], table["hard"]
    facts = sorted((f for f in facts if f.day <= today), key=lambda f: f.start_ts)
    share_from = today - timedelta(days=int(win["share_days"]) - 1)
    recent = [f for f in facts if f.day >= share_from]
    totals = {n: sum(f.need_s[n] for f in recent) for n in NEEDS}
    all_s = sum(totals.values())
    shares = {n: (100.0 * totals[n] / all_s if all_s else 0.0) for n in NEEDS}

    start = today - timedelta(days=int(win["history_days"]) - 1)
    by_day: dict[date, float] = {}
    for f in facts:
        by_day[f.day] = by_day.get(f.day, 0.0) + f.tss
    daily = [by_day.get(start + timedelta(days=i), 0.0) for i in range((today - start).days + 1)]
    ctl, atl = _ewma(daily, int(win["ctl_days"])), _ewma(daily, int(win["atl_days"]))

    hard_days = sorted({f.day for f in facts if f.hard})
    days_since_hard = (today - hard_days[-1]).days if hard_days else None
    hard_last_7 = sum(1 for f in facts if f.hard and (today - f.day).days < 7)

    minimum = {"light": hard_cfg["recent_light_s"], "intense": hard_cfg["recent_intense_s"],
               "anaerobic": hard_cfg["recent_anaerobic_s"]}
    last_by_need: dict[str, date | None] = {}
    for n in NEEDS:
        days = [f.day for f in facts if f.need_s[n] >= minimum[n]]
        last_by_need[n] = days[-1] if days else None

    tests = [f for f in facts if f.ftp_test_w]
    ftp_test_date = tests[-1].day if tests else None
    ftp_age = (today - ftp_test_date).days if ftp_test_date else None

    profile = None
    profile_from = today - timedelta(days=int(win["profile_days"]) - 1)
    if ftp_age is not None and ftp_age < int(win["profile_days"]) and ftp_w > 0:
        best: dict[str, float] = {}
        for f in facts:
            if f.day < profile_from:
                continue
            for key, w in f.best_w.items():
                if w is not None and w > best.get(key, 0.0):
                    best[key] = float(w)
        profile = {k: round(best[k] / ftp_w, 2) for k in table["profile"]["reference"] if k in best} or None

    return {
        "shares_pct": shares, "sessions_28d": len(recent),
        "duration_28d_s": round(sum(f.duration_s for f in recent), 1),
        "ctl": ctl, "atl": atl, "form": ctl - atl,
        "days_since_hard": days_since_hard, "hard_last_7d": hard_last_7, "hard_days": hard_days,
        "last_by_need": last_by_need, "ftp_w": ftp_w, "ftp_test_date": ftp_test_date,
        "ftp_age_days": ftp_age, "profile": profile,
    }


# --- règles (pur) ---------------------------------------------------------------------------------

@dataclass
class Inputs:
    """Ce que le joueur ou les autres lots donnent au conseil."""
    objective: str = "endurance"
    available_min: int = 60
    watch: dict[str, Any] | None = None          # {type, duration_min, target_w} saisi aujourd'hui (CO8)
    raced_yesterday: bool = False                # course disputée hier (CO6)
    yesterday_tss: float | None = None
    next_race: date | None = None                # prochaine course annoncée (CO3, CO6)
    plan_today: dict[str, Any] | None = None     # {plan, name, week, workout} : séance du plan non faite
    notes: list[str] = field(default_factory=list)


def parse_watch(text: str, table: dict[str, Any]) -> dict[str, Any]:
    """« seuil », « seuil:50 » ou « seuil:50:240 » → {type, duration_min, target_w}."""
    parts = text.split(":")
    kind = parts[0].strip().lower().replace(" ", "").replace("é", "e").replace("_", "")
    if kind not in table["watch"]:
        raise CoachError(f"type de suggestion inconnu : {parts[0]} (attendu : {', '.join(table['watch'])})")
    try:
        minutes = int(parts[1]) if len(parts) > 1 and parts[1] else None
        target = float(parts[2]) if len(parts) > 2 and parts[2] else None
    except ValueError as exc:
        raise CoachError(f"suggestion de la montre invalide : {text}") from exc
    if minutes is not None and not 5 <= minutes <= 600:
        raise CoachError("durée de la suggestion de la montre : 5 à 600 min")
    return {"type": kind, "duration_min": minutes, "target_w": target}


def _pct(x: float) -> str:
    return f"{round(x)} %"


def _days(n: int) -> str:
    return "hier" if n == 1 else ("aujourd'hui" if n == 0 else f"il y a {n} jours")


def targets_for(objective: str, ctl: float, table: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    t = table["targets"]
    if objective not in OBJECTIVES:
        raise CoachError(f"objectif inconnu : {objective} (attendu : {', '.join(OBJECTIVES)})")
    if ctl < t["ctl_reprise"]:
        return "reprise", t["reprise"]
    return objective, t[objective]


def recommend(signals: dict[str, Any], inputs: Inputs, today: date, table: dict[str, Any]) -> dict[str, Any]:
    """Conseil du jour : la première règle qui s'applique décide."""
    rules, dur = table["rules"], table["durations"]
    form = signals["form"]
    used_objective, target = targets_for(inputs.objective, signals["ctl"], table)
    targets = {n: float(target[n]) for n in NEEDS}
    deficits = {n: targets[n] - signals["shares_pct"][n] for n in NEEDS}
    notes = list(inputs.notes)
    hard_days = signals["hard_days"]
    days_to_race = (inputs.next_race - today).days if inputs.next_race else None

    def advice(need: str, rule: str, reason: str, minutes: int | None = None,
               alternatives: list[str] | None = None) -> dict[str, Any]:
        return {"need": need, "rule": rule, "reason": reason,
                "duration_min": int(minutes if minutes is not None else inputs.available_min),
                "alternatives": alternatives or [], "notes": notes,
                "used_objective": used_objective, "targets": targets, "deficits": deficits}

    # RG : la montre a parlé aujourd'hui.
    if inputs.watch:
        w = inputs.watch
        need = table["watch"][w["type"]]
        if inputs.raced_yesterday and need in ("intense", "anaerobic"):
            notes.append("Tu as couru hier : écoute tes jambes.")
        if days_to_race is not None and 0 < days_to_race <= rules["r2_days_before_race"] and need != "rest":
            notes.append(f"Course dans {days_to_race} jour{'s' if days_to_race > 1 else ''} : reste court.")
        label = w["type"].replace("vo2max", "VO2 max").replace("recuperation", "récupération").capitalize()
        span = f", {w['duration_min']} min" if w.get("duration_min") else ""
        alts = ["recovery"] if need == "rest" else []
        return advice(need, "RG", f"Suggestion de ta montre : {label}{span}.",
                      w.get("duration_min") or (0 if need == "rest" else None), alts)

    # R0 : pas assez de séances (ou pas de FTP) pour conseiller finement.
    if signals["ftp_w"] <= 0 or signals["sessions_28d"] < rules["r0_min_sessions"]:
        return advice("light", "R0", "Pas encore assez de séances pour te conseiller finement : "
                      "on commence par l'endurance, puis un test de FTP.", dur["r0_light"], ["ftp_test"])

    # R1 : course hier, ou forme très basse.
    if inputs.raced_yesterday:
        tss = f" (TSS {round(inputs.yesterday_tss)})" if inputs.yesterday_tss else ""
        return advice("recovery", "R1", f"Tu as couru hier{tss} : on récupère aujourd'hui.", dur["recovery"])
    if form < rules["r1_form"]:
        return advice("recovery", "R1", f"Forme {round(form)} : grosse fatigue, on récupère aujourd'hui.",
                      dur["recovery"])

    # R2 : course dans 1 à 2 jours.
    if days_to_race is not None and 0 < days_to_race <= rules["r2_days_before_race"]:
        when = "demain" if days_to_race == 1 else "après-demain"
        return advice("light", "R2", f"Course {when} : séance courte avec quelques accélérations, "
                      "pour garder la vivacité sans te fatiguer.", dur["activation"])

    # R3 : fatigue.
    two_hard = (today - timedelta(days=1)) in hard_days and (today - timedelta(days=2)) in hard_days
    if form < rules["r3_form"] or two_hard:
        why = "séances dures hier et avant-hier" if two_hard else f"forme {round(form)}"
        return advice("light", "R3", f"{why[0].upper()}{why[1:]} : on roule tranquille.")

    # R4 : FTP trop ancienne pour des zones justes.
    age = signals["ftp_age_days"]
    if (age is None or age > rules["r4_ftp_age_days"]) and form > rules["r4_min_form"]:
        since = (f"Ta FTP date du test du {signals['ftp_test_date'].strftime('%d/%m')}"
                 if signals["ftp_test_date"] else "Aucun test de FTP dans tes séances")
        return advice("ftp_test", "R4", f"{since} : un test recalera tes zones.", dur["ftp_test"])

    # R5 : séance du plan actif.
    if inputs.plan_today:
        p = inputs.plan_today
        week = f", semaine {p['week']}" if p.get("week") else ""
        return advice("plan", "R5", f"Séance du plan « {p['name']} »{week} : {p['workout']}.")

    # R6 : plus grand retard, avec garde-fous ; R7 départage.
    hard_cap = int(target["max_hard_per_week"])
    rest_days = rules["r6_rest_hours"] / 24.0
    since_hard = signals["days_since_hard"]
    blocked: str | None = None
    if since_hard is not None and since_hard < rest_days:
        blocked = f"dernière séance dure {_days(since_hard)}"
    elif signals["hard_last_7d"] >= hard_cap:
        blocked = f"déjà {signals['hard_last_7d']} séances dures cette semaine"
    ranked = sorted(NEEDS, key=lambda n: -deficits[n])
    candidates = [n for n in ranked if deficits[n] > 0]
    if blocked:
        candidates = [n for n in candidates if n == "light"]
    if not candidates:
        reason = (f"Répartition dans la cible sur 4 semaines ; {blocked} : endurance." if blocked
                  else "Répartition dans la cible sur 4 semaines : endurance pour entretenir la base.")
        return advice("light", "R6", reason)
    need = candidates[0]
    rule = "R6"
    if len(candidates) > 1 and deficits[candidates[0]] - deficits[candidates[1]] < rules["r7_tie_points"]:
        pair = candidates[:2]
        weak = profile_weak(signals, table)
        if weak in pair:
            need, rule = weak, "R7"
        else:
            last = signals["last_by_need"]
            need = min(pair, key=lambda n: last[n] or date.min)
            rule = "R7"
    share = signals["shares_pct"][need]
    parts = [f"{_pct(share)} de ton temps en {LABELS[need]} sur 4 semaines (cible {_pct(targets[need])})"]
    last = signals["last_by_need"][need]
    if need != "light" and last is not None:
        parts.append(f"dernière séance de ce type {_days((today - last).days)}")
    if rule == "R7" and profile_weak(signals, table) == need:
        parts.append("ton profil de puissance est plus faible de ce côté")
    if blocked:
        parts.append(blocked)
    parts.append(f"forme {'+' if form >= 0 else ''}{round(form)}")
    others = [n for n in candidates if n != need]
    return advice(need, rule, ", ".join(parts) + ".", alternatives=others)


def profile_weak(signals: dict[str, Any], table: dict[str, Any]) -> str | None:
    """Besoin du point faible du profil de puissance (plus bas rapport réel / attendu)."""
    profile = signals.get("profile")
    if not profile:
        return None
    ref, need = table["profile"]["reference"], table["profile"]["need"]
    key = min(profile, key=lambda k: profile[k] / ref[k])
    return need[key]


def advise(facts: Iterable[SessionFacts], ftp_w: float, today: date, inputs: Inputs,
           table: dict[str, Any] | None = None) -> dict[str, Any]:
    """Conseil complet (sortie `--json`) à partir des faits des séances."""
    table = load_table() if table is None else table
    sig = build_signals(facts, ftp_w, today, table)
    adv = recommend(sig, inputs, today, table)
    need = adv["need"]
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {
        "date": today.isoformat(), "need": need,
        "need_label": LABELS.get(need, "séance du plan"), "rule": adv["rule"], "reason": adv["reason"],
        "duration_min": adv["duration_min"], "notes": adv["notes"], "alternatives": adv["alternatives"],
        "details": {
            "objective": adv["used_objective"], "targets_pct": adv["targets"],
            "shares_pct": {n: round(v, 1) for n, v in sig["shares_pct"].items()},
            "deficits_pts": {n: round(v, 1) for n, v in adv["deficits"].items()},
            "sessions_28d": sig["sessions_28d"], "duration_28d_s": sig["duration_28d_s"],
            "ctl": round(sig["ctl"], 1), "atl": round(sig["atl"], 1), "form": round(sig["form"], 1),
            "days_since_hard": sig["days_since_hard"], "hard_last_7d": sig["hard_last_7d"],
            "ftp_w": round(ftp_w, 1), "ftp_test_date": iso(sig["ftp_test_date"]),
            "ftp_age_days": sig["ftp_age_days"], "profile": sig["profile"],
            "profile_weak": profile_weak(sig, table),
            "last_by_need": {n: iso(d) for n, d in sig["last_by_need"].items()},
            "plan": inputs.plan_today, "next_race": iso(inputs.next_race),
            "watch": ({**inputs.watch, "need": table["watch"][inputs.watch["type"]]} if inputs.watch else None),
        },
    }


# --- lecture du disque ----------------------------------------------------------------------------

def _cache_path() -> Path:
    from . import profiles
    return profiles.current().history_cache.with_name("coach.json")


def collect_facts(directory: Path | None, ftp_w: float, today: date, table: dict[str, Any],
                  cache_path: Path | None = None, counted_sources: tuple[str, ...] | None = None
                  ) -> list[SessionFacts]:
    """Faits des séances des `history_days` derniers jours du profil en cours (cache compris)."""
    from . import profiles
    from .tools.history import _discover_files, _header_of
    from .tools.session_summary import load_session

    ctx = profiles.current()
    act_dir = Path(directory) if directory is not None else ctx.activities_dir
    counted = counted_sources if counted_sources is not None else ctx.counted_sources
    cpath = Path(cache_path) if cache_path is not None else _cache_path()
    try:
        cache = json.loads(cpath.read_text(encoding="utf-8"))
        if not isinstance(cache, dict):
            cache = {}
    except (OSError, ValueError):
        cache = {}
    dirty = False
    oldest = datetime.combine(today - timedelta(days=int(table["window"]["history_days"])), datetime.min.time())
    fits, jsonls = _discover_files(act_dir)

    def facts_of(path: Path) -> SessionFacts | None:
        nonlocal dirty
        try:
            st = path.stat()
        except OSError:
            return None
        if datetime.fromtimestamp(st.st_mtime) < oldest:
            return None
        key = str(path.resolve())
        c = cache.get(key)
        if (isinstance(c, dict) and c.get("size") == st.st_size and c.get("mtime_ns") == st.st_mtime_ns
                and c.get("ftp_w") == round(ftp_w, 2)):
            return SessionFacts.from_dict(c["facts"]) if c.get("facts") else None
        source = ""
        if path.suffix.lower() == ".jsonl":
            src = _header_of(path).get("source")
            source = src if isinstance(src, str) else ""
        try:
            f = session_facts(load_session(path), ftp_w, table, source)
        except Exception:
            f = None
        cache[key] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "ftp_w": round(ftp_w, 2),
                      "facts": f.to_dict() if f else None}
        dirty = True
        return f

    from_jsonl = [f for f in (facts_of(p) for p in jsonls) if f is not None]
    out = list(from_jsonl)
    for p in fits:
        f = facts_of(p)
        if f is not None and not any(abs(f.start_ts - j.start_ts) <= MATCH_TOLERANCE_S for j in from_jsonl):
            out.append(f)
    if dirty:
        try:
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    first = today - timedelta(days=int(table["window"]["history_days"]) - 1)
    return [f for f in out
            if f.source != "replay" and (f.source in ("", "live") or f.source in counted)
            and first <= f.day <= today]


def plan_today(today: date, ftp_w: float) -> dict[str, Any] | None:
    """Séance du plan actif prévue aujourd'hui et pas encore faite (None sinon ; ne lève jamais)."""
    from . import plans
    try:
        st = plans.load_state()
        if st is None:
            return None
        plan = plans.load_plan(st.plan_id)
        day = plans.today(plan, st.start, plans.history_sessions(ftp_w=ftp_w), on=today)
        todo = [e for e in day["today"] if not e["done"]]
        if not todo:
            return None
        return {"plan": plan.id, "name": plan.name, "week": day["week"], "workout": todo[0]["workout"]}
    except Exception:
        return None


# --- commande -------------------------------------------------------------------------------------

def format_text(r: dict[str, Any]) -> str:
    d = r["details"]
    lines = [f"Séance conseillée du {r['date']} : {r['need_label'].upper()} ({r['duration_min']} min)",
             f"Pourquoi : {r['reason']}", f"Règle {r['rule']} · objectif {d['objective']}"]
    lines += [f"Note : {n}" for n in r["notes"]]
    if r["alternatives"]:
        lines.append("Autres idées : " + ", ".join(LABELS.get(a, a) for a in r["alternatives"]))
    sh, tg = d["shares_pct"], d["targets_pct"]
    lines.append("Répartition 4 semaines : " + " · ".join(
        f"{LABELS[n]} {sh[n]:.0f} % (cible {tg[n]:.0f})" for n in NEEDS))
    lines.append(f"Forme : CTL {d['ctl']:.0f}, ATL {d['atl']:.0f}, forme {d['form']:+.0f} · "
                 f"{d['sessions_28d']} séances en 4 semaines")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    from . import config as config_mod

    try:
        table = load_table()
        today = date.fromisoformat(args.date) if args.date else date.today()
        ftp = float(config_mod.load(args.config).rider.ftp_w) if args.ftp is None else args.ftp
        objective = args.objectif or "endurance"
        minutes = args.temps or 60
        if not 10 <= minutes <= 300:
            raise CoachError("--temps : 10 à 300 min")
        inputs = Inputs(objective=objective, available_min=minutes,
                        watch=parse_watch(args.montre, table) if args.montre else None,
                        next_race=date.fromisoformat(args.prochaine_course) if args.prochaine_course else None,
                        plan_today=plan_today(today, ftp))
        facts = collect_facts(args.directory, ftp, today, table)
        result = advise(facts, ftp, today, inputs, table)
    except (CoachError, config_mod.ConfigError, ValueError) as exc:
        print(f"openride-core coach : {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_text(result))
    return 0


def add_parser(sub: Any) -> None:
    p = sub.add_parser("coach", help="séance conseillée du jour et sa raison (série CO, lot CO1)")
    p.add_argument("--date", help="jour du conseil AAAA-MM-JJ (défaut : aujourd'hui)")
    p.add_argument("--objectif", choices=OBJECTIVES, help="objectif (défaut : endurance)")
    p.add_argument("--temps", type=int, help="temps disponible en minutes (défaut : 60)")
    p.add_argument("--montre", metavar="TYPE[:MIN[:W]]",
                   help="suggestion de la montre Garmin : repos, recuperation, fond, tempo, seuil, vo2max, "
                        "anaerobie, sprint")
    p.add_argument("--prochaine-course", metavar="AAAA-MM-JJ", help="date de la prochaine course annoncée")
    p.add_argument("--dir", type=Path, dest="directory", help="dossier des séances (défaut : profil en cours)")
    p.add_argument("--ftp", type=float, help="FTP en watts (défaut : config.toml)")
    p.add_argument("--json", action="store_true", help="sortie JSON")
    p.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")


if __name__ == "__main__":   # pragma: no cover
    ap = argparse.ArgumentParser(prog="python -m openride_core.coach")
    add_parser(ap.add_subparsers(dest="command", required=True))
    sys.exit(run(ap.parse_args()))
