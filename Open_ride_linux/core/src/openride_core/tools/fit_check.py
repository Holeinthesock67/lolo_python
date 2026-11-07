"""Contrôle d'un FIT de séance réelle, en local (lot X11, recette 1.0 ligne 21).

    openride-core fit-check FICHIER.fit [--journal JOURNAL.jsonl] [--json]

Décode le fichier en entier avec le SDK officiel de Garmin (`garmin-fit-sdk`, extra `dev`), puis :
- **décodage** : fichier FIT reconnu, CRC valide, aucune erreur du SDK ;
- **messages obligatoires** : `file_id`, `session`, `lap`, `activity` (et des `record`) ;
- **horodatage croissant** des enregistrements ;
- **puissance et cadence continues** : aucun enregistrement sans elles hors pauses (ATTENTION sinon) ;
- **trous aux pauses** : chaque trou de plus de 2 s entre deux enregistrements tombe sur une pause du
  chronomètre (`stop_all` puis `start`), et aucun enregistrement n'est écrit pendant une pause ;
- **FC figée** : aucune valeur identique plus de 15 s pendant que la puissance varie d'au moins 5 W ;
- **totaux de `session`** face aux enregistrements : distance, durées écoulée et chronométrée,
  puissance moyenne et maximale, FC moyenne ;
- **compatibilité Garmin Connect et GoldenCheetah** (lot X56) : en-tête de 12 ou 14 octets signé
  `.FIT` (seuls acceptés par GoldenCheetah), `file_id` d'activité daté avec fabricant et produit,
  `session` de vélo datée qui couvre les enregistrements (GoldenCheetah ignore un tour fini avant le
  premier relevé), autant de tours et de séances que l'annoncent `session` et `activity`, heure
  locale de `activity` (Garmin Connect s'en sert pour dater la sortie), positions dans le globe ;
- **totaux affichés** (lot X56, ATTENTION) : calories, travail, D+ et D-, cadence maximale, que les
  deux logiciels montrent tels quels sans les recalculer (absents des FIT d'avant la 3.0) ;
- avec `--journal` : **distance et durée chronométrée** face au journal de la séance (± 1 %).

Une ligne OK, ATTENTION ou ÉCHEC par contrôle ; code 0, 1 si un contrôle échoue, 2 si le fichier est
illisible ou le SDK absent. Rien n'est écrit ni envoyé : le FIT reste sur le PC.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

GAP_S = 2.0            # deux enregistrements à 1 Hz : un écart de plus de 2 s est un trou
FROZEN_S = 15.0        # FC identique plus longtemps : figée (lot Q5)
POWER_VAR_W = 5.0      # « la puissance varie » : au moins 5 W d'écart pendant la valeur répétée
REL_TOL = 0.01         # ± 1 % face au journal et aux enregistrements
ABS_TOL = {"m": 1.0, "s": 1.0, "W": 1.0, "bpm": 1.0}   # résolution du FIT (secondes entières, entiers)
REQUIRED = ("file_id", "session", "lap", "activity", "record")
SEMICIRCLE_DEG = 180.0 / 2**31
SDK_HINT = "garmin-fit-sdk absent : installer l'extra dev du core (pip install -e 'core[dev]')"


class FitCheckError(Exception):
    """Fichier introuvable ou illisible, SDK absent."""


def _ts(v: Any) -> float | None:
    return v.timestamp() if isinstance(v, datetime) else None


def decode(path: Path) -> tuple[dict[str, list[dict[str, Any]]], list[str], bool]:
    """Messages par type (`record`, `session`…), erreurs du SDK, intégrité (FIT reconnu et CRC valide)."""
    try:
        from garmin_fit_sdk import Decoder, Stream
    except ImportError as exc:
        raise FitCheckError(SDK_HINT) from exc
    if not path.is_file():
        raise FitCheckError(f"fichier introuvable : {path}")
    stream = Stream.from_file(str(path))
    decoder = Decoder(stream)
    ok = decoder.is_fit() and decoder.check_integrity()
    stream.reset()
    messages, errors = decoder.read()
    return ({k.removesuffix("_mesgs"): v for k, v in messages.items()}, [str(e) for e in errors], bool(ok))


def read_header(path: Path) -> bytes:
    """Les 14 premiers octets du fichier (en-tête FIT), pour le contrôle de compatibilité."""
    with Path(path).open("rb") as fh:
        return fh.read(14)


def _header_issue(header: bytes) -> str | None:
    if len(header) < 12 or header[0] not in (12, 14):
        return f"en-tête de {header[0] if header else 0} octets (GoldenCheetah n'accepte que 12 ou 14)"
    if header[8:12] != b".FIT":
        return "signature .FIT absente de l'en-tête"
    return None


def compat_issues(messages: dict[str, list[dict[str, Any]]], records: list[dict[str, Any]],
                  header: bytes | None = None) -> list[str]:
    """Ce qui ferait refuser le fichier, ou perdre une partie de la séance, par Garmin Connect ou GoldenCheetah."""
    issues = [i for i in [_header_issue(header) if header is not None else None] if i]
    fid = (messages.get("file_id") or [{}])[0]
    if fid.get("type") != "activity":
        issues.append(f"file_id de type {fid.get('type')} au lieu de activity")
    missing = [k for k in ("manufacturer", "product", "time_created") if fid.get(k) is None]
    if missing:
        issues.append("file_id sans " + ", ".join(missing))
    sessions, laps = messages.get("session") or [], messages.get("lap") or []
    first = records[0]["t"] if records else None
    last = records[-1]["t"] if records else None
    for kind, items in (("session", sessions), ("tour", laps)):
        for i, m in enumerate(items):
            start, end = _ts(m.get("start_time")), _ts(m.get("timestamp"))
            if start is None or end is None:
                issues.append(f"{kind} {i} sans début ou sans fin")
            elif end < start:
                issues.append(f"{kind} {i} finit avant de commencer")
            elif first is not None and end < first:
                issues.append(f"{kind} {i} fini avant le premier enregistrement (ignoré par GoldenCheetah)")
    for i, m in enumerate(sessions):
        if m.get("sport") != "cycling":
            issues.append(f"session {i} de sport {m.get('sport')} au lieu de cycling")
        if last is not None and _ts(m.get("timestamp")) is not None and _ts(m["timestamp"]) < last - 1:
            issues.append(f"session {i} finie avant le dernier enregistrement")
    if sessions and sessions[0].get("num_laps") not in (None, len(laps)):
        issues.append(f"session annonce {sessions[0].get('num_laps')} tour(s) pour {len(laps)} écrit(s)")
    starts = [_ts(m.get("start_time")) for m in laps]
    if any(a is not None and b is not None and b < a for a, b in zip(starts, starts[1:])):
        issues.append("tours dans le désordre")
    act = (messages.get("activity") or [{}])[0]
    if act.get("num_sessions") not in (None, len(sessions)):
        issues.append(f"activity annonce {act.get('num_sessions')} séance(s) pour {len(sessions)} écrite(s)")
    if act.get("local_timestamp") is None:
        issues.append("activity sans heure locale (local_timestamp)")
    off = [r for r in records if r.get("position_lat") is not None and r.get("position_long") is not None
           and not (-90 <= r["position_lat"] * SEMICIRCLE_DEG <= 90 and -180 <= r["position_long"] * SEMICIRCLE_DEG <= 180)]
    if off:
        issues.append(f"{len(off)} position(s) hors du globe")
    return issues


def displayed_totals(messages: dict[str, list[dict[str, Any]]], records: list[dict[str, Any]]) -> list[str]:
    """Totaux de `session` que Garmin Connect et GoldenCheetah affichent tels quels, absents du fichier."""
    s = (messages.get("session") or [{}])[0]
    want = []
    if any(r.get("power") is not None for r in records):
        want += ["total_calories", "total_work"]
    if any(r.get("cadence") for r in records):
        want.append("max_cadence")
    if any(r.get("altitude") is not None or r.get("enhanced_altitude") is not None for r in records):
        want += ["total_ascent", "total_descent"]
    return [k for k in want if s.get(k) is None]


def pauses(events: list[dict[str, Any]]) -> list[tuple[float, float]]:
    """Intervalles de pause du chronomètre : `stop_all` jusqu'au `start` suivant (fin de séance exclue)."""
    out, paused_at = [], None
    for ev in events:
        if ev.get("event") != "timer":
            continue
        t = _ts(ev.get("timestamp"))
        if ev.get("event_type") == "stop_all" and paused_at is None:
            paused_at = t
        elif ev.get("event_type") == "start" and paused_at is not None:
            out.append((paused_at, t))
            paused_at = None
    return out


def _within(got: float, want: float, unit: str) -> bool:
    return abs(got - want) <= max(REL_TOL * abs(want), ABS_TOL[unit])


def _line(name: str, level: str, detail: str) -> dict[str, str]:
    return {"controle": name, "niveau": level, "detail": detail}


def frozen_hr(recs: list[dict[str, Any]]) -> tuple[float, Any, float]:
    """(durée, valeur, début) de la plus longue FC identique pendant que la puissance varie."""
    worst: tuple[float, Any, float] = (0.0, None, 0.0)
    run: list[dict[str, Any]] = []
    for r in recs + [{"heart_rate": None}]:
        hr = r.get("heart_rate")
        if run and hr == run[0]["heart_rate"]:
            run.append(r)
            continue
        if len(run) > 1:
            powers = [x["power"] for x in run if x.get("power") is not None]
            length = run[-1]["t"] - run[0]["t"]
            if powers and max(powers) - min(powers) >= POWER_VAR_W and length > worst[0]:
                worst = (length, run[0]["heart_rate"], run[0]["t"])
        run = [r] if hr is not None else []
    return worst


def check(messages: dict[str, list[dict[str, Any]]], errors: list[str], integrity: bool,
          journal: list[dict[str, Any]] | None = None, header: bytes | None = None) -> list[dict[str, str]]:
    out = [_line("décodage", "OK" if integrity and not errors else "ÉCHEC",
                 "FIT reconnu, CRC valide, aucune erreur du SDK" if integrity and not errors
                 else ("CRC invalide ou fichier non FIT ; " if not integrity else "") + "; ".join(errors[:3]))]
    missing = [m for m in REQUIRED if not messages.get(m)]
    out.append(_line("messages obligatoires", "ÉCHEC" if missing else "OK",
                     f"absents : {', '.join(missing)}" if missing else ", ".join(REQUIRED) + " présents"))
    records = [dict(r, t=_ts(r.get("timestamp"))) for r in messages.get("record", []) if r.get("timestamp")]
    if not records:
        return out
    t0 = records[0]["t"]
    back = [r["t"] - t0 for a, r in zip(records, records[1:]) if r["t"] < a["t"]]
    out.append(_line("horodatage croissant", "ÉCHEC" if back else "OK",
                     f"{len(back)} retour(s) en arrière, le premier à {back[0]:.0f} s" if back
                     else f"{len(records)} enregistrements dans l'ordre"))
    stops = pauses(messages.get("event", []))
    in_pause = [r for r in records if any(a < r["t"] < b for a, b in stops)]
    running = [r for r in records if r not in in_pause]
    holes = [r for r in running if r.get("power") is None or r.get("cadence") is None]
    out.append(_line("puissance et cadence continues", "ATTENTION" if holes else "OK",
                     f"{len(holes)} enregistrement(s) sans puissance ou cadence hors pauses, le premier à "
                     f"{holes[0]['t'] - t0:.0f} s" if holes else "présentes à chaque enregistrement hors pauses"))
    gaps = [(a["t"], b["t"]) for a, b in zip(records, records[1:]) if b["t"] - a["t"] > GAP_S]
    loose = [(a, b) for a, b in gaps if not any(a <= s and e <= b for s, e in stops)]
    level = "ÉCHEC" if loose else "ATTENTION" if in_pause else "OK"
    detail = (f"{len(loose)} trou(s) hors pause, le premier de {loose[0][0] - t0:.0f} à {loose[0][1] - t0:.0f} s"
              if loose else f"{len(in_pause)} enregistrement(s) écrits pendant une pause" if in_pause
              else f"{len(gaps)} trou(s), tous aux {len(stops)} pause(s)")
    out.append(_line("trous aux pauses", level, detail))
    length, value, at = frozen_hr(records)
    out.append(_line("FC figée", "ÉCHEC" if length > FROZEN_S else "OK",
                     f"{value} bpm pendant {length:.0f} s à partir de {at - t0:.0f} s (au plus {FROZEN_S:g} s)"
                     if value is not None else "aucune valeur répétée pendant que la puissance varie"))
    out.append(session_totals(messages, records, stops))
    issues = compat_issues(messages, records, header)
    out.append(_line("compatibilité Garmin Connect et GoldenCheetah", "ÉCHEC" if issues else "OK",
                     "; ".join(issues[:4]) if issues else "en-tête, file_id, tours, séance et activity conformes"))
    absent = displayed_totals(messages, records)
    out.append(_line("totaux affichés", "ATTENTION" if absent else "OK",
                     "absents : " + ", ".join(absent) if absent else "calories, travail, cadence et dénivelé présents"))
    if journal is not None:
        out.append(against_journal(messages, journal))
    return out


def session_totals(messages: dict[str, list[dict[str, Any]]], records: list[dict[str, Any]],
                   stops: list[tuple[float, float]]) -> dict[str, str]:
    sessions = messages.get("session") or []
    if not sessions:
        return _line("totaux de la séance", "ÉCHEC", "pas de message session")
    s = sessions[0]
    start, end = _ts(s.get("start_time")), _ts(s.get("timestamp"))
    timer_events = [e for e in messages.get("event", []) if e.get("event") == "timer"]
    first_start = next((_ts(e["timestamp"]) for e in timer_events if e.get("event_type") == "start"), start)
    last_stop = next((_ts(e["timestamp"]) for e in reversed(timer_events) if e.get("event_type") == "stop_all"), end)
    powers = [r["power"] for r in records if r.get("power") is not None]
    hrs = [r["heart_rate"] for r in records if r.get("heart_rate")]
    wants = [("distance", s.get("total_distance"), max(r.get("distance") or 0.0 for r in records), "m"),
             ("durée écoulée", s.get("total_elapsed_time"), (end or 0) - (start or 0), "s"),
             ("durée chronométrée", s.get("total_timer_time"),
              (last_stop or 0) - (first_start or 0) - sum(b - a for a, b in stops), "s")]
    if powers:
        wants += [("puissance moyenne", s.get("avg_power"), statistics.fmean(powers), "W"),
                  ("puissance maximale", s.get("max_power"), max(powers), "W")]
    if hrs:
        wants.append(("FC moyenne", s.get("avg_heart_rate"), statistics.fmean(hrs), "bpm"))
    bad = [f"{name} {got} {unit} pour {want:.1f} {unit}" for name, got, want, unit in wants
           if got is None or not _within(float(got), want, unit)]
    return _line("totaux de la séance", "ÉCHEC" if bad else "OK",
                 "; ".join(bad) if bad else f"{len(wants)} totaux conformes aux enregistrements")


def against_journal(messages: dict[str, list[dict[str, Any]]], journal: list[dict[str, Any]]) -> dict[str, str]:
    from ..fit_export import summarize
    from ..journal import TIMER_EVENTS

    recs = [x for x in journal if x.get("kind") == "record" and x.get("ts") is not None]
    events = [x for x in journal if x.get("kind") == "event" and x.get("event") in TIMER_EVENTS]
    sessions = messages.get("session") or []
    if not recs or not sessions:
        return _line("face au journal", "ÉCHEC", "journal sans relevé" if not recs else "pas de message session")
    want = summarize(recs, events)
    s = sessions[0]
    pairs = [("distance", s.get("total_distance"), want.distance_m, "m"),
             ("durée chronométrée", s.get("total_timer_time"), want.timer_s, "s")]
    bad = [f"{name} {got} {unit} pour {w:.1f} {unit} au journal" for name, got, w, unit in pairs
           if got is None or not _within(float(got), w, unit)]
    return _line("face au journal", "ÉCHEC" if bad else "OK",
                 "; ".join(bad) if bad else f"distance {want.distance_m:.0f} m et durée {want.timer_s:.0f} s à ± 1 %")


def run(path: Path, journal_path: Path | None = None, as_json: bool = False) -> int:
    try:
        messages, errors, integrity = decode(Path(path))
        header = read_header(Path(path))
    except FitCheckError as exc:
        print(f"fit-check : {exc}")
        return 2
    except Exception as exc:   # fichier tronqué ou étranger : le SDK peut lever n'importe quoi
        print(f"fit-check : fichier illisible ({path}) : {exc}")
        return 2
    journal = None
    if journal_path is not None:
        from ..journal import read_journal

        if not Path(journal_path).is_file():
            print(f"fit-check : journal introuvable : {journal_path}")
            return 2
        journal = list(read_journal(Path(journal_path)))
    lines = check(messages, errors, integrity, journal, header)
    failed = any(ln["niveau"] == "ÉCHEC" for ln in lines)
    if as_json:
        print(json.dumps({"fichier": Path(path).name, "ok": not failed, "controles": lines},
                         ensure_ascii=False, indent=2))
    else:
        print(f"Contrôle de {Path(path).name}")
        for ln in lines:
            print(f"  [{ln['niveau']}] {ln['controle']} : {ln['detail']}")
        print("Verdict : " + ("au moins un contrôle échoue" if failed else "le fichier peut être importé"))
    return 1 if failed else 0
