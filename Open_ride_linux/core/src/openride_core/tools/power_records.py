"""Records de puissance de la séance et signal « FTP à revoir » au bilan (série PP, lot PP4).

    python -m openride_core.tools.power_records JOURNAL.jsonl [--dir DOSSIER] [--ftp W] [--json]

À la fin d'une séance, le core compare la courbe de la séance (13 durées, lot PP1, fenêtres jamais à cheval
sur une pause) aux meilleurs efforts des **6 derniers mois** du profil, séance exclue :

- un record est une durée où la séance fait mieux d'au moins 1 W (watts arrondis) que tout ce que le profil
  a fait sur 6 mois ; une durée jamais tenue avant (premier effort de 60 min) est un record sans « avant » ;
- la première séance du profil (rien sur 6 mois) n'annonce rien : tout y serait record ;
- au plus `MAX_RECORDS` records, les plus grands gains en pour cent, rangés par durée ; chaque record dit
  si l'effort était libre ou en ERG (le mot, jamais la couleur seule).

Le signal « FTP à revoir » reprend l'estimation du lot PP2 (séance comprise) : il part seulement quand
l'écart avec la FTP réglée dépasse 5 % ; c'est une proposition, à accepter au menu (« Qui roule ? › Ma
puissance ») : rien n'est écrit ici, et rien ne s'affiche pendant la séance.

Une séance non comptée par le profil (rejeu, séance simulée d'un joueur) n'annonce rien.

Clés de la sortie (objet `summary.power_records` et `summary.ftp_review` du contrat IPC 1.29) :
records ([{s, w, prev_w, e}]), ftp_review (null ou {estimate_w, ftp_set_w, delta_pct, confidence}).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from .. import profiles
from . import ftp_estimate
from . import power_curve as pc

MAX_RECORDS = 4


def _same(p: Path, journal: Path) -> bool:
    try:
        return p.resolve() == journal.resolve()
    except OSError:
        return p == journal


def records_from_sessions(kept: list[tuple[Path, dict]], journal: Path, now: float) -> list[dict[str, Any]] | None:
    """Records de la séance `journal` face aux séances comptées des 6 mois qui la précèdent ; None si la séance
    n'est pas comptée par le profil."""
    cur = next((e for p, e in kept if _same(p, Path(journal))), None)
    if cur is None:
        return None
    start = cur["start_ts"]
    days = pc.WINDOWS["months6"] * 86400.0
    before = [e for p, e in kept if e is not cur and e["start_ts"] < start and now - e["start_ts"] <= days]
    if not before:
        return []
    found = []
    for d in pc.DURATIONS_S:
        w = cur["all"].get(str(d))
        if w is None:
            continue
        prev = max((e["all"][str(d)] for e in before if e["all"].get(str(d)) is not None), default=None)
        if prev is not None and round(w) <= round(prev):
            continue
        fw = cur["free"].get(str(d))
        effort = pc.EFFORT_FREE if fw is not None and fw >= w - 0.05 else pc.EFFORT_ERG
        gain = (w - prev) / prev if prev else float("inf")
        found.append(({"s": d, "w": round(w), "prev_w": round(prev) if prev is not None else None, "e": effort},
                      gain))
    found.sort(key=lambda x: (-x[1], -x[0]["s"]))
    return sorted((r for r, _ in found[:MAX_RECORDS]), key=lambda r: r["s"])


def ftp_review(kept: list[tuple[Path, dict]], ftp_set_w: float, now: float) -> dict[str, Any] | None:
    est = ftp_estimate.estimate_from_sessions(kept, ftp_set_w, now)
    if not est["review"] or est["estimate"] is None or est["proposal"] is None:
        return None
    return {"estimate_w": est["estimate"]["ftp_w"], "ftp_set_w": est["ftp_set_w"], "delta_pct": est["delta_pct"],
            "confidence": est["confidence"]}


def session_report(journal: Path, ftp_set_w: float, directory: Path, cache_path: Path, sources: Iterable[str],
                   now: float | None = None, since: float | None = None) -> dict[str, Any] | None:
    """Records et signal de la séance `journal` (dans `directory` ou son sous-dossier `.journal/`) ; None si la
    séance n'est pas comptée. Lit le cache commun des courbes (lot PP1).

    `since` (remise à zéro des statistiques, lot RZ1) : les records comparent la séance aux seules séances d'après
    la remise à zéro ; le signal « FTP à revoir » lit toutes les séances, comme la FTP estimée."""
    now = time.time() if now is None else now
    found = pc.session_entries(Path(directory), Path(cache_path))
    kept = pc.kept_sessions(found, tuple(sources))
    stats = kept if since is None else pc.kept_sessions(found, tuple(sources), since)
    recs = records_from_sessions(stats, Path(journal), now)
    if recs is None:
        return None
    return {"records": recs, "ftp_review": ftp_review(kept, ftp_set_w, now)}


def format_text(r: dict[str, Any] | None) -> str:
    if r is None:
        return "Séance non comptée par le profil : pas de record."
    lines = []
    for x in r["records"]:
        before = f"avant {x['prev_w']} W" if x["prev_w"] is not None else "premier effort de cette durée"
        lines.append(f"Record {pc.duration_label(x['s'])} : {x['w']} W ({x['e']}), {before}")
    if not lines:
        lines.append("Aucun record de puissance sur 6 mois.")
    fr = r["ftp_review"]
    if fr:
        lines.append(f"FTP à revoir : estimée {fr['estimate_w']} W ({fr['confidence']}), réglée {fr['ftp_set_w']} W.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openride_core.tools.power_records",
                                 description="Records de puissance d'une séance et signal « FTP à revoir ».")
    ap.add_argument("journal", type=Path, help="journal .jsonl de la séance")
    ap.add_argument("--dir", type=Path, dest="directory", help="dossier des séances (défaut : profil en cours)")
    ap.add_argument("--ftp", type=float, default=None, help="FTP réglée (défaut : celle de la configuration)")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    a = ap.parse_args(argv)
    ctx = profiles.current()
    ftp = a.ftp
    if ftp is None:
        from .. import config
        ftp = float(config.load().rider.ftp_w)
    try:
        r = session_report(a.journal, ftp, a.directory or ctx.activities_dir, ctx.mmp_cache, ctx.counted_sources,
                           since=getattr(ctx, "stats_since", None))
    except Exception as exc:
        print(f"Records impossibles : {exc}", file=sys.stderr)
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else format_text(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
