"""Cote Elo du cycliste et des bots (lot BOT-elo, demande du propriétaire du 16 novembre 2026, lancé le 20/11).

Module pur hors lecture et écriture de `<profil>/elo.json`. Étude : `ETUDE_ELO_BOTS_2026-11-20.md` (dossier du
projet, `plans/`) ; cahier : `docs/lots/LOT_BOT_ELO_cote_des_bots.md`.

- **Une cote pour le cycliste** (départ `START`) et **un écart propre par bot** : la cote d'un bot est la cote du
  cycliste plus son écart. Un bot garde son identité d'une course à l'autre par sa place dans le plateau composé
  par le core (`bot_key` : profil et rang, « Grimpeur 2 » → `climber#2`).
- **Courses qui comptent** : celles qui finissent par un classement (Grand Prix, Dernier survivant, épreuves de
  piste en groupe : `TRACK_EVENTS`). Les bots à puissance fixe et le fantôme ne sont jamais dans un plateau composé.
- **Mise à jour** (`update`) : Elo à plusieurs, chaque coureur comparé à chacun des autres (1 devant, 0 derrière,
  ½ à égalité), somme divisée par le nombre d'adversaires ; K du cycliste `K_RIDER_NEW` sur ses
  `PROVISIONAL_RACES` premières courses puis `K_RIDER`, K des bots `K_BOT`. Les écarts des bots restent centrés
  sur 0 et bornés à ± `OFFSET_MAX` : la difficulté d'ensemble ne suit que la cote du cycliste.
- **Ce que la cote règle** (`level_factor`) : niveau d'un bot = « Niveau des bots » × (1 + (cote du bot −
  `START`) / `POINTS_PER_UNIT`), soit +2,5 % de puissance par 100 points ; la cote du cycliste est bornée
  (`RATING_BOUNDS`). Si le cycliste gagne, sa cote monte et le peloton avec ; s'il perd, il baisse.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

FILE_NAME = "elo.json"
VERSION = 1
START = 1500.0
RATING_BOUNDS = (1000.0, 2100.0)    # cote du cycliste : facteur de 0,875 à 1,15
OFFSET_MAX = 100.0                  # écart propre d'un bot, ± points (± 2,5 % de puissance)
POINTS_PER_UNIT = 4000.0            # +100 points = +2,5 % de puissance
ELO_SCALE = 400.0                   # Elo classique : 400 points d'écart = 10 contre 1
K_RIDER_NEW = 40.0
K_RIDER = 24.0
PROVISIONAL_RACES = 10
K_BOT = 8.0
HISTORY_MAX = 20
ME = "me"
# Épreuves de piste qui comptent : courses en groupe à classement individuel (les poursuites et contre-la-montre
# se courent seul ou par équipes, l'américaine et les épreuves par équipes classent des équipes).
TRACK_EVENTS = ("scratch", "points", "tempo", "elimination", "keirin", "omnium")
MODES = ("grandprix", "survivor", "track")


def bot_key(profile: str, rank: int) -> str:
    """Identité d'un bot d'un plateau composé : `climber#1`, `climber#2`…"""
    return f"{profile}#{int(rank)}"


def plan_keys(profiles: Sequence[str]) -> list[str]:
    """Identités des bots d'un plateau, dans l'ordre (même rang que `bots.profile_bot_names`)."""
    seen: dict[str, int] = {}
    out = []
    for p in profiles:
        seen[p] = seen.get(p, 0) + 1
        out.append(bot_key(p, seen[p]))
    return out


def expected(r_a: float, r_b: float) -> float:
    """Score attendu de A contre B (Elo)."""
    return 1.0 / (1.0 + 10.0 ** ((r_b - r_a) / ELO_SCALE))


def level_factor(bot_rating: float) -> float:
    """Facteur du niveau d'un bot de cote `bot_rating` (1 à `START`)."""
    return max(1.0 + (bot_rating - START) / POINTS_PER_UNIT, 0.1)


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


@dataclass
class EloBook:
    """Cotes du profil : cycliste, nombre de ses courses comptées, écarts propres des bots, dernières courses."""

    rating: float = START
    races: int = 0
    offsets: dict[str, float] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)

    def bot_rating(self, key: str) -> float:
        return self.rating + self.offsets.get(key, 0.0)

    def factor(self, key: str) -> float:
        return level_factor(self.bot_rating(key))

    def k_rider(self) -> float:
        return K_RIDER_NEW if self.races < PROVISIONAL_RACES else K_RIDER

    def update(self, order: Sequence[Sequence[str]], mode: str, ts: float | None = None) -> dict[str, Any]:
        """Classement de la course (`order` : groupes de coureurs à égalité, du premier au dernier ; le cycliste
        est `ME`, les bots par `bot_key`) ; met les cotes à jour et rend la ligne de résultat
        (`{mode, place, of, before, after, delta}`). Le cycliste absent du classement : ValueError."""
        groups = [list(g) for g in order if g]
        racers = [r for g in groups for r in g]
        if ME not in racers or len(racers) < 2 or len(set(racers)) != len(racers):
            raise ValueError("classement sans le cycliste, sans adversaire ou avec un coureur en double")
        rank = {r: i for i, g in enumerate(groups) for r in g}
        before = {r: (self.rating if r == ME else self.bot_rating(r)) for r in racers}
        n = len(racers) - 1
        delta: dict[str, float] = {}
        for a in racers:
            total = 0.0
            for b in racers:
                if a == b:
                    continue
                score = 1.0 if rank[a] < rank[b] else (0.5 if rank[a] == rank[b] else 0.0)
                total += score - expected(before[a], before[b])
            delta[a] = total / n
        old = self.rating
        self.rating = _clamp(old + self.k_rider() * delta[ME], *RATING_BOUNDS)
        for b in racers:
            if b != ME:
                self.offsets[b] = self.offsets.get(b, 0.0) + K_BOT * delta[b]
        # Écarts recentrés sur 0 (les bots de la course seulement) puis bornés : le peloton suit le cycliste.
        mean = sum(self.offsets[b] for b in racers if b != ME) / n
        for b in racers:
            if b != ME:
                self.offsets[b] = round(_clamp(self.offsets[b] - mean, -OFFSET_MAX, OFFSET_MAX), 1)
        self.races += 1
        place = 1 + sum(len(g) for g in groups[:rank[ME]])
        line = {"mode": mode, "place": place, "of": len(racers), "before": round(old), "after": round(self.rating),
                "delta": round(self.rating) - round(old)}
        if ts is not None:
            line["ts"] = round(ts, 3)
        self.history = (self.history + [line])[-HISTORY_MAX:]
        return line

    def to_dict(self) -> dict[str, Any]:
        return {"version": VERSION, "rating": round(self.rating, 2), "races": self.races,
                "offsets": dict(sorted(self.offsets.items())), "history": self.history}

    @classmethod
    def from_dict(cls, data: Any) -> "EloBook":
        """Cotes lues ; une valeur refusée (fichier modifié à la main) repart de sa valeur par défaut."""
        book = cls()
        if not isinstance(data, dict):
            return book
        r = data.get("rating")
        if _num(r):
            book.rating = _clamp(float(r), *RATING_BOUNDS)
        n = data.get("races")
        if isinstance(n, int) and not isinstance(n, bool) and n >= 0:
            book.races = n
        offs = data.get("offsets")
        if isinstance(offs, dict):
            book.offsets = {str(k): _clamp(float(v), -OFFSET_MAX, OFFSET_MAX) for k, v in offs.items() if _num(v)}
        hist = data.get("history")
        if isinstance(hist, list):
            book.history = [h for h in hist if isinstance(h, dict)][-HISTORY_MAX:]
        return book


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def path_for(root: Path) -> Path:
    return root / FILE_NAME


def load(path: Path) -> EloBook:
    """Cotes du fichier ; cotes de départ si le fichier manque ou est illisible."""
    try:
        return EloBook.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, ValueError):
        return EloBook()


def save(path: Path, book: EloBook) -> None:
    """Écriture sûre (fichier temporaire puis remplacement) ; lève `OSError`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(book.to_dict(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def order_from_places(places: Iterable[tuple[str, int | None]], unplaced_first: bool = False) -> list[list[str]]:
    """Classement en groupes depuis des places ; les coureurs sans place (None) sont à égalité derrière tous les
    classés, ou devant avec `unplaced_first` (Dernier survivant : encore en course quand le cycliste est éliminé)."""
    by: dict[int, list[str]] = {}
    unplaced: list[str] = []
    for rid, place in places:
        if place is None:
            unplaced.append(rid)
        else:
            by.setdefault(int(place), []).append(rid)
    out = [sorted(by[p]) for p in sorted(by)]
    if unplaced:
        if unplaced_first:
            out.insert(0, sorted(unplaced))
        else:
            out.append(sorted(unplaced))
    return out
