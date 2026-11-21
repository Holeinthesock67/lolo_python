"""Essais physiques sur le vélo, guidés par le jeu lui-même (série EP, lot EP2).

Principe validé par le propriétaire le 15 novembre 2026 (`docs/lots/LOT_EP2_guide_essais_physiques.md`) :
une seule forme de séance, sans exception.

1. Une **fiche** (`data/essais/<id>.toml`) dit ce que l'essai teste (`but`, annoncé avant de pédaler).
2. Le **terrain est verrouillé** : la fiche porte la liste des commandes du menu (`commandes`, lot EP1) et
   les réglages de la séance (`[config]`) ; le guide lance OpenRide en `--autostart --seance`, rien n'est
   choisi au menu ni repris de la partie d'avant. Le guide vérifie à l'en-tête du journal que le jeu roule
   bien sur le parcours de la fiche, sinon il arrête.
3. Les **étapes suivent le jeu**, jamais l'horloge : chaque étape attend une ligne du journal de séance
   (`quand`, lu en direct, une ligne par seconde), donne sa consigne (voix, bip, bandeau dans le jeu),
   puis, si elle a un `attendu`, regarde au journal si l'action a eu lieu : « vu », ou un seul rappel.
   Toutes les étapes sont armées dès le départ et partent quand le jeu les déclenche, dans l'ordre du jeu ;
   une étape dont le déclencheur ne vient pas se tait (comptée à la fin, essai du 21/11).
4. Au plus 10 min de **pédalage réel** (temps de séance `t` du journal) : le guide arrête OpenRide (la
   séance est enregistrée), remet les réglages, puis pose 2 ou 3 questions notées dans `essais.txt`.

Consignes en watts directs : `{cible}` (moyenne réelle des 3 dernières séances sur le vrai trainer, lue
sur le PC et jamais écrite dans le dépôt), `{cible:120}` (120 % de la cible), arrondis à 5 W.

Déclencheurs et attendus : une table qui doit correspondre à une ligne du journal ; chaque clé est égale,
ou porte un opérateur en suffixe (`"distance>=" = 500`, `"phase!=" = "WARMUP"`, `"t<=" = 30`).

    python -m openride_core.tools.essai_physique liste
    python -m openride_core.tools.essai_physique voir gp-voies
    python -m openride_core.tools.essai_physique lancer gp-voies [--profil principal] [--sim] [--cible 120]
    python -m openride_core.tools.essai_physique rejouer gp-voies ~/OpenRide/.../séance.jsonl   # banc : instants des consignes
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from .. import seance_file

FICHES_DIR = Path(__file__).resolve().parents[1] / "data" / "essais"
DUREE_MAX_S = 600                 # règle du propriétaire : 10 min de pédalage au plus par séance
ATTENTE_MAX_S = 180.0             # ancien délai avant de sauter une étape : lu, plus utilisé (21/11)
DELAI_ATTENDU_S = 30.0            # temps laissé pour faire l'action demandée, avant le rappel
QUESTIONS_MAX = 3
CIBLE_DEFAUT_W = 100              # sans séance réelle au journal (premier essai)
OPS = (">=", "<=", "!=", ">", "<")


class FicheError(ValueError):
    """Fiche d'essai illisible ou incohérente."""


# ---------------------------------------------------------------- fiches


@dataclass
class Etape:
    quand: dict
    dire: str
    attendu: dict | None = None
    delai_s: float = DELAI_ATTENDU_S
    rappel: str = ""
    attente_max_s: float = ATTENTE_MAX_S


@dataclass
class Fiche:
    id: str
    but: str
    commandes: list[tuple[str, dict]]
    etapes: list[Etape]
    questions: list[str]
    config: list[tuple[str, str, Any]] = field(default_factory=list)
    duree_max_s: int = DUREE_MAX_S
    bots_cible_pct: float | None = None   # bots réglés sur la consigne : effort visé = ce % de {cible}
    bots_duree_s: float | None = None     # durée de course estimée pour la courbe des bots (défaut : duree_max_s)
    rogue_balance: dict = field(default_factory=dict)   # surcharge de la table d'une run d'essai (échauffement)
    surcharges: dict = field(default_factory=dict)      # fichier de ~/OpenRide → table posée le temps de l'essai

    @property
    def monde_ouvert(self) -> bool:
        return any(n == "start_open_world" for n, _ in self.commandes)

    @property
    def mode(self) -> str | None:
        for name, args in self.commandes:
            if name == "start":
                return args.get("mode")
        return None

    @property
    def a_des_bots(self) -> bool:
        """Vrai si la séance roule avec des bots (Grand Prix, vélodrome, ou `bots` donnés au départ)."""
        for name, args in self.commandes:
            if name == "start" and (args.get("mode") in ("grandprix", "track", "survivor") or args.get("bots")):
                return True
        return False

    @property
    def objectif_bots(self) -> str:
        """Objectif des bots (lot BT1) : celui de l'épreuve au vélodrome, sinon `[config.bots] objective`."""
        from ..bot_effort import DEFAULT_OBJECTIVE, TRACK_EFFORT
        for name, args in self.commandes:
            if name == "start" and args.get("mode") == "track":
                return TRACK_EFFORT.get(str((args.get("track") or {}).get("event")), ("tempo",))[0]
        for section, cle, v in self.config:
            if (section, cle) == ("bots", "objective"):
                return str(v)
        return DEFAULT_OBJECTIVE

    @property
    def route_id(self) -> str | None:
        """Parcours attendu à l'en-tête du journal (`None` pour une run Cyber-Rogue, sans parcours)."""
        for name, args in self.commandes:
            if name == "select_route":
                return str(args.get("route_id"))
        return None


def _predicat(value: Any, ou: str) -> dict:
    if not isinstance(value, dict) or not value:
        raise FicheError(f"{ou} : table non vide attendue")
    for k in value:
        cle, op = _cle_op(k)
        if not cle:
            raise FicheError(f"{ou} : clé « {k} » sans nom de champ")
        if op not in ("", "!=") and not isinstance(value[k], (int, float)):
            raise FicheError(f"{ou} : « {k} » compare un nombre")
    return dict(value)


def lire_fiche(data: dict, source: str = "fiche") -> Fiche:
    """Fiche vérifiée ; `FicheError` avec la raison sinon."""
    try:
        fid, but = str(data["id"]), str(data["but"]).strip()
        commandes = seance_file.check(data["commandes"])
    except KeyError as exc:
        raise FicheError(f"{source} : champ {exc} manquant") from None
    except seance_file.SeanceError as exc:
        raise FicheError(f"{source} : {exc}") from None
    if not but:
        raise FicheError(f"{source} : 'but' vide (l'essai dit ce qu'il teste)")
    duree = int(data.get("duree_max_s", DUREE_MAX_S))
    if not 60 <= duree <= DUREE_MAX_S:
        raise FicheError(f"{source} : duree_max_s {duree} hors de 60 à {DUREE_MAX_S} s")
    etapes = []
    for i, e in enumerate(data.get("etapes") or [], 1):
        ou = f"{source}, étape {i}"
        if not isinstance(e, dict) or not str(e.get("dire", "")).strip():
            raise FicheError(f"{ou} : 'dire' manquant")
        etapes.append(Etape(quand=_predicat(e.get("quand"), f"{ou}, quand"), dire=str(e["dire"]),
                            attendu=_predicat(e["attendu"], f"{ou}, attendu") if "attendu" in e else None,
                            delai_s=float(e.get("delai_s", DELAI_ATTENDU_S)), rappel=str(e.get("rappel", "")),
                            attente_max_s=float(e.get("attente_max_s", ATTENTE_MAX_S))))
    if not etapes:
        raise FicheError(f"{source} : aucune étape")
    questions = [str(q) for q in data.get("questions") or []]
    if not 1 <= len(questions) <= QUESTIONS_MAX:
        raise FicheError(f"{source} : 1 à {QUESTIONS_MAX} questions de fin attendues")
    config = []
    for section, keys in (data.get("config") or {}).items():
        if not isinstance(keys, dict):
            raise FicheError(f"{source} : [config.{section}] attend une table")
        config += [(str(section), str(k), v) for k, v in keys.items()]
    rb = data.get("rogue_balance") or {}
    if rb:
        from ..rogue.balance import BalanceError, RogueBalance, apply_overrides
        try:
            apply_overrides(RogueBalance(), rb)
        except BalanceError as exc:
            raise FicheError(f"{source} : rogue_balance : {exc}") from None
    surcharges = data.get("surcharges") or {}
    for nom, table in surcharges.items():
        if nom not in SURCHARGES_PERMISES or not isinstance(table, dict):
            raise FicheError(f"{source} : surcharge « {nom} » refusée ({', '.join(SURCHARGES_PERMISES)})")
    if "powerups.toml" in surcharges:
        import tempfile

        from ..powerups import PowerUpError, load_table
        try:
            with tempfile.TemporaryDirectory() as d:
                essai = Path(d) / "powerups.toml"
                essai.write_text(_toml(surcharges["powerups.toml"]) + "\n", encoding="utf-8")
                load_table(essai)
        except PowerUpError as exc:
            raise FicheError(f"{source} : surcharge powerups.toml : {exc}") from None
    bc = data.get("bots_cible_pct")
    bd = data.get("bots_duree_s")
    fiche = Fiche(fid, but, commandes, etapes, questions, config, duree,
                  float(bc) if bc is not None else None, float(bd) if bd is not None else None, dict(rb),
                  {k: dict(v) for k, v in surcharges.items()})
    ecarts = incoherences(fiche)
    if ecarts:
        raise FicheError(f"{source} : incohérent : " + " ; ".join(ecarts))
    return fiche


def _pcts(texte: str) -> list[float]:
    """% de la cible demandés par une consigne (`{cible}` = 100, `{cible:120}` = 120)."""
    out, i = [], 0
    while (a := texte.find("{cible", i)) >= 0:
        b = texte.find("}", a)
        if b < 0:
            break
        out.append(float(texte[a + 6:b].lstrip(":") or "100"))
        i = b + 1
    return out


# Événements que le jeu écrit vraiment au journal de séance, par sorte de ligne (contrôlés par les tests
# contre le code qui les écrit) : un déclencheur hors de cette table n'arriverait jamais (essai du 21/11 :
# « fin de l'échauffement » attendait une ligne `phase` que le journal ne recevait pas).
EVENEMENTS = {
    "event": {"start", "pause", "resume", "stop", "decrochage", "resume_after_crash"},
    "gp": {"box", "use", "hit", "warn", "parry", "steal", "finish"},
    "track": {"start", "lap", "out", "bell", "finish", "points", "lap_gained", "lap_lost", "arrival",
              "result", "timing", "sub_start", "pacer_off", "relay", "caught"},
    "rogue": {"phase", "boss_phase", "room_start", "room_won", "room_fled", "room_end", "defeat", "card_taken",
              "run_end", "room_skipped", "life_used", "balance", "perfect_shift"},
    "ftms": {"brake_loss", "power_back", "power_not_back", "status", "training_status", "resistance_weak",
             "resistance_fallback"},
}

def evenements_piste(epreuve: str) -> set[str]:
    """Événements `track` qu'une épreuve écrit vraiment (lus dans le code de sa classe et de ses parents) :
    la cloche n'existe qu'aux courses en peloton à l'arrivée (scratch, points…), pas à l'élimination."""
    import inspect
    import re

    from .. import track as track_mod
    spec = track_mod.EVENTS.get(epreuve)
    if spec is None:
        return set()
    out: set[str] = set()
    for c in spec.cls.__mro__:
        if c.__module__.startswith("openride_core.track"):
            out |= set(re.findall(r'_emit\("(\w+)"', inspect.getsource(c)))
    return out


SURCHARGES_PERMISES = ("powerups.toml",)   # fichiers de ~/OpenRide qu'un essai peut surcharger (remis après)
ECHAUFFEMENT_ESSAI_MAX_MIN = 3             # échauffement de course (#958) permis dans un essai

ECART_CONSIGNE_PCT = 10.0   # consigne du départ et effort des bots : 10 points d'écart au plus


def incoherences(f: Fiche) -> list[str]:
    """Contrôle de cohérence d'une fiche (essai du 21/11 : consigne 125 W, bots à 140 W) : une séance avec
    des bots règle leur effort sur la consigne (`bots_cible_pct`, jamais un niveau fixe en % de la FTP), et
    la consigne donnée au départ demande la même puissance que les bots, à 10 points près."""
    from ..bot_effort import OBJECTIVES
    out = []
    niveau_fixe = any((s, k) == ("bots", "level_pct") for s, k, _ in f.config)
    if f.a_des_bots:
        if f.bots_cible_pct is None:
            out.append("séance avec bots sans 'bots_cible_pct' (bots réglés sur la consigne)")
        if niveau_fixe:
            out.append("[config.bots] level_pct fixe : le niveau des bots se calcule depuis la consigne")
        if f.objectif_bots not in OBJECTIVES:
            out.append(f"objectif des bots « {f.objectif_bots} » inconnu ({', '.join(OBJECTIVES)})")
        depart = [e for e in f.etapes if e.quand.get("kind") == "event" and e.quand.get("event") == "start"]
        if f.bots_cible_pct is not None:
            for e in depart:
                for pct in _pcts(e.dire):
                    if abs(pct - f.bots_cible_pct) > ECART_CONSIGNE_PCT:
                        out.append(f"consigne du départ à {pct:.0f} % de la cible, bots à {f.bots_cible_pct:.0f} %")
    elif f.bots_cible_pct is not None or niveau_fixe:
        out.append("réglage des bots dans une séance sans bots")
    course = f.mode in ("grandprix", "survivor") or (f.mode == "track" and any(
        (a.get("track") or {}).get("event") != "free" for n, a in f.commandes if n == "start"))
    echauf = [v for sec, k, v in f.config if (sec, k) == ("depart", "echauffement_min")]
    if course and not (echauf and isinstance(echauf[0], int) and 0 <= echauf[0] <= ECHAUFFEMENT_ESSAI_MAX_MIN):
        out.append(f"course sans [config.depart] echauffement_min de 0 à {ECHAUFFEMENT_ESSAI_MAX_MIN} : "
                   "l'échauffement de 10 min (#958) mangerait l'essai")
    for n, a in f.commandes:   # bots à puissance fixe écrite en consigne : même puissance que le départ
        for b in (a.get("bots") or []) if n == "start" else []:
            pw = b.get("power_w") if isinstance(b, dict) else None
            if isinstance(pw, str) and f.bots_cible_pct is not None:
                for pct in _pcts(pw):
                    if abs(pct - f.bots_cible_pct) > ECART_CONSIGNE_PCT:
                        out.append(f"bot à {pct:.0f} % de la cible, bots_cible_pct {f.bots_cible_pct:.0f}")
    if any(n == "start_run" for n, _ in f.commandes):
        for e in f.etapes:
            if _pcts(e.dire):
                out.append("Cyber-Rogue : le jeu donne lui-même la puissance visée, pas de {cible} dans les consignes")
                break
    epreuve = next((str((a.get("track") or {}).get("event")) for n, a in f.commandes
                    if n == "start" and a.get("mode") == "track"), None)
    piste = evenements_piste(epreuve) if epreuve else None
    for e in f.etapes:
        for pred in (e.quand, e.attendu or {}):
            sorte, ev = pred.get("kind"), pred.get("event")
            if sorte in EVENEMENTS and ev is not None and ev not in EVENEMENTS[sorte]:
                out.append(f"déclencheur {sorte}/{ev} : le jeu n'écrit pas cet événement au journal")
            elif sorte == "track" and piste is not None and ev is not None and ev not in piste:
                out.append(f"déclencheur track/{ev} : l'épreuve {epreuve} n'écrit pas cet événement")
        for pct in _pcts(e.dire):
            if not 50 <= pct <= 150:
                out.append(f"consigne à {pct:.0f} % de la cible (50 à 150 %)")
    return out


def _toml(table: dict, prefixe: str = "") -> str:
    """TOML d'une table simple (nombres, chaînes, listes, sous-tables) : surcharge écrite par le guide."""
    def val(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (list, tuple)):
            return "[" + ", ".join(val(x) for x in v) + "]"
        if isinstance(v, str):
            return json.dumps(v, ensure_ascii=False)
        return repr(v)
    out = [f"{json.dumps(k) if not k.isidentifier() else k} = {val(v)}" for k, v in table.items()
           if not isinstance(v, dict)]
    for k, v in table.items():
        if isinstance(v, dict):
            out += ["", f"[{prefixe}{k}]", _toml(v, f"{prefixe}{k}.")]
    return "\n".join(out)


def niveau_bots(f: Fiche, cible_w: float, ftp_w: float) -> int:
    """`bots.level_pct` qui donne aux bots l'effort `bots_cible_pct` % de la cible : effort des bots =
    FTP × courbe(durée) × objectif × niveau (`bot_effort`), borné au réglage (50 à 150)."""
    from ..bot_effort import curve_pct, share_pct
    duree = f.bots_duree_s or float(f.duree_max_s)
    vise_w = cible_w * (f.bots_cible_pct or 100.0) / 100.0
    pleine_w = ftp_w * share_pct(f.objectif_bots) / 100.0 * curve_pct(duree) / 100.0
    return int(min(150, max(50, round(100.0 * vise_w / pleine_w)))) if pleine_w > 0 else 100


def fiches(dossier: Path = FICHES_DIR) -> dict[str, Fiche]:
    out = {}
    for p in sorted(dossier.glob("*.toml")):
        try:
            f = lire_fiche(tomllib.loads(p.read_text(encoding="utf-8")), p.name)
        except tomllib.TOMLDecodeError as exc:
            raise FicheError(f"{p.name} : {exc}") from None
        if f.id != p.stem:
            raise FicheError(f"{p.name} : id « {f.id} » différent du nom du fichier")
        out[f.id] = f
    return out


# ---------------------------------------------------------------- lignes du journal


def _cle_op(k: str) -> tuple[str, str]:
    for op in OPS:
        if k.endswith(op):
            return k[: -len(op)], op
    return k, ""


def correspond(pred: dict, ligne: dict) -> bool:
    """Vrai si la ligne du journal remplit toutes les conditions du prédicat."""
    for k, attendu in pred.items():
        cle, op = _cle_op(k)
        if cle not in ligne:
            return False
        v = ligne[cle]
        if op == "":
            ok = v == attendu
        elif op == "!=":
            ok = v != attendu
        elif not isinstance(v, (int, float)) or isinstance(v, bool):
            return False
        else:
            ok = {">=": v >= attendu, "<=": v <= attendu, ">": v > attendu, "<": v < attendu}[op]
        if not ok:
            return False
    return True


def en_watts(v: Any, cible_w: float) -> Any:
    """Arguments d'une commande avec `"{cible}"` / `"{cible:P}"` remplacés par des watts (nombre entier)."""
    if isinstance(v, dict):
        return {k: en_watts(x, cible_w) for k, x in v.items()}
    if isinstance(v, list):
        return [en_watts(x, cible_w) for x in v]
    if isinstance(v, str) and v.startswith("{cible") and v.endswith("}"):
        return int(watts(v, cible_w))
    return v


def watts(texte: str, cible_w: float) -> str:
    """`{cible}` et `{cible:PCT}` remplacés par des watts arrondis à 5 W."""
    out, i = [], 0
    while (a := texte.find("{cible", i)) >= 0:
        b = texte.find("}", a)
        if b < 0:
            break
        pct = texte[a + 6:b].lstrip(":") or "100"
        out += [texte[i:a], str(int(round(cible_w * float(pct) / 100.0 / 5.0)) * 5)]
        i = b + 1
    return "".join(out) + texte[i:]


def moyenne_reelle(journaux: Iterable[Path], n: int = 3) -> float | None:
    """Puissance moyenne en pédalant des `n` dernières séances sur le vrai trainer (source `live`)."""
    moyennes = []
    for p in sorted(journaux, key=lambda q: q.stat().st_mtime, reverse=True):
        somme, compte, live = 0.0, 0, False
        try:
            with p.open(encoding="utf-8") as fh:
                for raw in fh:
                    try:
                        d = json.loads(raw)
                    except ValueError:
                        continue
                    if d.get("kind") == "header":
                        live = d.get("source", "live") == "live"
                    elif d.get("kind") == "record" and isinstance(d.get("power"), (int, float)) and d["power"] > 20:
                        somme, compte = somme + d["power"], compte + 1
        except OSError:
            continue
        if live and compte >= 120:   # 2 min de pédalage au moins
            moyennes.append(somme / compte)
        if len(moyennes) == n:
            break
    return sum(moyennes) / len(moyennes) if moyennes else None


# ---------------------------------------------------------------- déroulé


@dataclass
class Action:
    sorte: str      # annonce | consigne | vu | rappel | saute | terrain | fin
    texte: str
    ts_jeu: float | None = None   # heure (ts) de la ligne du jeu qui l'a déclenchée : retard mesuré au PC
    t_jeu: float | None = None    # temps de séance à ce moment


class Deroule:
    """Déroulé d'une fiche, nourri ligne par ligne par le journal de séance ; module pur (testé sans jeu).

    Chaque étape suit le jeu à l'instant t (retour du 21/11 : « cette étape n'arrive pas, je passe à la
    suivante » revenait sans cesse) : toutes les étapes sont armées dès le vrai départ et chacune part au
    moment où son déclencheur arrive, dans l'ordre où le jeu les donne et non dans celui de la fiche. Deux
    étapes au même déclencheur partent à la 1re puis à la 2e occurrence (1er objet, 2e objet). Une étape
    dont le déclencheur ne vient pas se tait : rien n'est annoncé en roulant, elle est comptée à la fin.
    Une consigne liée au temps ou à la distance attend `CALME_S` après la consigne précédente."""

    CALME_S = 8.0

    def __init__(self, fiche: Fiche, cible_w: float) -> None:
        self.fiche, self.cible_w = fiche, cible_w
        self.t = 0.0                        # temps de séance (s), lu dans les lignes qui le portent
        self.parti = not any(e.quand.get("kind") == "event" and e.quand.get("event") == "start"
                             for e in fiche.etapes)
        self.faites: set[int] = set()
        self.attentes: list[list] = []      # [étape, fin du délai, rappel fait]
        self.derniere_t = -1e9
        self.fini = False
        self.vus = 0

    @property
    def i(self) -> int:
        return len(self.faites)

    @property
    def sautes(self) -> int:
        return len(self.fiche.etapes) - len(self.faites)

    def _txt(self, s: str) -> str:
        return watts(s, self.cible_w)

    def lire(self, ligne: dict) -> list[Action]:
        if self.fini:
            return []
        out: list[Action] = []
        if ligne.get("kind") == "header":
            attendu = self.fiche.route_id
            if self.fiche.monde_ouvert and not str(ligne.get("route_id") or "").startswith("ow:"):
                self.fini = True
                return [Action("terrain", f"Mauvais terrain : parcours {ligne.get('route_id')} au lieu du monde "
                                          "ouvert. J'arrête, cet essai ne compte pas.")]
            if attendu is not None and ligne.get("route_id") != attendu:   # run Cyber-Rogue : pas de parcours
                self.fini = True
                return [Action("terrain", f"Mauvais terrain : parcours {ligne.get('route_id')} au lieu de "
                                          f"{attendu}. J'arrête, cet essai ne compte pas.")]
            return out
        if ligne.get("kind") == "record" and isinstance(ligne.get("t"), (int, float)):
            self.t = max(self.t, float(ligne["t"]))   # temps de séance : seules les lignes à 1 Hz le portent
        if ligne.get("kind") == "event" and ligne.get("event") == "start":
            self.parti = True
        for att in list(self.attentes):
            etape, limite, rappele = att
            if correspond(etape.attendu or {}, ligne):
                ts = ligne.get("ts")
                out.append(Action("vu", "Vu, merci.", float(ts) if isinstance(ts, (int, float)) else None, self.t))
                self.vus += 1
                self.attentes.remove(att)
            elif self.t >= limite:
                if not rappele:
                    out.append(Action("rappel", self._txt(etape.rappel or etape.dire)))
                    att[1], att[2] = self.t + etape.delai_s, True
                else:
                    self.attentes.remove(att)
        if self.parti:
            evenement = ligne.get("kind") != "record"
            for k, etape in enumerate(self.fiche.etapes):
                if k in self.faites or not correspond(etape.quand, ligne):
                    continue
                if not evenement and self.t - self.derniere_t < self.CALME_S:
                    break                       # repris à la ligne suivante : un record vaut encore
                self.faites.add(k)
                self.derniere_t = self.t
                ts = ligne.get("ts")
                out.append(Action("consigne", self._txt(etape.dire),
                                  float(ts) if isinstance(ts, (int, float)) else None, self.t))
                if etape.attendu:
                    self.attentes.append([etape, self.t + etape.delai_s, False])
                break                           # une seule consigne par ligne du jeu
        if self.t >= self.fiche.duree_max_s or (ligne.get("kind") == "event" and ligne.get("event") == "stop"):
            self.fini = True
            out.append(Action("fin", "Stop. Arrête de pédaler, j'enregistre et je ferme le jeu."))
        return out


# ---------------------------------------------------------------- entrées-sorties (sur le PC)


def _voix() -> list[str] | None:
    if shutil.which("spd-say"):
        return ["spd-say", "-l", "fr", "-r", "10"]
    for exe in ("espeak-ng", "espeak"):
        if shutil.which(exe):
            return [exe, "-v", "fr", "-s", "165"]
    return None


SONS = {"consigne": "/usr/share/sounds/freedesktop/stereo/bell.oga",
        "vu": "/usr/share/sounds/freedesktop/stereo/complete.oga",
        "fin": "/usr/share/sounds/freedesktop/stereo/complete.oga"}


class Sortie:
    """Voix, son différent pour « vu », bandeau dans le jeu (fichier lu par l'engine, lot EP3) et terminal."""

    def __init__(self, bandeau: Path | None, muet: bool = False) -> None:
        self.voix = None if muet else _voix()
        self.bandeau, self.muet, self.n = bandeau, muet, 0

    def __call__(self, a: Action) -> None:
        print(f"  [{a.sorte}] {a.texte}", flush=True)
        if self.muet:
            return
        son = SONS.get(a.sorte, SONS["consigne"])
        if Path(son).exists() and shutil.which("paplay"):
            subprocess.Popen(["paplay", son], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if self.voix:
            subprocess.Popen(self.voix + [a.texte], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if self.bandeau is not None:
            self.n += 1
            tmp = self.bandeau.with_suffix(".tmp")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps({"id": self.n, "texte": a.texte, "sorte": a.sorte, "duree_s": 8}),
                           encoding="utf-8")
            tmp.replace(self.bandeau)


def suivre(chemin: Path, arret: Any) -> Iterator[dict]:
    """Lignes du journal au fur et à mesure qu'elles sont écrites, jusqu'à `arret()`."""
    with chemin.open(encoding="utf-8") as fh:
        reste = ""
        while not arret():
            bloc = fh.readline()
            if not bloc:
                time.sleep(0.3)
                continue
            reste += bloc
            if not reste.endswith("\n"):
                continue
            try:
                yield json.loads(reste)
            except ValueError:
                pass
            reste = ""


def journal_neuf(dossier: Path, depuis: float) -> Path | None:
    neufs = [p for p in dossier.glob("*.jsonl") if p.stat().st_mtime >= depuis]
    return max(neufs, key=lambda p: p.stat().st_mtime) if neufs else None


def lancer(fiche: Fiche, profil: str, sim: bool, cible: float | None, muet: bool = False) -> int:
    from .. import config_edit
    from .. import config as config_mod
    from ..profiles import ProfileContext

    ctx = ProfileContext.for_id(profil)
    cible_w = cible or moyenne_reelle(ctx.journal_dir.glob("*.jsonl")) or CIBLE_DEFAUT_W
    essais = config_mod.OPENRIDE_HOME / "Essais"
    sortie = Sortie(essais / "consigne_directe.json", muet)
    print(f"\n=== Essai {fiche.id} ===\n  Ce qu'il teste : {fiche.but}\n  Cible : {cible_w:.0f} W\n")
    sortie(Action("annonce", f"Essai {fiche.id}. Ce qu'il teste : {fiche.but}"))
    seance = essais / f"seance_{fiche.id}.json"
    seance.parent.mkdir(parents=True, exist_ok=True)
    seance.write_text(json.dumps({"id": fiche.id, "but": fiche.but, "commandes": [
        {"cmd": n, "args": en_watts(a, cible_w)} for n, a in fiche.commandes]}, ensure_ascii=False),
        encoding="utf-8")
    config_path, profil_path = config_mod.DEFAULT_CONFIG_PATH, ctx.root / "profil.toml"
    fichiers = [config_mod.OPENRIDE_HOME / nom for nom in fiche.surcharges]
    sauvegardes = {p: (p.read_bytes() if p.exists() else None) for p in (config_path, profil_path, *fichiers)}
    deroule = Deroule(fiche, cible_w)
    reglages = list(fiche.config)
    if fiche.a_des_bots and fiche.bots_cible_pct is not None:
        ftp_w = float(config_mod.load(config_path, profil_path if profil_path.exists() else None).rider.ftp_w)
        niveau = niveau_bots(fiche, cible_w, ftp_w)
        reglages.append(("bots", "level_pct", niveau))
        print(f"  Bots : {fiche.objectif_bots}, réglés sur {watts('{cible:%g}' % fiche.bots_cible_pct, cible_w)} W "
              f"(niveau {niveau} %)\n")
    proc = None
    retards: list[tuple[float, float, str]] = []
    try:
        if reglages:
            config_edit.update_layers(reglages, config_path, profil_path)
        for nom, table in fiche.surcharges.items():   # posée par-dessus le fichier du joueur, remis après
            p = config_mod.OPENRIDE_HOME / nom
            base = tomllib.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
            for sec, val in table.items():
                base[sec] = {**base.get(sec, {}), **val} if isinstance(val, dict) else val
            p.write_text(_toml(base) + "\n", encoding="utf-8")
        materiel = ["--trainer", "sim", "--input", "sim", "--hr", "sim"] if sim else ["--trainer", "ftms",
                                                                                     "--input", "click"]
        depart = time.time() - 1
        env = dict(os.environ)
        if fiche.rogue_balance:
            from ..rogue.balance import ESSAI_ENV
            table = essais / f"rogue_balance_{fiche.id}.toml"
            table.write_text(_toml(fiche.rogue_balance) + "\n", encoding="utf-8")
            env[ESSAI_ENV] = str(table)
        proc = subprocess.Popen([sys.executable, "-m", "openride_core.launcher", "--no-compile", *materiel,
                                 "--profil", profil, "--autostart", "--seance", str(seance)],
                                start_new_session=True, env=env)
        sortie(Action("annonce", "Le jeu se lance sur le bon terrain. Pédale dès que le parcours s'affiche."
                      + (" Le monde se prépare d'abord, une à deux minutes." if fiche.monde_ouvert else "")))
        chemin = None
        while chemin is None:
            if proc.poll() is not None:
                print("  Le jeu s'est arrêté avant la séance : voir ~/run_trainer.log.")
                return 1
            if time.time() - depart > (600 if fiche.monde_ouvert else 300):   # monde ouvert : génération
                print("  Pas de journal de séance à temps : j'arrête.")
                return 1
            chemin = journal_neuf(ctx.journal_dir, depart)
            time.sleep(1.0)
        for ligne in suivre(chemin, lambda: deroule.fini or proc.poll() is not None):
            for a in deroule.lire(ligne):
                if a.ts_jeu is not None:   # retard entre l'instant du jeu et la consigne dite
                    retards.append((a.t_jeu or 0.0, time.time() - a.ts_jeu, a.texte))
                sortie(a)
    finally:
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)   # arrêt propre du lanceur : séance enregistrée
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
        for p, contenu in sauvegardes.items():
            if contenu is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(contenu)
    lignes = [f"[{dt.datetime.now():%Y-%m-%d %H:%M}] {fiche.id} : {deroule.i}/{len(fiche.etapes)} étapes, "
              f"{deroule.vus} vues, {deroule.sautes} jamais venues, {deroule.t:.0f} s de séance, cible {cible_w:.0f} W"]
    for t_jeu, retard, texte in retards:
        lignes.append(f"  t={t_jeu:5.0f} s  retard {retard:4.1f} s  {texte}")
    if retards:
        print(f"  Retard des consignes sur le jeu : au plus {max(r for _, r, _ in retards):.1f} s.")
    for k, e in enumerate(fiche.etapes):
        if k not in deroule.faites:
            lignes.append(f"  jamais venue : {e.dire} (quand {e.quand})")
    for q in fiche.questions:
        try:
            r = input(f"  ? {q}\n    > ").strip()
        except EOFError:
            r = ""
        lignes.append(f"{q} -> {r}")
    with (essais / "essais.txt").open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lignes) + "\n\n")
    print(f"\n  Noté dans {essais / 'essais.txt'}.")
    return 0


def rejouer(fiche: Fiche, journal: Path, cible_w: float = CIBLE_DEFAUT_W) -> list[str]:
    """Rejoue un journal de séance réel dans le déroulé : instant de chaque consigne (temps de séance) et
    étapes jamais venues ; le banc qui vérifie qu'une fiche suit vraiment le jeu."""
    d = Deroule(fiche, cible_w)
    out = []
    with journal.open(encoding="utf-8") as fh:
        for raw in fh:
            try:
                ligne = json.loads(raw)
            except ValueError:
                continue
            for a in d.lire(ligne):
                if a.sorte in ("consigne", "vu", "rappel", "terrain", "fin"):
                    out.append(f"t={d.t:5.0f} s  [{a.sorte}] {a.texte}")
            if d.fini:
                break
    for k, e in enumerate(fiche.etapes):
        if k not in d.faites:
            out.append(f"jamais venue : {e.dire} (quand {e.quand})")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="essai_physique", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("liste", help="fiches disponibles et ce qu'elles testent")
    v = sub.add_parser("voir", help="déroulé d'une fiche, sans rien lancer")
    v.add_argument("id")
    lc = sub.add_parser("lancer", help="lance l'essai : jeu verrouillé, consignes du jeu, questions")
    lc.add_argument("id")
    lc.add_argument("--profil", default="principal")
    lc.add_argument("--sim", action="store_true", help="matériel simulé (essai à blanc, sans vélo)")
    lc.add_argument("--cible", type=float, help="cible en watts (défaut : moyenne réelle des 3 dernières séances)")
    lc.add_argument("--muet", action="store_true")
    rj = sub.add_parser("rejouer", help="rejoue un journal de séance (.jsonl) : instant de chaque consigne")
    rj.add_argument("id")
    rj.add_argument("journal", type=Path)
    args = p.parse_args(argv)
    try:
        toutes = fiches()
    except FicheError as exc:
        print(f"essai_physique : {exc}", file=sys.stderr)
        return 1
    if args.cmd == "liste":
        for f in toutes.values():
            print(f"{f.id:24s} {f.but}")
        return 0
    if args.id not in toutes:
        print(f"essai_physique : fiche « {args.id} » inconnue ({', '.join(toutes)})", file=sys.stderr)
        return 2
    f = toutes[args.id]
    if args.cmd == "voir":
        print(f"{f.id} : {f.but}\nTerrain : {f.route_id or ('monde ouvert' if f.monde_ouvert else 'run Cyber-Rogue')}, {f.duree_max_s // 60} min au plus")
        for i, e in enumerate(f.etapes, 1):
            print(f"  {i}. quand {e.quand} : {e.dire}" + (f"  (attendu {e.attendu})" if e.attendu else ""))
        for q in f.questions:
            print(f"  ? {q}")
        return 0
    if args.cmd == "rejouer":
        print("\n".join(rejouer(f, args.journal)))
        return 0
    return lancer(f, args.profil, args.sim, args.cible, args.muet)


if __name__ == "__main__":
    raise SystemExit(main())
