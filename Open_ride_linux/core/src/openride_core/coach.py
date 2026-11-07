"""Séance conseillée (série CO, lot CO1) : besoin du jour et sa raison, calculés depuis l'historique.

    openride-core coach [--date AAAA-MM-JJ] [--objectif endurance|courses|grimpeur] [--temps MIN]
                        [--montre TYPE[:MIN[:W]] [--enregistrer]] [--effacer-montre]
                        [--prochaine-course AAAA-MM-JJ] [--dir DOSSIER]
                        [--workouts DOSSIER] [--ftp W] [--json] [--config FICHIER]

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

La suggestion de la montre Garmin (lot CO8) se donne avec `--montre` ; avec `--enregistrer`, elle est
gardée pour la journée dans `conseil.json` du profil et reprise par les appels suivants du même jour
(`--effacer-montre` l'efface). La course d'hier et la prochaine course (lots CO3, CO6) sont des
paramètres de `recommend` ; `--prochaine-course` permet d'essayer la règle R2.

Clés de la sortie `--json` (stables) : date, need, need_label, rule, reason, duration_min, notes
(liste de textes), alternatives (besoins proposés en second), workout (null ou {id, name,
duration_min, need, dominant_zone, tss_estimate} : entraînement conseillé, lot CO2), other_workouts
(liste de la même forme : autres entraînements du même besoin), details {objective, targets_pct,
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
    for key in ("needs", "window", "hard", "targets", "rules", "profile", "durations", "watch", "workouts"):
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
    workout: str | None = None               # entraînement ERG de la séance (en-tête du journal)

    @property
    def day(self) -> date:
        return datetime.fromtimestamp(self.start_ts).date()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SessionFacts":
        return cls(float(d["start_ts"]), float(d["duration_s"]), float(d["tss"]),
                   {k: float(v) for k, v in d["need_s"].items()}, bool(d["hard"]),
                   dict(d["best_w"]), d.get("ftp_test_w"), str(d.get("source") or ""), d.get("workout"))


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


def session_facts(session: Any, ftp_w: float, table: dict[str, Any], source: str = "",
                  workout: str | None = None) -> SessionFacts:
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
                        dict(s["best_power_w"]), test_w, source, workout)


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


def pick_workout(adv: dict[str, Any], facts: list[SessionFacts], today: date, inputs: Inputs,
                 table: dict[str, Any], library: list[WorkoutNeed]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Entraînement conseillé et autres entraînements du même besoin (lot CO2) ; ajoute une note quand
    la bibliothèque n'en a aucun."""
    need = adv["need"]
    if need == "rest":
        return None, []
    if need == "plan":
        return {"id": inputs.plan_today["workout"], "name": inputs.plan_today["workout"], "need": "plan",
                "duration_min": adv["duration_min"], "dominant_zone": None, "tss_estimate": None}, []
    if need == "ftp_test":
        return {"id": table["workouts"]["ftp_test"], "name": "Test de FTP (rampe)", "need": "ftp_test",
                "duration_min": adv["duration_min"], "dominant_zone": None, "tss_estimate": None}, []
    since = today - timedelta(days=int(table["window"]["share_days"]) - 1)
    done: dict[str, int] = {}
    for f in facts:
        if f.workout and since <= f.day <= today:
            done[f.workout] = done.get(f.workout, 0) + 1
    zone = None
    if inputs.watch and adv["rule"] == "RG":
        zone = table["workouts"]["watch_zone"].get(inputs.watch["type"])
    chosen = choose_workouts(library, need, adv["duration_min"], done, zone)
    if not chosen:
        adv["notes"].append(f"Aucun entraînement de ce besoin ({LABELS[need]}) dans ta bibliothèque : "
                            "installe les contenus de départ (Réglages › Contenus).")
        return None, []
    return chosen[0].to_dict(), [w.to_dict() for w in chosen[1:]]


def profile_weak(signals: dict[str, Any], table: dict[str, Any]) -> str | None:
    """Besoin du point faible du profil de puissance (plus bas rapport réel / attendu)."""
    profile = signals.get("profile")
    if not profile:
        return None
    ref, need = table["profile"]["reference"], table["profile"]["need"]
    key = min(profile, key=lambda k: profile[k] / ref[k])
    return need[key]


def advise(facts: Iterable[SessionFacts], ftp_w: float, today: date, inputs: Inputs,
           table: dict[str, Any] | None = None, library: Iterable[WorkoutNeed] | None = None) -> dict[str, Any]:
    """Conseil complet (sortie `--json`) à partir des faits des séances et de la bibliothèque."""
    table = load_table() if table is None else table
    facts = list(facts)
    sig = build_signals(facts, ftp_w, today, table)
    adv = recommend(sig, inputs, today, table)
    need = adv["need"]
    workout, others = pick_workout(adv, facts, today, inputs, table, list(library or []))
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {
        "date": today.isoformat(), "need": need,
        "need_label": LABELS.get(need, "séance du plan"), "rule": adv["rule"], "reason": adv["reason"],
        "duration_min": adv["duration_min"], "notes": adv["notes"], "alternatives": adv["alternatives"],
        "workout": workout, "other_workouts": others,
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


# --- entraînements par besoin (lot CO2, pur) -----------------------------------------------------

@dataclass(frozen=True)
class WorkoutNeed:
    """Entraînement de la bibliothèque et le besoin qu'il travaille."""
    id: str
    name: str
    duration_s: float
    need: str                    # light, intense, anaerobic ou recovery
    dominant_zone: str | None    # zone la plus longue au-dessus de Z2 (tempo Z3, seuil Z4, VO2 max Z5…)
    tss: float                   # TSS estimé à la FTP donnée

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "duration_min": round(self.duration_s / 60.0),
                "need": self.need, "dominant_zone": self.dominant_zone, "tss_estimate": round(self.tss)}


def workout_need(workout: Any, ftp_w: float, table: dict[str, Any]) -> WorkoutNeed:
    """Besoin d'un entraînement (`workout.Workout`), à la seconde sur les cibles de ses blocs.

    Récupération si au plus `recovery_max_above_z1_pct` % du temps dépasse Z1 ; sinon aérobie léger si
    le temps pondéré au-dessus de Z2 reste sous `light_max_above_s` ; sinon le plus grand des temps
    intense et anaérobie (ce dernier multiplié par `anaerobic_weight`).
    """
    from .tools.session_summary import ZONES, normalized_power, zone_of

    names = [z[0] for z in ZONES]
    zone_s = dict.fromkeys(names, 0.0)
    watts: list[float] = []
    for b in workout.blocks:
        for i in range(int(round(b.duration_s))):
            w = b.watts_at(i + 0.5, ftp_w)
            watts.append(w)
            zone_s[names[zone_of(w, ftp_w)]] += 1.0
    cfg = table["workouts"]
    total = sum(zone_s.values()) or 1.0
    need_s = {n: sum(zone_s[z] for z in table["needs"][n]) for n in NEEDS}
    above = need_s["intense"] + cfg["anaerobic_weight"] * need_s["anaerobic"]
    if 100.0 * (total - zone_s["Z1"]) / total <= cfg["recovery_max_above_z1_pct"]:
        need = "recovery"
    elif above < cfg["light_max_above_s"]:
        need = "light"
    else:
        need = "intense" if need_s["intense"] >= cfg["anaerobic_weight"] * need_s["anaerobic"] else "anaerobic"
    hot = {z: zone_s[z] for z in table["needs"]["intense"] + table["needs"]["anaerobic"] if zone_s[z] > 0}
    dominant = max(hot, key=lambda z: hot[z]) if hot else None
    np_w = normalized_power(watts)
    tss = len(watts) / 3600.0 * (np_w / ftp_w) ** 2 * 100.0 if ftp_w > 0 else 0.0
    return WorkoutNeed(workout.id, workout.name, float(len(watts)), need, dominant, tss)


def classify_library(directory: Path, ftp_w: float, table: dict[str, Any]) -> list[WorkoutNeed]:
    """Entraînements lisibles d'un dossier (`~/OpenRide/Workouts/`) et leur besoin ; les illisibles sont omis."""
    from .workout import WorkoutError, load_workout, list_workouts, workout_path

    out = []
    for info in list_workouts(Path(directory)):
        if not info.selectable or info.id.startswith("rampe"):
            continue
        try:
            out.append(workout_need(load_workout(workout_path(Path(directory), info.id)), ftp_w, table))
        except (WorkoutError, OSError, ValueError):
            continue
    return out


def choose_workouts(library: Iterable[WorkoutNeed], need: str, minutes: int, done_28d: dict[str, int],
                    zone: str | None = None, limit: int = 3) -> list[WorkoutNeed]:
    """Entraînements du besoin, du mieux placé au moins bien : la zone de la montre d'abord (si donnée),
    puis la durée la plus proche de `minutes`, puis le moins fait sur 4 semaines, puis l'identifiant."""
    pool = [w for w in library if w.need == need]
    return sorted(pool, key=lambda w: (zone is not None and w.dominant_zone != zone,
                                       abs(w.duration_s / 60.0 - minutes), done_28d.get(w.id, 0), w.id))[:limit]


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
        source, workout = "", None
        if path.suffix.lower() == ".jsonl":
            head = _header_of(path)
            source = head.get("source") if isinstance(head.get("source"), str) else ""
            workout = head.get("workout_id") if isinstance(head.get("workout_id"), str) else None
        try:
            f = session_facts(load_session(path), ftp_w, table, source, workout)
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


def advice_path() -> Path:
    """Fichier des saisies du conseil du profil en cours (suggestion de la montre, lot CO8)."""
    from . import profiles
    return profiles.current().root / "conseil.json"


def _read_advice_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_watch(watch: dict[str, Any], today: date, path: Path | None = None) -> None:
    """Enregistre la suggestion de la montre pour la journée `today` (écriture sûre, autres clés gardées)."""
    p = advice_path() if path is None else Path(path)
    data = _read_advice_file(p)
    data["watch"] = {**watch, "date": today.isoformat()}
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)


def clear_watch(path: Path | None = None) -> bool:
    """Efface la suggestion enregistrée ; False s'il n'y en avait pas."""
    p = advice_path() if path is None else Path(path)
    data = _read_advice_file(p)
    if "watch" not in data:
        return False
    del data["watch"]
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)
    return True


def saved_watch(today: date, table: dict[str, Any], path: Path | None = None) -> dict[str, Any] | None:
    """Suggestion enregistrée aujourd'hui (None si absente, d'un autre jour ou abîmée)."""
    w = _read_advice_file(advice_path() if path is None else Path(path)).get("watch")
    if not isinstance(w, dict) or w.get("date") != today.isoformat() or w.get("type") not in table["watch"]:
        return None
    minutes, target = w.get("duration_min"), w.get("target_w")
    return {"type": w["type"], "duration_min": minutes if isinstance(minutes, int) else None,
            "target_w": float(target) if isinstance(target, (int, float)) else None}


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
    if r["workout"]:
        w = r["workout"]
        tss = f" · TSS ≈ {w['tss_estimate']}" if w.get("tss_estimate") is not None else ""
        lines.insert(1, f"Séance : {w['name']} ({w['duration_min']} min{tss})")
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
        if args.effacer_montre:
            print("Suggestion de la montre effacée." if clear_watch() else "Aucune suggestion de la montre enregistrée.")
            return 0
        watch = parse_watch(args.montre, table) if args.montre else None
        if watch and args.enregistrer:
            save_watch(watch, today)
        if watch is None:
            watch = saved_watch(today, table)
        inputs = Inputs(objective=objective, available_min=minutes, watch=watch,
                        next_race=date.fromisoformat(args.prochaine_course) if args.prochaine_course else None,
                        plan_today=plan_today(today, ftp))
        facts = collect_facts(args.directory, ftp, today, table)
        library = classify_library(args.workouts or config_mod.WORKOUTS_DIR, ftp, table)
        result = advise(facts, ftp, today, inputs, table, library)
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
    p.add_argument("--enregistrer", action="store_true",
                   help="avec --montre : garde la suggestion pour la journée (profil en cours)")
    p.add_argument("--effacer-montre", action="store_true", help="efface la suggestion de la montre enregistrée")
    p.add_argument("--prochaine-course", metavar="AAAA-MM-JJ", help="date de la prochaine course annoncée")
    p.add_argument("--dir", type=Path, dest="directory", help="dossier des séances (défaut : profil en cours)")
    p.add_argument("--workouts", type=Path, help="dossier des entraînements (défaut : ~/OpenRide/Workouts)")
    p.add_argument("--ftp", type=float, help="FTP en watts (défaut : config.toml)")
    p.add_argument("--json", action="store_true", help="sortie JSON")
    p.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")


if __name__ == "__main__":   # pragma: no cover
    ap = argparse.ArgumentParser(prog="python -m openride_core.coach")
    add_parser(ap.add_subparsers(dest="command", required=True))
    sys.exit(run(ap.parse_args()))
