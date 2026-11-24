"""« Se connaître » : profil de cycliste, point fort et point faible, forme du moment, record vieillissant et
trous de la courbe (série PP, lot PP5).

    python -m openride_core.tools.power_profile [--dir DOSSIER] [--json]

Tout se lit dans la courbe du lot PP1 (meilleurs efforts des 6 derniers mois et des 6 dernières semaines), sans
aucune comparaison avec d'autres personnes (plan PP §8.5) : le profil compare le cycliste à lui-même.

- **Profil en un mot** : les rapports 5 s / 20 min, 1 min / 20 min et 5 min / 20 min sont comparés à ceux d'un
  cycliste sans dominante (`REFERENCE`) ; la durée qui ressort le plus donne le mot (5 s : sprinteur, 1 min :
  puncheur, 5 min : grimpeur, 20 min : rouleur) ; « complet » quand aucune ne ressort de plus de `BALANCED` ;
  sans effort à fond sur une des quatre durées, pas de mot et la liste des durées qui manquent.
- **Point fort, point faible** : la durée qui ressort le plus et celle qui ressort le moins.
- **Forme du moment** : médiane, sur les durées tenues dans les deux fenêtres, du rapport 6 semaines / 6 mois,
  en pour cent.
- **Record vieillissant** : le record des 6 mois le plus ancien, s'il a plus de `AGING_DAYS` jours : il sortira
  de la courbe dans `183 - âge` jours.
- **Trous** : plages de durées sans effort **libre** depuis 6 semaines (une séance ERG n'est pas un effort à
  fond), regroupées (« de 8 à 12 min »).

Clés (objet `profile` du message `power_curve`, révision 1.35) : kind, strong, weak, missing, form_pct, aging
(null ou {s, age_d, left_d}), gaps ([[de, à]] en secondes).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from .. import profiles
from . import power_curve as pc

# Rapports à la puissance de 20 min d'un cycliste sans dominante (ordre de grandeur des profils de puissance
# publiés pour des amateurs entraînés) ; seul l'écart relatif entre durées compte.
REFERENCE = {5: 3.4, 60: 1.7, 300: 1.18}
KEY_DURATIONS = (5, 60, 300, 1200)
KINDS = {5: "sprinteur", 60: "puncheur", 300: "grimpeur", 1200: "rouleur"}
KIND_BALANCED = "complet"
BALANCED = 0.06          # écart maximal entre indices pour « complet »
AGING_DAYS = 120
MAX_GAPS = 3


def _watts(points: list[dict], free_only: bool = False) -> dict[int, float]:
    out = {}
    for p in points:
        if free_only:
            f = p.get("free")
            if f and f.get("watts") is not None:
                out[p["seconds"]] = float(f["watts"])
        elif p.get("watts") is not None:
            out[p["seconds"]] = float(p["watts"])
    return out


def kind_of(best: dict[int, float]) -> dict[str, Any]:
    """Profil en un mot depuis les meilleurs efforts {secondes: watts}."""
    missing = [d for d in KEY_DURATIONS if not best.get(d)]
    if missing:
        return {"kind": None, "strong": None, "weak": None, "missing": missing}
    p20 = best[1200]
    idx = {d: best[d] / p20 / REFERENCE[d] for d in REFERENCE}
    idx[1200] = 1.0 / statistics.geometric_mean(list(idx.values()))
    strong = max(idx, key=lambda d: (idx[d], d))
    weak = min(idx, key=lambda d: (idx[d], -d))
    if idx[strong] - idx[weak] < BALANCED:
        return {"kind": KIND_BALANCED, "strong": None, "weak": None, "missing": []}
    return {"kind": KINDS[strong], "strong": strong, "weak": weak, "missing": []}


def profile_from_windows(m6: dict, w6: dict, now: float) -> dict[str, Any]:
    """Profil depuis les deux fenêtres de `power_curve.window_curve`."""
    best = _watts(m6["points"])
    out = kind_of(best)
    recent = _watts(w6["points"])
    ratios = [recent[d] / best[d] for d in best if d in recent and best[d] > 0]
    out["form_pct"] = round(statistics.median(ratios) * 100) if ratios else None
    aging = None
    for p in m6["points"]:
        if p.get("ts") is None:
            continue
        age = int((now - p["ts"]) // 86400)
        if age > AGING_DAYS and (aging is None or age > aging["age_d"]):
            aging = {"s": p["seconds"], "age_d": age, "left_d": max(0, pc.WINDOWS["months6"] - age)}
    out["aging"] = aging
    free = _watts(w6["points"], free_only=True)
    gaps: list[list[int]] = []
    if best:   # profil vide : l'écran dit déjà « roule une première séance »
        for d in pc.DURATIONS_S:
            if d in free:
                continue
            if gaps and gaps[-1][1] == pc.DURATIONS_S[pc.DURATIONS_S.index(d) - 1]:
                gaps[-1][1] = d
            else:
                gaps.append([d, d])
    out["gaps"] = gaps[:MAX_GAPS]
    return out


def compute(directory: Path | None = None, sources=None, cache_path: Path | None = None,
            now: float | None = None, since: float | None = None) -> dict[str, Any]:
    ctx = profiles.current()
    since = getattr(ctx, "stats_since", None) if since is None else since   # remise à zéro (lot RZ1)
    now = time.time() if now is None else now
    act = Path(directory) if directory is not None else ctx.activities_dir
    kept = pc.kept_sessions(pc.session_entries(act, Path(cache_path) if cache_path else ctx.mmp_cache),
                            tuple(sources) if sources is not None else tuple(ctx.counted_sources), since)
    m6 = pc.window_curve(kept, pc.WINDOWS["months6"], now)
    w6 = pc.window_curve(kept, pc.WINDOWS["weeks6"], now)
    return {"profile_id": ctx.id, **profile_from_windows(m6, w6, now)}


def format_text(r: dict[str, Any]) -> str:
    lab = pc.duration_label
    if r["kind"] is None:
        lines = ["Profil : pas encore de mot (il manque un effort à fond de "
                 + ", ".join(lab(d) for d in r["missing"]) + ")"]
    else:
        lines = [f"Profil : {r['kind']}"]
        if r["strong"]:
            lines.append(f"Point fort : {lab(r['strong'])} ; à travailler : {lab(r['weak'])}")
    if r["form_pct"] is not None:
        lines.append(f"Forme du moment : {r['form_pct']} % de ton niveau des 6 mois")
    if r["aging"]:
        a = r["aging"]
        lines.append(f"Record vieillissant : {lab(a['s'])}, il sort de la courbe dans {a['left_d']} jours")
    for a, b in r["gaps"]:
        span = lab(a) if a == b else f"de {lab(a)} à {lab(b)}"
        lines.append(f"Trou : aucun effort libre {span} depuis 6 semaines")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openride_core.tools.power_profile",
                                 description="Profil de cycliste tiré de la courbe de puissance du profil en cours.")
    ap.add_argument("--dir", type=Path, dest="directory", help="dossier des séances (défaut : profil en cours)")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    a = ap.parse_args(argv)
    try:
        r = compute(a.directory)
    except Exception as exc:
        print(f"Profil impossible : {exc}", file=sys.stderr)
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else format_text(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
