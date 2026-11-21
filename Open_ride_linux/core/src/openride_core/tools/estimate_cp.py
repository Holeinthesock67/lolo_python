"""Estimation de CP et W' à partir des séances passées (lot R16).

    python -m openride_core.tools.estimate_cp [--dir DOSSIER] [--days N] [--ftp W] [--json] [--config FICHIER]

Meilleure puissance moyenne (MMP) sur 3, 5, 8, 12 et 20 min dans les journaux `.jsonl` et les `.fit`
des 90 derniers jours, puis modèle à deux paramètres travail = CP × t + W' par régression linéaire.
Depuis le lot PP1, les meilleures puissances viennent de la courbe de `power_curve` (même cache par
séance, version 2) : une fenêtre ne traverse plus une pause ni une coupure du trainer.
L'estimation n'est acceptée que si elle est fiable (au moins 3 durées, R² ≥ 0,98, CP entre 0,8 et
1,2 × FTP, W' entre 5 et 40 kJ) ; sinon la raison est donnée. Elle suppose des efforts maximaux : elle
est basse si l'historique n'en contient pas. Les séances rejouées sont exclues. Rien n'est écrit en
dehors du cache des meilleures puissances du profil (`Profils/<id>/.cache/mmp.json`) ; la configuration n'est jamais modifiée.

Clés de la sortie `--json` (stables) : directory, ftp_w, days, sessions, estimate (null ou {cp_w,
w_prime_j, r2, durations: [{seconds, mmp_w, date}]}), reason (null ou texte), warning.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import config as config_mod
from .. import profiles
from . import power_curve
from .history import MATCH_TOLERANCE_S

DURATIONS_S = (180, 300, 480, 720, 1200)
MIN_DURATIONS = 3
MIN_R2 = 0.98
CP_RANGE = (0.8, 1.2)               # en fraction de la FTP
WPRIME_RANGE_J = (5000.0, 40000.0)
DEFAULT_DAYS = 90
CACHE_PATH = power_curve.CACHE_PATH   # cache commun avec la courbe de puissance (lot PP1, version 2)
WARNING = ("L'estimation suppose des efforts maximaux : elle est basse si l'historique n'en contient pas.")


def mmp(powers: list[float], durations: tuple = DURATIONS_S) -> dict[int, float]:
    """Meilleure puissance moyenne pour chaque durée sur une série continue à 1 Hz (`power_curve.best_means`)."""
    return power_curve.best_means(powers, durations)


def fit_cp_model(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Régression de W = CP × t + W' sur des points (t, MMP × t) ; renvoie (CP, W', R²)."""
    n = len(points)
    mt = sum(t for t, _ in points) / n
    mw = sum(w for _, w in points) / n
    sxx = sum((t - mt) ** 2 for t, _ in points)
    sxy = sum((t - mt) * (w - mw) for t, w in points)
    cp = sxy / sxx
    wp = mw - cp * mt
    ss_res = sum((w - (cp * t + wp)) ** 2 for t, w in points)
    ss_tot = sum((w - mw) ** 2 for _, w in points)
    return cp, wp, (1.0 - ss_res / ss_tot) if ss_tot > 0 else 1.0


def estimate(directory: Path | None = None, ftp_w: float = 250.0, days: int = DEFAULT_DAYS,
             cache_path: Path | None = None, now: float | None = None) -> dict[str, Any]:
    ctx = profiles.current()   # séances et cache du profil en cours (série MJ, lot MJ1)
    act_dir = Path(directory) if directory is not None else ctx.activities_dir
    cpath = Path(cache_path) if cache_path is not None else ctx.mmp_cache
    now = time.time() if now is None else now
    sessions = [(p, e) for p, e in power_curve.session_entries(act_dir, cpath)
                if e.get("start_ts") is not None and not e.get("error")]

    replays = [e["start_ts"] for _, e in sessions if e.get("source") == "replay"]
    kept = []
    for p, e in sessions:
        if e.get("source") == "replay":
            continue
        if any(abs(e["start_ts"] - t) <= MATCH_TOLERANCE_S for t in replays):    # .fit d'une séance rejouée
            continue
        if now - e["start_ts"] > days * 86400.0:
            continue
        kept.append(e)

    best: dict[int, tuple[float, float]] = {}
    for e in kept:
        for d in DURATIONS_S:
            w = e["all"].get(str(d))
            if w is None:
                continue
            if d not in best or w > best[d][0]:
                best[d] = (w, e["start_ts"])
    result: dict[str, Any] = {"directory": str(act_dir), "ftp_w": ftp_w, "days": days, "sessions": len(kept),
                              "estimate": None, "reason": None, "warning": WARNING}
    if DURATIONS_S[0] not in best:
        result["reason"] = f"pas d'effort maximal de {DURATIONS_S[0] // 60} min dans les {days} derniers jours"
        return result
    if len(best) < MIN_DURATIONS:
        result["reason"] = (f"{len(best)} durée(s) seulement parmi {', '.join(str(d // 60) for d in DURATIONS_S)} min "
                            f"(il en faut {MIN_DURATIONS})")
        return result
    used = sorted(best)
    cp, wp, r2 = fit_cp_model([(float(d), best[d][0] * d) for d in used])
    if r2 < MIN_R2:
        result["reason"] = f"efforts peu cohérents (R² = {r2:.2f}, il faut {MIN_R2:.2f})"
    elif not CP_RANGE[0] * ftp_w <= cp <= CP_RANGE[1] * ftp_w:
        result["reason"] = f"CP = {cp:.0f} W hors de {CP_RANGE[0]:.1f} à {CP_RANGE[1]:.1f} × FTP ({ftp_w:.0f} W)"
    elif not WPRIME_RANGE_J[0] <= wp <= WPRIME_RANGE_J[1]:
        result["reason"] = f"W' = {wp / 1000:.1f} kJ hors de 5 à 40 kJ"
    else:
        result["estimate"] = {
            "cp_w": round(cp, 1), "w_prime_j": round(wp, 0), "r2": round(r2, 4),
            "durations": [{"seconds": d, "mmp_w": round(best[d][0], 1),
                           "date": datetime.fromtimestamp(best[d][1]).strftime("%Y-%m-%d")} for d in used]}
    return result


def estimate_w_prime(directory: Path | None = None, ftp_w: float = 250.0, **kw) -> float | None:
    """W' estimé (J) ou `None` : valeur de `hello_ack.config.rogue.w_prime_estimate_j`."""
    est = estimate(directory, ftp_w, **kw)["estimate"]
    return est["w_prime_j"] if est else None


def format_text(r: dict[str, Any]) -> str:
    lines = [f"Séances lues : {r['sessions']} ({r['days']} derniers jours)"]
    if r["estimate"]:
        e = r["estimate"]
        lines.append(f"CP = {e['cp_w']:.0f} W, W' = {e['w_prime_j'] / 1000:.1f} kJ (R² = {e['r2']:.3f})")
        for d in e["durations"]:
            lines.append(f"  {d['seconds'] // 60:>2} min : {d['mmp_w']:.0f} W ({d['date']})")
    else:
        lines.append(f"Pas d'estimation : {r['reason']}")
    lines.append(r["warning"])
    return "\n".join(lines)


def run(directory: Path | None, ftp: float | None, days: int, as_json: bool, config_path: Path | None) -> int:
    try:
        cfg = config_mod.load(config_path)
    except config_mod.ConfigError as exc:
        print(f"Erreur de configuration : {exc}", file=sys.stderr)
        return 2
    result = estimate(directory, ftp if ftp else cfg.rider.ftp_w, days)
    print(json.dumps(result, ensure_ascii=False, indent=2) if as_json else format_text(result))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m openride_core.tools.estimate_cp",
                                description="Estime CP et W' depuis les séances passées.")
    p.add_argument("--dir", type=Path, dest="directory", help="dossier des séances (défaut : ~/OpenRide/Activities)")
    p.add_argument("--days", type=int, default=DEFAULT_DAYS, help="historique pris en compte (défaut : 90 jours)")
    p.add_argument("--ftp", type=float, help="FTP en watts (défaut : config.toml)")
    p.add_argument("--json", action="store_true", help="sortie JSON")
    p.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    a = p.parse_args(argv)
    return run(a.directory, a.ftp, a.days, a.json, a.config)


if __name__ == "__main__":
    raise SystemExit(main())
