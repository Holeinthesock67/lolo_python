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
- Noms fictifs uniquement, aucun coureur réel ; le nom de famille dit le caractère (« Léo Lacime », « Gaston
  Lentrain »), une liste par profil.
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
NAME_MAX = 16          # longueur des noms complets (fiches, écran de la ligue)
SHORT_MAX = 11         # nom court du HUD (« L. Lacime ») : la largeur de « Sprinteur 2 » d'avant R4

PROFILE_LABELS = {"climber": "Grimpeur", "rouleur": "Rouleur", "sprinter": "Sprinteur", "diesel": "Diesel"}
PERSONALITY_LABELS = {"attacker": "attaquant", "follower": "suiveur", "opportunist": "opportuniste"}

# Noms fictifs (aucun coureur réel), un jeu de mots sur le caractère dans le nom de famille (choix du propriétaire
# du 22/11 : « noms à jeu de mots ») : on devine le type d'un rival à son nom, sans rien ajouter à l'écran. Douze
# noms par profil (11 bots au plus dans un plateau) ; nom court du HUD de 11 caractères au plus.
NAMES: dict[str, tuple[str, ...]] = {
    "climber": ("Léo Lacime", "Paul Ducol", "Tom Pic", "Marc Lacet", "Hugo Sommet", "Yves Rampe",
                "Ange Altitude", "Noé Névé", "Félix Crête", "Gilles Lagrimpe", "Bruno Mont", "Simon Perché"),
    "rouleur": ("Max Laroue", "Jean Duplat", "Rémi Relais", "Yann Bitume", "Luc Plaine", "Igor Tempo",
                "Victor Bordure", "Hervé Rouleau", "Cyril Chrono", "Alain Asphalte", "Denis Braquet",
                "Oscar Lebidon"),
    "sprinter": ("Kévin Lafusée", "Sam Léclair", "Basile Flèche", "Théo Turbo", "Fred Boulet", "Zack Fulgur",
                 "Ugo Rapido", "Enzo Bolide", "Nils Nitro", "Vincent Vitesse", "Loïc Laligne", "Dylan Démarre"),
    "diesel": ("Gaston Lentrain", "Marcel Piston", "Henri Tracteur", "Roger Loco", "Albert Mazout",
               "Michel Moteur", "Gérard Gasoil", "Raoul Vapeur", "Camille Cargo", "Émile Endurant",
               "Bernard Bielle", "Thierry Tenace"),
}
ALL_NAMES = tuple(n for names in NAMES.values() for n in names)
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
    def short(self) -> str:
        """Nom affiché en course (bandes, listes, éliminations) : initiale du prénom et nom, « L. Lacime »."""
        first, _, last = self.name.partition(" ")
        return f"{first[0]}. {last}" if last else first

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

    def _free_names(self, profile: str) -> list[str]:
        used = {r.name for r in self.rivals.values()} | set(self.retired)
        return [n for n in NAMES.get(profile, ()) if n not in used]

    def _team_for(self, rng: random.Random) -> str:
        """Équipe la moins remplie (tirage parmi les ex æquo) : 11 équipes, un à quatre coureurs chacune."""
        count = {t: 0 for t, _ in TEAMS}
        for r in self.rivals.values():
            if r.team in count:
                count[r.team] += 1
        low = min(count.values())
        return rng.choice([t for t, n in count.items() if n == low])

    def _create(self, key: str) -> Rival | None:
        free = self._free_names(profile_of(key))
        if not free:
            return None
        rng = random.Random(self.seed * 7919 + zlib.crc32(f"{key}:{len(self.retired)}".encode()))
        rival = Rival(key, rng.choice(free), self._team_for(rng))
        self.rivals[key] = rival
        self.changed = True
        return rival

    def ensure(self, keys: Iterable[str]) -> list[Rival | None]:
        """Rivaux des identités `keys`, créés s'ils manquent (None si tous les noms du profil sont pris)."""
        return [self.rivals.get(k) or self._create(k) for k in keys]

    def names_for(self, profiles: Sequence[str]) -> list[str]:
        """Noms courts des bots d'un plateau (profils dans l'ordre du plateau) ; sans nom libre, nom de profil
        numéroté comme avant R4 (« Grimpeur 5 »)."""
        keys = plan_keys(profiles)
        out = []
        for k, r in zip(keys, self.ensure(keys)):
            if r is not None:
                out.append(r.short)
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
            if self._create(k) is None:   # plus de nom libre du profil : son plus ancien retraité revient
                profile = profile_of(k)
                back = next(i for i, n in enumerate(self.retired) if n in NAMES.get(profile, ()))
                self.retired.pop(back)
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
            line = {"key": k, "name": r.name, "short": r.short, "profile": r.profile, "style": r.style(), "team": r.team,
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
