#!/usr/bin/env python3
"""File des bancs du PC en étapes courtes, avec reprise (plan du 19 novembre, « échecs partiels »).

Un échec partiel ne doit plus coûter un rebanc de plusieurs heures. La file est décrite dans un fichier TOML :
une entrée par PR, découpée en étapes courtes (une qualité, une tête) ; chaque verdict est écrit au fil de
l'eau dans `etat.json`, et une étape OK sur la même tête n'est jamais rejouée.

    scripts/file_bancs.py lancer file.toml          # fumées de toute la file, puis longues étapes (risque d'abord)
    scripts/file_bancs.py relancer file.toml --pr r907   # seulement les étapes en échec, fumée avant
    scripts/file_bancs.py etat file.toml            # tableau PR × étape (aussi dans etat.md)
    scripts/file_bancs.py lancer file.toml --seulement-fumees

Format de la file :

    [file]
    depot = "~/Games/lolo_python"            # dépôt d'où partent les worktrees (reste sur main, propre)
    sortie = "~/OpenRide/file/nuit-20nov"    # etat.json, etat.md, un dossier par étape, worktrees/, caches/

    avant_etape = "~/outils/portail.sh"     # facultatif : code 0 = on y va ; sinon la file attend et réessaie
                                             # toutes les `attente_s` (60) s : fenêtre de pause du user, Godot ouvert
    apres_etape = "~/outils/pousse_auto.sh {dossier} {pr} {etape} {verdict}"   # facultatif : poussage anonymisé

    [[pr]]
    id = "r907"                  # nom court de la PR dans la file
    pr = 907
    branche = "claude/project-thread-xxxxxx"
    tete = "602eaf1b"            # facultatif : la tête attendue ; la file refuse une autre tête
    risque = 1                   # 1 jamais tourné / cache / départ / format, 2 déjà échoué, 3 confirmation
    cache = "separe"             # "reel" (défaut) ou "separe" : copie du cache du monde ouvert, propre à la PR
    assemblage = []              # facultatif : branches fusionnées par-dessus, en local (essai assemblé, ex. essai-ow)
    fumee = "python3 engine/tests/menu_bench.py --native --scenario w23_mer --qualite low --voies clavier --out {sortie}"
    fumee_delai_min = 8

    [[pr.etape]]
    id = "low"
    commande = "python3 engine/tests/menu_bench.py --native --scenario w23_mer --qualite low --out {sortie}"
    delai_min = 60

    [[pr.etape]]
    id = "main-low"
    sur = "main"                 # dans un worktree de main ; verdict commun à toute la file pour ce commit
    commande = "python3 engine/tests/menu_bench.py --native --scenario w17_cap --qualite low --out {sortie}"

Les commandes tournent dans `<worktree>/Open_ride_linux`, avec `{sortie}` (dossier de l'étape), `{worktree}` et
`{projet}`, `{depot}` (le dépôt du user, pour son environnement Python) remplacés ; chaque étape a PYTHONPATH sur
les sources du worktree (core et compilateur), le core/.venv du dépôt en tête du PATH (lié dans le worktree),
LC_NUMERIC=C et OPENRIDE_NO_GUI=1, comme job.sh ; le portail reçoit FILE_PR,
FILE_ETAPE et FILE_DUREE_MIN (délai de l'étape, pour ne pas déborder sur la fenêtre du user). Verdicts :
- OK ; CONTACTS : seules des vérifications de contacts ont échoué (non bloquant, lot AS11) ;
- ÉCHEC : une vérification du jeu ; DÉLAI : étape arrêtée au bout de `delai_min` ;
- ENVIRONNEMENT : le PC, pas la PR (code 2 des bancs, cache au mauvais schéma, réseau, disque plein) ;
- BLOQUÉ : non jouée car la fumée de la PR n'est pas passée.
Têtes relues (git fetch) avant les étapes de chaque PR ; une tête différente de `tete` donne ENVIRONNEMENT.
Une PR dont le `SCHEMA_VERSION` du cache diffère de main ne tourne jamais sur le cache réel : sans `cache = "separe"`,
ses étapes sont refusées (ENVIRONNEMENT) sans être lancées.
Reprise : `lancer` rejoue tout ce qui n'est pas OK ou CONTACTS sur la tête actuelle ; `relancer` rejoue seulement
les étapes en échec (les OK d'une tête précédente restent acquises et sont marquées « sur tête X »).
Pause : un fichier `PAUSE` dans le dossier de sortie arrête la file avant l'étape suivante (« PC libre ») ;
Ctrl-C ou SIGTERM arrête l'étape en cours sans verdict. Code de sortie : 0 si rien n'est en ÉCHEC, DÉLAI ni
ENVIRONNEMENT, 1 sinon, 2 si l'appel ou la file est invalide, 3 si la file est en pause. Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

OK, CONTACTS, ECHEC, DELAI, ENV, BLOQUE, A_FAIRE = "OK", "CONTACTS", "ÉCHEC", "DÉLAI", "ENVIRONNEMENT", "BLOQUÉ", "À FAIRE"
ACQUIS = (OK, CONTACTS)                       # verdicts qui ne se rejouent pas sur la même tête
EN_ECHEC = (ECHEC, DELAI, ENV)
FUMEE = "fumee"
CACHES = ("reel", "separe")
CODE_ENV_BANCS = 2                            # menu_bench, sim_bench, recette_pc : Godot ou xvfb-run absent
LIGNE_ECHEC = re.compile(r"^\[ÉCHEC\] (.*)$", re.M)
CONTACT = re.compile(r"contact", re.I)
# Défauts du PC, pas de la PR : une seule réparation, puis seules les étapes touchées sont rejouées.
MOTIFS_ENV = (
    re.compile(r"schéma \S+ au lieu de \S+"),            # cache du monde ouvert au mauvais format (17 novembre)
    re.compile(r"cache réel au schéma"),                  # garde-fou de menu_bench
    re.compile(r"Godot introuvable|xvfb-run introuvable"),
    re.compile(r"No space left on device|Aucun espace disponible"),
    re.compile(r"Temporary failure in name resolution|Network is unreachable|Name or service not known"),
)


class FileInvalide(Exception):
    """Fichier de file mal formé."""


class Assemblage(Exception):
    """Essai assemblé impossible : fusion des branches en conflit."""


class TeteChangee(Exception):
    """La tête de la PR n'est plus celle que la file attend."""


# --- file ----------------------------------------------------------------------------------------

@dataclass
class Etape:
    id: str
    commande: str
    delai_min: float = 60.0
    sur: str = "branche"                      # "branche" ou "main"

    @property
    def empreinte(self) -> str:
        return hashlib.sha1(self.commande.encode()).hexdigest()[:10]


@dataclass
class PR:
    id: str
    branche: str
    pr: int | None = None
    tete: str | None = None
    risque: int = 2
    cache: str = "reel"
    etapes: list[Etape] = field(default_factory=list)
    rang: int = 0                              # ordre d'écriture dans la file, à risque égal
    assemblage: list[str] = field(default_factory=list)   # branches fusionnées par-dessus (essai assemblé)


@dataclass
class File:
    depot: Path
    sortie: Path
    prs: list[PR]
    avant_etape: str | None = None             # portail : code 0 = on y va, sinon on attend (fenêtre du user, Godot)
    apres_etape: str | None = None             # après chaque étape (poussage anonymisé des résultats)
    attente_s: float = 60.0

    def par_risque(self) -> list[PR]:
        return sorted(self.prs, key=lambda p: (p.risque, p.rang))


def lire_file(chemin: Path) -> File:
    try:
        doc = tomllib.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise FileInvalide(f"{chemin} : {exc}") from exc
    tete = doc.get("file", {})
    depot = Path(str(tete.get("depot", Path.cwd()))).expanduser()
    sortie = Path(str(tete.get("sortie", chemin.with_suffix("")))).expanduser()
    prs: list[PR] = []
    vus: set[str] = set()
    for rang, d in enumerate(doc.get("pr", [])):
        pid, branche = d.get("id"), d.get("branche")
        if not pid or not branche:
            raise FileInvalide(f"entrée [[pr]] n° {rang + 1} : `id` et `branche` obligatoires")
        if pid in vus or pid == "main":
            raise FileInvalide(f"identifiant de PR en double ou réservé : {pid}")
        vus.add(pid)
        cache = d.get("cache", "reel")
        if cache not in CACHES:
            raise FileInvalide(f"{pid} : cache « {cache} » inconnu ({', '.join(CACHES)})")
        etapes = []
        if d.get("fumee"):
            etapes.append(Etape(FUMEE, str(d["fumee"]), float(d.get("fumee_delai_min", 8))))
        for e in d.get("etape", []):
            if not e.get("id") or not e.get("commande") or e["id"] == FUMEE:
                raise FileInvalide(f"{pid} : chaque [[pr.etape]] a un `id` (pas « {FUMEE} ») et une `commande`")
            sur = e.get("sur", "branche")
            if sur not in ("branche", "main"):
                raise FileInvalide(f"{pid}/{e['id']} : `sur` vaut « branche » ou « main »")
            etapes.append(Etape(str(e["id"]), str(e["commande"]), float(e.get("delai_min", 60)), sur))
        if len({e.id for e in etapes}) != len(etapes):
            raise FileInvalide(f"{pid} : identifiants d'étape en double")
        assemblage = [str(b) for b in d.get("assemblage", [])]
        prs.append(PR(str(pid), str(branche), d.get("pr"), d.get("tete"), int(d.get("risque", 2)), cache, etapes, rang,
                      assemblage))
    if not prs:
        raise FileInvalide(f"{chemin} : aucune entrée [[pr]]")
    return File(depot, sortie, prs, tete.get("avant_etape"), tete.get("apres_etape"), float(tete.get("attente_s", 60)))


# --- état ----------------------------------------------------------------------------------------

class Etat:
    """etat.json : {"prs": {pr: {etape: verdict}}, "main": {empreinte: verdict}} ; écrit après chaque étape."""

    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin
        self.data: dict[str, Any] = {"prs": {}, "main": {}}
        if chemin.is_file():
            self.data = json.loads(chemin.read_text(encoding="utf-8"))
            self.data.setdefault("prs", {})
            self.data.setdefault("main", {})

    def get(self, pr: PR, e: Etape) -> dict[str, Any] | None:
        if e.sur == "main":
            return self.data["main"].get(e.empreinte)
        return self.data["prs"].get(pr.id, {}).get(e.id)

    def put(self, pr: PR, e: Etape, verdict: dict[str, Any]) -> None:
        if e.sur == "main":
            self.data["main"][e.empreinte] = verdict
        else:
            self.data["prs"].setdefault(pr.id, {})[e.id] = verdict
        self.save()

    def save(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.chemin.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.chemin)


# --- verdict d'une étape -------------------------------------------------------------------------

def classer(code: int, journal: str) -> tuple[str, str]:
    """(verdict, détail) d'une étape terminée, d'après son code de sortie et son journal."""
    if code == 0:
        return OK, ""
    for motif in MOTIFS_ENV:
        m = motif.search(journal)
        if m:
            return ENV, m.group(0)
    if code == CODE_ENV_BANCS:
        return ENV, f"code {code} (outil ou affichage absent)"
    echecs = LIGNE_ECHEC.findall(journal)          # « [ÉCHEC] libellé : mesure » de menu_bench et sim_bench
    if echecs and all(CONTACT.search(ligne) for ligne in echecs):
        return CONTACTS, f"{len(echecs)} vérification(s) de contacts (non bloquant, AS11)"
    if echecs:
        return ECHEC, f"{len(echecs)} échec(s), d'abord : {echecs[0]}"[:300]
    return ECHEC, f"code {code}"


# --- git -----------------------------------------------------------------------------------------

def git(depot: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(depot), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} : {p.stderr.strip()[-300:]}")
    return p.stdout.strip()


def resoudre_tete(f: File, branche: str, reseau: bool) -> str:
    """Tête de `branche` sur origin. Refspec explicite : le dépôt du user ne suit que main
    (`+refs/heads/main:refs/remotes/origin/main`), un simple `git fetch origin <branche>` n'y crée pas la ref distante
    (pilote arrêté le 19 novembre à 10h30)."""
    if reseau:
        git(f.depot, "fetch", "--quiet", "origin", f"+refs/heads/{branche}:refs/remotes/origin/{branche}")
    return git(f.depot, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branche}^{{commit}}")


MARQUE_TETE = ".file_bancs_tete"


def worktree(f: File, nom: str, tete: str) -> Path:
    """Worktree détaché dans sortie/worktrees/nom (le dépôt du user reste sur main, propre). `tete` : un commit, ou
    « sha1+sha2+… » pour un essai assemblé : sha1, puis les suivants fusionnés par-dessus (fusion locale, jamais poussée)."""
    shas = tete.split("+")
    wt = f.sortie / "worktrees" / nom
    marque = wt / MARQUE_TETE
    if (wt / ".git").exists():
        if marque.is_file() and marque.read_text(encoding="utf-8").strip() == tete:
            return wt
        git(wt, "reset", "--quiet", "--hard")
        git(wt, "checkout", "--quiet", "--detach", shas[0])
    else:
        wt.parent.mkdir(parents=True, exist_ok=True)
        git(f.depot, "worktree", "add", "--quiet", "--detach", str(wt), shas[0])
    for sha in shas[1:]:
        try:
            git(wt, "-c", "user.name=file_bancs", "-c", "user.email=file@bancs", "merge", "--quiet", "--no-edit", sha)
        except RuntimeError as exc:
            with contextlib.suppress(RuntimeError):
                git(wt, "merge", "--abort")
            raise Assemblage(f"assemblage en conflit avec {sha[:8]}") from exc
    marque.write_text(tete + "\n", encoding="utf-8")
    return wt


SCHEMA_SRC = "Open_ride_linux/compiler/src/openride_compiler/worldgen/osmdb.py"
SCHEMA_RE = re.compile(r"^SCHEMA_VERSION\s*=\s*(\d+)", re.M)


def schema_cache(texte: str | None) -> str | None:
    m = SCHEMA_RE.search(texte or "")
    return m.group(1) if m else None


def cache_separe(f: File, pr: PR) -> Path:
    """Dossier OPENRIDE_BANC_CACHES de la PR ; amorcé une fois par copie du cache réel du monde ouvert."""
    racine = f.sortie / "caches" / pr.id
    monde = racine / "monde"
    reel = Path.home() / "OpenRide" / "Cache" / "monde"
    if not monde.exists():
        racine.mkdir(parents=True, exist_ok=True)
        if reel.is_dir():
            subprocess.run(["cp", "-a", "--reflink=auto", str(reel), str(monde)], check=True)
        else:
            monde.mkdir()
    return racine


# --- exécution -----------------------------------------------------------------------------------

def environnement_etape(depot: Path, projet: Path) -> dict[str, str]:
    """Environnement d'une étape, comme job.sh du fil de fusion : sources du worktree d'abord (PYTHONPATH : core et
    compilateur, sinon « No module named 'openride_compiler' » dans les tests de l'engine, 19 novembre), environnement
    Python du dépôt du user (core/.venv : VIRTUAL_ENV, PATH, et lien core/.venv dans le worktree), chiffres à la C,
    aucune fenêtre bloquante."""
    env = dict(os.environ)
    env.pop("OPENRIDE_BANC_CACHES", None)
    sources = [str(projet / "core" / "src"), str(projet / "compiler" / "src")]
    env["PYTHONPATH"] = os.pathsep.join([*sources, *([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])])
    venv = depot / "Open_ride_linux" / "core" / ".venv"
    if (venv / "bin" / "python").exists():
        env["VIRTUAL_ENV"] = str(venv)
        env["PATH"] = os.pathsep.join([str(venv / "bin"), env.get("PATH", "")])
        lien = projet / "core" / ".venv"
        if (projet / "core").is_dir() and not lien.exists() and not lien.is_symlink():
            lien.symlink_to(venv)
    env["LC_NUMERIC"] = "C"
    env["OPENRIDE_NO_GUI"] = "1"
    return env


class Arret(Exception):
    """Ctrl-C ou SIGTERM : l'étape en cours est arrêtée sans verdict."""


def jouer(commande: str, cwd: Path, env: dict[str, str], journal: Path, delai_s: float) -> tuple[int | None, str]:
    """Lance la commande dans son groupe de processus ; (code, texte du journal), code None si délai dépassé."""
    journal.parent.mkdir(parents=True, exist_ok=True)
    with journal.open("w", encoding="utf-8") as out:
        p = subprocess.Popen(commande, shell=True, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT,
                             start_new_session=True)
        try:
            code: int | None = p.wait(timeout=delai_s)
        except subprocess.TimeoutExpired:
            code = None
        except BaseException:
            tuer(p)
            raise
        if code is None:
            tuer(p)
    return code, journal.read_text(encoding="utf-8", errors="replace")


def tuer(p: subprocess.Popen) -> None:
    for sig in (signal.SIGTERM, signal.SIGKILL):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(p.pid, sig)
        try:
            p.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            continue


class Runner:
    def __init__(self, f: File, reseau: bool = True, log=print) -> None:
        self.f, self.reseau, self.log = f, reseau, log
        self.etat = Etat(f.sortie / "etat.json")
        self.tetes: dict[str, str] = {}

    def tete(self, branche: str) -> str:
        if branche not in self.tetes:
            self.tetes[branche] = resoudre_tete(self.f, branche, self.reseau)
        return self.tetes[branche]

    def relire(self, pr: PR) -> None:
        """Têtes de la PR relues (git fetch) avant ses étapes : une branche poussée pendant la nuit est vue."""
        for b in (pr.branche, *pr.assemblage):
            self.tetes.pop(b, None)

    def tete_pr(self, pr: PR) -> str:
        sha = self.tete(pr.branche)
        if pr.tete and not sha.startswith(pr.tete):
            raise TeteChangee(f"tête {sha[:8]} au lieu de {pr.tete} (file à mettre à jour)")
        return "+".join([sha, *(self.tete(b) for b in pr.assemblage)])

    def a_jouer(self, pr: PR, e: Etape, mode: str) -> bool:
        v = self.etat.get(pr, e)
        if v is None or v["verdict"] not in ACQUIS:
            return True
        try:
            sha = self.tete("main") if e.sur == "main" else self.tete_pr(pr)
        except TeteChangee:
            return True
        if v.get("tete") == sha and v.get("empreinte", e.empreinte) == e.empreinte:
            return False
        # Après correction (relancer), une étape OK d'une tête précédente reste acquise (règle 6 du plan).
        return mode == "lancer"

    def pause(self) -> bool:
        return (self.f.sortie / "PAUSE").exists()

    def portail(self, pr: PR, e: Etape) -> bool:
        """Attend que `avant_etape` rende 0 (fenêtre de pause du user, Godot du user fermé…) ; faux si PAUSE."""
        attente = False
        while self.f.avant_etape:
            env = {**os.environ, "FILE_PR": pr.id, "FILE_ETAPE": e.id, "FILE_DUREE_MIN": f"{e.delai_min:.0f}"}
            p = subprocess.run(self.f.avant_etape, shell=True, env=env, capture_output=True, text=True, check=False)
            if p.returncode == 0:
                break
            if not attente:
                raison = (p.stdout + p.stderr).strip().splitlines()[-1:] or [f"code {p.returncode}"]
                self.log(f"  en attente avant {pr.id}/{e.id} : {raison[0]}")
                attente = True
            if self.pause():
                return False
            time.sleep(self.f.attente_s)
        return not self.pause()

    def apres(self, pr: PR, e: Etape, verdict: str, dossier: Path) -> bool | None:
        if not self.f.apres_etape:
            return None
        cmd = self.f.apres_etape.format(dossier=shlex.quote(str(dossier)), pr=shlex.quote(pr.id),
                                        etape=shlex.quote(e.id), verdict=shlex.quote(verdict))
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        if p.returncode:
            self.log(f"  après l'étape : code {p.returncode} {(p.stdout + p.stderr).strip()[-200:]}")
        return p.returncode == 0

    def schema_refuse(self, pr: PR, wt: Path) -> str | None:
        """Règle du 19 novembre : jamais le HOME réel pour une PR qui change le schéma du cache."""
        if pr.cache == "separe":
            return None
        with contextlib.suppress(OSError):
            branche = schema_cache((wt / SCHEMA_SRC).read_text(encoding="utf-8"))
            try:
                main = schema_cache(git(self.f.depot, "show", f"{self.tete('main')}:{SCHEMA_SRC}"))
            except RuntimeError:
                return None
            if branche and main and branche != main:
                return (f"PR qui change le schéma du cache ({main} → {branche}) : cache = \"separe\" obligatoire, "
                        "jamais le HOME réel")
        return None

    def noter(self, pr: PR, e: Etape, verdict: str, detail: str, sha: str | None) -> str:
        self.etat.put(pr, e, {"verdict": verdict, "detail": detail, "tete": sha, "empreinte": e.empreinte,
                              "fin": datetime.now().isoformat(timespec="seconds")})
        self.log(f"  {verdict} {detail}")
        return verdict

    def executer(self, pr: PR, e: Etape) -> str | None:
        """Joue une étape et note son verdict ; None si la file s'est mise en pause avant."""
        if not self.portail(pr, e):
            return None
        try:
            sha = self.tete("main") if e.sur == "main" else self.tete_pr(pr)
        except TeteChangee as exc:
            return self.noter(pr, e, ENV, str(exc), None)
        nom = "main" if e.sur == "main" else pr.id
        try:
            wt = worktree(self.f, nom, sha)
        except Assemblage as exc:
            return self.noter(pr, e, ENV, str(exc), sha)
        if e.sur == "branche":
            refus = self.schema_refuse(pr, wt)
            if refus:
                return self.noter(pr, e, ENV, refus, sha)
        dossier = self.f.sortie / ("main" if e.sur == "main" else pr.id) / (e.empreinte if e.sur == "main" else e.id)
        dossier.mkdir(parents=True, exist_ok=True)
        projet = wt / "Open_ride_linux"
        cmd = e.commande.format(sortie=shlex.quote(str(dossier / "rapport")), worktree=shlex.quote(str(wt)),
                                projet=shlex.quote(str(projet)), depot=shlex.quote(str(self.f.depot)))
        env = environnement_etape(self.f.depot, projet)
        if pr.cache == "separe" and e.sur == "branche":
            env["OPENRIDE_BANC_CACHES"] = str(cache_separe(self.f, pr))
        self.log(f"→ {pr.id}/{e.id} sur {'main' if e.sur == 'main' else pr.branche} {sha[:8]} "
                 f"(délai {e.delai_min:.0f} min)")
        t0 = time.monotonic()
        code, texte = jouer(cmd, projet if projet.is_dir() else wt, env, dossier / "journal.txt", e.delai_min * 60)
        if code is None:
            verdict, detail = DELAI, f"arrêtée après {e.delai_min:.0f} min"
        else:
            verdict, detail = classer(code, texte)
        resultat = {"verdict": verdict, "detail": detail, "tete": sha, "empreinte": e.empreinte,
                    "duree_s": round(time.monotonic() - t0), "code": code, "dossier": str(dossier),
                    "fin": datetime.now().isoformat(timespec="seconds")}
        self.etat.put(pr, e, resultat)
        self.log(f"  {verdict} {detail}".rstrip())
        pousse = self.apres(pr, e, verdict, dossier)
        if pousse is not None:
            self.etat.put(pr, e, {**resultat, "apres_etape": "OK" if pousse else "ÉCHEC"})
        return verdict

    def fumee_ok(self, pr: PR) -> bool:
        fum = next((e for e in pr.etapes if e.id == FUMEE), None)
        if fum is None:
            return True
        v = self.etat.get(pr, fum)
        return v is not None and v["verdict"] in ACQUIS

    def lancer(self, mode: str = "lancer", seulement: set[str] | None = None, fumees_seules: bool = False) -> int:
        prs = [p for p in self.f.par_risque() if not seulement or p.id in seulement]
        # 1. Fumées de toute la file : une PR qui ne peut pas démarrer est écartée en minutes, pas en heures.
        for pr in prs:
            fum = next((e for e in pr.etapes if e.id == FUMEE), None)
            if fum is None:
                continue
            doit = self.a_jouer(pr, fum, "lancer")
            if mode == "relancer":   # après correction : fumée rejouée sur la nouvelle tête avant les étapes
                doit = doit or any(self.a_jouer(pr, e, mode) for e in pr.etapes if e.id != FUMEE)
            if doit:
                self.relire(pr)
                if self.executer(pr, fum) is None:
                    return 3
        if fumees_seules:
            return self.code(prs)
        # 2. Longues étapes, PR par PR dans l'ordre du risque.
        for pr in prs:
            longues = [e for e in pr.etapes if e.id != FUMEE]
            self.relire(pr)
            if not self.fumee_ok(pr):
                for e in longues:
                    if self.a_jouer(pr, e, mode):
                        self.etat.put(pr, e, {"verdict": BLOQUE, "detail": "fumée non passée", "tete": None,
                                              "empreinte": e.empreinte})
                continue
            for e in longues:
                if self.a_jouer(pr, e, mode) and self.executer(pr, e) is None:
                    return 3
        ecrire_tableau(self.f, self.etat)
        return self.code(prs)

    def code(self, prs: list[PR]) -> int:
        for pr in prs:
            for e in pr.etapes:
                v = self.etat.get(pr, e)
                if v is not None and v["verdict"] in EN_ECHEC:
                    return 1
        return 0


# --- tableau -------------------------------------------------------------------------------------

def tableau(f: File, etat: Etat, tetes: dict[str, str] | None = None) -> str:
    noms = list(dict.fromkeys(e.id for pr in f.prs for e in pr.etapes))
    lignes = ["| PR | " + " | ".join(noms) + " |", "|---|" + "---|" * len(noms)]
    for pr in f.par_risque():
        cases = []
        for n in noms:
            e = next((x for x in pr.etapes if x.id == n), None)
            if e is None:
                cases.append("")
                continue
            v = etat.get(pr, e)
            if v is None:
                cases.append(A_FAIRE)
                continue
            txt = v["verdict"]
            branches = ["main"] if e.sur == "main" else [pr.branche, *pr.assemblage]
            connues = [(tetes or {}).get(b) for b in branches]
            tete = "+".join(connues) if all(connues) else None
            if v.get("tete") and tete and v["tete"] != tete:
                txt += f" (sur tête {v['tete'][:8]})"
            cases.append(txt)
        nom = f"#{pr.pr} {pr.id}" if pr.pr else pr.id
        lignes.append(f"| {nom} | " + " | ".join(cases) + " |")
    return "\n".join(lignes) + "\n"


def ecrire_tableau(f: File, etat: Etat, tetes: dict[str, str] | None = None) -> str:
    txt = tableau(f, etat, tetes)
    details = []
    for pr in f.par_risque():
        for e in pr.etapes:
            v = etat.get(pr, e)
            if v and v["verdict"] not in (OK,) and v.get("detail"):
                details.append(f"- {pr.id}/{e.id} : {v['verdict']}, {v['detail']}")
    md = f"# File des bancs : {f.sortie.name}\n\n{txt}" + ("\n" + "\n".join(details) + "\n" if details else "")
    f.sortie.mkdir(parents=True, exist_ok=True)
    (f.sortie / "etat.md").write_text(md, encoding="utf-8")
    return md


# --- ligne de commande ---------------------------------------------------------------------------

@contextlib.contextmanager
def verrou(sortie: Path):
    """Une seule file à la fois sur ce dossier de sortie."""
    sortie.mkdir(parents=True, exist_ok=True)
    with (sortie / ".verrou").open("w") as fd:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise FileInvalide(f"une file tourne déjà sur {sortie}") from None
        yield


def _arret(*_: Any) -> None:
    raise Arret()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="File des bancs du PC en étapes courtes, avec reprise.")
    ap.add_argument("action", choices=("lancer", "relancer", "etat"))
    ap.add_argument("file", type=Path)
    ap.add_argument("--pr", action="append", help="seulement ces PR (identifiant de la file, répétable)")
    ap.add_argument("--seulement-fumees", action="store_true", help="jouer seulement les fumées")
    ap.add_argument("--sans-reseau", action="store_true", help="pas de git fetch : têtes lues dans origin/*")
    args = ap.parse_args(argv)
    try:
        f = lire_file(args.file)
        inconnues = set(args.pr or ()) - {p.id for p in f.prs}
        if inconnues:
            raise FileInvalide(f"PR absentes de la file : {', '.join(sorted(inconnues))}")
        if args.action == "etat":
            print(ecrire_tableau(f, Etat(f.sortie / "etat.json")), end="")
            return 0
        with verrou(f.sortie):
            r = Runner(f, reseau=not args.sans_reseau)
            signal.signal(signal.SIGTERM, _arret)
            try:
                code = r.lancer(args.action, set(args.pr or ()), args.seulement_fumees)
            except (Arret, KeyboardInterrupt):
                print("File arrêtée : l'étape en cours sera rejouée au prochain lancement.")
                code = 130
            print(ecrire_tableau(f, r.etat, r.tetes), end="")
            if code == 3:
                print(f"File en pause (fichier {f.sortie / 'PAUSE'}) : supprimer ce fichier puis relancer.")
            return code
    except (FileInvalide, RuntimeError) as exc:
        print(f"File invalide : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
