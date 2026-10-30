"""Catalogue des règles du mode WTF et fichier des règles actives (lot WTF1, module pur).

Chaque règle se coupe seule dans `~/OpenRide/wtf.toml` (facultatif, écrit par le core) :

    [rules]                 # true : règle jouée ; règle absente : active
    gravity = true
    upside_down = false
    [director]              # rythme des événements
    first_s = 20            # premier événement après 20 s
    gap_min_s = 45          # pause entre deux événements, tirée entre min et max
    gap_max_s = 90

Deux familles : les **événements** (une seule à la fois, durée limitée, tirés au hasard par
`WtfMode`) et les **règles permanentes** (actives toute la séance).
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from ..config import OPENRIDE_HOME

WTF_FILE = OPENRIDE_HOME / "wtf.toml"

EVENT, AMBIENT = "event", "ambient"


@dataclass(frozen=True)
class Rule:
    id: str
    label: str
    family: str
    pitch: str              # une phrase pour le menu


RULES: tuple[Rule, ...] = (
    Rule("gravity", "Gravité au choix", EVENT,
         "La Lune (pentes divisées par 6, le vélo bondit) ou Jupiter (un faux plat devient un mur)."),
    Rule("upside_down", "Monde à l'envers", EVENT, "Les descentes durcissent, les montées sont faciles, le ciel est en bas."),
    Rule("collapse", "La route s'effondre", EVENT, "La route s'écroule derrière toi : garde le rythme ou tu tombes."),
    Rule("katamari", "Katamari à vélo", AMBIENT, "Tu ramasses ce que tu touches et tu grossis."),
    Rule("peloton", "Peloton délirant", AMBIENT, "Mamies qui attaquent, tracteur, baignoire et baleine volante (abri XXL)."),
    Rule("cheese", "Fromage géant", EVENT, "Une meule de fromage te poursuit dans les descentes."),
    Rule("micro", "Micro-défis", EVENT, "Trois défis de 30 s à la suite : cadence pile, sprint, plafond, régularité."),
    Rule("eggs", "Livraison d'œufs", EVENT, "Six œufs à livrer : chaque à-coup de puissance en casse un."),
    Rule("clock", "La cadence pilote le monde", AMBIENT, "Pédaler vite fait tourner le soleil ; au-dessus de 100 rpm il pleut des poissons."),
    Rule("tiny", "Vélo minuscule", EVENT, "Tu roules dans une cuisine géante, une pente c'est le bord d'une assiette."),
    Rule("storm", "Météo folle", EVENT, "Tornade de vaches et vent de face qui te fait reculer si tu ne pousses pas."),
    Rule("camera", "Caméras improbables", EVENT, "Vue d'un pigeon, d'un escargot ou de ta propre roue."),
    Rule("chef", "Surprise du chef", EVENT, "Le chef arrive en tandem et soulève sa cloche : plat surprise, refusable une fois."),
)
RULE_IDS = tuple(r.id for r in RULES)
EVENT_IDS = tuple(r.id for r in RULES if r.family == EVENT)
AMBIENT_IDS = tuple(r.id for r in RULES if r.family == AMBIENT)

FIRST_MIN_S, GAP_MIN_S, GAP_MAX_S = 5.0, 15.0, 900.0


class WtfError(ValueError):
    """Fichier `wtf.toml` invalide."""


@dataclass(frozen=True)
class WtfTable:
    enabled: frozenset[str] = field(default_factory=lambda: frozenset(RULE_IDS))
    first_s: float = 20.0
    gap_min_s: float = 45.0
    gap_max_s: float = 90.0

    def on(self, rule_id: str) -> bool:
        return rule_id in self.enabled

    def with_rule(self, rule_id: str, on: bool) -> "WtfTable":
        """Copie avec une règle allumée ou coupée ; `WtfError` si la règle est inconnue."""
        if rule_id not in RULE_IDS:
            raise WtfError(f"règle inconnue : {rule_id} (règles : {', '.join(RULE_IDS)})")
        enabled = set(self.enabled)
        (enabled.add if on else enabled.discard)(rule_id)
        return WtfTable(frozenset(enabled), self.first_s, self.gap_min_s, self.gap_max_s)

    def rules_list(self) -> list[dict]:
        """Liste pour le menu : identifiant, nom, famille, phrase, état."""
        return [{"id": r.id, "label": r.label, "family": r.family, "pitch": r.pitch, "on": r.id in self.enabled}
                for r in RULES]


DEFAULT_TABLE = WtfTable()


def _number(section: dict, key: str, default: float, lo: float, hi: float) -> float:
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise WtfError(f"director.{key} doit être un nombre")
    if not lo <= value <= hi:
        raise WtfError(f"director.{key} = {value} hors de [{lo:g}, {hi:g}]")
    return float(value)


def load_table(path: Path | None = None) -> WtfTable:
    """Règles actives : toutes par défaut, coupées une à une par le fichier s'il existe."""
    path = path or WTF_FILE
    if not path.is_file():
        return DEFAULT_TABLE
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise WtfError(f"{path} illisible : {exc}") from exc
    unknown = set(data) - {"rules", "director"}
    if unknown:
        raise WtfError(f"sections inconnues dans {path.name} : {', '.join(sorted(unknown))}")
    rules = data.get("rules", {})
    director = data.get("director", {})
    if not isinstance(rules, dict) or not isinstance(director, dict):
        raise WtfError("[rules] et [director] doivent être des sections")
    bad = set(rules) - set(RULE_IDS)
    if bad:
        raise WtfError(f"règles inconnues : {', '.join(sorted(bad))}")
    for key, value in rules.items():
        if not isinstance(value, bool):
            raise WtfError(f"rules.{key} doit valoir true ou false")
    bad = set(director) - {"first_s", "gap_min_s", "gap_max_s"}
    if bad:
        raise WtfError(f"clés inconnues dans [director] : {', '.join(sorted(bad))}")
    enabled = frozenset(r for r in RULE_IDS if rules.get(r, True))
    d = DEFAULT_TABLE
    first = _number(director, "first_s", d.first_s, FIRST_MIN_S, GAP_MAX_S)
    gap_min = _number(director, "gap_min_s", d.gap_min_s, GAP_MIN_S, GAP_MAX_S)
    gap_max = _number(director, "gap_max_s", d.gap_max_s, GAP_MIN_S, GAP_MAX_S)
    if gap_min > gap_max:
        raise WtfError("director.gap_min_s doit être inférieur ou égal à gap_max_s")
    return WtfTable(enabled, first, gap_min, gap_max)


def dump_table(table: WtfTable) -> str:
    """Texte de `wtf.toml` (fichier écrit par le core seul, réécrit en entier)."""
    lines = ["# Mode WTF : règles jouées (true) ou coupées (false). Écrit par OpenRide.", "[rules]"]
    lines += [f"{r} = {'true' if r in table.enabled else 'false'}" for r in RULE_IDS]
    lines += ["", "[director]", f"first_s = {table.first_s:g}", f"gap_min_s = {table.gap_min_s:g}",
              f"gap_max_s = {table.gap_max_s:g}", ""]
    return "\n".join(lines)


def save_table(table: WtfTable, path: Path | None = None) -> None:
    """Écrit le fichier par remplacement atomique (jamais à moitié écrit)."""
    path = path or WTF_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_text(dump_table(table), encoding="utf-8")
    tmp.replace(path)
