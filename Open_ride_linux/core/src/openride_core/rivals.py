"""Rivaux reconnaissables (lot R4, 22 novembre 2026).

Module pur hors lecture et écriture de `<profil>/rivaux.json`. Cahier : `docs/lots/LOT_BR4_rivaux_reconnaissables.md`.

- **Un seul groupe de rivaux pour tous les modes** (décision du propriétaire du 22/11 : « Mêmes rivaux partout ») :
  un bot à profil garde, d'une course à l'autre, le même nom fictif, la même équipe (nom écrit et couleur du
  maillot), le même caractère (son profil : grimpeur, rouleur…) et le même tempérament (attaquant, suiveur,
  opportuniste, tiré du nom par `bot_tactics.personality_of`). Sa cote est celle de `bot_elo` sous la même identité.
- **Identité** : celle de la cote Elo (`bot_elo.bot_key`, `climber#1`, `climber#2`…), donnée par le rang du bot
  parmi ceux du même profil dans le plateau. Un rival est créé la première fois que son identité court, puis
  gardé dans le fichier du profil.
- **Ligue d'hiver** (série CH) : la saison reprend ces rivaux ; `renew` en remplace 3 à chaque nouvelle saison
  (des têtes connues, un peu de neuf) et le changement vaut pour tous les modes.
- Noms fictifs uniquement, aucun coureur réel.
"""

from __future__ import annotations

import json
import os
import random
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from .bot_elo import plan_keys
from .bot_tactics import personality_of

FILE_NAME = "rivaux.json"
VERSION = 1
NAME_MAX = 16          # longueur des noms au HUD (`bots.Bot.name`)

PROFILE_LABELS = {"climber": "Grimpeur", "rouleur": "Rouleur", "sprinter": "Sprinteur", "diesel": "Diesel"}
PERSONALITY_LABELS = {"attacker": "attaquant", "follower": "suiveur", "opportunist": "opportuniste"}

# Noms fictifs (aucun coureur réel), 16 caractères au plus. Les 24 premiers sont ceux du cahier CH1.
NAMES = (
    "Arno Vidal", "Bastien Morel", "Cyril Fabre", "Damien Roux", "Élio Garnier", "Fabien Lacroix", "Gaël Perrin",
    "Hugo Marchal", "Ilan Bertin", "Jonas Delmas", "Kévin Aubry", "Loïc Ferrand", "Mathis Carrel", "Nils Pujol",
    "Oscar Lemaire", "Pierre Vasseur", "Quentin Rey", "Rémi Joubert", "Simon Barral", "Théo Valette",
    "Ugo Lambert", "Victor Chauvin", "Yann Mercier", "Zacharie Brun",
    "Adrien Calvet", "Benoît Sarrat", "Clément Ollier", "Denis Faure", "Émile Tessier", "Florent Gauthier",
    "Gilles Royer", "Henri Baudet", "Jules Peyrot", "Lucas Rivière", "Marius Bonnet", "Noé Castel",
    "Paul Arnaud", "Raphaël Tissot", "Sacha Morin", "Tristan Laborde", "Valentin Roche", "Xavier Dumas",
    "Antoine Pagès", "Baptiste Leroy",
)
# Équipes : nom écrit et couleur du maillot (la couleur ne sert jamais seule).
TEAMS = (
    ("Équipe Brume", "#4f7bbf"), ("Équipe Granit", "#7a7a7a"), ("Équipe Cèdre", "#2f8a4c"),
    ("Équipe Braise", "#c4472d"), ("Équipe Glacier", "#7fc4d9"), ("Équipe Ocre", "#c48a2d"),
    ("Équipe Lavande", "#8a6fbf"), ("Équipe Ardoise", "#3d4a5c"), ("Équipe Coquelicot", "#d93a4a"),
    ("Équipe Prairie", "#8ab83d"), ("Équipe Sable", "#d9c48a"),
)
TEAM_COLORS = dict(TEAMS)


def profile_of(key: str) -> str:
    return key.split("#", 1)[0]


@dataclass
class Rival:
    key: str        # identité Elo (`climber#1`)
    name: str
    team: str

    @property
    def profile(self) -> str:
        return profile_of(self.key)

    @property
    def color(self) -> str:
        return TEAM_COLORS.get(self.team, "#7a7a7a")

    @property
    def personality(self) -> str:
        """Tempérament de course, le même que celui des tactiques (`bot_tactics.Tactics`, tiré du nom)."""
        return personality_of(self.name)

    def style(self) -> str:
        """Caractère écrit : « Grimpeur, attaquant »."""
        return f"{PROFILE_LABELS.get(self.profile, self.profile)}, {PERSONALITY_LABELS[self.personality]}"

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "name": self.name, "team": self.team}


@dataclass
class Roster:
    """Rivaux du profil, par identité. `changed` : un rival a été créé ou remplacé depuis la lecture."""

    seed: int = 0
    rivals: dict[str, Rival] = field(default_factory=dict)
    retired: list[str] = field(default_factory=list)   # noms des rivaux remplacés (pas de retour d'un ancien)
    changed: bool = False

    def get(self, key: str) -> Rival | None:
        return self.rivals.get(key)

    def _free_names(self) -> list[str]:
        used = {r.name for r in self.rivals.values()} | set(self.retired)
        return [n for n in NAMES if n not in used]

    def _team_for(self, rng: random.Random) -> str:
        """Équipe la moins remplie (tirage parmi les ex æquo) : 11 équipes, un à quatre coureurs chacune."""
        count = {t: 0 for t, _ in TEAMS}
        for r in self.rivals.values():
            if r.team in count:
                count[r.team] += 1
        low = min(count.values())
        return rng.choice([t for t, n in count.items() if n == low])

    def _create(self, key: str) -> Rival | None:
        free = self._free_names()
        if not free:
            return None
        rng = random.Random(self.seed * 7919 + zlib.crc32(f"{key}:{len(self.retired)}".encode()))
        rival = Rival(key, rng.choice(free), self._team_for(rng))
        self.rivals[key] = rival
        self.changed = True
        return rival

    def ensure(self, keys: Iterable[str]) -> list[Rival | None]:
        """Rivaux des identités `keys`, créés s'ils manquent (None si tous les noms sont pris)."""
        return [self.rivals.get(k) or self._create(k) for k in keys]

    def names_for(self, profiles: Sequence[str]) -> list[str]:
        """Noms des bots d'un plateau (profils dans l'ordre du plateau) ; sans nom libre, nom de profil
        numéroté comme avant R4 (« Grimpeur 5 »)."""
        keys = plan_keys(profiles)
        out = []
        for k, r in zip(keys, self.ensure(keys)):
            if r is not None:
                out.append(r.name[:NAME_MAX])
            else:
                p, n = k.split("#", 1)
                base = PROFILE_LABELS.get(p, p)
                out.append(base if n == "1" else f"{base} {n}")
        return out

    def renew(self, keys: Sequence[str], count: int, rng: random.Random) -> list[str]:
        """Remplace `count` rivaux tirés parmi `keys` (nouvelle saison de la ligue) ; rend leurs identités.
        Le nouveau venu garde l'identité, donc le profil et la cote du partant."""
        self.ensure(keys)
        leaving = rng.sample([k for k in keys if k in self.rivals], min(count, len(keys)))
        for k in leaving:
            self.retired.append(self.rivals.pop(k).name)
            if self._create(k) is None:   # plus de nom libre : le plus ancien retraité revient
                self.retired.pop(0)
                self._create(k)
        self.changed = True
        return leaving

    def describe(self, keys: Iterable[str], ratings: dict[str, float] | None = None) -> list[dict[str, Any]]:
        """Fiches écrites des rivaux (écran de la ligue, bilan) : nom, caractère, équipe, couleur, cote."""
        out = []
        for k in keys:
            r = self.rivals.get(k)
            if r is None:
                continue
            line = {"key": k, "name": r.name, "profile": r.profile, "style": r.style(), "team": r.team,
                    "color": r.color}
            if ratings is not None and k in ratings:
                line["rating"] = int(round(ratings[k]))
            out.append(line)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {"version": VERSION, "seed": self.seed,
                "rivals": [self.rivals[k].to_dict() for k in sorted(self.rivals)], "retired": list(self.retired)}

    @classmethod
    def from_dict(cls, data: Any) -> "Roster":
        if not isinstance(data, dict) or data.get("version") != VERSION:
            raise ValueError("fichier des rivaux d'une autre version")
        rivals = {}
        for r in data.get("rivals", []):
            key, name, team = str(r["key"]), str(r["name"]), str(r["team"])
            if "#" not in key or not name:
                raise ValueError(f"rival mal écrit : {r!r}")
            rivals[key] = Rival(key, name[:NAME_MAX], team)
        return cls(int(data.get("seed", 0)), rivals, [str(n) for n in data.get("retired", [])])


def load(path: Path) -> Roster:
    """Rivaux du fichier ; groupe vide (graine 0, mêmes premiers noms pour tous) si le fichier manque ou est
    illisible."""
    try:
        return Roster.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError):
        return Roster()


def save(path: Path, roster: Roster) -> None:
    """Écriture sûre (fichier temporaire puis remplacement) ; lève `OSError`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(roster.to_dict(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    roster.changed = False
