"""Historique des séances et cumul hebdomadaire (lot L7, SRS §9, §11) : `openride-core history`.

    openride-core history [--dir DOSSIER] [--weeks N] [--ftp W] [--json] [--config FICHIER]

Parcourt les séances enregistrées dans `~/OpenRide/Activities/` (fichiers `.fit`) et son
sous-dossier `.journal/` (journaux `.jsonl`), de la plus récente à la plus ancienne :
- une séance présente à la fois en `.fit` et en `.jsonl` (heure de début à ± 60 s) n'apparaît
  qu'une seule fois, le `.fit` faisant foi ;
- un journal `.jsonl` sans `.fit` correspondant (séance interrompue non récupérée) est listé
  avec la mention « à récupérer : openride-core recover » ;
- un fichier illisible ou tronqué apparaît avec son erreur sans arrêter la commande (code 0) ;
- les bilans sont mis en cache dans `~/.cache/openride/history.json` (clé : chemin résolu,
  taille, `mtime_ns`, FTP) ; un cache absent ou corrompu est recalculé sans erreur.

Clés de la sortie `--json` (stables) :
    directory, ftp_w, weeks_limit,
    sessions (liste de {source, filename, format ("fit" | "jsonl"),
        status ("ok" | "recover" | "error"), date, start_ts, route, duration_s, distance_m,
        elevation_gain_m, avg_power_w, np_w, if, tss, note, error}),
    weeks (liste de {week ("AAAA-Wss"), start_date, end_date, count, duration_s,
        distance_m, elevation_gain_m, tss}).
Les arrondis numériques sont identiques à ceux de `openride-core summary` (puissances, durées,
distances, dénivelés et TSS à 0,1 ; IF à 0,01).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .. import fit_export
from ..journal import read_journal
from .session_summary import SummaryError, _hms, compute_summary, load_session

CACHE_PATH = Path.home() / ".cache" / "openride" / "history.json"
MATCH_TOLERANCE_S = 60.0
RECOVER_NOTE = "à récupérer : openride-core recover"
_STAMP_ROUTE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[_T]\d{2}-\d{2}(?:-\d{2})?_(.+)$")


def _route_from_path(path: Path, fmt: str) -> str:
    if fmt == "jsonl":
        try:
            for line in read_journal(path):
                if isinstance(line, dict) and line.get("kind") == "header":
                    rid = line.get("route_id")
                    if isinstance(rid, str) and rid.strip():
                        return rid.strip()
                    break
        except Exception:
            pass
    m = _STAMP_ROUTE_RE.match(path.stem)
    return m.group(1) if m else path.stem


def _load_cache(cache_path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("entries"), dict):
            return data["entries"]
    except Exception:
        pass
    return {}


def _save_cache(cache_path: Path, entries: dict[str, dict[str, Any]]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"version": 1, "entries": entries}, ensure_ascii=False)
        cache_path.write_text(payload, encoding="utf-8")
    except Exception:
        pass


def _summarize_file(
    path: Path,
    ftp: float,
    cache_entries: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None, bool]:
    """Renvoie `(bilan, erreur, cache_modifié)` pour un fichier `.fit` ou `.jsonl`."""
    fmt = path.suffix.lower().lstrip(".")
    try:
        st = path.stat()
        resolved = str(path.resolve())
    except OSError as exc:
        return None, str(exc), False

    ftp_key = round(float(ftp), 2)
    cached = cache_entries.get(resolved)
    if (
        isinstance(cached, dict)
        and cached.get("size") == st.st_size
        and cached.get("mtime_ns") == st.st_mtime_ns
        and cached.get("ftp_w") == ftp_key
        and isinstance(cached.get("summary"), dict)
    ):
        return cached["summary"], None, False

    try:
        sess = load_session(path)
        s = compute_summary(sess, ftp, str(path))
        route = _route_from_path(path, fmt)
        summary = {
            "start_ts": round(float(s["start_ts"]), 3),
            "route": route,
            "duration_s": round(float(s["duration_s"]), 1),
            "distance_m": round(float(s["distance_m"]), 1),
            "elevation_gain_m": round(float(s["elevation_gain_m"]), 1),
            "avg_power_w": round(float(s["avg_power_w"]), 1),
            "np_w": round(float(s["np_w"]), 1),
            "if": round(float(s["if"]), 2),
            "tss": round(float(s["tss"]), 1),
        }
    except (SummaryError, Exception) as exc:
        return None, str(exc), False

    cache_entries[resolved] = {
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "ftp_w": ftp_key,
        "summary": summary,
    }
    return summary, None, True


def _discover_files(directory: Path) -> tuple[list[Path], list[Path]]:
    """Renvoie `(fichiers_fit, fichiers_jsonl)` trouvés dans `directory` et `directory/.journal`."""
    if not directory.is_dir():
        return [], []
    fits = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".fit")
    jsonls: list[Path] = []
    seen: set[Path] = set()
    for folder in (directory, directory / ".journal"):
        if folder.is_dir():
            for p in sorted(folder.iterdir()):
                if p.is_file() and p.suffix.lower() == ".jsonl":
                    rp = p.resolve()
                    if rp not in seen:
                        seen.add(rp)
                        jsonls.append(p)
    return fits, jsonls


def compute_history(
    directory: Path | None = None,
    ftp: float = 250.0,
    weeks: int = 8,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    """Calcule l'historique des séances et le cumul hebdomadaire ISO."""
    act_dir = Path(directory) if directory is not None else fit_export.ACTIVITIES_DIR
    cpath = Path(cache_path) if cache_path is not None else CACHE_PATH
    weeks = max(int(weeks), 1)

    cache_entries = _load_cache(cpath)
    cache_dirty = False

    fits, jsonls = _discover_files(act_dir)

    fit_valid: list[tuple[Path, dict[str, Any]]] = []
    errors_list: list[dict[str, Any]] = []

    for p in fits:
        summ, err, dirty = _summarize_file(p, ftp, cache_entries)
        cache_dirty = cache_dirty or dirty
        if summ is not None:
            fit_valid.append((p, summ))
        else:
            errors_list.append({
                "source": str(p),
                "filename": p.name,
                "format": "fit",
                "status": "error",
                "date": None,
                "start_ts": None,
                "route": None,
                "duration_s": None,
                "distance_m": None,
                "elevation_gain_m": None,
                "avg_power_w": None,
                "np_w": None,
                "if": None,
                "tss": None,
                "note": None,
                "error": err,
            })

    jsonl_valid: list[tuple[Path, dict[str, Any]]] = []
    for p in jsonls:
        summ, err, dirty = _summarize_file(p, ftp, cache_entries)
        cache_dirty = cache_dirty or dirty
        if summ is not None:
            jsonl_valid.append((p, summ))
        else:
            errors_list.append({
                "source": str(p),
                "filename": p.name,
                "format": "jsonl",
                "status": "error",
                "date": None,
                "start_ts": None,
                "route": None,
                "duration_s": None,
                "distance_m": None,
                "elevation_gain_m": None,
                "avg_power_w": None,
                "np_w": None,
                "if": None,
                "tss": None,
                "note": None,
                "error": err,
            })

    if cache_dirty:
        _save_cache(cpath, cache_entries)

    valid_sessions: list[dict[str, Any]] = []
    fit_starts = [s["start_ts"] for _, s in fit_valid]

    for p, s in fit_valid:
        dt = datetime.fromtimestamp(s["start_ts"])
        valid_sessions.append({
            "source": str(p),
            "filename": p.name,
            "format": "fit",
            "status": "ok",
            "date": dt.strftime("%Y-%m-%d %H:%M"),
            "start_ts": s["start_ts"],
            "route": s["route"],
            "duration_s": s["duration_s"],
            "distance_m": s["distance_m"],
            "elevation_gain_m": s["elevation_gain_m"],
            "avg_power_w": s["avg_power_w"],
            "np_w": s["np_w"],
            "if": s["if"],
            "tss": s["tss"],
            "note": None,
            "error": None,
        })

    for p, s in jsonl_valid:
        if any(abs(s["start_ts"] - fs) <= MATCH_TOLERANCE_S for fs in fit_starts):
            continue
        dt = datetime.fromtimestamp(s["start_ts"])
        valid_sessions.append({
            "source": str(p),
            "filename": p.name,
            "format": "jsonl",
            "status": "recover",
            "date": dt.strftime("%Y-%m-%d %H:%M"),
            "start_ts": s["start_ts"],
            "route": s["route"],
            "duration_s": s["duration_s"],
            "distance_m": s["distance_m"],
            "elevation_gain_m": s["elevation_gain_m"],
            "avg_power_w": s["avg_power_w"],
            "np_w": s["np_w"],
            "if": s["if"],
            "tss": s["tss"],
            "note": RECOVER_NOTE,
            "error": None,
        })

    valid_sessions.sort(key=lambda item: item["start_ts"], reverse=True)
    errors_list.sort(key=lambda item: item["filename"], reverse=True)

    by_week: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for item in valid_sessions:
        iso = datetime.fromtimestamp(item["start_ts"]).isocalendar()
        by_week.setdefault((int(iso.year), int(iso.week)), []).append(item)

    weekly_out: list[dict[str, Any]] = []
    for year, week_num in sorted(by_week, reverse=True)[:weeks]:
        items = by_week[(year, week_num)]
        monday = date.fromisocalendar(year, week_num, 1).isoformat()
        sunday = date.fromisocalendar(year, week_num, 7).isoformat()
        weekly_out.append({
            "week": f"{year:04d}-W{week_num:02d}",
            "start_date": monday,
            "end_date": sunday,
            "count": len(items),
            "duration_s": round(sum(x["duration_s"] for x in items), 1),
            "distance_m": round(sum(x["distance_m"] for x in items), 1),
            "elevation_gain_m": round(sum(x["elevation_gain_m"] for x in items), 1),
            "tss": round(sum(x["tss"] for x in items), 1),
        })

    return {
        "directory": str(act_dir),
        "ftp_w": round(float(ftp), 1),
        "weeks_limit": weeks,
        "sessions": valid_sessions + errors_list,
        "weeks": weekly_out,
    }


def format_text(result: dict[str, Any]) -> str:
    sessions = result["sessions"]
    if not sessions:
        return f"Aucune séance dans {result['directory']}."
    lines: list[str] = []
    for s in sessions:
        if s["status"] == "error":
            lines.append(f"{s['filename']} : erreur : {s['error']}")
            continue
        suffix = f"  [{s['note']}]" if s["note"] else ""
        lines.append(
            f"{s['date']}  {s['route']:<16}  {_hms(s['duration_s']):>8}  "
            f"{s['distance_m'] / 1000:6.2f} km  +{s['elevation_gain_m']:4.0f} m  "
            f"moy {s['avg_power_w']:3.0f} W  NP {s['np_w']:3.0f} W  "
            f"TSS {s['tss']:5.1f}{suffix}"
        )
    if result["weeks"]:
        lines.append("")
        lines.append("Cumul par semaine ISO :")
        for w in result["weeks"]:
            lines.append(
                f"  {w['week']} ({w['start_date']} au {w['end_date']}) : "
                f"{w['count']} séance(s), {_hms(w['duration_s'])}, "
                f"{w['distance_m'] / 1000:.2f} km, TSS {w['tss']:.1f}"
            )
    return "\n".join(lines)


def run(
    directory: Path | None = None,
    weeks: int = 8,
    ftp: float | None = None,
    as_json: bool = False,
    config_path: Path | None = None,
) -> int:
    from .. import config as config_mod

    if weeks < 1:
        print("openride-core history : --weeks doit être >= 1", file=sys.stderr)
        return 1
    if ftp is None:
        try:
            ftp = float(config_mod.load(config_path).rider.ftp_w)
        except config_mod.ConfigError as exc:
            print(f"openride-core : configuration invalide : {exc} (utiliser --ftp)", file=sys.stderr)
            return 1
    elif ftp <= 0:
        print("openride-core history : --ftp doit être > 0", file=sys.stderr)
        return 1

    result = compute_history(directory=directory, ftp=ftp, weeks=weeks)
    print(json.dumps(result, ensure_ascii=False, indent=2) if as_json else format_text(result))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m openride_core.tools.history",
        description="Historique des séances et cumul par semaine ISO.",
    )
    p.add_argument("--dir", type=Path, dest="directory",
                   help="dossier des séances (défaut : ~/OpenRide/Activities)")
    p.add_argument("--weeks", type=int, default=8,
                   help="nombre de semaines ISO à afficher (défaut : 8)")
    p.add_argument("--ftp", type=float, help="FTP en watts (défaut : config.toml)")
    p.add_argument("--json", action="store_true", help="sortie JSON")
    p.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    a = p.parse_args(argv)
    return run(a.directory, a.weeks, a.ftp, a.json, a.config)


if __name__ == "__main__":
    raise SystemExit(main())
