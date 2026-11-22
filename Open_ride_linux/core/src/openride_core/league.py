"""Ligue d'hiver : saison de 8 manches contre 11 rivaux fixes (série CH, lot CH1, plan `docs/6.0/PLAN_SERIE_CH.md`).

Module pur, hors lecture et écriture de `<profil>/ligue.json` (écriture sûre : fichier temporaire puis
remplacement). Rien ne dépend de l'horloge : chaque fonction reçoit la date du jour (`today`, date locale du PC).

Règles (cahier CH0, §3, validé le 21 novembre 2026) :
- **Calendrier** : 8 manches, une par semaine ISO (lundi au dimanche), modes existants à tour de rôle (`ROUNDS`) ;
  le Cyber-Rogue n'y entre pas. La saison commence le lundi de la semaine où elle est créée.
- **Rivaux** : 11 bots fixes, 3 grimpeurs, 3 rouleurs, 3 sprinteurs et 2 diesels (`FIELD`), avec un nom fictif et
  une équipe (nom écrit et couleur). Leur identité `key` est celle de la cote Elo (`climber#1`… comme
  `bot_elo.bot_key`) : la séance compose le plateau dans l'ordre de `field_profiles`. Une nouvelle saison en garde
  8 et en remplace 3, chacun par un rival du même profil (le plateau garde sa composition).
- **Points** : barème `POINTS` par place sur 12 ; semaine non courue 0 ; total = 6 meilleures manches (`BEST`),
  plus la classique × `CLASSIC_FACTOR`, comptée en plus. Égalité : plus de victoires, puis meilleure place à la
  finale, puis le nom.
- **Une seule tentative** : le premier résultat enregistré d'une manche compte ; une manche abandonnée n'envoie pas
  de résultat et se recourt tant que sa semaine n'est pas finie.
- **Semaine non courue** : les rivaux la courent quand même ; leur classement est simulé quand la semaine est
  passée (`advance`, simulateur `simulate_order` par défaut : tirage d'après la cote et le caractère, que le banc
  du lot CH2 peut remplacer).
- **Classique** : facultative, date choisie dans la saison (samedi ou dimanche) ; elle se court à partir de cette
  date et jusqu'à la fin de la semaine 8 ; non courue, les rivaux la courent (simulée) à la fin de la saison.
- **Pause** : gèle le calendrier par semaines entières ; au-delà de `PAUSE_MAX_WEEKS` semaines gelées en tout
  (pauses additionnées), la saison est close
  au classement du moment, sans trophée.
- **Fin de saison** : trophée d'or, d'argent ou de bronze sur le podium, « Trophée de régularité » pour au moins
  6 manches courues hors podium.
"""

from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from . import rivals as rivals_mod

FILE_NAME = "ligue.json"
VERSION = 1
ME = "me"                       # le cycliste (même identité que `bot_elo.ME`)
WEEKS = 8
BEST = 6
POINTS = (25, 20, 16, 13, 11, 10, 9, 8, 7, 6, 5, 4)
CLASSIC_FACTOR = 1.5
PAUSE_MAX_WEEKS = 4
KEEP_RIVALS = 8
RIDERS = 12
START_RATING = 1500.0           # cote de départ (`bot_elo.START`)
ELO_SCALE = 400.0

# Composition du plateau, dans l'ordre où la séance le compose (identités `profil#rang`).
FIELD = (("climber", 3), ("rouleur", 3), ("sprinter", 3), ("diesel", 2))


@dataclass(frozen=True)
class Round:
    """Une manche du calendrier : mode de course de la séance (`start.mode`), épreuve (vélodrome), parcours voulu
    (`boucle`, `arrivee_cote`, `piste`), libellés écrits et ce qui départage (texte de l'écran de la ligue)."""

    mode: str
    title: str
    short: str
    terrain: str
    decides: str
    event: str | None = None


ROUNDS: tuple[Round, ...] = (
    Round("race", "Course en tours, circuit vallonné", "Course en tours", "boucle", "rouleurs"),
    Round("survivor", "Dernier survivant", "Dernier survivant", "boucle", "sprint de survie"),
    Round("grandprix", "Grand Prix des objets", "Grand Prix", "grandprix", "tête et objets"),
    Round("track", "Vélodrome : course à l'élimination", "Élimination", "piste", "placement, relances",
          event="elimination"),
    Round("race", "Course en ligne, arrivée en côte", "Arrivée en côte", "arrivee_cote", "grimpeurs"),
    Round("survivor", "Dernier survivant", "Dernier survivant", "boucle", "sprint de survie"),
    Round("grandprix", "Grand Prix des objets", "Grand Prix", "grandprix", "tête et objets"),
    Round("race", "Finale : course en tours", "Finale", "boucle", "tous"),
)
CLASSIC = Round("race", "Classique de la ligue", "Classique", "classique", "endurance")

# Avantage de cote (points Elo) d'un caractère selon le terrain de la manche, pour le tirage simulé.
AFFINITY: dict[str, dict[str, float]] = {
    "boucle": {"rouleur": 40.0, "diesel": 20.0},
    "grandprix": {},
    "piste": {"sprinter": 40.0, "rouleur": 10.0},
    "arrivee_cote": {"climber": 60.0, "diesel": 10.0, "sprinter": -40.0},
    "classique": {"diesel": 40.0, "rouleur": 20.0, "climber": 10.0},
}
PROFILE_LABELS = {"climber": "Grimpeur", "rouleur": "Rouleur", "sprinter": "Sprinteur", "diesel": "Diesel"}

TROPHIES = {1: ("or", "Trophée d'or"), 2: ("argent", "Trophée d'argent"), 3: ("bronze", "Trophée de bronze")}
REGULARITY = ("regularite", "Trophée de régularité")
ROUND_SOURCES = ("joueur", "simule")


class LeagueError(ValueError):
    """Action refusée (manche déjà courue, saison en pause ou close, classement incomplet…)."""


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def ordinal(place: int) -> str:
    return "1er" if place == 1 else f"{place}e"


def points_for(place: int | None) -> int:
    """Points d'une place (1 à 12) ; non classé ou non couru : 0."""
    if place is None or place < 1 or place > len(POINTS):
        return 0
    return POINTS[place - 1]


def field_keys() -> list[str]:
    """Identités des 11 rivaux, dans l'ordre du plateau (`climber#1`… `diesel#2`)."""
    return [f"{p}#{i}" for p, n in FIELD for i in range(1, n + 1)]


@dataclass
class Rival:
    key: str
    profile: str
    name: str
    team: str
    color: str

    @property
    def short(self) -> str:
        """Nom court de la course (HUD), comme `rivals.Rival.short` : « L. Lacime »."""
        first, _, last = self.name.partition(" ")
        return f"{first[0]}. {last}" if last else first

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "profile": self.profile, "name": self.name, "team": self.team, "color": self.color}


@dataclass
class RoundResult:
    """Classement d'une manche : places de chaque coureur (1 = premier, égalités permises), qui l'a produit
    (`joueur` : la course du cycliste ; `simule` : semaine non courue), intensité facile (R1), date."""

    places: dict[str, int]
    source: str
    easy: bool = False
    day: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"places": dict(self.places), "source": self.source, "easy": self.easy, "day": self.day}


@dataclass
class Season:
    number: int
    seed: int
    start: date
    rivals: list[Rival]
    results: dict[int, RoundResult] = field(default_factory=dict)
    classic_day: date | None = None
    classic: RoundResult | None = None
    pauses: list[list[date | None]] = field(default_factory=list)   # [début, fin] ; fin None : en pause
    closed: str | None = None                                       # None, « fin » ou « pause »

    # --- calendrier -------------------------------------------------------------------------------

    def paused_weeks(self, today: date) -> int:
        """Semaines gelées par les pauses (lundis franchis pendant chaque pause), jusqu'à aujourd'hui."""
        total = 0
        for start, end in self.pauses:
            if start is None:
                continue
            stop = end if end is not None else today
            total += max((monday(stop) - monday(start)).days // 7, 0)
        return total

    @property
    def paused(self) -> bool:
        return bool(self.pauses) and self.pauses[-1][1] is None

    def week_index(self, today: date) -> int:
        """Rang de la semaine en cours (0 = manche 1) ; `WEEKS` ou plus : saison finie."""
        weeks = (monday(today) - self.start).days // 7 - self.paused_weeks(today)
        return max(weeks, 0)

    def round_day(self, index: int, today: date) -> date:
        """Lundi de la semaine de la manche `index`, pauses passées comprises."""
        return self.start + timedelta(weeks=index + self.paused_weeks(today))

    def end_day(self, today: date) -> date:
        """Dernier jour de la saison (dimanche de la semaine 8), pauses passées comprises."""
        return self.round_day(WEEKS - 1, today) + timedelta(days=6)

    # --- actions ----------------------------------------------------------------------------------

    def current_round(self, today: date) -> int | None:
        """Manche à courir cette semaine (0 à 7), None si elle est faite, la saison close ou en pause."""
        if self.closed or self.paused:
            return None
        i = self.week_index(today)
        if i >= WEEKS or i in self.results:
            return None
        return i

    def record(self, index: int, places: Mapping[str, int], today: date, easy: bool = False) -> RoundResult:
        """Résultat de la course du cycliste pour la manche `index` (premier résultat seulement)."""
        if self.closed:
            raise LeagueError("saison close")
        if self.paused:
            raise LeagueError("saison en pause")
        if index != self.week_index(today):
            raise LeagueError(f"la manche {index + 1} n'est pas celle de la semaine")
        if index in self.results:
            raise LeagueError(f"manche {index + 1} déjà courue : le premier résultat compte")
        res = RoundResult(self._check_places(places), "joueur", bool(easy), today.isoformat())
        self.results[index] = res
        return res

    def classic_open(self, today: date) -> bool:
        """La classique se court-elle aujourd'hui ? (date choisie passée, saison pas finie, pas déjà courue)."""
        return (self.classic_day is not None and self.classic is None and not self.closed and not self.paused
                and self.classic_day <= today <= self.end_day(today))

    def classic_days(self, today: date) -> list[date]:
        """Jours proposés pour la classique : samedis et dimanches de la saison, à partir d'aujourd'hui."""
        out = []
        d = self.start + timedelta(weeks=self.paused_weeks(today))
        end = self.end_day(today)
        while d <= end:
            if d.weekday() >= 5 and d >= today:
                out.append(d)
            d += timedelta(days=1)
        return out

    def choose_classic(self, day: date, today: date) -> None:
        if self.closed:
            raise LeagueError("saison close")
        if self.classic is not None:
            raise LeagueError("classique déjà courue")
        if day not in self.classic_days(today):
            raise LeagueError("jour refusé : un samedi ou un dimanche de la saison, pas dans le passé")
        self.classic_day = day

    def record_classic(self, places: Mapping[str, int], today: date, easy: bool = False) -> RoundResult:
        if not self.classic_open(today):
            raise LeagueError("classique fermée aujourd'hui")
        self.classic = RoundResult(self._check_places(places), "joueur", bool(easy), today.isoformat())
        return self.classic

    def pause(self, today: date) -> None:
        if self.closed:
            raise LeagueError("saison close")
        if self.paused:
            raise LeagueError("saison déjà en pause")
        self.pauses.append([today, None])

    def resume(self, today: date) -> None:
        if not self.paused:
            raise LeagueError("saison pas en pause")
        start = self.pauses[-1][0]
        if self.paused_weeks(today) > PAUSE_MAX_WEEKS:
            self.closed = "pause"
        self.pauses[-1][1] = max(today, start) if start is not None else today

    def advance(self, today: date, simulate: Callable[["Season", Round, int], dict[str, int]] | None = None,
                ratings: Mapping[str, float] | None = None) -> list[int]:
        """Met la saison à jour : manches passées non courues simulées pour les rivaux, pause trop longue, fin de
        saison (classique simulée si besoin). Rend les rangs des manches simulées (`WEEKS` pour la classique)."""
        if self.closed:
            return []
        sim = simulate or (lambda s, rnd, i: simulate_order(s, rnd, i, ratings))
        done: list[int] = []
        if self.paused:
            if self.paused_weeks(today) > PAUSE_MAX_WEEKS:
                self.closed = "pause"
            return done
        last = min(self.week_index(today), WEEKS)
        for i in range(last):
            if i not in self.results:
                self.results[i] = RoundResult(self._check_places(sim(self, ROUNDS[i], i), with_me=False), "simule",
                                              day=today.isoformat())
                done.append(i)
        if last >= WEEKS:
            if self.classic is None:
                self.classic = RoundResult(self._check_places(sim(self, CLASSIC, WEEKS), with_me=False), "simule",
                                           day=today.isoformat())
                done.append(WEEKS)
            self.closed = "fin"
        return done

    # --- classement -------------------------------------------------------------------------------

    def racers(self) -> list[str]:
        return [ME] + [r.key for r in self.rivals]

    def rival(self, key: str) -> Rival | None:
        return next((r for r in self.rivals if r.key == key), None)

    def name_of(self, rid: str) -> str:
        if rid == ME:
            return "Toi"
        r = self.rival(rid)
        return r.name if r else rid

    def standings(self) -> list[dict[str, Any]]:
        """Classement général : place, coureur, points (6 meilleures + classique × 1,5), manches courues,
        victoires ; égalité départagée par les victoires, la place à la finale, puis le nom."""
        rows = []
        for rid in self.racers():
            per = [points_for(self.results[i].places.get(rid)) if i in self.results else 0 for i in range(WEEKS)]
            best = sum(sorted(per, reverse=True)[:BEST])
            classic = points_for(self.classic.places.get(rid)) * CLASSIC_FACTOR if self.classic else 0.0
            ran = sum(1 for i, res in self.results.items() if rid in res.places)
            wins = sum(1 for res in self.results.values() if res.places.get(rid) == 1)
            final = self.results.get(WEEKS - 1)
            final_place = final.places.get(rid) if final else None
            rows.append({"id": rid, "name": self.name_of(rid),
                         "profile": (self.rival(rid).profile if rid != ME else None),
                         "points": best + classic, "rounds": per, "classic": classic, "ran": ran, "wins": wins,
                         "final_place": final_place})
        rows.sort(key=lambda r: (-r["points"], -r["wins"], r["final_place"] or 99, r["name"]))
        for n, r in enumerate(rows, 1):
            r["place"] = n
        return rows

    def place_of(self, rid: str = ME) -> int:
        return next(r["place"] for r in self.standings() if r["id"] == rid)

    def rider_rounds(self) -> int:
        """Manches courues par le cycliste (résultats « joueur »)."""
        return sum(1 for res in self.results.values() if res.source == "joueur" and ME in res.places)

    def trophy(self) -> tuple[str, str] | None:
        """Trophée de fin de saison du cycliste (identifiant, libellé écrit), None sans trophée."""
        if self.closed != "fin":
            return None
        place = self.place_of(ME)
        if place in TROPHIES:
            return TROPHIES[place]
        if self.rider_rounds() >= BEST:
            return REGULARITY
        return None

    def home_line(self, today: date) -> str:
        """Ligne de l'accueil (maquette 01) : place et manche de la semaine, en mots."""
        place = ordinal(self.place_of(ME))
        if self.closed == "pause":
            return f"Saison close après une longue pause · {place}"
        if self.closed == "fin":
            t = self.trophy()
            return f"Saison finie · {place}" + (f" · {t[1]}" if t else "")
        i = min(self.week_index(today), WEEKS - 1)
        if self.paused:
            return f"{place} · saison en pause · manche {i + 1}/{WEEKS}"
        if i in self.results:
            nxt = "prochaine lundi" if i + 1 < WEEKS else "fin de saison dimanche"
            return f"{place} · manche {i + 1}/{WEEKS} faite · {nxt}"
        return f"{place} · manche {i + 1}/{WEEKS} : {ROUNDS[i].short}, à courir cette semaine"

    # --- lecture et écriture ----------------------------------------------------------------------

    def _check_places(self, places: Mapping[str, int], with_me: bool = True) -> dict[str, int]:
        """Places complètes : les 11 rivaux (et le cycliste s'il a couru), places de 1 au nombre de coureurs."""
        want = set(self.racers()) if with_me else {r.key for r in self.rivals}
        got = {str(k): v for k, v in places.items()}
        if set(got) != want:
            missing, extra = sorted(want - set(got)), sorted(set(got) - want)
            raise LeagueError(f"classement incomplet (manquent {missing}, en trop {extra})")
        for k, v in got.items():
            if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= len(want):
                raise LeagueError(f"place refusée pour {k} : {v!r}")
        return got

    def to_dict(self) -> dict[str, Any]:
        return {"version": VERSION, "number": self.number, "seed": self.seed, "start": self.start.isoformat(),
                "rivals": [r.to_dict() for r in self.rivals],
                "results": {str(i): r.to_dict() for i, r in sorted(self.results.items())},
                "classic_day": self.classic_day.isoformat() if self.classic_day else None,
                "classic": self.classic.to_dict() if self.classic else None,
                "pauses": [[a.isoformat() if a else None, b.isoformat() if b else None] for a, b in self.pauses],
                "closed": self.closed}

    @classmethod
    def from_dict(cls, data: Any) -> "Season":
        """Saison lue ; lève `LeagueError` si le fichier ne décrit pas une saison valide."""
        try:
            if not isinstance(data, dict) or data.get("version") != VERSION:
                raise LeagueError("version inconnue")
            rivals = [Rival(str(r["key"]), str(r["profile"]), str(r["name"]), str(r["team"]), str(r["color"]))
                      for r in data["rivals"]]
            if [r.key for r in rivals] != field_keys():
                raise LeagueError("rivaux incomplets")
            s = cls(int(data["number"]), int(data["seed"]), date.fromisoformat(data["start"]), rivals)
            s.start = monday(s.start)
            for k, r in (data.get("results") or {}).items():
                i = int(k)
                if not 0 <= i < WEEKS:
                    raise LeagueError(f"manche {k} hors calendrier")
                s.results[i] = _result_from(s, r)
            if data.get("classic_day"):
                s.classic_day = date.fromisoformat(data["classic_day"])
            if data.get("classic"):
                s.classic = _result_from(s, data["classic"])
            s.pauses = [[date.fromisoformat(a) if a else None, date.fromisoformat(b) if b else None]
                        for a, b in (data.get("pauses") or [])]
            closed = data.get("closed")
            if closed not in (None, "fin", "pause"):
                raise LeagueError(f"fin de saison inconnue : {closed!r}")
            s.closed = closed
            return s
        except (KeyError, TypeError, ValueError) as e:   # LeagueError est un ValueError
            raise LeagueError(f"saison illisible : {e}") from e


def _result_from(season: Season, r: Any) -> RoundResult:
    source = r.get("source")
    if source not in ROUND_SOURCES:
        raise LeagueError(f"source inconnue : {source!r}")
    places = season._check_places(r["places"], with_me=ME in r["places"])
    return RoundResult(places, source, bool(r.get("easy", False)), str(r.get("day", "")))


# --- création et simulation -----------------------------------------------------------------------

def _roster_of(season: Season) -> rivals_mod.Roster:
    """Groupe des rivaux rebâti d'une saison (fichier des rivaux absent : tests, profil d'avant R4)."""
    return rivals_mod.Roster(season.seed, {r.key: rivals_mod.Rival(r.key, r.name, r.team) for r in season.rivals})


def new_season(today: date, seed: int | None = None, previous: Season | None = None,
               roster: rivals_mod.Roster | None = None) -> Season:
    """Nouvelle saison commençant le lundi de cette semaine. Rivaux pris du groupe des rivaux du profil
    (`rivals.py`, lot R4 : mêmes noms, équipes et caractères dans tous les modes), créés s'ils manquent. Après
    `previous`, 3 rivaux sont remplacés (`Roster.renew` : le nouveau venu garde l'identité, donc le profil et la
    cote). `roster` est modifié en place (à enregistrer par l'appelant) ; None : groupe de la saison précédente, ou
    groupe neuf tiré de `seed`."""
    if seed is None:
        seed = random.SystemRandom().randrange(1 << 31)
    rng = random.Random(seed)
    keys = field_keys()
    if roster is None:
        roster = _roster_of(previous) if previous is not None else rivals_mod.Roster(seed)
    if previous is None:
        roster.ensure(keys)
        number = 1
    else:
        roster.renew(keys, len(keys) - KEEP_RIVALS, rng)
        number = previous.number + 1
    found = roster.ensure(keys)
    if any(r is None for r in found):
        raise LeagueError("plus de nom libre pour un rival")
    rivals = [Rival(r.key, r.profile, r.name, r.team, r.color) for r in found if r is not None]
    return Season(number, seed, monday(today), rivals)


def round_strength(season: Season, rnd: Round, ratings: Mapping[str, float] | None = None) -> dict[str, float]:
    """Force de tirage des rivaux d'une manche : cote (défaut 1 500) plus l'avantage du caractère au terrain."""
    ratings = ratings or {}
    aff = AFFINITY.get(rnd.terrain, {})
    return {r.key: float(ratings.get(r.key, START_RATING)) + aff.get(r.profile, 0.0) for r in season.rivals}


def plackett_luce(strengths: Mapping[str, float], rng: random.Random) -> list[str]:
    """Ordre d'arrivée tiré au sort : chaque place va à un coureur avec une chance proportionnelle à
    10^(force/400), comme le score attendu de l'Elo."""
    left = dict(strengths)
    order = []
    while left:
        top = max(left.values())
        weights = {k: math.pow(10.0, (v - top) / ELO_SCALE) for k, v in left.items()}
        x = rng.random() * sum(weights.values())
        for k in sorted(weights):
            x -= weights[k]
            if x <= 0:
                break
        order.append(k)
        del left[k]
    return order


def simulate_order(season: Season, rnd: Round, index: int, ratings: Mapping[str, float] | None = None,
                   extra: Mapping[str, float] | None = None) -> dict[str, int]:
    """Classement simulé d'une manche (places 1 à n) : rivaux, plus les coureurs de `extra` (identité → force,
    le cycliste pour un banc). Tirage reproductible : graine de la saison et rang de la manche."""
    strengths = round_strength(season, rnd, ratings)
    strengths.update(extra or {})
    rng = random.Random(season.seed * 1009 + index)
    return {k: n for n, k in enumerate(plackett_luce(strengths, rng), 1)}


def field_profiles(season: Season) -> list[str]:
    """Profils du plateau dans l'ordre des identités (`climber`, `climber`, `climber`, `rouleur`…), pour que la
    séance donne à chaque bot l'identité Elo du rival (`bot_elo.plan_keys`)."""
    return [r.profile for r in season.rivals]


# --- fichier du profil ----------------------------------------------------------------------------

def path_for(root: Path) -> Path:
    return root / FILE_NAME


def load(path: Path) -> Season | None:
    """Saison du profil ; None sans fichier. Un fichier illisible est mis de côté (`ligue.json.abime`), jamais
    écrasé en silence, et la ligue repart sans saison."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError):
        text = None
    try:
        if text is None:
            raise LeagueError("fichier illisible")
        return Season.from_dict(json.loads(text))
    except (ValueError, LeagueError):
        try:
            os.replace(path, path.with_name(path.name + ".abime"))
        except OSError:
            pass
        return None


def save(path: Path, season: Season) -> None:
    """Écriture sûre (fichier temporaire puis remplacement) ; lève `OSError`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(season.to_dict(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
