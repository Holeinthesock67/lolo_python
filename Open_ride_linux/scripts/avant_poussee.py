#!/usr/bin/env python3
"""Contrôle avant poussée (lot AP1, 26 novembre) : les causes d'échec de CI les plus fréquentes, vues en 1 minute
sur la machine qui pousse au lieu de 25 minutes plus tard sur la CI ou dans un train de fusion.

Relevé des 24-26 novembre (statut/FIABILITE_CI_BANCS_2026-11-26.md) : sur 10 exécutions rouges de la CI,
8 venaient d'un oubli qu'un contrôle local voit tout de suite :
  - fichier `.uid` d'un nouveau script GDScript non versionné (trains 940 et 999/1038, #1008, #953) ;
  - test qui écrit hors de son `tmp_path` (#1039, train de la courbe de puissance) ;
  - deux PR qui prennent le même numéro (lot EN1 décrit deux fois ; révision IPC ou WORLDGEN déjà prise par main) ;
  - schéma ou test d'une autre PR fusionnée entre-temps (branche partie d'une base périmée).

Étapes, dans l'ordre :
  1. git : `git fetch origin main` (sauf `--sans-reseau`), base commune, fichiers changés, rien de non commité ;
  2. `.uid` : chaque `engine/**/*.gd` a son `.gd.uid` (format Godot, unique) ; `--corriger` écrit ceux qui manquent ;
  3. numéros partagés : révision IPC (`CONTRACT_REV`), `WORLDGEN_VERSION`, `SCHEMA_VERSION` changés par la branche
     doivent dépasser la valeur de main *actuelle* (une autre PR a pu prendre le même numéro depuis le départ) ;
  4. assemblage à blanc avec main (`git merge-tree`, rien n'est écrit) : conflit de texte vu avant la poussée ;
  5. tests rapides : cohérence des docs et index des lots (numéro de lot en double), `.uid`, contrat IPC (5 s) ;
  6. tests touchés : fichiers de test changés par la branche, et `test_<module>*.py` des modules changés, joués
     avec le garde-fou d'écriture de `isolation_tests.py` (écriture hors de `tmp_path` = échec) ;
     `--sans-tests` saute 5 et 6, `--tous` joue toutes les suites du core et du compilateur.

    python3 scripts/avant_poussee.py                  # depuis Open_ride_linux/, avant chaque `git push`
    python3 scripts/avant_poussee.py --corriger       # écrit aussi les .uid manquants (à commiter ensuite)
    python3 scripts/avant_poussee.py --installer-crochet   # crochet git pre-push du dépôt local
    python3 scripts/avant_poussee.py --avant-fusion   # fil de fusion, juste avant de fusionner un train (secondes)

Fraîcheur (lot BM1) : main changé depuis la base de la branche sur un fichier qu'elle touche aussi, ou sur un fichier
partagé (contrat IPC, `main.gd`, garde-fou des tests) : avis avant une poussée, échec avec `--avant-fusion` (la CI
verte du train ne vaut alors plus : fusionner main dans le train et attendre sa CI).

À jouer aussi sur la branche d'un train, avant sa CI : une faute peut naître de l'assemblage (26/11, #1039 passait
seul, le train de la courbe de puissance écrivait hors de `tmp_path`). Rejoué sur les deux trains rouges du 26/11
au matin, il les arrête tous les deux (.uid du train 940, écriture hors de `tmp_path` du train 975…1039).

Code de sortie : 0 si la poussée peut partir, 1 sinon, 2 si l'appel est invalide. Bibliothèque standard seulement
(pytest est lancé avec l'interpréteur courant, ou `OPENRIDE_VENV`/bin/python s'il existe).
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJET = Path(__file__).resolve().parents[1]          # Open_ride_linux/
SOUS_DOSSIER = PROJET.name                             # chemins git relatifs à la racine du dépôt

# Constantes qu'une seule PR à la fois peut monter (mêmes que scripts/file_bancs.py, VERSIONS).
VERSIONS = {
    "révision IPC": ("core/src/openride_core/ipc_server.py", re.compile(r"^CONTRACT_REV\s*=\s*[\"']([^\"']+)[\"']", re.M)),
    "WORLDGEN_VERSION": ("compiler/src/openride_compiler/worldgen/squares.py",
                         re.compile(r"^WORLDGEN_VERSION\s*=\s*(\d+)", re.M)),
    "SCHEMA_VERSION": ("compiler/src/openride_compiler/worldgen/osmdb.py", re.compile(r"^SCHEMA_VERSION\s*=\s*(\d+)", re.M)),
}

# Tests rapides joués à chaque fois (moins de 10 s) : ce qu'une autre PR casse le plus souvent sans conflit de texte.
TESTS_RAPIDES = {
    "core": ["tests/test_engine_uid.py", "tests/test_docs_coherence.py", "tests/test_index_lots.py",
             "tests/test_contract_ipc.py"],
}

UID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"   # ResourceUID::id_to_text de Godot (base 36)
UID_RE = re.compile(r"uid://[a-z0-9]{1,13}")

OK, ECHEC, AVIS = "OK", "ÉCHEC", "AVIS"


@dataclass
class Bilan:
    lignes: list[tuple[str, str]] = field(default_factory=list)

    def note(self, verdict: str, texte: str) -> None:
        self.lignes.append((verdict, texte))
        print(f"[{verdict}] {texte}", flush=True)

    @property
    def echecs(self) -> int:
        return sum(1 for v, _ in self.lignes if v == ECHEC)


def git(*args: str, cwd: Path = PROJET, check: bool = True) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} : {p.stderr.strip()[-200:]}")
    return p.stdout


def montrer(rev: str, chemin: str) -> str | None:
    """Contenu de `chemin` (relatif à Open_ride_linux/) à la révision `rev`, None s'il n'existe pas."""
    p = subprocess.run(["git", "show", f"{rev}:{SOUS_DOSSIER}/{chemin}"], cwd=PROJET, capture_output=True,
                       text=True, check=False)
    return p.stdout if p.returncode == 0 else None


def cle_version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def version(rev: str, nom: str) -> str | None:
    chemin, motif = VERSIONS[nom]
    m = motif.search(montrer(rev, chemin) or "")
    return m.group(1) if m else None


def suivante(v: str) -> str:
    parts = v.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


# --- 2. fichiers .uid ---------------------------------------------------------------------------------------------

def nouvel_uid(pris: set[str]) -> str:
    """Identifiant au format de Godot : entier positif sur 63 bits écrit en base 36 (lettres puis chiffres)."""
    while True:
        n = secrets.randbits(63) or 1
        s = ""
        while n:
            s = UID_ALPHABET[n % 36] + s
            n //= 36
        uid = "uid://" + s
        if uid not in pris:
            return uid


def controle_uid(engine: Path, corriger: bool, bilan: Bilan) -> None:
    scripts = sorted(p for p in engine.rglob("*.gd") if ".godot" not in p.parts)
    pris: dict[str, Path] = {}
    mal_formes = []
    for u in sorted(engine.rglob("*.gd.uid")):
        texte = u.read_text(encoding="utf-8").strip()
        if not UID_RE.fullmatch(texte):
            mal_formes.append(u.relative_to(engine).as_posix())
        elif texte in pris:
            bilan.note(ECHEC, f".uid en double : {u.relative_to(engine)} et {pris[texte].relative_to(engine)} ({texte})")
        pris[texte] = u
    if mal_formes:
        bilan.note(ECHEC, f".uid mal formé(s) : {', '.join(mal_formes)}")
    manquants = [p for p in scripts if not p.with_name(p.name + ".uid").is_file()]
    orphelins = [u for u in engine.rglob("*.gd.uid") if not u.with_name(u.name[:-4]).is_file()]
    if orphelins:
        bilan.note(AVIS, ".uid sans script (à retirer avec son script) : "
                   + ", ".join(u.relative_to(engine).as_posix() for u in sorted(orphelins)))
    if not manquants:
        bilan.note(OK, f".uid : les {len(scripts)} scripts GDScript ont le leur")
        return
    noms = ", ".join(p.relative_to(engine).as_posix() for p in manquants)
    if not corriger:
        bilan.note(ECHEC, f".uid manquant(s) : {noms} (relancer avec --corriger, puis git add)")
        return
    deja = set(pris)
    for p in manquants:
        uid = nouvel_uid(deja)
        deja.add(uid)
        p.with_name(p.name + ".uid").write_text(uid + "\n", encoding="utf-8")
    bilan.note(AVIS, f".uid écrit(s) : {noms} (à ajouter au commit : git add engine/)")


# --- 3. numéros partagés et 4. assemblage ---------------------------------------------------------------------------

def controle_versions(base: str, main: str, bilan: Bilan) -> None:
    for nom in VERSIONS:
        avant, apres, sur_main = version(base, nom), version("HEAD", nom), version(main, nom)
        if avant == apres:
            continue
        if apres is None or sur_main is None:
            bilan.note(AVIS, f"{nom} : non lu ({avant} → {apres}, main {sur_main})")
        elif cle_version(apres) <= cle_version(sur_main):
            bilan.note(ECHEC, f"{nom} : la branche passe à {apres}, mais main est déjà à {sur_main} "
                       f"(prise par une autre PR) : renuméroter en {suivante(sur_main)}")
        else:
            bilan.note(OK, f"{nom} : {avant} → {apres} (main {sur_main})")


def controle_assemblage(main: str, bilan: Bilan) -> None:
    p = subprocess.run(["git", "merge-tree", "--write-tree", "--name-only", main, "HEAD"], cwd=PROJET,
                       capture_output=True, text=True, check=False)
    if p.returncode == 0:
        bilan.note(OK, "assemblage avec main : sans conflit")
    elif p.returncode == 1:
        conflits = [l for l in p.stdout.splitlines()[1:] if l and not l.startswith(("Auto-merging", "CONFLICT"))]
        bilan.note(ECHEC, f"assemblage avec main en conflit : {', '.join(conflits[:6]) or 'voir git merge'} "
                   "(fusionner main dans la branche)")
    else:
        bilan.note(AVIS, f"assemblage non vérifié (git trop ancien ?) : {p.stderr.strip()[-120:]}")


# --- fraîcheur de la base (lot BM1) -------------------------------------------------------------------------------

# Fichiers dont un changement sur main peut casser une branche sans toucher à ses fichiers (contrat IPC, schémas,
# scène principale de l'engine, règles partagées des tests) : signalés même sans fichier commun.
SENSIBLES = re.compile(r"^(docs/contracts/|engine/scripts/main\.gd$|core/src/openride_core/ipc_server\.py$|"
                       r"scripts/isolation_tests\.py$|core/tests/conftest\.py$|compiler/tests/conftest\.py$)")


def controle_fraicheur(base: str, main_sha: str, changes: list[str], avant_fusion: bool, bilan: Bilan) -> None:
    """Base qui bouge (26/11 : 3 trains rouges sur 5, #820 et #821 le 08/11) : une CI verte ne vaut que pour le main
    qu'elle a vu. Fichiers changés sur main depuis la base de la branche, croisés avec ceux de la branche."""
    prefixe = SOUS_DOSSIER + "/"
    sur_main = {l[len(prefixe):] for l in git("diff", "--name-only", base, main_sha).splitlines()
                if l.startswith(prefixe)}
    if not sur_main:
        bilan.note(OK, "fraîcheur : main n'a rien changé depuis la base de la branche")
        return
    communs = sorted(sur_main & set(changes))
    sensibles = sorted(c for c in sur_main - set(changes) if SENSIBLES.match(c))
    verdict = ECHEC if avant_fusion else AVIS
    if communs:
        bilan.note(verdict, f"fraîcheur : main a changé depuis la base {len(communs)} fichier(s) que la branche touche "
                   f"aussi : {', '.join(communs[:6])}{' …' if len(communs) > 6 else ''} "
                   "(fusionner main dans la branche, puis attendre sa CI)")
    if sensibles:
        bilan.note(verdict, f"fraîcheur : main a changé depuis la base des fichiers partagés : {', '.join(sensibles[:6])} "
                   "(fusionner main dans la branche, puis attendre sa CI)")
    if not communs and not sensibles:
        bilan.note(OK, f"fraîcheur : {len(sur_main)} fichier(s) changé(s) sur main depuis la base, aucun en commun")


# --- 5. et 6. tests -------------------------------------------------------------------------------------------------

def tests_touches(changes: list[str]) -> dict[str, set[str]]:
    """{suite: fichiers de test} : tests changés, et tests nommés d'après un module changé (`test_<module>*.py`)."""
    out: dict[str, set[str]] = {"core": set(), "compiler": set()}
    for c in changes:
        parts = Path(c).parts
        if len(parts) < 2 or parts[0] not in out:
            continue
        suite, nom = parts[0], Path(c).name
        dossier = PROJET / suite / "tests"
        if parts[1] == "tests" and nom.startswith("test_") and nom.endswith(".py"):
            if (PROJET / c).is_file():
                out[suite].add(Path(*parts[1:]).as_posix())
        elif parts[1] == "src" and nom.endswith(".py") and nom != "__init__.py":
            for t in dossier.glob(f"test_{Path(nom).stem}*.py"):
                out[suite].add(t.relative_to(PROJET / suite).as_posix())
    return out


def python_tests() -> str:
    venv = os.environ.get("OPENRIDE_VENV")
    if venv and (Path(venv) / "bin" / "python").is_file():
        return str(Path(venv) / "bin" / "python")
    return sys.executable


def controle_paquets(bilan: Bilan) -> None:
    """Les paquets importés par les tests doivent être ceux de ce dossier (sinon les tests jugent un autre code)."""
    p = subprocess.run([python_tests(), "-c", "import openride_core, openride_compiler as c; "
                        "print(openride_core.__file__); print(c.__file__)"],
                       capture_output=True, text=True, check=False)
    if p.returncode != 0:
        bilan.note(AVIS, "openride_core ou openride_compiler absent de l'environnement des tests "
                   "(pip install -e core[dev] -e compiler[dev,worldgen])")
        return
    ailleurs = [f for f in p.stdout.split() if not Path(f).resolve().is_relative_to(PROJET)]
    if ailleurs:
        bilan.note(AVIS, f"paquets installés depuis un autre dossier : {', '.join(ailleurs)} (tests sur un autre code)")


def jouer_pytest(suite: str, fichiers: list[str], bilan: Bilan, quoi: str) -> None:
    if not fichiers:
        return
    env = {k: v for k, v in os.environ.items() if k != "OPENRIDE_TESTS_PARTIE"}
    p = subprocess.run([python_tests(), "-m", "pytest", "-q", "-p", "no:cacheprovider", *fichiers],
                       cwd=PROJET / suite, env=env, capture_output=True, text=True, check=False)
    fin = (p.stdout.strip().splitlines() or [""])[-1]
    if p.returncode == 0:
        bilan.note(OK, f"{quoi} ({suite}, {len(fichiers)} fichier(s)) : {fin}")
        return
    rates = [l for l in p.stdout.splitlines() if l.startswith(("FAILED", "ERROR"))]
    if p.returncode == 5 and not rates:
        bilan.note(AVIS, f"{quoi} ({suite}) : aucun test trouvé")
        return
    bilan.note(ECHEC, f"{quoi} ({suite}) : {fin}")
    for l in rates[:10]:
        print("    " + l[:300], flush=True)
    if not rates:
        print("\n".join("    " + l for l in (p.stdout + p.stderr).strip().splitlines()[-15:]), flush=True)


# --- crochet git ----------------------------------------------------------------------------------------------------

CROCHET = """#!/bin/sh
# Crochet posé par scripts/avant_poussee.py --installer-crochet (lot AP1). Contourner une fois : git push --no-verify
exec python3 "$(git rev-parse --show-toplevel)/{sous}/scripts/avant_poussee.py" --sans-reseau
"""


def installer_crochet() -> int:
    dossier = Path(git("rev-parse", "--git-path", "hooks").strip())
    if not dossier.is_absolute():
        dossier = PROJET / dossier
    dossier.mkdir(parents=True, exist_ok=True)
    crochet = dossier / "pre-push"
    if crochet.exists() and "avant_poussee.py" not in crochet.read_text(encoding="utf-8", errors="replace"):
        print(f"un autre crochet pre-push existe déjà : {crochet} (laissé tel quel)")
        return 1
    crochet.write_text(CROCHET.format(sous=SOUS_DOSSIER), encoding="utf-8")
    crochet.chmod(0o755)
    print(f"crochet installé : {crochet}")
    return 0


# --- principal ------------------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--main", default="origin/main", help="référence de main (défaut origin/main)")
    ap.add_argument("--sans-reseau", action="store_true", help="pas de git fetch")
    ap.add_argument("--corriger", action="store_true", help="écrire les .uid manquants")
    ap.add_argument("--sans-tests", action="store_true", help="sauter les tests (étapes 5 et 6)")
    ap.add_argument("--tous", action="store_true", help="jouer toutes les suites du core et du compilateur")
    ap.add_argument("--installer-crochet", action="store_true", help="poser le crochet git pre-push et sortir")
    ap.add_argument("--avant-fusion", action="store_true",
                    help="juste avant de fusionner (fil de fusion) : main changé sur un fichier commun = échec ; sans tests")
    a = ap.parse_args(argv)
    if a.installer_crochet:
        return installer_crochet()

    bilan = Bilan()
    try:
        if not a.sans_reseau and a.main.startswith("origin/"):
            git("fetch", "-q", "origin", a.main.split("/", 1)[1])
        main_sha = git("rev-parse", a.main).strip()
        base = git("merge-base", "HEAD", main_sha).strip()
    except RuntimeError as exc:
        print(f"[{ECHEC}] git : {exc}")
        return 2
    prefixe = SOUS_DOSSIER + "/"
    changes = [l[len(prefixe):] for l in git("diff", "--name-only", base, "HEAD").splitlines() if l.startswith(prefixe)]
    sale = [l for l in git("status", "--porcelain", "--", ".").splitlines() if l.strip()]
    retard = int(git("rev-list", "--count", f"{base}..{main_sha}").strip() or 0)
    bilan.note(OK, f"branche : {len(changes)} fichier(s) changé(s) depuis main ; main a {retard} commit(s) de plus "
               "que la base de la branche")
    if sale:
        bilan.note(AVIS, f"{len(sale)} fichier(s) non commité(s) : {', '.join(l[3:] for l in sale[:5])}"
                   + (" …" if len(sale) > 5 else "") + " (ils ne partiront pas avec la poussée)")

    controle_uid(PROJET / "engine", a.corriger, bilan)
    controle_versions(base, main_sha, bilan)
    controle_assemblage(main_sha, bilan)
    controle_fraicheur(base, main_sha, changes, a.avant_fusion, bilan)

    if not (a.sans_tests or a.avant_fusion):
        controle_paquets(bilan)
        if a.tous:
            jouer_pytest("core", ["tests"], bilan, "toute la suite")
            jouer_pytest("compiler", ["tests"], bilan, "toute la suite")
        else:
            for suite, fichiers in TESTS_RAPIDES.items():
                jouer_pytest(suite, [f for f in fichiers if (PROJET / suite / f).is_file()], bilan, "tests rapides")
            for suite, fichiers in tests_touches(changes).items():
                reste = sorted(fichiers - set(TESTS_RAPIDES.get(suite, [])))
                jouer_pytest(suite, reste, bilan, "tests touchés")

    quoi = "FUSIONNER" if a.avant_fusion else "POUSSER"
    if bilan.echecs:
        print(f"=== NE PAS {quoi} : {bilan.echecs} échec(s)", flush=True)
        return 1
    print(f"=== PRÊT À {quoi}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
