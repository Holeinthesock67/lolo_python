"""Collection de cartes recalculée depuis le journal (série BC, lot BC1) : `openride-core collection`.

    openride-core collection [--dir DOSSIER] [--json]

Lit les journaux du profil en cours (`~/OpenRide/Profils/<id>/Activities/.journal/`, ou `--dir`)
avec les règles de la progression (sources comptées par le profil, séances trop courtes
refusées), puis le catalogue `data/collection.toml`. Affiche les cartes gagnées (date, rareté,
édition des cartes de saison), puis l'avancement des cartes restantes. Rien n'est écrit : la
liste des cartes déjà montrées (`collection_vue.json`) n'est lue que pour dire lesquelles
seraient annoncées comme nouvelles.

Clés de la sortie `--json` (stables) :
    directory, profile, profile_type, sessions, ignored_future, catalogue (nombre de cartes),
    earned (liste de {id, key, edition, title, text, family, rarity, visual, journal, date}),
    remaining (liste de {id, title, family, rarity, value, target} ; cartes de saison absentes),
    new (clés des cartes pas encore montrées), announce ({key, others, first_time}).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .. import profiles
from ..collection import (CollectionError, announcement, card_line, evaluate, load_catalogue,
                          load_seen, new_cards, seen_path)
from ..garage import workout_duration_finder
from ..config import WORKOUTS_DIR
from ..progression import ProgressionError, load_table, recompute

RARITY_FR = {"commune": "commune", "rare": "rare", "epique": "épique", "legendaire": "légendaire"}


def _fr(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ") if x >= 1000 else f"{x:g}".replace(".", ",")


def snapshot(directory: Path | None = None, ctx: "profiles.ProfileContext | None" = None,
             now: float | None = None) -> dict[str, Any]:
    ctx = ctx or profiles.current()
    directory = directory or ctx.journal_dir
    table = load_table(ctx.table_path)
    cards = load_catalogue(table=table)
    progress = recompute(directory, table, workout_duration_finder(WORKOUTS_DIR),
                         counted=ctx.counted_sources, owns=ctx.owns)
    col = evaluate(progress, cards, table, now=now)
    seen = load_seen(seen_path(ctx.root))
    ann = announcement(col, seen)
    by_id = {c.id: c for c in cards}
    return {
        "directory": str(directory), "profile": ctx.id, "profile_type": ctx.type,
        "sessions": col.sessions, "ignored_future": col.ignored_future, "catalogue": len(cards),
        "earned": [card_line(e) for e in col.earned],
        "remaining": [{"id": cid, "title": by_id[cid].title, "family": by_id[cid].family,
                       "rarity": by_id[cid].rarity, "value": v, "target": t}
                      for cid, (v, t) in col.progress.items()],
        "new": [e.key for e in new_cards(col, seen)],
        "announce": {"key": ann.card.key if ann.card else None, "others": ann.others,
                     "first_time": ann.first_time},
    }


def run(directory: Path | None, as_json: bool) -> int:
    try:
        out = snapshot(directory)
    except (CollectionError, ProgressionError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    if out["profile"] is not None:
        print(f"Profil : {out['profile']}" + (" (PROFIL D'ESSAI)" if out["profile_type"] == "essai" else ""))
    distinct = len({e["id"] for e in out["earned"]})
    print(f"Collection : {distinct} cartes sur {out['catalogue']} ({out['sessions']} séances comptées)")
    if out["ignored_future"]:
        print(f"{out['ignored_future']} séance(s) datée(s) dans le futur ignorée(s) (horloge ?)")
    new = set(out["new"])
    for e in out["earned"]:
        edition = f" {e['edition']}" if e["edition"] is not None else ""
        mark = "  (nouvelle)" if e["key"] in new else ""
        print(f"  {e['date'] or '?'}  {e['title']}{edition}  [{RARITY_FR[e['rarity']]}]{mark}")
    if out["remaining"]:
        print("À gagner :")
        for r in out["remaining"]:
            print(f"  {r['title']} : {_fr(r['value'])} / {_fr(r['target'])}")
    return 0
