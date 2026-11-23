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
   Une étape dont le déclencheur ne vient pas (`attente_max_s` de séance) est annoncée et sautée.
4. Au plus 10 min de **pédalage réel** (temps de séance `t` du journal) : le guide arrête OpenRide (la
   séance est enregistrée), remet les réglages, puis pose 2 ou 3 questions notées dans `essais.txt`.

Consignes en watts directs : `{cible}` (moyenne réelle des 3 dernières séances sur le vrai trainer, lue
sur le PC et jamais écrite dans le dépôt), `{cible:120}` (120 % de la cible), arrondis à 5 W.

Déclencheurs et attendus : une table qui doit correspondre à une ligne du journal ; chaque clé est égale,
ou porte un opérateur en suffixe (`"distance>=" = 500`, `"phase!=" = "WARMUP"`, `"t<=" = 30`).

    python -m openride_core.tools.essai_physique liste
    python -m openride_core.tools.essai_physique voir gp-voies
    python -m openride_core.tools.essai_physique lancer gp-voies [--profil principal] [--sim] [--cible 120]
    python -m openride_core.tools.essai_physique restaurer      # réglages remis après un essai coupé

Réglages du joueur (revue de code C7-02) : avant d'écrire les réglages `[config]` d'une fiche, le guide
copie `config.toml` et `profil.toml` dans `~/OpenRide/Essais/sauvegarde_reglages/` avec un marqueur ;
il les remet à la fin, sur Ctrl+C, sur SIGTERM et sur SIGHUP (terminal fermé). Si le guide est tué
sans pouvoir les remettre (SIGKILL, PC éteint), le prochain `lancer` ou `restaurer` le fait.
Une fiche sans `[config]` ne touche à aucun fichier du joueur.

Essai à blanc (`--sim`, revue de code C7-03) : il roule sur le profil d'essai `_essai` par défaut et
il est refusé sur un profil de joueur, pour qu'aucune séance simulée n'aille dans le vrai profil.
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
from ..rogue.mode import JOURNAL_ROUTE_ID

FICHES_DIR = Path(__file__).resolve().parents[1] / "data" / "essais"
DUREE_MAX_S = 600                 # règle du propriétaire : 10 min de pédalage au plus par séance
ATTENTE_MAX_S = 180.0             # étape sautée si son déclencheur ne vient pas en 3 min de séance
DELAI_ATTENDU_S = 30.0            # temps laissé pour faire l'action demandée, avant le rappel
QUESTIONS_MAX = 3
CIBLE_DEFAUT_W = 100              # sans séance réelle au journal (premier essai)
OPS = (">=", "<=", "!=", ">", "<")
SAUVEGARDE_DIR = "sauvegarde_reglages"   # sous ~/OpenRide/Essais : copie des réglages du joueur (C7-02)
MARQUEUR = "en_cours.json"               # présent tant que les réglages de la fiche sont posés
PROFIL_REEL_DEFAUT = "principal"


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

    @property
    def route_id(self) -> str | None:
        """Parcours attendu à l'en-tête du journal (`None` pour une run Cyber-Rogue, sans parcours)."""
        for name, args in self.commandes:
            if name == "select_route":
                return str(args.get("route_id"))
        return None

    @property
    def route_journal(self) -> str:
        """`route_id` que la séance écrit à l'en-tête du journal (C7-01) : celui de la run Cyber-Rogue
        (`rogue.mode.JOURNAL_ROUTE_ID`) pour une fiche sans `select_route`."""
        rid = self.route_id
        return rid if rid is not None else JOURNAL_ROUTE_ID


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
    return Fiche(fid, but, commandes, etapes, questions, config, duree)


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


class Deroule:
    """Déroulé d'une fiche, nourri ligne par ligne par le journal de séance ; module pur (testé sans jeu)."""

    def __init__(self, fiche: Fiche, cible_w: float) -> None:
        self.fiche, self.cible_w = fiche, cible_w
        self.i = 0                          # étape attendue
        self.t = 0.0                        # temps de séance (s), lu dans les lignes qui le portent
        self.t_etape = 0.0                  # début de l'attente de l'étape en cours
        self.en_attente: tuple[Etape, float, bool] | None = None   # étape donnée, fin du délai, rappel fait
        self.fini = False
        self.vus = self.sautes = 0

    def _txt(self, s: str) -> str:
        return watts(s, self.cible_w)

    def lire(self, ligne: dict) -> list[Action]:
        if self.fini:
            return []
        out: list[Action] = []
        if ligne.get("kind") == "header":
            attendu = self.fiche.route_journal
            if ligne.get("route_id") != attendu:
                self.fini = True
                return [Action("terrain", f"Mauvais terrain : parcours {ligne.get('route_id')} au lieu de "
                                          f"{attendu}. J'arrête, cet essai ne compte pas.")]
            return out
        if ligne.get("kind") == "record" and isinstance(ligne.get("t"), (int, float)):
            self.t = max(self.t, float(ligne["t"]))   # temps de séance : seules les lignes à 1 Hz le portent
        if self.en_attente is not None:
            etape, limite, rappele = self.en_attente
            if correspond(etape.attendu or {}, ligne):
                out.append(Action("vu", "Vu, merci."))
                self.vus += 1
                self._suivante()
            elif self.t >= limite:
                if rappele:
                    self._suivante()
                else:
                    out.append(Action("rappel", self._txt(etape.rappel or etape.dire)))
                    self.en_attente = (etape, self.t + etape.delai_s, True)
        if self.en_attente is None and self.i < len(self.fiche.etapes):
            etape = self.fiche.etapes[self.i]
            if correspond(etape.quand, ligne):
                out.append(Action("consigne", self._txt(etape.dire)))
                if etape.attendu:
                    self.en_attente = (etape, self.t + etape.delai_s, False)
                else:
                    self._suivante()
            elif self.t - self.t_etape >= etape.attente_max_s:
                out.append(Action("saute", "Cette étape n'arrive pas, je passe à la suivante."))
                self.sautes += 1
                self._suivante()
        if self.t >= self.fiche.duree_max_s or (ligne.get("kind") == "event" and ligne.get("event") == "stop"):
            self.fini = True
            out.append(Action("fin", "Stop. Arrête de pédaler, j'enregistre et je ferme le jeu."))
        return out

    def _suivante(self) -> None:
        self.en_attente = None
        self.i += 1
        self.t_etape = self.t


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


def sauvegarder_reglages(fichiers: list[Path], essais: Path) -> Path:
    """Copie sur disque des réglages du joueur avant d'y écrire ceux d'une fiche (C7-02).

    Le marqueur, écrit en dernier, liste chaque fichier, son original et s'il existait : tant qu'il est là,
    `restaurer_reglages` sait remettre les fichiers, même après un guide tué sans `finally`.
    """
    dossier = essais / SAUVEGARDE_DIR
    dossier.mkdir(parents=True, exist_ok=True)
    entrees = []
    for i, f in enumerate(fichiers):
        copie = dossier / f"{i}_{f.name}"
        existait = f.is_file()
        if existait:
            tmp = copie.with_suffix(copie.suffix + ".tmp")
            shutil.copy2(f, tmp)
            os.replace(tmp, copie)
        entrees.append({"fichier": str(f), "copie": str(copie), "existait": existait})
    marqueur = dossier / MARQUEUR
    tmp = marqueur.with_suffix(".tmp")
    tmp.write_text(json.dumps({"date": dt.datetime.now().isoformat(timespec="seconds"), "fichiers": entrees},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, marqueur)
    return marqueur


def restaurer_reglages(essais: Path) -> list[str]:
    """Réglages d'avant l'essai remis (écriture atomique), puis copie et marqueur retirés ; [] sans marqueur."""
    dossier = essais / SAUVEGARDE_DIR
    marqueur = dossier / MARQUEUR
    try:
        data = json.loads(marqueur.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        return [f"Marqueur illisible ({marqueur}) : {exc} ; réglages non remis, copies gardées dans {dossier}."]
    faits = []
    for e in data.get("fichiers", []):
        f, copie = Path(e["fichier"]), Path(e["copie"])
        if e.get("existait"):
            if not copie.is_file():
                faits.append(f"Copie introuvable : {copie} ; {f} laissé tel quel.")
                continue
            tmp = f.with_name(f.name + ".essai.tmp")
            shutil.copy2(copie, tmp)
            os.replace(tmp, f)
            copie.unlink(missing_ok=True)
            faits.append(f"Remis : {f}")
        elif f.exists():
            f.unlink()
            faits.append(f"Retiré (absent avant l'essai) : {f}")
    marqueur.unlink(missing_ok=True)
    return faits


class _Coupe(KeyboardInterrupt):
    """SIGTERM ou SIGHUP reçu pendant l'essai : traité comme Ctrl+C, pour que le `finally` remette tout."""


def _sur_signal(signum: int, _frame: Any) -> None:
    raise _Coupe(signal.Signals(signum).name)


def profil_par_defaut(sim: bool) -> str:
    """`_essai` pour un essai à blanc, le profil du joueur sinon (C7-03)."""
    from ..profiles import TRIAL_ID

    return TRIAL_ID if sim else PROFIL_REEL_DEFAUT


def lancer(fiche: Fiche, profil: str, sim: bool, cible: float | None, muet: bool = False) -> int:
    from .. import config_edit
    from .. import config as config_mod
    from ..profiles import ProfileContext

    ctx = ProfileContext.for_id(profil)
    if sim and not ctx.is_trial:
        print(f"essai_physique : essai à blanc (--sim) refusé sur le profil de joueur « {profil} » : "
              f"ses séances simulées iraient dans ce profil. Lance-le sans --profil (profil d'essai).",
              file=sys.stderr)
        return 2
    essais = config_mod.OPENRIDE_HOME / "Essais"
    for ligne in restaurer_reglages(essais):   # essai précédent coupé sans remise (C7-02)
        print(f"  Essai précédent : {ligne}")
    cible_w = cible or moyenne_reelle(ctx.journal_dir.glob("*.jsonl")) or CIBLE_DEFAUT_W
    sortie = Sortie(essais / "consigne_directe.json", muet)
    print(f"\n=== Essai {fiche.id} ===\n  Ce qu'il teste : {fiche.but}\n  Cible : {cible_w:.0f} W\n")
    sortie(Action("annonce", f"Essai {fiche.id}. Ce qu'il teste : {fiche.but}"))
    seance = essais / f"seance_{fiche.id}.json"
    seance.parent.mkdir(parents=True, exist_ok=True)
    seance.write_text(json.dumps({"id": fiche.id, "but": fiche.but, "commandes": [
        {"cmd": n, "args": a} for n, a in fiche.commandes]}, ensure_ascii=False), encoding="utf-8")
    config_path, profil_path = config_mod.DEFAULT_CONFIG_PATH, ctx.root / "profil.toml"
    deroule = Deroule(fiche, cible_w)
    proc = None
    anciens: dict[int, Any] = {}
    for sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            anciens[sig] = signal.signal(sig, _sur_signal)
        except ValueError:   # hors du fil principal : le marqueur et `restaurer` restent le filet
            pass
    try:
        if fiche.config:
            sauvegarder_reglages([config_path, profil_path], essais)   # sur disque avant toute écriture
            config_edit.update_layers(fiche.config, config_path, profil_path)
        materiel = ["--trainer", "sim", "--input", "sim", "--hr", "sim"] if sim else ["--trainer", "ftms",
                                                                                     "--input", "click"]
        depart = time.time() - 1
        proc = subprocess.Popen([sys.executable, "-m", "openride_core.launcher", "--no-compile", *materiel,
                                 "--profil", profil, "--autostart", "--seance", str(seance)],
                                start_new_session=True)
        sortie(Action("annonce", "Le jeu se lance sur le bon terrain. Pédale dès que le parcours s'affiche."))
        chemin = None
        while chemin is None:
            if proc.poll() is not None:
                print("  Le jeu s'est arrêté avant la séance : voir ~/run_trainer.log.")
                return 1
            if time.time() - depart > 300:
                print("  Pas de journal de séance après 5 min : j'arrête.")
                return 1
            chemin = journal_neuf(ctx.journal_dir, depart)
            time.sleep(1.0)
        for ligne in suivre(chemin, lambda: deroule.fini or proc.poll() is not None):
            for a in deroule.lire(ligne):
                sortie(a)
    except _Coupe as exc:
        print(f"\n  Guide arrêté ({exc}) : jeu fermé, réglages remis.")
        return 1
    finally:
        try:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)   # arrêt propre du lanceur : séance enregistrée
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
        finally:   # même si un 2e Ctrl+C tombe pendant l'arrêt du jeu ; sinon `restaurer` le fera
            for ligne in restaurer_reglages(essais):
                print(f"  {ligne}")
            for sig, h in anciens.items():
                signal.signal(sig, h)
    lignes = [f"[{dt.datetime.now():%Y-%m-%d %H:%M}] {fiche.id} : {deroule.i}/{len(fiche.etapes)} étapes, "
              f"{deroule.vus} vues, {deroule.sautes} sautées, {deroule.t:.0f} s de séance, cible {cible_w:.0f} W"]
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="essai_physique", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("liste", help="fiches disponibles et ce qu'elles testent")
    v = sub.add_parser("voir", help="déroulé d'une fiche, sans rien lancer")
    v.add_argument("id")
    lc = sub.add_parser("lancer", help="lance l'essai : jeu verrouillé, consignes du jeu, questions")
    lc.add_argument("id")
    lc.add_argument("--profil", default=None,
                    help=f"profil (défaut : {PROFIL_REEL_DEFAUT}, ou le profil d'essai avec --sim)")
    lc.add_argument("--sim", action="store_true",
                    help="matériel simulé (essai à blanc, sans vélo), sur le profil d'essai seulement")
    sub.add_parser("restaurer", help="remet les réglages du joueur après un essai coupé (terminal fermé, PC éteint)")
    lc.add_argument("--cible", type=float, help="cible en watts (défaut : moyenne réelle des 3 dernières séances)")
    lc.add_argument("--muet", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "restaurer":   # avant la lecture des fiches : marche même si une fiche est cassée
        from .. import config as config_mod

        for ligne in restaurer_reglages(config_mod.OPENRIDE_HOME / "Essais") or ["Rien à restaurer."]:
            print(ligne)
        return 0
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
        print(f"{f.id} : {f.but}\nTerrain : {f.route_id or 'run Cyber-Rogue'}, {f.duree_max_s // 60} min au plus")
        for i, e in enumerate(f.etapes, 1):
            print(f"  {i}. quand {e.quand} : {e.dire}" + (f"  (attendu {e.attendu})" if e.attendu else ""))
        for q in f.questions:
            print(f"  ? {q}")
        return 0
    return lancer(f, args.profil or profil_par_defaut(args.sim), args.sim, args.cible, args.muet)


if __name__ == "__main__":
    raise SystemExit(main())
