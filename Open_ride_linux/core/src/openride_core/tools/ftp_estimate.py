"""FTP estimée depuis la courbe de puissance du profil, proposée au joueur (série PP, lot PP2).

    python -m openride_core.tools.ftp_estimate [--dir DOSSIER] [--ftp W] [--json] [--accept W] [--config FICHIER]

Trois sources, de la plus fiable à la moins fiable ; une seule est retenue, et sa source est écrite en
toutes lettres (cadrage PP §3.3) :

1. test de rampe de moins de 6 semaines, sans avertissement bloquant (lot O10 : 75 % de la meilleure
   minute) : « Fiable » ;
2. puissance critique (CP, modèle travail = CP × durée + W' de R16) sur les efforts **libres** de 3 à
   20 min des 6 dernières semaines : « Fiable » avec au moins 4 durées dont 20 min, « Indicative » sinon ;
3. meilleur effort libre de 20 min des 6 dernières semaines × 95 % : « Indicative ».

Sans rien de tout cela : « Pas assez de données », avec la raison (« aucun effort libre de plus de
12 min depuis 6 semaines »). Les séances ERG ne comptent jamais (décision Q1 : une séance réglée à
100 % de 250 W « prouverait » 250 W), sauf le test de rampe, fait pour aller au bout.

Rien n'est jamais écrit sans accord (décision Q2) : le résultat porte une proposition « Utiliser 249 W
comme FTP » ; `--accept 249` l'enregistre par le chemin des réglages du profil (`config_edit.update_layers`,
clé joueur `rider.ftp_w`, lot MJ4), seulement si l'estimation du moment vaut toujours 249 W. Le jeu ne la
montre qu'au menu et sur le bilan de fin de séance, jamais pendant que le joueur roule (lots PP3 et PP4).

Clés de la sortie `--json` (stables) : profile_id, ftp_set_w, estimate (null ou {ftp_w, source, source_text,
confidence, date}), confidence, reason, proposal (null ou {ftp_w, text}), review (bool : écart de plus de
5 % avec la FTP réglée), delta_pct, monthly ([{month, best_5min_w, best_20min_w, ftp_w}], 6 mois),
warnings.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import profiles
from . import power_curve as pc
from .estimate_cp import CP_RANGE, MIN_R2, WPRIME_RANGE_J, fit_cp_model

RECENT_DAYS = 42
CP_DURATIONS_S = (180, 300, 480, 720, 1200)
BEST20_FACTOR = 0.95
REVIEW_PCT = 5.0
MONTHS = 6
BLOCKING_RAMP = ("too_short", "trainer_dropout", "paused")   # ftp_test.BLOCKING
CONF_RELIABLE, CONF_INDICATIVE, CONF_NONE = "Fiable", "Indicative", "Pas assez de données"
WARNINGS = (
    "L'estimation suppose des efforts à fond : sans effort à fond récent, elle est trop basse.",
    "La puissance vient du home trainer : un changement de calibration décale toute la courbe, "
    "et le jeu ne peut pas le voir.",
)


def _date(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def _fr_date(ts: float) -> str:
    months = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")
    d = datetime.fromtimestamp(ts)
    return f"{d.day} {months[d.month - 1]}"


def _free_best(kept: list, days: float, now: float, start: float | None = None) -> dict[int, tuple[float, float]]:
    """Meilleur effort libre de chaque durée : `{durée: (watts, ts)}` sur `days` jours avant `now`."""
    out: dict[int, tuple[float, float]] = {}
    for _, e in kept:
        ts = e["start_ts"]
        if not (now - days * 86400.0 <= ts <= now) or (start is not None and ts < start):
            continue
        for d_str, w in (e.get("free") or {}).items():
            d = int(d_str)
            if d not in out or w > out[d][0]:
                out[d] = (float(w), ts)
    return out


def _last_ramp(kept: list, now: float) -> dict | None:
    best = None
    for _, e in kept:
        for t in e.get("ftp_tests") or []:
            ts, ftp = t.get("ts"), t.get("ftp_w")
            if ts is None or ftp is None or t.get("test", "ramp") != "ramp":
                continue
            if now - float(ts) > RECENT_DAYS * 86400.0 or any(w in BLOCKING_RAMP for w in t.get("warnings") or []):
                continue
            if best is None or float(ts) > best["ts"]:
                best = {"ts": float(ts), "ftp_w": int(round(float(ftp))), "ref_power_w": t.get("ref_power_w")}
    return best


def _cp_estimate(free: dict[int, tuple[float, float]], ftp_set_w: float) -> tuple[dict | None, str | None]:
    used = [d for d in CP_DURATIONS_S if d in free]
    if len(used) < 3:
        return None, None
    cp, wp, r2 = fit_cp_model([(float(d), free[d][0] * d) for d in used])
    if r2 < MIN_R2:
        return None, f"efforts libres de 3 à 20 min peu cohérents (R² = {r2:.2f})"
    if not CP_RANGE[0] * ftp_set_w <= cp <= CP_RANGE[1] * ftp_set_w:
        return None, f"puissance critique de {cp:.0f} W trop loin de la FTP réglée ({ftp_set_w:.0f} W)"
    if not WPRIME_RANGE_J[0] <= wp <= WPRIME_RANGE_J[1]:
        return None, "réserve anaérobie hors des valeurs plausibles"
    conf = CONF_RELIABLE if len(used) >= 4 and 1200 in used else CONF_INDICATIVE
    last = max(free[d][1] for d in used)
    return {"ftp_w": int(round(cp)), "source": "cp", "confidence": conf, "date": _date(last),
            "source_text": (f"puissance critique de tes efforts libres de "
                            f"{pc.duration_label(used[0])} à {pc.duration_label(used[-1])} "
                            f"des 6 dernières semaines ({len(used)} durées)")}, None


def estimate_from_sessions(kept: list, ftp_set_w: float, now: float) -> dict[str, Any]:
    """Estimation depuis les séances comptées du profil (`power_curve.kept_sessions`)."""
    reason = None
    est: dict[str, Any] | None = None
    ramp = _last_ramp(kept, now)
    if ramp is not None:
        ref = f" (75 % de {ramp['ref_power_w']} W)" if ramp.get("ref_power_w") else ""
        est = {"ftp_w": ramp["ftp_w"], "source": "ramp", "confidence": CONF_RELIABLE, "date": _date(ramp["ts"]),
               "source_text": f"test de rampe du {_fr_date(ramp['ts'])}{ref}"}
    free = _free_best(kept, RECENT_DAYS, now)
    if est is None:
        est, _cp_reason = _cp_estimate(free, ftp_set_w)   # refus de la CP : le 20 min libre peut encore servir
    if est is None and 1200 in free:
        w, ts = free[1200]
        est = {"ftp_w": int(round(w * BEST20_FACTOR)), "source": "best20", "confidence": CONF_INDICATIVE,
               "date": _date(ts),
               "source_text": f"meilleur effort libre de 20 min du {_fr_date(ts)} (95 % de {w:.0f} W)"}
    if est is None:   # raison utile au joueur : la durée d'effort libre qui manque
        longest = max((d for d in free), default=None)
        reason = ("aucun effort libre depuis 6 semaines" if longest is None
                  else f"aucun effort libre de plus de {pc.duration_label(longest)} depuis 6 semaines")
    out: dict[str, Any] = {"ftp_set_w": round(ftp_set_w), "estimate": est,
                           "confidence": est["confidence"] if est else CONF_NONE,
                           "reason": None if est else reason, "proposal": None, "review": False,
                           "delta_pct": None, "warnings": list(WARNINGS)}
    if est is not None:
        delta = (est["ftp_w"] - ftp_set_w) / ftp_set_w * 100.0 if ftp_set_w else 0.0
        out["delta_pct"] = round(delta, 1)
        out["review"] = abs(delta) > REVIEW_PCT
        if est["ftp_w"] != round(ftp_set_w):
            out["proposal"] = {"ftp_w": est["ftp_w"], "text": f"Utiliser {est['ftp_w']} W comme FTP"}
    out["monthly"] = monthly(kept, now)
    return out


def _month_start(year: int, month: int) -> float:
    return datetime(year, month, 1).timestamp()


def monthly(kept: list, now: float, months: int = MONTHS) -> list[dict[str, Any]]:
    """Évolution mois par mois (du plus ancien au mois en cours) : meilleurs 5 et 20 min libres du mois,
    et FTP du mois (test de rampe du mois, sinon 95 % du meilleur 20 min libre)."""
    d = datetime.fromtimestamp(now)
    ym = [(d.year, d.month)]
    for _ in range(months - 1):
        y, m = ym[-1]
        ym.append((y - 1, 12) if m == 1 else (y, m - 1))
    out = []
    for y, m in reversed(ym):
        start = _month_start(y, m)
        end = _month_start(y + 1, 1) if m == 12 else _month_start(y, m + 1)
        sel = [(p, e) for p, e in kept if start <= e["start_ts"] < end]
        free = _free_best(sel, 10_000, end)
        ramps = [t for _, e in sel for t in e.get("ftp_tests") or []
                 if t.get("ftp_w") is not None and not any(w in BLOCKING_RAMP for w in t.get("warnings") or [])]
        ftp = (int(round(float(max(ramps, key=lambda t: t.get("ts") or 0)["ftp_w"]))) if ramps
               else (int(round(free[1200][0] * BEST20_FACTOR)) if 1200 in free else None))
        out.append({"month": f"{y:04d}-{m:02d}",
                    "best_5min_w": int(round(free[300][0])) if 300 in free else None,
                    "best_20min_w": int(round(free[1200][0])) if 1200 in free else None,
                    "ftp_w": ftp})
    return out


def estimate(directory: Path | None = None, ftp_set_w: float = 250.0, sources=None, cache_path: Path | None = None,
             now: float | None = None) -> dict[str, Any]:
    """FTP estimée du profil en cours (ou du dossier `directory`)."""
    ctx = profiles.current()
    act_dir = Path(directory) if directory is not None else ctx.activities_dir
    cpath = Path(cache_path) if cache_path is not None else ctx.mmp_cache
    srcs = tuple(sources) if sources is not None else tuple(ctx.counted_sources)
    now = time.time() if now is None else now
    kept = pc.kept_sessions(pc.session_entries(act_dir, cpath), srcs)
    return {"profile_id": ctx.id, **estimate_from_sessions(kept, ftp_set_w, now)}


class AcceptError(Exception):
    """Proposition refusée : l'estimation a changé, ou il n'y en a pas."""


def accept(expected_w: int, config_path: Path | None = None, directory: Path | None = None,
           now: float | None = None) -> bool:
    """Enregistre la FTP proposée, si l'estimation du moment vaut toujours `expected_w` ; True si écrite."""
    from .. import config as config_mod
    from .. import config_edit

    cfg = config_mod.load(config_path)
    r = estimate(directory, cfg.rider.ftp_w, now=now)
    prop = r["proposal"]
    if prop is None or prop["ftp_w"] != int(expected_w):
        raise AcceptError(f"la FTP proposée n'est pas {int(expected_w)} W"
                          + (f" mais {prop['ftp_w']} W" if prop else " (aucune proposition)"))
    return bool(config_edit.update_layers([("rider", "ftp_w", prop["ftp_w"])], config_path))


def format_text(r: dict[str, Any]) -> str:
    lines = [f"FTP réglée : {r['ftp_set_w']} W"]
    e = r["estimate"]
    if e:
        lines.append(f"FTP estimée : {e['ftp_w']} W — {e['confidence']}")
        lines.append(f"Source : {e['source_text']}")
        if r["proposal"]:
            lines.append(f"Proposition : {r['proposal']['text']} (écart {r['delta_pct']:+.1f} %)")
    else:
        lines.append(f"FTP estimée : {CONF_NONE} ({r['reason']})")
    lines.append("Évolution : " + ", ".join(
        f"{m['month']} {m['ftp_w']} W" if m["ftp_w"] else f"{m['month']} —" for m in r["monthly"]))
    lines.extend(r["warnings"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    from .. import config as config_mod

    ap = argparse.ArgumentParser(prog="python -m openride_core.tools.ftp_estimate",
                                 description="FTP estimée du profil en cours, proposée sans rien écrire.")
    ap.add_argument("--dir", type=Path, dest="directory", help="dossier des séances (défaut : profil en cours)")
    ap.add_argument("--ftp", type=float, help="FTP réglée en watts (défaut : configuration)")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    ap.add_argument("--accept", type=int, metavar="W", help="enregistre la FTP proposée si elle vaut toujours W")
    ap.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    a = ap.parse_args(argv)
    try:
        cfg = config_mod.load(a.config)
    except config_mod.ConfigError as exc:
        print(f"Erreur de configuration : {exc}", file=sys.stderr)
        return 2
    if a.accept is not None:
        try:
            changed = accept(a.accept, a.config, a.directory)
        except AcceptError as exc:
            print(f"Rien n'est écrit : {exc}.", file=sys.stderr)
            return 1
        print(f"FTP enregistrée : {a.accept} W" if changed else "FTP inchangée.")
        return 0
    r = estimate(a.directory, a.ftp if a.ftp else cfg.rider.ftp_w)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else format_text(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
