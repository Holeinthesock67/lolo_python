"""Collection de cartes à gagner (série BC, 5.0, lot BC1) : catalogue, cartes gagnées, annonce.

Module pur, comme la progression de la série V (`progression.py`) dont il reprend les séances
comptées : il ne lit que le catalogue `data/collection.toml` et reçoit `Progress` (séances du
profil en cours, sources comptées par le profil, séances trop courtes refusées, journaux repris
après une panne comptés une fois). Les cartes ne sont pas stockées : elles se recalculent à
chaque appel. Seule la liste des cartes déjà montrées au joueur est écrite, dans le dossier du
profil (`collection_vue.json`), pour n'annoncer qu'une carte nouvelle à la fois.

Règles (plan `docs/5.0/PLAN_SERIE_BC.md` §3 à §6) :
- une séance du profil d'essai ne compte que dans le profil d'essai ; une séance simulée ou
  rejouée ne compte jamais dans un profil de joueur (sources de `profil.toml`, série MJ) ;
- une séance datée de plus d'un jour après l'heure de l'appel (horloge déréglée) ne compte pas ;
- les heures et les dates sont celles du fuseau local (`tz`, pour les tests) au départ de la séance ;
- une carte de saison se gagne une fois par année (édition) ; une carte des défis de la série V
  se gagne à la séance où le défi est réussi, avec le même seuil (une seule définition).
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any, Iterable

from .progression import STATS, FACT_EVENT_KINDS, Progress, SessionFacts, Table, add_stats

DEFAULT_CATALOGUE_PATH = Path(__file__).resolve().parent / "data" / "collection.toml"
SEEN_NAME = "collection_vue.json"
SEEN_VERSION = 1

FAMILIES = ("distance", "seance", "denivele", "regularite", "heure", "entrainement", "modes",
            "saison", "anniversaire")
RARITIES = ("commune", "rare", "epique", "legendaire")   # ordre croissant de rareté
TITLE_MAX = 24
TEXT_MAX = 70
FUTURE_TOLERANCE_S = 86400.0

_ID_RE = re.compile(r"^[a-z0-9_]{1,32}$")
_MMDD_RE = re.compile(r"^(\d{2})-(\d{2})$")

# Clés de chaque règle : nom -> (type, obligatoire). `count` vaut 1 par défaut.
_RULES: dict[str, dict[str, tuple[type, bool]]] = {
    "cumul": {"stat": (str, True), "threshold": (float, True)},
    "defi": {"challenge": (str, True)},
    "seance": {"count": (int, False), "min_km": (float, False), "min_climb_m": (float, False),
               "min_minutes": (float, False)},
    "heure": {"from_h": (int, True), "to_h": (int, True), "count": (int, False),
              "min_minutes": (float, False)},
    "semaines": {"count": (int, True), "per_week": (int, True)},
    "jours": {"count": (int, True)},
    "mode": {"event": (str, True), "count": (int, False), "win": (bool, False)},
    "saison": {"from": (str, False), "to": (str, False), "easter_from": (int, False),
               "easter_to": (int, False), "count": (int, False), "min_minutes": (float, False)},
    "anniversaire": {"years": (int, True)},
}


class CollectionError(Exception):
    """Catalogue invalide (le message nomme la carte et la clé fautive)."""


# --- catalogue ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Card:
    id: str
    title: str
    text: str
    family: str
    rarity: str
    visual: str
    rule: dict[str, Any] = field(hash=False, compare=False)

    @property
    def kind(self) -> str:
        return self.rule["kind"]

    @property
    def count(self) -> int:
        return int(self.rule.get("count", 1))


def _check(value: Any, expected: type, where: str) -> Any:
    if expected is float and isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if expected is int and isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, expected) and not (expected is int and isinstance(value, bool)):
        return value
    raise CollectionError(f"{where} : {expected.__name__} attendu, reçu {value!r}")


def _mmdd(text: str, where: str) -> tuple[int, int]:
    m = _MMDD_RE.match(text)
    if not m:
        raise CollectionError(f"{where} : date « MM-JJ » attendue, reçu {text!r}")
    month, day = int(m.group(1)), int(m.group(2))
    try:
        date(2024, month, day)   # année bissextile : le 29 février est permis
    except ValueError:
        raise CollectionError(f"{where} : date impossible {text!r}") from None
    return month, day


def _check_rule(raw: Any, where: str, table: Table | None) -> dict[str, Any]:
    if not isinstance(raw, dict) or raw.get("kind") not in _RULES:
        raise CollectionError(f"{where}.rule : `kind` parmi {', '.join(_RULES)} attendu")
    kind = raw["kind"]
    spec = _RULES[kind]
    rule: dict[str, Any] = {"kind": kind}
    for key, value in raw.items():
        if key == "kind":
            continue
        if key not in spec:
            raise CollectionError(f"{where}.rule.{key} : clé inconnue pour la règle « {kind} »")
        rule[key] = _check(value, spec[key][0], f"{where}.rule.{key}")
    for key, (_t, required) in spec.items():
        if required and key not in rule:
            raise CollectionError(f"{where}.rule.{key} : clé obligatoire pour la règle « {kind} »")
    if rule.get("count", 1) < 1:
        raise CollectionError(f"{where}.rule.count : 1 ou plus")
    if kind == "cumul" and rule["stat"] not in STATS:
        raise CollectionError(f"{where}.rule.stat : stat inconnue « {rule['stat']} »")
    if kind == "defi" and table is not None \
            and rule["challenge"] not in {c.id for c in table.challenges}:
        raise CollectionError(f"{where}.rule.challenge : défi inconnu « {rule['challenge']} »")
    if kind == "heure" and not (0 <= rule["from_h"] <= 23 and 0 <= rule["to_h"] <= 24
                                and rule["from_h"] != rule["to_h"]):
        raise CollectionError(f"{where}.rule : heures de 0 à 24, `from_h` différent de `to_h`")
    if kind == "mode":
        if rule["event"] not in FACT_EVENT_KINDS:
            raise CollectionError(f"{where}.rule.event : ligne de jeu inconnue « {rule['event']} »")
        if rule.get("win") and rule["event"] != "survivor_summary":
            raise CollectionError(f"{where}.rule.win : seulement pour `survivor_summary`")
    if kind == "saison":
        dates = "from" in rule or "to" in rule
        easter = "easter_from" in rule or "easter_to" in rule
        if dates == easter:
            raise CollectionError(f"{where}.rule : soit `from` et `to`, soit `easter_from` et `easter_to`")
        if dates:
            if "from" not in rule or "to" not in rule:
                raise CollectionError(f"{where}.rule : `from` et `to` vont ensemble")
            _mmdd(rule["from"], f"{where}.rule.from")
            _mmdd(rule["to"], f"{where}.rule.to")
        elif "easter_from" not in rule or "easter_to" not in rule \
                or rule["easter_from"] > rule["easter_to"]:
            raise CollectionError(f"{where}.rule : `easter_from` ≤ `easter_to`, tous deux donnés")
    if kind == "anniversaire" and rule["years"] < 1:
        raise CollectionError(f"{where}.rule.years : 1 ou plus")
    return rule


def parse_catalogue(data: dict, source: str = "collection.toml",
                    table: Table | None = None) -> tuple[Card, ...]:
    """Cartes du catalogue, dans l'ordre du fichier ; `table` vérifie les défis cités."""
    raw_cards = data.get("cards")
    if not isinstance(raw_cards, list) or not raw_cards:
        raise CollectionError(f"{source} : liste [[cards]] absente ou vide")
    cards: list[Card] = []
    seen: set[str] = set()
    for i, raw in enumerate(raw_cards):
        where = f"{source} : cards[{i}]"
        if not isinstance(raw, dict):
            raise CollectionError(f"{where} : table attendue")
        cid = raw.get("id")
        if not isinstance(cid, str) or not _ID_RE.match(cid):
            raise CollectionError(f"{where}.id : minuscules, chiffres et _ (1 à 32)")
        where = f"{source} : carte « {cid} »"
        if cid in seen:
            raise CollectionError(f"{where} : identifiant en double")
        seen.add(cid)
        values = {}
        for key, limit in (("title", TITLE_MAX), ("text", TEXT_MAX), ("visual", 32)):
            val = _check(raw.get(key), str, f"{where}.{key}")
            if not val.strip() or len(val) > limit:
                raise CollectionError(f"{where}.{key} : texte de 1 à {limit} caractères")
            values[key] = val
        if raw.get("family") not in FAMILIES:
            raise CollectionError(f"{where}.family : parmi {', '.join(FAMILIES)}")
        if raw.get("rarity") not in RARITIES:
            raise CollectionError(f"{where}.rarity : parmi {', '.join(RARITIES)}")
        unknown = set(raw) - {"id", "title", "text", "family", "rarity", "visual", "rule"}
        if unknown:
            raise CollectionError(f"{where} : clé inconnue {sorted(unknown)[0]}")
        rule = _check_rule(raw.get("rule"), where, table)
        if (rule["kind"] == "saison") != (raw["family"] == "saison"):
            raise CollectionError(f"{where} : la famille « saison » va avec la règle « saison »")
        cards.append(Card(id=cid, family=raw["family"], rarity=raw["rarity"], rule=rule, **values))
    return tuple(cards)


def load_catalogue(path: Path = DEFAULT_CATALOGUE_PATH, table: Table | None = None) -> tuple[Card, ...]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise CollectionError(f"{path} : {exc}") from exc
    return parse_catalogue(data, str(path.name), table)


# --- dates ----------------------------------------------------------------------------------

def easter(year: int) -> date:
    """Dimanche de Pâques du calendrier grégorien (algorithme de Meeus, Jones et Butcher)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def season_edition(rule: dict[str, Any], day: date) -> int | None:
    """Année de l'édition de saison qui contient `day`, ou None hors de la fenêtre."""
    if "easter_from" in rule:
        offset = (day - easter(day.year)).days   # Pâques tombe entre le 22 mars et le 25 avril
        return day.year if rule["easter_from"] <= offset <= rule["easter_to"] else None
    start, end = _mmdd(rule["from"], "from"), _mmdd(rule["to"], "to")
    md = (day.month, day.day)
    if start <= end:
        return day.year if start <= md <= end else None
    if md >= start:          # fenêtre qui passe le 31 décembre : édition de l'année du début
        return day.year
    if md <= end:
        return day.year - 1
    return None


def add_years(day: date, years: int) -> date:
    """Même jour `years` ans plus tard ; le 29 février devient le 1er mars."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return date(day.year + years, 3, 1)


# --- calcul ---------------------------------------------------------------------------------

@dataclass(frozen=True)
class Earned:
    card: Card
    edition: int | None     # année d'une carte de saison, sinon None
    journal: str
    start_ts: float | None

    @property
    def key(self) -> str:
        return self.card.id if self.edition is None else f"{self.card.id}:{self.edition}"


@dataclass
class Collection:
    cards: tuple[Card, ...]
    earned: list[Earned]                              # ordre d'obtention
    progress: dict[str, tuple[float, float]]          # carte pas encore gagnée -> (valeur, cible)
    sessions: int                                     # séances retenues
    ignored_future: int = 0                           # séances datées dans le futur

    def has(self, card_id: str, edition: int | None = None) -> bool:
        return any(e.card.id == card_id and (edition is None or e.edition == edition)
                   for e in self.earned)


def _local(ts: float, tz: tzinfo | None) -> datetime:
    return datetime.fromtimestamp(ts, tz) if tz is not None else datetime.fromtimestamp(ts).astimezone()


def _minutes_ok(card: Card, facts: SessionFacts) -> bool:
    return facts.duration_s >= 60.0 * card.rule.get("min_minutes", 0.0)


def _matches(card: Card, facts: SessionFacts, when: datetime | None) -> int:
    """Nombre d'occurrences de la séance pour les règles comptées séance par séance."""
    rule, kind = card.rule, card.kind
    if kind == "seance":
        ok = (facts.distance_m >= 1000.0 * rule.get("min_km", 0.0)
              and facts.climb_m >= rule.get("min_climb_m", 0.0) and _minutes_ok(card, facts))
        return 1 if ok else 0
    if kind == "heure":
        if when is None or not _minutes_ok(card, facts):
            return 0
        lo, hi, h = rule["from_h"], rule["to_h"], when.hour
        return 1 if ((lo <= h < hi) if lo < hi else (h >= lo or h < hi)) else 0
    if kind == "mode":
        lines = [ev for ev in facts.events if ev.get("kind") == rule["event"]]
        if rule.get("win"):
            lines = [ev for ev in lines if ev.get("place") == 1]
        return len(lines)
    return 0


def evaluate(progress: Progress, cards: Iterable[Card], table: Table,
             tz: tzinfo | None = None, now: float | None = None) -> Collection:
    """Cartes gagnées par les séances comptées de `progress`, dans l'ordre chronologique.

    `table` donne le seuil des défis de la série V ; `tz` le fuseau des heures et des dates
    (défaut : celui de la machine) ; `now` l'heure de l'appel (défaut : maintenant).
    """
    cards = tuple(cards)
    limit = (now if now is not None else datetime.now().timestamp()) + FUTURE_TOLERANCE_S
    challenges = {c.id: c for c in table.challenges}
    kept: list[SessionFacts] = []
    future = 0
    for r in progress.counted:
        if r.facts.start_ts is not None and r.facts.start_ts > limit:
            future += 1
        else:
            kept.append(r.facts)

    stats = dict.fromkeys(STATS, 0.0)
    counters: dict[str, float] = dict.fromkeys((c.id for c in cards), 0.0)
    season_counts: dict[tuple[str, int], int] = {}
    week_counts: dict[tuple[int, int], int] = {}
    days: set[date] = set()
    streaks: dict[str, tuple[Any, int]] = {}      # carte -> (dernière semaine ou dernier jour, série)
    best: dict[str, int] = dict.fromkeys((c.id for c in cards), 0)
    first_day: date | None = None
    earned: list[Earned] = []
    done: set[str] = set()

    def win(card: Card, facts: SessionFacts, edition: int | None = None) -> None:
        e = Earned(card, edition, facts.journal, facts.start_ts)
        if e.key not in done:
            done.add(e.key)
            earned.append(e)

    for facts in kept:
        add_stats(stats, facts)
        when = _local(facts.start_ts, tz) if facts.start_ts is not None else None
        day = when.date() if when is not None else None
        if day is not None:
            first_day = first_day or day
            iso = day.isocalendar()
            week = (iso[0], iso[1])
            week_counts[week] = week_counts.get(week, 0) + 1
            new_day = day not in days
            days.add(day)
        for card in cards:
            rule, kind = card.rule, card.kind
            if kind in ("cumul", "defi"):
                stat, target = ((rule["stat"], rule["threshold"]) if kind == "cumul" else
                                (challenges[rule["challenge"]].stat, challenges[rule["challenge"]].threshold)
                                if rule["challenge"] in challenges else (None, 0.0))
                if stat is not None and stats[stat] >= target:
                    win(card, facts)
            elif kind in ("seance", "heure", "mode"):
                counters[card.id] += _matches(card, facts, when)
                if counters[card.id] >= card.count:
                    win(card, facts)
            elif day is None:
                continue
            elif kind == "saison":
                edition = season_edition(rule, day)
                if edition is not None and _minutes_ok(card, facts):
                    n = season_counts.get((card.id, edition), 0) + 1
                    season_counts[(card.id, edition)] = n
                    if n >= card.count:
                        win(card, facts, edition)
            elif kind == "semaines":
                if week_counts[week] == rule["per_week"]:
                    last, run = streaks.get(card.id, (None, 0))
                    monday = date.fromisocalendar(week[0], week[1], 1)
                    run = run + 1 if last is not None and monday - last == timedelta(days=7) else 1
                    streaks[card.id] = (monday, run)
                    best[card.id] = max(best[card.id], run)
                    if run >= card.count:
                        win(card, facts)
            elif kind == "jours":
                if new_day:
                    last, run = streaks.get(card.id, (None, 0))
                    run = run + 1 if last is not None and day - last == timedelta(days=1) else 1
                    streaks[card.id] = (day, run)
                    best[card.id] = max(best[card.id], run)
                    if run >= card.count:
                        win(card, facts)
            elif kind == "anniversaire":
                if first_day is not None and day >= add_years(first_day, rule["years"]):
                    win(card, facts)

    progress_of: dict[str, tuple[float, float]] = {}
    today = _local(limit - FUTURE_TOLERANCE_S, tz).date()
    for card in cards:
        if card.id in done or card.kind == "saison":
            continue
        rule = card.rule
        if card.kind == "cumul":
            progress_of[card.id] = (round(stats[rule["stat"]], 1), rule["threshold"])
        elif card.kind == "defi" and rule["challenge"] in challenges:
            ch = challenges[rule["challenge"]]
            progress_of[card.id] = (round(stats[ch.stat], 1), ch.threshold)
        elif card.kind in ("seance", "heure", "mode"):
            progress_of[card.id] = (counters[card.id], float(card.count))
        elif card.kind in ("semaines", "jours"):
            progress_of[card.id] = (float(best[card.id]), float(card.count))
        elif card.kind == "anniversaire":
            span = 365.0 * rule["years"]
            elapsed = float((today - first_day).days) if first_day is not None else 0.0
            progress_of[card.id] = (min(elapsed, span), span)
    return Collection(cards=cards, earned=earned, progress=progress_of, sessions=len(kept),
                      ignored_future=future)


# --- cartes déjà montrées et annonce --------------------------------------------------------

def seen_path(profile_root: Path) -> Path:
    """Fichier des cartes déjà montrées, dans le dossier du profil en cours (série MJ)."""
    return profile_root / SEEN_NAME


def load_seen(path: Path) -> set[str] | None:
    """Clés des cartes déjà montrées ; None si le fichier manque (collection jamais ouverte).

    Un fichier abîmé ou d'une autre version vaut « tout est déjà vu » : aucune avalanche
    d'annonces, et la collection reste entière (elle se recalcule).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {"*"}
    if not isinstance(data, dict) or data.get("version") != SEEN_VERSION \
            or not isinstance(data.get("seen"), list):
        return {"*"}
    return {k for k in data["seen"] if isinstance(k, str)}


def save_seen(path: Path, keys: Iterable[str]) -> None:
    """Écrit la liste triée (fichier temporaire puis remplacement)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"version": SEEN_VERSION, "seen": sorted(set(keys) - {"*"})},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


@dataclass(frozen=True)
class Announcement:
    card: Earned | None    # la carte à montrer (la plus rare des nouvelles, puis la plus récente)
    others: int            # autres cartes nouvelles, à voir dans l'écran « Collection »
    first_time: bool       # collection jamais ouverte : cartes des séances d'avant la série BC


def new_cards(collection: Collection, seen: set[str] | None) -> list[Earned]:
    if seen is not None and "*" in seen:
        return []
    seen = seen or set()
    return [e for e in collection.earned if e.key not in seen]


def announcement(collection: Collection, seen: set[str] | None) -> Announcement:
    """Une seule information nouvelle à la fois (plan §7) : une carte, et le nombre des autres."""
    fresh = new_cards(collection, seen)
    if not fresh:
        return Announcement(None, 0, seen is None and not collection.earned)
    order = {e.key: i for i, e in enumerate(collection.earned)}
    top = max(fresh, key=lambda e: (RARITIES.index(e.card.rarity), order[e.key]))
    return Announcement(top, len(fresh) - 1, seen is None)


def card_line(e: Earned, tz: tzinfo | None = None) -> dict[str, Any]:
    """Forme d'une carte gagnée pour l'outil `collection` et le futur message IPC (lot BC2)."""
    c = e.card
    return {"id": c.id, "key": e.key, "edition": e.edition, "title": c.title, "text": c.text,
            "family": c.family, "rarity": c.rarity, "visual": c.visual, "journal": e.journal,
            "date": _local(e.start_ts, tz).strftime("%Y-%m-%d") if e.start_ts is not None else None}
