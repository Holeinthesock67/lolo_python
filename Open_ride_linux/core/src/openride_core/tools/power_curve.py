"""Courbe de puissance du profil en cours sur 6 mois et 6 semaines (série PP, lot PP1).

    python -m openride_core.tools.power_curve [--dir DOSSIER] [--sources live,simulated] [--json]

Meilleure puissance moyenne de 13 durées (5 s à 60 min) dans les journaux `.jsonl` du profil en cours,
et dans ses `.fit` quand le journal manque. Deux fenêtres : les 183 derniers jours (« 6 derniers mois »)
et les 42 derniers jours (« 6 dernières semaines », la forme du moment).

Règles (cadrage PP du 21 novembre 2026, décisions du propriétaire) :
- une fenêtre de calcul ne traverse jamais une pause, une coupure du trainer (`device` `trainer` `down`
  puis `up`) ni un trou de plus de 2 s entre deux relevés : chaque séance est découpée en morceaux
  continus, et chaque morceau est calculé seul (le « meilleur 20 min avec une pause cachée » de R16,
  qui recollait les relevés hors pause, n'existe plus) ;
- relevé de plus de 2 000 W, ou pic isolé (plus de 1 000 W et plus de 3 fois ses deux voisins) : pic de
  capteur, remplacé par le relevé précédent ; relevé sans puissance : coupure ;
- séances gardées : celles dont la `source` est comptée par le profil (`live` ; le profil d'essai garde
  aussi `simulated`), jamais les rejeux ; un FIT sans journal compte comme `live` ;
- chaque point garde ses watts, sa date, sa séance et le mot de l'effort : « libre », ou « ERG » quand
  la consigne du trainer fixait la puissance (relevé avec `target_w` ou `mode` ERG). Une seconde courbe,
  faite des seuls efforts libres, est gardée à part : l'estimation de FTP (PP2) ne lit qu'elle. Un FIT
  sans journal ne dit pas s'il était en ERG : son effort est « inconnu », hors de la courbe libre.

Le calcul d'une séance (quelques dizaines de millisecondes pour une heure) est fait une fois par fichier
puis lu dans le cache du profil (`Profils/<id>/.cache/mmp.json`, version 2, qui remplace le cache de R16).
Jamais dans la boucle à 50 Hz. Rien n'est écrit en dehors de ce cache.

Clés de la sortie `--json` (stables) : profile_id, directory, sources, durations, windows (`months6` et
`weeks6` : {days, sessions, points: [{seconds, label, watts, effort, date, ts, session, free}]}), warning.
`watts` vaut null pour une durée sans effort ; `free` vaut null ou {watts, date, ts, session} ;
`session` = {file, route_id, workout_id}.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .. import profiles
from .history import MATCH_TOLERANCE_S, _discover_files, _header_of, _route_from_path
from .session_summary import SummaryError, load_session

DURATIONS_S = (5, 15, 30, 60, 120, 180, 300, 480, 720, 1200, 1800, 2700, 3600)
WINDOWS = {"months6": 183, "weeks6": 42}
CACHE_VERSION = 2
CACHE_PATH = Path.home() / ".cache" / "openride" / "mmp.json"   # contexte historique (sans profil)
MAX_GAP_S = 2.0
MAX_POWER_W = 2000.0
SPIKE_MIN_W = 1000.0
SPIKE_RATIO = 3.0
EFFORT_FREE, EFFORT_ERG, EFFORT_UNKNOWN = "libre", "ERG", "inconnu"
WARNING = ("La courbe n'est juste que là où il y a un effort à fond récent ; un changement de calibration "
           "du home trainer la décale tout entière.")


def duration_label(seconds: int) -> str:
    """« 5 s », « 1 min », « 60 min »."""
    return f"{seconds} s" if seconds < 60 else f"{seconds // 60} min"


# --- découpage d'une séance ---------------------------------------------------------------

def _intervals(events: Iterable[dict], start: str, end: str, key: str = "event") -> list[tuple[float, float]]:
    """Intervalles [début, fin] entre une ligne `start` et la ligne `end` suivante (fin infinie si absente)."""
    out: list[tuple[float, float]] = []
    opened: float | None = None
    for ev in sorted(events, key=lambda e: e["ts"]):
        if ev.get(key) == start and opened is None:
            opened = float(ev["ts"])
        elif ev.get(key) == end and opened is not None:
            out.append((opened, float(ev["ts"])))
            opened = None
    if opened is not None:
        out.append((opened, float("inf")))
    return out


def _is_erg(rec: dict) -> bool:
    return rec.get("target_w") is not None or str(rec.get("mode") or "").upper() == "ERG"


def segments(records: list[dict], events: list[dict] | None = None, devices: list[dict] | None = None,
             known_mode: bool = True) -> list[list[tuple[float, bool]]]:
    """Morceaux continus de la séance : listes de `(watts, erg)` à 1 Hz.

    Coupure à chaque pause (relevés entre `pause` et `resume` écartés), à chaque coupure du trainer
    (relevés entre `down` et `up` écartés), à chaque trou de plus de `MAX_GAP_S` et à chaque relevé sans
    puissance. Pics de capteur remplacés par le relevé précédent (`MAX_POWER_W`, pic isolé)."""
    pauses = _intervals(events or [], "pause", "resume")
    downs = _intervals([d for d in devices or [] if d.get("device") == "trainer"], "down", "up", key="state")
    holes = pauses + downs
    cuts = sorted(a for a, _ in holes)
    recs = sorted((r for r in records if r.get("ts") is not None), key=lambda r: float(r["ts"]))

    out: list[list[tuple[float, bool]]] = []
    cur: list[tuple[float, bool]] = []
    raw: list[float] = []            # puissances brutes du morceau, pour reconnaître les pics isolés
    prev_ts: float | None = None
    ci = 0

    def close() -> None:
        nonlocal cur, raw
        if cur:
            out.append(_despike(cur, raw))
        cur, raw = [], []

    for r in recs:
        ts = float(r["ts"])
        if any(a < ts < b for a, b in holes):
            continue
        p = r.get("power")
        if p is None:
            close()
            prev_ts = None
            continue
        broken = prev_ts is None or ts - prev_ts > MAX_GAP_S
        while ci < len(cuts) and cuts[ci] <= ts:
            if prev_ts is not None and cuts[ci] >= prev_ts:
                broken = True
            ci += 1
        if broken:
            close()
        cur.append((float(p), _is_erg(r) if known_mode else False))
        raw.append(float(p))
        prev_ts = ts
    close()
    return out


def _despike(seg: list[tuple[float, bool]], raw: list[float]) -> list[tuple[float, bool]]:
    fixed: list[tuple[float, bool]] = []
    for i, (p, erg) in enumerate(seg):
        before = raw[i - 1] if i > 0 else None
        after = raw[i + 1] if i + 1 < len(raw) else None
        spike = p > MAX_POWER_W or (
            p > SPIKE_MIN_W and before is not None and after is not None
            and p > SPIKE_RATIO * max(before, after, 1.0))
        if spike:
            p = fixed[-1][0] if fixed else 0.0
        fixed.append((p, erg))
    return fixed


def best_means(values: list[float], durations: Iterable[int] = DURATIONS_S) -> dict[int, float]:
    """Meilleure moyenne de chaque durée sur une série continue à 1 Hz (absente si la série est plus courte)."""
    n = len(values)
    cums = [0.0]
    for v in values:
        cums.append(cums[-1] + v)
    out: dict[int, float] = {}
    for d in durations:
        if n >= d:
            out[d] = max(cums[i + d] - cums[i] for i in range(n - d + 1)) / d
    return out


def session_curves(segs: list[list[tuple[float, bool]]]) -> tuple[dict[int, float], dict[int, float]]:
    """`(toutes, libres)` : meilleures moyennes de la séance, tous efforts confondus et efforts libres seuls
    (une fenêtre libre ne contient aucune seconde en ERG)."""
    all_best: dict[int, float] = {}
    free_best: dict[int, float] = {}
    for seg in segs:
        for d, w in best_means([p for p, _ in seg]).items():
            all_best[d] = max(w, all_best.get(d, 0.0))
        run: list[float] = []
        for p, erg in seg + [(0.0, True)]:            # sentinelle : ferme le dernier morceau libre
            if erg:
                for d, w in best_means(run).items():
                    free_best[d] = max(w, free_best.get(d, 0.0))
                run = []
            else:
                run.append(p)
    return all_best, free_best


# --- cache et séances ---------------------------------------------------------------------

def load_cache(path: Path) -> dict:
    """Entrées du cache version 2 (un cache de R16, version 1, est ignoré puis remplacé)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("version") == CACHE_VERSION and isinstance(data.get("entries"), dict):
            return data["entries"]
    except Exception:
        pass
    return {}


def save_cache(path: Path, entries: dict) -> None:
    """Écriture atomique : un lecteur ne voit jamais un fichier à moitié écrit."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"version": CACHE_VERSION, "entries": entries}), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def _compute_entry(path: Path, st: os.stat_result) -> dict[str, Any]:
    fmt = "jsonl" if path.suffix.lower() == ".jsonl" else "fit"
    entry: dict[str, Any] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "fmt": fmt, "start_ts": None,
                             "source": "", "route_id": None, "workout_id": None, "all": {}, "free": {},
                             "ftp_tests": []}
    try:
        session = load_session(path)
        entry["start_ts"] = float(session.records[0]["ts"])
        segs = segments(session.records, session.events, getattr(session, "devices", None), known_mode=fmt == "jsonl")
        all_best, free_best = session_curves(segs)
        entry["all"] = {str(d): round(w, 1) for d, w in all_best.items()}
        entry["free"] = {str(d): round(w, 1) for d, w in free_best.items()} if fmt == "jsonl" else {}
        entry["ftp_tests"] = [{"ts": t.get("ts"), "test": t.get("test"), "ftp_w": t.get("ftp_w"),
                               "ref_power_w": t.get("ref_power_w"), "warnings": list(t.get("warnings") or [])}
                              for t in getattr(session, "ftp_tests", []) or [] if isinstance(t, dict)]
    except (SummaryError, OSError, ValueError, KeyError, TypeError):
        entry["error"] = True
    if fmt == "jsonl":
        header = _header_of(path)
        entry["source"] = str(header.get("source") or "")
        entry["workout_id"] = header.get("workout_id")
    try:
        entry["route_id"] = _route_from_path(path, fmt)
    except Exception:
        entry["route_id"] = None
    return entry


def session_entries(directory: Path, cache_path: Path) -> list[tuple[Path, dict]]:
    """Toutes les séances du dossier (FIT et journaux), depuis le cache quand le fichier n'a pas changé.
    Le cache est réécrit seulement s'il a changé ; les entrées des fichiers disparus en sortent."""
    entries = load_cache(cache_path)
    fresh: dict[str, dict] = {}
    dirty = False
    out: list[tuple[Path, dict]] = []
    fits, jsonls = _discover_files(Path(directory))
    for p in fits + jsonls:
        try:
            st = p.stat()
            key = str(p.resolve())
        except OSError:
            continue
        e = entries.get(key)
        if not (isinstance(e, dict) and e.get("size") == st.st_size and e.get("mtime_ns") == st.st_mtime_ns):
            e = _compute_entry(p, st)
            dirty = True
        fresh[key] = e
        out.append((p, e))
    if dirty or set(fresh) != set(entries):
        save_cache(cache_path, fresh)
    return out


def kept_sessions(found: list[tuple[Path, dict]], sources: Iterable[str]) -> list[tuple[Path, dict]]:
    """Séances comptées : source du profil, jamais un rejeu ; FIT écarté quand son journal est là."""
    sources = set(sources)
    ok = [(p, e) for p, e in found if e.get("start_ts") is not None and not e.get("error")]
    journals = [e["start_ts"] for _, e in ok if e["fmt"] == "jsonl"]
    replays = [e["start_ts"] for _, e in ok if e["fmt"] == "jsonl" and e.get("source") == "replay"]
    kept = []
    for p, e in ok:
        if e["fmt"] == "fit":
            if any(abs(e["start_ts"] - t) <= MATCH_TOLERANCE_S for t in journals):   # même séance, journal lu
                continue
            source = "live"
        else:
            source = e.get("source") or "live"      # journal d'avant le lot V2 : séance réelle
        if source == "replay" or source not in sources:
            continue
        if any(abs(e["start_ts"] - t) <= MATCH_TOLERANCE_S for t in replays):
            continue
        kept.append((p, e))
    return kept


# --- courbe ---------------------------------------------------------------------------------

def _session_ref(p: Path, e: dict) -> dict[str, Any]:
    return {"file": p.name, "route_id": e.get("route_id"), "workout_id": e.get("workout_id")}


def _date(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def window_curve(kept: list[tuple[Path, dict]], days: int, now: float) -> dict[str, Any]:
    inside = [(p, e) for p, e in kept if 0 <= now - e["start_ts"] <= days * 86400.0 or e["start_ts"] > now]
    points = []
    for d in DURATIONS_S:
        best = free = None
        for p, e in inside:
            w = e["all"].get(str(d))
            if w is not None and (best is None or w > best[0]):
                best = (w, p, e)
            fw = e["free"].get(str(d))
            if fw is not None and (free is None or fw > free[0]):
                free = (fw, p, e)
        point: dict[str, Any] = {"seconds": d, "label": duration_label(d), "watts": None, "effort": None,
                                 "date": None, "ts": None, "session": None, "free": None}
        if best is not None:
            w, p, e = best
            if e["fmt"] != "jsonl":
                effort = EFFORT_UNKNOWN
            elif free is not None and free[0] >= w:
                effort = EFFORT_FREE
            else:
                effort = EFFORT_ERG
            point.update(watts=round(w), effort=effort, date=_date(e["start_ts"]), ts=e["start_ts"],
                         session=_session_ref(p, e))
        if free is not None:
            fw, fp, fe = free
            point["free"] = {"watts": round(fw), "date": _date(fe["start_ts"]), "ts": fe["start_ts"],
                             "session": _session_ref(fp, fe)}
        points.append(point)
    return {"days": days, "sessions": len(inside), "points": points}


def compute(directory: Path | None = None, sources: Iterable[str] | None = None, cache_path: Path | None = None,
            now: float | None = None) -> dict[str, Any]:
    """Courbe du profil en cours (ou du dossier `directory`) pour les deux fenêtres."""
    ctx = profiles.current()
    act_dir = Path(directory) if directory is not None else ctx.activities_dir
    cpath = Path(cache_path) if cache_path is not None else ctx.mmp_cache
    srcs = tuple(sources) if sources is not None else tuple(ctx.counted_sources)
    now = time.time() if now is None else now
    kept = kept_sessions(session_entries(act_dir, cpath), srcs)
    return {"profile_id": ctx.id, "directory": str(act_dir), "sources": list(srcs), "durations": list(DURATIONS_S),
            "windows": {name: window_curve(kept, days, now) for name, days in WINDOWS.items()},
            "warning": WARNING}


def format_text(r: dict[str, Any]) -> str:
    m6, w6 = r["windows"]["months6"], r["windows"]["weeks6"]
    lines = [f"Séances lues : {m6['sessions']} sur 6 mois, {w6['sessions']} sur 6 semaines",
             f"{'Durée':<8}{'6 mois':>8}  {'Quand':<11}{'Effort':<9}{'6 semaines':>11}"]
    for p, q in zip(m6["points"], w6["points"]):
        if p["watts"] is None:
            lines.append(f"{p['label']:<8}{'—':>8}  {'aucun effort':<20}{'—':>11}")
            continue
        recent = f"{q['watts']} W" if q["watts"] is not None else "—"
        lines.append(f"{p['label']:<8}{p['watts']:>6} W  {p['date']:<11}{p['effort']:<9}{recent:>11}")
    lines.append(r["warning"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openride_core.tools.power_curve",
                                 description="Courbe de puissance du profil en cours (6 mois et 6 semaines).")
    ap.add_argument("--dir", type=Path, dest="directory", help="dossier des séances (défaut : profil en cours)")
    ap.add_argument("--sources", help="sources comptées, séparées par des virgules (défaut : celles du profil)")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    a = ap.parse_args(argv)
    srcs = [s.strip() for s in a.sources.split(",") if s.strip()] if a.sources else None
    try:
        r = compute(a.directory, srcs)
    except Exception as exc:   # profil illisible : message lisible plutôt qu'une trace
        print(f"Courbe impossible : {exc}", file=sys.stderr)
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else format_text(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
