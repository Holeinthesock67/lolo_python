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
    assemblage_strategie = "ours"   # facultatif : option -X de ces fusions (« ours » ou « theirs »)
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

Paquets, matrice et cloud (plan du 20 novembre, file PC trop lente) :

    [[paquet]]                   # 2 à 4 PR dans un seul banc, sur leurs branches assemblées en local
    id = "p1"
    fumee = "…"
    matrice = "python3 engine/tests/menu_bench.py --native --scenario sessions --qualite {qualite} --out {sortie}"
    [[paquet.etape]]
    id = "contacts"
    lieu = "cloud"               # sans GPU : sautée sur le PC, jouée par `lancer FILE --lieu cloud`
    commande = "…"
    [[paquet.membre]]
    pr = 930
    branche = "claude/…"
    tete = "1a2b3c4d"            # obligatoire
    categorie = "logique"        # « Catégorie : » de la section « Recette PC » de la PR (défaut : rendu)

- `categorie` (« rendu » par défaut, « logique ») et `matrice` génèrent une étape par qualité : low, high, medium en
  rendu ; medium seul en logique, fumée obligatoire. Un paquet est rendu dès qu'un de ses membres l'est.
- Un paquet est REFUSÉ, sans rien lancer, si deux membres changent la même constante de VERSIONS (WORLDGEN_VERSION,
  SCHEMA_VERSION, révision IPC) ou si leurs branches ne s'assemblent pas (git merge-tree, à blanc).
- Une étape du paquet en ÉCHEC ou DÉLAI passe SCINDÉ ; la file la rejoue aussitôt PR par PR (« p1.r930 »…), fumée
  comprise, sur la branche seule ; les étapes OK du paquet restent acquises.
- `--lieu cloud` : seulement les étapes `lieu = "cloud"`, sans portail ni fumée du PC (conteneur préparé par
  file_bancs/prepare_cloud.sh, qui pose $GODOT) ; `importer FILE --depuis ETAT.json` recopie leurs verdicts sur le PC.
- `verifier FILE` : têtes et composition des paquets, sans rien lancer ; `categorie CORPS.md` : catégorie lue dans la
  section « Recette PC » d'une PR (« - » : entrée standard).

Les commandes tournent dans `<worktree>/Open_ride_linux`, avec `{sortie}` (dossier de l'étape), `{worktree}` et
`{projet}`, `{depot}` (le dépôt du user, pour son environnement Python) remplacés ; chaque étape a PYTHONPATH sur
les sources du worktree (core et compilateur), le core/.venv du dépôt en tête du PATH (lié dans le worktree),
LC_NUMERIC=C et OPENRIDE_NO_GUI=1, comme job.sh ; le portail reçoit FILE_PR,
FILE_ETAPE et FILE_DUREE_MIN (délai de l'étape, pour ne pas déborder sur la fenêtre du user). Verdicts :
- OK ; CONTACTS : seules des vérifications de contacts ont échoué (non bloquant, lot AS11) ;
- À-COUPS : seuls des à-coups connus (pire image, images lentes), avec ou sans contacts (non bloquant, lot PI1) ;
- ÉCHEC : une vérification du jeu ; DÉLAI : étape arrêtée au bout de `delai_min` ;
- ENVIRONNEMENT : le PC, pas la PR (code 2 des bancs, cache au mauvais schéma, réseau, disque plein) ;
- BLOQUÉ : non jouée car la fumée de la PR n'est pas passée ; REFUSÉ : paquet mal composé (rien n'est lancé) ;
- SCINDÉ : étape d'un paquet en échec, rejouée PR par PR (le verdict est celui des PR séparées).
Têtes relues (git fetch) avant les étapes de chaque PR ; une tête différente de `tete` donne ENVIRONNEMENT.
Une PR dont le `SCHEMA_VERSION` du cache diffère de main ne tourne jamais sur le cache réel : sans `cache = "separe"`,
ses étapes sont refusées (ENVIRONNEMENT) sans être lancées.
Reprise : `lancer` rejoue tout ce qui n'est pas OK, CONTACTS ou À-COUPS sur la tête actuelle ; `relancer` rejoue seulement
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

OK, CONTACTS, ACOUPS, ECHEC, DELAI, ENV, BLOQUE, A_FAIRE, REFUSE = (
    "OK", "CONTACTS", "À-COUPS", "ÉCHEC", "DÉLAI", "ENVIRONNEMENT", "BLOQUÉ", "À FAIRE", "REFUSÉ")
ACQUIS = (OK, CONTACTS, ACOUPS)                       # verdicts qui ne se rejouent pas sur la même tête
EN_ECHEC = (ECHEC, DELAI, ENV, REFUSE)
FUMEE = "fumee"
CACHES = ("reel", "separe")
CODE_ENV_BANCS = 2                            # menu_bench, sim_bench, recette_pc : Godot ou xvfb-run absent
LIGNE_ECHEC = re.compile(r"^\[ÉCHEC\] (.*)$", re.M)
CONTACT = re.compile(r"contact", re.I)
# À-coups connus (pire image, images lentes, périodicité) : défaut commun suivi par un fil global (lot PI1), non bloquant.
ACOUP = re.compile(r"à-coups|pire image|images lentes", re.I)
# Délais de capture du rendu logiciel d'un conteneur cloud (Xvfb, lavapipe, sans GPU) : une image redemandée ne dit
# rien de la PR (nuit du 20 novembre, captures #932 et #935). Ignorés dans les étapes `lieu = "cloud"` seulement.
DELAI_CAPTURE_CLOUD = re.compile(r"images enregistrées après le chargement.*captures de l'engine", re.I)
STRATEGIES = ("", "ours", "theirs")
SCINDE = "SCINDÉ"                              # étape d'un paquet en échec, rejouée PR par PR (voir scissions)
LIEUX = ("pc", "cloud")
RENDU, LOGIQUE = "rendu", "logique"
CATEGORIES = (RENDU, LOGIQUE)
# Matrice selon la catégorie (plan du 20 novembre) : le rendu passe les 3 qualités, risque d'abord (low, high, medium) ;
# la logique, une fumée et medium seulement. En cas de doute, rendu.
MATRICE = {RENDU: ("low", "high", "medium"), LOGIQUE: ("medium",)}
PAQUET_MAX = 4

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
    lieu: str = "pc"                          # "pc" (GPU, GTX 1060) ou "cloud" (sans GPU, voir --lieu cloud)

    @property
    def empreinte(self) -> str:
        return hashlib.sha1(self.commande.encode()).hexdigest()[:10]


@dataclass
class Membre:
    """Une PR d'un paquet : sa branche et sa tête fixée, comme une entrée [[pr]]."""
    id: str
    branche: str
    pr: int | None = None
    tete: str | None = None
    categorie: str = RENDU


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
    strategie: str = ""                        # « ours » ou « theirs » : option -X de la fusion d'assemblage
    categorie: str = RENDU                     # « rendu » (low, high, medium) ou « logique » (fumée + medium)
    membres: list[Membre] = field(default_factory=list)   # paquet : les PR réunies (la 1re porte `branche`)
    paquet: str | None = None                  # PR séparée d'un paquet en échec : identifiant du paquet

    @property
    def est_paquet(self) -> bool:
        return bool(self.membres)


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


def _etapes(nom: str, d: dict[str, Any], categorie: str) -> list[Etape]:
    """Étapes d'une entrée [[pr]] ou [[paquet]] : fumée, matrice de la catégorie, puis étapes écrites à la main."""
    etapes = []
    if d.get("fumee"):
        etapes.append(Etape(FUMEE, str(d["fumee"]), float(d.get("fumee_delai_min", 8)),
                            lieu=str(d.get("fumee_lieu", "pc"))))
    elif categorie == LOGIQUE:
        raise FileInvalide(f"{nom} : une PR de logique a une `fumee` (matrice : fumée + medium)")
    if d.get("matrice"):
        modele = str(d["matrice"])
        if "{qualite}" not in modele:
            raise FileInvalide(f"{nom} : `matrice` contient {{qualite}}, remplacé par low, high, medium")
        for q in MATRICE[categorie]:
            etapes.append(Etape(q, modele.replace("{qualite}", q), float(d.get("matrice_delai_min", 40))))
    for e in d.get("etape", []):
        if not e.get("id") or not e.get("commande") or e["id"] == FUMEE:
            raise FileInvalide(f"{nom} : chaque étape a un `id` (pas « {FUMEE} ») et une `commande`")
        sur = e.get("sur", "branche")
        if sur not in ("branche", "main"):
            raise FileInvalide(f"{nom}/{e['id']} : `sur` vaut « branche » ou « main »")
        etapes.append(Etape(str(e["id"]), str(e["commande"]), float(e.get("delai_min", 60)), sur,
                            str(e.get("lieu", "pc"))))
    for e in etapes:
        if e.lieu not in LIEUX:
            raise FileInvalide(f"{nom}/{e.id} : `lieu` vaut « pc » ou « cloud »")
    if len({e.id for e in etapes}) != len(etapes):
        raise FileInvalide(f"{nom} : identifiants d'étape en double")
    return etapes


def _categorie(nom: str, valeur: Any) -> str:
    cat = str(valeur or RENDU)
    if cat not in CATEGORIES:
        raise FileInvalide(f"{nom} : catégorie « {cat} » inconnue ({', '.join(CATEGORIES)})")
    return cat


def _commun(nom: str, d: dict[str, Any]) -> tuple[str, str]:
    cache = d.get("cache", "reel")
    if cache not in CACHES:
        raise FileInvalide(f"{nom} : cache « {cache} » inconnu ({', '.join(CACHES)})")
    strategie = str(d.get("assemblage_strategie", ""))
    if strategie not in STRATEGIES:
        raise FileInvalide(f"{nom} : assemblage_strategie « {strategie} » inconnue (ours, theirs)")
    return cache, strategie


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

    def nouveau(pid: Any, quoi: str) -> str:
        if not pid or "." in str(pid):
            raise FileInvalide(f"{quoi} : `id` obligatoire, sans point (réservé aux PR séparées d'un paquet)")
        if pid in vus or pid == "main":
            raise FileInvalide(f"identifiant de PR en double ou réservé : {pid}")
        vus.add(str(pid))
        return str(pid)

    for rang, d in enumerate(doc.get("pr", [])):
        pid = nouveau(d.get("id"), f"entrée [[pr]] n° {rang + 1}")
        if not d.get("branche"):
            raise FileInvalide(f"entrée [[pr]] n° {rang + 1} : `id` et `branche` obligatoires")
        cache, strategie = _commun(pid, d)
        categorie = _categorie(pid, d.get("categorie"))
        prs.append(PR(pid, str(d["branche"]), d.get("pr"), d.get("tete"), int(d.get("risque", 2)), cache,
                      _etapes(pid, d, categorie), rang, [str(b) for b in d.get("assemblage", [])], strategie,
                      categorie))
    for n, d in enumerate(doc.get("paquet", [])):
        pid = nouveau(d.get("id"), f"entrée [[paquet]] n° {n + 1}")
        membres = []
        for m in d.get("membre", []):
            if not m.get("branche") or not m.get("tete"):
                raise FileInvalide(f"{pid} : chaque [[paquet.membre]] a une `branche` et une `tete` fixée")
            mid = str(m.get("id") or (f"r{m['pr']}" if m.get("pr") else ""))
            if not mid or "." in mid:
                raise FileInvalide(f"{pid} : membre sans `id` ni `pr`")
            membres.append(Membre(mid, str(m["branche"]), m.get("pr"), str(m["tete"]),
                                  _categorie(f"{pid}/{mid}", m.get("categorie"))))
        if not 2 <= len(membres) <= PAQUET_MAX:
            raise FileInvalide(f"{pid} : un paquet réunit de 2 à {PAQUET_MAX} PR ({len(membres)} ici)")
        if len({m.id for m in membres}) != len(membres) or len({m.branche for m in membres}) != len(membres):
            raise FileInvalide(f"{pid} : membres en double")
        # Catégorie du paquet : rendu dès qu'un membre est rendu (le doute va au rendu).
        categorie = LOGIQUE if all(m.categorie == LOGIQUE for m in membres) else RENDU
        if d.get("categorie") and _categorie(pid, d["categorie"]) != categorie:
            raise FileInvalide(f"{pid} : catégorie « {d['categorie']} » contraire à celle des membres ({categorie})")
        cache, strategie = _commun(pid, d)
        prs.append(PR(pid, membres[0].branche, None, membres[0].tete, int(d.get("risque", 2)), cache,
                      _etapes(pid, d, categorie), len(prs), [m.branche for m in membres[1:]], strategie,
                      categorie, membres))
    if not prs:
        raise FileInvalide(f"{chemin} : aucune entrée [[pr]] ni [[paquet]]")
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

def classer(code: int, journal: str, lieu: str = "pc") -> tuple[str, str]:
    """(verdict, détail) d'une étape terminée, d'après son code de sortie et son journal. En cloud, les délais de
    capture du rendu logiciel sont retirés des échecs (OK si rien d'autre n'a échoué)."""
    if code == 0:
        return OK, ""
    for motif in MOTIFS_ENV:
        m = motif.search(journal)
        if m:
            return ENV, m.group(0)
    if code == CODE_ENV_BANCS:
        return ENV, f"code {code} (outil ou affichage absent)"
    echecs = LIGNE_ECHEC.findall(journal)          # « [ÉCHEC] libellé : mesure » de menu_bench et sim_bench
    if lieu == "cloud" and echecs:
        lents = [ligne for ligne in echecs if DELAI_CAPTURE_CLOUD.search(ligne)]
        echecs = [ligne for ligne in echecs if not DELAI_CAPTURE_CLOUD.search(ligne)]
        if lents and not echecs:
            return OK, f"{len(lents)} délai(s) de capture du rendu logiciel ignoré(s) (cloud)"
    if echecs and all(CONTACT.search(ligne) for ligne in echecs):
        return CONTACTS, f"{len(echecs)} vérification(s) de contacts (non bloquant, AS11)"
    if echecs and all(CONTACT.search(ligne) or ACOUP.search(ligne) for ligne in echecs):
        n = sum(1 for ligne in echecs if ACOUP.search(ligne))
        return ACOUPS, f"{n} à-coup(s) connu(s), {len(echecs) - n} contact(s) (non bloquant, PI1 et AS11) : {echecs[0]}"[:300]
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


def worktree(f: File, nom: str, tete: str, strategie: str = "") -> Path:
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
            option = ["-X", strategie] if strategie else []
            git(wt, "-c", "user.name=file_bancs", "-c", "user.email=file@bancs", "merge", "--quiet", "--no-edit", *option, sha)
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


# Constantes qu'une seule PR d'un paquet peut changer : deux changements dans un même banc ne se démêlent pas
# (format des carrés du monde ouvert, schéma du cache, révision du contrat IPC).
VERSIONS = {
    "WORLDGEN_VERSION": ("Open_ride_linux/compiler/src/openride_compiler/worldgen/squares.py",
                         re.compile(r"^WORLDGEN_VERSION\s*=\s*(\d+)", re.M)),
    "SCHEMA_VERSION": (SCHEMA_SRC, SCHEMA_RE),
    "révision IPC": ("Open_ride_linux/core/src/openride_core/ipc_server.py",
                     re.compile(r"^CONTRACT_REV\s*=\s*[\"']([^\"']+)[\"']", re.M)),
}


def lire_version(depot: Path, sha: str, chemin: str, motif: re.Pattern) -> str | None:
    try:
        m = motif.search(git(depot, "show", f"{sha}:{chemin}"))
    except RuntimeError:
        return None
    return m.group(1) if m else None


def versions_changees(depot: Path, sha: str, main: str) -> dict[str, tuple[str | None, str | None]]:
    """Constantes de VERSIONS changées par la branche `sha` depuis son point de départ sur main (merge-base) :
    une branche partie avant une montée de main n'est pas comptée comme un changement."""
    base = git(depot, "merge-base", sha, main)
    out = {}
    for nom, (chemin, motif) in VERSIONS.items():
        avant, apres = lire_version(depot, base, chemin, motif), lire_version(depot, sha, chemin, motif)
        if avant != apres:
            out[nom] = (avant, apres)
    return out


def fichiers_changes(depot: Path, sha: str, main: str) -> set[str]:
    base = git(depot, "merge-base", sha, main)
    return {l for l in git(depot, "diff", "--name-only", base, sha).splitlines() if l}


def verifier_paquet(depot: Path, pr: PR, shas: list[str], main: str) -> tuple[list[str], list[str]]:
    """(refus, avis) d'un paquet dont les membres ont les têtes `shas`. Refus : deux membres changent la même
    constante de VERSIONS, ou leurs branches ne s'assemblent pas sans conflit. Avis : fichiers touchés par
    plusieurs membres (le plan veut des PR sur des fichiers distincts ; les docs communes sont fréquentes)."""
    refus, avis = [], []
    par_const: dict[str, list[str]] = {}
    fichiers: dict[str, list[str]] = {}
    for m, sha in zip(pr.membres, shas):
        for nom, (avant, apres) in versions_changees(depot, sha, main).items():
            par_const.setdefault(nom, []).append(f"{m.id} ({avant} → {apres})")
        for chemin in fichiers_changes(depot, sha, main):
            fichiers.setdefault(chemin, []).append(m.id)
    for nom, qui in par_const.items():
        if len(qui) > 1:
            refus.append(f"{nom} changé par {len(qui)} PR : {', '.join(qui)} (une seule par paquet)")
    communs = sorted(c for c, qui in fichiers.items() if len(qui) > 1)
    if communs:
        avis.append(f"{len(communs)} fichier(s) touché(s) par plusieurs PR : {', '.join(communs[:5])}"
                    + (" …" if len(communs) > 5 else ""))
    # Assemblage à blanc (git merge-tree, rien n'est écrit dans le dépôt de travail) : mêmes fusions que worktree().
    courant = shas[0]
    option = ["-X", pr.strategie] if pr.strategie else []
    for m, sha in zip(pr.membres[1:], shas[1:]):
        p = subprocess.run(["git", "-C", str(depot), "merge-tree", "--write-tree", "--name-only", *option, courant, sha],
                           capture_output=True, text=True, check=False)
        if p.returncode == 1:
            conflits = [l for l in p.stdout.splitlines()[1:] if l and not l.startswith(("Auto-merging", "CONFLICT"))]
            refus.append(f"assemblage en conflit avec {m.id} : {', '.join(conflits[:5]) or 'voir git merge'}")
            break
        if p.returncode != 0:
            avis.append(f"assemblage non vérifié à blanc (git trop ancien ?) : {p.stderr.strip()[-120:]}")
            break
        arbre = p.stdout.splitlines()[0]
        courant = git(depot, "-c", "user.name=file_bancs", "-c", "user.email=file@bancs", "commit-tree", arbre,
                      "-p", courant, "-p", sha, "-m", "essai de paquet")
    return refus, avis


def scissions(f: File, etat: Etat) -> list[PR]:
    """PR séparées des paquets en échec : pour chaque membre, la fumée du paquet et seulement les étapes en échec
    (marquées SCINDÉ dans le paquet), sur sa branche seule. Calculées depuis etat.json, donc stables d'un appel à
    l'autre (`etat`, `relancer --pr p1.r930`)."""
    out = []
    for pr in f.prs:
        if not pr.est_paquet:
            continue
        faits = etat.data["prs"].get(pr.id, {})
        echecs = [e for e in pr.etapes if (faits.get(e.id) or {}).get("verdict") == SCINDE]
        if not echecs:
            continue
        fum = [e for e in pr.etapes if e.id == FUMEE]
        for m in pr.membres:
            out.append(PR(f"{pr.id}.{m.id}", m.branche, m.pr, m.tete, pr.risque, pr.cache, [*fum, *echecs], pr.rang,
                          categorie=m.categorie, paquet=pr.id))
    return out


def toutes(f: File, etat: Etat) -> list[PR]:
    return sorted([*f.prs, *scissions(f, etat)], key=lambda p: (p.risque, p.rang, p.id))


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
    # Conteneur cloud préparé par file_bancs/prepare_cloud.sh : $GODOT sans accolades dans les commandes
    # (les accolades des commandes sont celles de str.format).
    godot_env = Path.home() / ".cache" / "godot-4.7.2" / "env"
    if not env.get("GODOT") and godot_env.is_file():
        for ligne in godot_env.read_text(encoding="utf-8").splitlines():
            if ligne.startswith("GODOT="):
                env["GODOT"] = ligne.split("=", 1)[1].strip()
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
    def __init__(self, f: File, reseau: bool = True, log=print, lieu: str = "pc") -> None:
        self.f, self.reseau, self.log, self.lieu = f, reseau, log, lieu
        self.etat = Etat(f.sortie / "etat.json")
        self.tetes: dict[str, str] = {}
        self.verifies: dict[str, str] = {}         # paquet → têtes déjà vérifiées

    def etapes(self, pr: PR) -> list[Etape]:
        """Étapes jouées ici : celles du lieu (pc ou cloud). En cloud, la fumée du PC ne conditionne rien."""
        return [e for e in pr.etapes if e.lieu == self.lieu]

    def tete(self, branche: str) -> str:
        if branche not in self.tetes:
            self.tetes[branche] = resoudre_tete(self.f, branche, self.reseau)
        return self.tetes[branche]

    def relire(self, pr: PR) -> None:
        """Têtes de la PR relues (git fetch) avant ses étapes : une branche poussée pendant la nuit est vue."""
        for b in (pr.branche, *pr.assemblage):
            self.tetes.pop(b, None)

    def tete_pr(self, pr: PR) -> str:
        if pr.est_paquet:
            shas = []
            for m in pr.membres:
                sha = self.tete(m.branche)
                if not sha.startswith(m.tete or ""):
                    raise TeteChangee(f"{m.id} : tête {sha[:8]} au lieu de {m.tete} (file à mettre à jour)")
                shas.append(sha)
            return "+".join(shas)
        sha = self.tete(pr.branche)
        if pr.tete and not sha.startswith(pr.tete):
            raise TeteChangee(f"tête {sha[:8]} au lieu de {pr.tete} (file à mettre à jour)")
        return "+".join([sha, *(self.tete(b) for b in pr.assemblage)])

    def a_jouer(self, pr: PR, e: Etape, mode: str) -> bool:
        v = self.etat.get(pr, e)
        if v is not None and v["verdict"] == SCINDE:
            return False                          # rejouée PR par PR (scissions), jamais plus en paquet
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
        while self.f.avant_etape and self.lieu == "pc":
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
        if pr.est_paquet and e.sur == "branche":
            refus = self.refus_paquet(pr, sha)
            if refus:
                return self.noter(pr, e, REFUSE, refus, sha)
        nom = "main" if e.sur == "main" else pr.id
        try:
            wt = worktree(self.f, nom, sha, "" if e.sur == "main" else pr.strategie)
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
            verdict, detail = classer(code, texte, e.lieu)
        resultat = {"verdict": verdict, "detail": detail, "tete": sha, "empreinte": e.empreinte,
                    "duree_s": round(time.monotonic() - t0), "code": code, "dossier": str(dossier),
                    "fin": datetime.now().isoformat(timespec="seconds")}
        self.etat.put(pr, e, resultat)
        self.log(f"  {verdict} {detail}".rstrip())
        pousse = self.apres(pr, e, verdict, dossier)
        if pousse is not None:
            self.etat.put(pr, e, {**resultat, "apres_etape": "OK" if pousse else "ÉCHEC"})
        return verdict

    def refus_paquet(self, pr: PR, sha: str) -> str | None:
        """Composition du paquet vérifiée une fois par jeu de têtes (VERSIONS, assemblage à blanc)."""
        if pr.id not in self.verifies or not self.verifies[pr.id].startswith(sha + "|"):
            refus, avis = verifier_paquet(self.f.depot, pr, sha.split("+"), self.tete("main"))
            for a in avis:
                self.log(f"  {pr.id} : {a}")
            self.verifies[pr.id] = sha + "|" + " ; ".join(refus)
        texte = self.verifies[pr.id].split("|", 1)[1]
        return f"paquet refusé : {texte}" if texte else None

    def fumee_ok(self, pr: PR) -> bool:
        fum = next((e for e in self.etapes(pr) if e.id == FUMEE), None)
        if fum is None:
            return True
        v = self.etat.get(pr, fum)
        return v is not None and v["verdict"] in ACQUIS

    def lancer(self, mode: str = "lancer", seulement: set[str] | None = None, fumees_seules: bool = False) -> int:
        prs = [p for p in toutes(self.f, self.etat) if not seulement or p.id in seulement or p.paquet in seulement]
        code = self.jouer_liste(prs, mode, fumees_seules)
        if code is not None:
            return code
        # 3. Paquets en échec : séparés PR par PR, seulement les étapes en échec (plan du 20 novembre).
        nouvelles = self.scinder([p for p in prs if p.est_paquet])
        if nouvelles and not fumees_seules:
            code = self.jouer_liste(nouvelles, "lancer", False)
            if code is not None:
                return code
            prs += nouvelles
        ecrire_tableau(self.f, self.etat, self.tetes)
        return self.code(prs)

    def jouer_liste(self, prs: list[PR], mode: str, fumees_seules: bool) -> int | None:
        """Fumées puis longues étapes ; 3 si la file s'est mise en pause, sinon None."""
        # 1. Fumées de toute la file : une PR qui ne peut pas démarrer est écartée en minutes, pas en heures.
        for pr in prs:
            fum = next((e for e in self.etapes(pr) if e.id == FUMEE), None)
            if fum is None:
                continue
            doit = self.a_jouer(pr, fum, "lancer")
            if mode == "relancer":   # après correction : fumée rejouée sur la nouvelle tête avant les étapes
                doit = doit or any(self.a_jouer(pr, e, mode) for e in self.etapes(pr) if e.id != FUMEE)
            if doit:
                self.relire(pr)
                if self.executer(pr, fum) is None:
                    return 3
        if fumees_seules:
            return None
        # 2. Longues étapes, PR par PR dans l'ordre du risque.
        for pr in prs:
            longues = [e for e in self.etapes(pr) if e.id != FUMEE]
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
        return None

    def scinder(self, paquets: list[PR]) -> list[PR]:
        """Marque SCINDÉ les étapes du PC en ÉCHEC ou DÉLAI des paquets (pas ENVIRONNEMENT ni REFUSÉ : le PC ou la
        composition, pas une PR) et rend les PR séparées nouvelles. Une étape cloud n'est jamais séparée d'office :
        ses captures servent à toutes les PR du paquet et se relisent sur la planche (nuit du 20 novembre)."""
        avant = {p.id for p in scissions(self.f, self.etat)}
        for pr in paquets:
            for e in self.etapes(pr):
                v = self.etat.get(pr, e)
                if e.sur == "branche" and e.lieu == "pc" and v and v["verdict"] in (ECHEC, DELAI):
                    self.etat.put(pr, e, {**v, "verdict": SCINDE, "avant": v["verdict"],
                                          "detail": f"{v['verdict']} en paquet, rejouée PR par PR : {v.get('detail', '')}"[:300]})
                    self.log(f"  {pr.id}/{e.id} : {v['verdict']} en paquet, séparé PR par PR")
        return [p for p in scissions(self.f, self.etat) if p.id not in avant and p.paquet in {q.id for q in paquets}]

    def code(self, prs: list[PR]) -> int:
        for pr in prs:
            for e in self.etapes(pr):
                v = self.etat.get(pr, e)
                if v is not None and v["verdict"] in EN_ECHEC:
                    return 1
        return 0


# --- tableau -------------------------------------------------------------------------------------

def nom_pr(pr: PR) -> str:
    if pr.est_paquet:
        return f"{pr.id} (" + " + ".join(f"#{m.pr}" if m.pr else m.id for m in pr.membres) + ")"
    return f"#{pr.pr} {pr.id}" if pr.pr else pr.id


def tableau(f: File, etat: Etat, tetes: dict[str, str] | None = None) -> str:
    prs = toutes(f, etat)
    noms = list(dict.fromkeys(e.id for pr in prs for e in pr.etapes))
    lignes = ["| PR | " + " | ".join(noms) + " |", "|---|" + "---|" * len(noms)]
    for pr in prs:
        cases = []
        for n in noms:
            e = next((x for x in pr.etapes if x.id == n), None)
            if e is None:
                cases.append("")
                continue
            v = etat.get(pr, e)
            if v is None:
                cases.append(A_FAIRE + (" (cloud)" if e.lieu == "cloud" else ""))
                continue
            txt = v["verdict"]
            branches = ["main"] if e.sur == "main" else [pr.branche, *pr.assemblage]
            connues = [(tetes or {}).get(b) for b in branches]
            tete = "+".join(connues) if all(connues) else None
            if v.get("tete") and tete and v["tete"] != tete:
                txt += f" (sur tête {v['tete'][:8]})"
            cases.append(txt)
        lignes.append(f"| {nom_pr(pr)} | " + " | ".join(cases) + " |")
    return "\n".join(lignes) + "\n"


def ecrire_tableau(f: File, etat: Etat, tetes: dict[str, str] | None = None) -> str:
    txt = tableau(f, etat, tetes)
    details = []
    for pr in toutes(f, etat):
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


RECETTE_TITRE = re.compile(r"^(#{2,4})\s*(?:\d+\.\s*)?Recette PC\b.*$", re.M | re.I)
RECETTE_CATEGORIE = re.compile(r"^\s*[-*]?\s*\**\s*Cat[ée]gorie\s*\**\s*:\s*\**\s*(rendu|logique)\b", re.M | re.I)


def categorie_recette(texte: str) -> tuple[str, str]:
    """(catégorie, raison) lue dans la section « Recette PC » d'une PR ou d'un cahier de lot : ligne
    « Catégorie : rendu » ou « Catégorie : logique ». Absente ou illisible : rendu (en cas de doute, rendu)."""
    m = RECETTE_TITRE.search(texte)
    if not m:
        return RENDU, "pas de section « Recette PC » : rendu par défaut"
    suite = texte[m.end():]
    fin = re.search(rf"^#{{1,{len(m.group(1))}}}\s", suite, re.M)
    section = suite[:fin.start()] if fin else suite
    c = RECETTE_CATEGORIE.search(section)
    if not c:
        return RENDU, "ligne « Catégorie : » absente de « Recette PC » : rendu par défaut"
    return c.group(1).lower(), "lue dans « Recette PC »"


def importer(f: File, etat: Etat, autre: Path) -> int:
    """Recopie dans l'état du PC les verdicts des étapes `lieu = "cloud"` d'un etat.json joué en cloud."""
    try:
        data = json.loads(autre.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FileInvalide(f"{autre} : {exc}") from exc
    n = 0
    for pr in toutes(f, etat):
        for e in pr.etapes:
            if e.lieu != "cloud":
                continue
            v = data.get("main", {}).get(e.empreinte) if e.sur == "main" else data.get("prs", {}).get(pr.id, {}).get(e.id)
            if v:
                etat.put(pr, e, {**v, "importe": str(autre)})
                n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="File des bancs du PC en étapes courtes, avec reprise.")
    ap.add_argument("action", choices=("lancer", "relancer", "etat", "verifier", "importer", "categorie"))
    ap.add_argument("file", type=Path, help="fichier de file TOML (categorie : corps de la PR, « - » pour l'entrée)")
    ap.add_argument("--pr", action="append", help="seulement ces PR (identifiant de la file, répétable)")
    ap.add_argument("--seulement-fumees", action="store_true", help="jouer seulement les fumées")
    ap.add_argument("--sans-reseau", action="store_true", help="pas de git fetch : têtes lues dans origin/*")
    ap.add_argument("--lieu", choices=LIEUX, default="pc",
                    help="pc (défaut) : étapes du PC ; cloud : étapes sans GPU (lieu = \"cloud\"), sans portail")
    ap.add_argument("--depuis", type=Path, help="importer : etat.json de la file jouée en cloud")
    args = ap.parse_args(argv)
    try:
        if args.action == "categorie":
            texte = sys.stdin.read() if str(args.file) == "-" else args.file.read_text(encoding="utf-8")
            cat, raison = categorie_recette(texte)
            print(f"{cat} ({raison}) : " + ", ".join(MATRICE[cat]) + (" après la fumée" if cat == LOGIQUE else ""))
            return 0
        f = lire_file(args.file)
        etat0 = Etat(f.sortie / "etat.json")
        inconnues = set(args.pr or ()) - {p.id for p in toutes(f, etat0)}
        if inconnues:
            raise FileInvalide(f"PR absentes de la file : {', '.join(sorted(inconnues))}")
        if args.action == "etat":
            print(ecrire_tableau(f, etat0), end="")
            return 0
        if args.action == "verifier":
            return verifier(f, not args.sans_reseau)
        if args.action == "importer":
            if not args.depuis:
                raise FileInvalide("importer : --depuis ETAT.json obligatoire")
            with verrou(f.sortie):
                n = importer(f, etat0, args.depuis)
                print(f"{n} verdict(s) d'étapes cloud importé(s)")
                print(ecrire_tableau(f, etat0), end="")
            return 0
        with verrou(f.sortie):
            r = Runner(f, reseau=not args.sans_reseau, lieu=args.lieu)
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


def verifier(f: File, reseau: bool) -> int:
    """Contrôle de la file sans rien lancer (cloud ou PC) : têtes fixées, et composition de chaque paquet."""
    r = Runner(f, reseau=reseau, log=lambda *_: None)
    code = 0
    for pr in f.prs:
        try:
            sha = r.tete_pr(pr)
        except (TeteChangee, RuntimeError) as exc:
            print(f"{nom_pr(pr)} : {exc}")
            code = 1
            continue
        etapes = ", ".join(f"{e.id}{' (cloud)' if e.lieu == 'cloud' else ''}" for e in pr.etapes)
        print(f"{nom_pr(pr)} : {pr.categorie}, têtes {sha[:8] if '+' not in sha else '+'.join(x[:8] for x in sha.split('+'))} ; {etapes}")
        if pr.est_paquet:
            refus, avis = verifier_paquet(f.depot, pr, sha.split("+"), r.tete("main"))
            for a in avis:
                print(f"  avis : {a}")
            for x in refus:
                print(f"  REFUSÉ : {x}")
            code = code or (1 if refus else 0)
            if not refus:
                print("  paquet accepté")
    return code


if __name__ == "__main__":
    sys.exit(main())
