#!/usr/bin/env python3
"""PR ouvertes que la dernière fusion a mises en conflit avec main (lot CF1, 26 novembre).

Après la fusion du train de la courbe de puissance (#1098, 15h57), les PR en attente qu'elle mettait en conflit
n'ont été vues qu'à 17h28, au moment de bâtir le train suivant : 1 h 30 perdue pour le train de protocole. À lancer
par le fil de fusion **juste après chaque fusion** : en moins d'une minute, il dit quelles PR prévenir.

Pour chaque PR ouverte, sur main *actuelle* et à blanc (`git merge-tree`, rien n'est écrit, aucune branche n'est
touchée) :
  - CONFLIT : la fusion avec main ne passe pas ; fichiers en conflit listés ;
  - NUMÉRO : la branche monte la révision IPC, `WORLDGEN_VERSION` ou `SCHEMA_VERSION` (règle de
    `avant_poussee.py`), mais main a déjà cette valeur ou plus : renuméroter (renumérotation seule = go gardé) ;
  - OK : rien à faire.

Liste des PR ouvertes, au choix :
    python3 scripts/conflits_ouverts.py --gh                      # gh pr list (gh connecté)
    python3 scripts/conflits_ouverts.py --liste prs.txt           # une ligne « NUMÉRO BRANCHE » par PR
    printf '1095 claude/x\\n1096 claude/y\\n' | python3 scripts/conflits_ouverts.py --liste -
Options : `--sortie FICHIER` (tableau Markdown, à transmettre aux fils), `--main REF` (défaut origin/main),
`--sans-reseau` (pas de git fetch), `--tous` (affiche aussi les PR OK).

Code de sortie : 0 si aucune PR à prévenir, 1 s'il y en a, 2 si l'appel est invalide. Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJET = Path(__file__).resolve().parents[1]


def _avant_poussee():
    """Règle des numéros partagés lue dans avant_poussee.py (une seule règle, pas une copie)."""
    spec = importlib.util.spec_from_file_location("avant_poussee", PROJET / "scripts" / "avant_poussee.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("avant_poussee", mod)
    spec.loader.exec_module(mod)
    return mod


ap = _avant_poussee()

CONFLIT, NUMERO, OK, ERREUR = "CONFLIT", "NUMÉRO", "OK", "ERREUR"


@dataclass
class Resultat:
    numero: str
    branche: str
    verdict: str = OK
    details: list[str] = field(default_factory=list)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", *args], cwd=PROJET, capture_output=True, text=True, check=False)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])} : {p.stderr.strip()[-200:]}")
    return p


def lire_liste(texte: str) -> list[tuple[str, str]]:
    """Lignes « NUMÉRO BRANCHE » (le # du numéro est accepté ; lignes vides et commentaires ignorés)."""
    prs = []
    for ligne in texte.splitlines():
        morceaux = ligne.split()
        if morceaux and morceaux[0].startswith("#"):                   # « #1096 branche » ou commentaire
            morceaux[0] = morceaux[0][1:]
        if len(morceaux) >= 2 and morceaux[0].isdigit():
            prs.append((morceaux[0], morceaux[1]))
    return prs


def liste_gh() -> list[tuple[str, str]]:
    p = subprocess.run(["gh", "pr", "list", "--state", "open", "--limit", "300", "--json", "number,headRefName"],
                       cwd=PROJET, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"gh pr list : {p.stderr.strip()[-200:]} (sinon : --liste)")
    return [(str(d["number"]), d["headRefName"]) for d in json.loads(p.stdout)]


def examiner(numero: str, branche: str, main: str) -> Resultat:
    r = Resultat(numero, branche)
    tete = f"origin/{branche}"
    if git("rev-parse", "--verify", "-q", tete, check=False).returncode != 0:
        r.verdict, r.details = ERREUR, [f"branche {branche} introuvable sur origin"]
        return r
    p = git("merge-tree", "--write-tree", "--name-only", main, tete, check=False)
    if p.returncode == 1:
        fichiers = [l for l in p.stdout.splitlines()[1:] if l and not l.startswith(("Auto-merging", "CONFLICT"))]
        r.verdict = CONFLIT
        r.details.append("conflit avec main : " + (", ".join(fichiers[:6]) + (" …" if len(fichiers) > 6 else "")
                                                   if fichiers else "voir git merge"))
    elif p.returncode != 0:
        r.verdict, r.details = ERREUR, [f"git merge-tree : {p.stderr.strip()[-160:]}"]
        return r
    base = git("merge-base", main, tete).stdout.strip()
    for nom in ap.VERSIONS:
        avant, apres, sur_main = ap.version(base, nom), ap.version(tete, nom), ap.version(main, nom)
        if avant != apres and apres and sur_main and ap.cle_version(apres) <= ap.cle_version(sur_main):
            if r.verdict == OK:
                r.verdict = NUMERO
            r.details.append(f"{nom} {apres} déjà prise par main ({sur_main}) : renuméroter en {ap.suivante(sur_main)}")
    return r


def tableau(resultats: list[Resultat], main_sha: str, tous: bool) -> str:
    lignes = [f"# PR ouvertes à prévenir après la fusion (main {main_sha[:8]})", "",
              "| PR | Branche | Verdict | Détail |", "|---|---|---|---|"]
    for r in resultats:
        if tous or r.verdict != OK:
            lignes.append(f"| #{r.numero} | `{r.branche}` | {r.verdict} | {' ; '.join(r.details) or '—'} |")
    a_prevenir = sum(1 for r in resultats if r.verdict in (CONFLIT, NUMERO))
    lignes += ["", f"{a_prevenir} PR à prévenir sur {len(resultats)} ouvertes."]
    return "\n".join(lignes) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--gh", action="store_true", help="PR ouvertes lues par gh pr list")
    source.add_argument("--liste", help="fichier de lignes « NUMÉRO BRANCHE » (- : entrée standard)")
    p.add_argument("--main", default="origin/main")
    p.add_argument("--sans-reseau", action="store_true")
    p.add_argument("--sortie", type=Path, help="tableau Markdown écrit ici")
    p.add_argument("--tous", action="store_true", help="afficher aussi les PR sans rien à faire")
    a = p.parse_args(argv)
    try:
        prs = liste_gh() if a.gh else lire_liste(sys.stdin.read() if a.liste == "-" else Path(a.liste).read_text())
        if not prs:
            print("aucune PR dans la liste", file=sys.stderr)
            return 2
        if not a.sans_reseau:
            refs = [f"+refs/heads/{b}:refs/remotes/origin/{b}" for _, b in prs]
            if a.main.startswith("origin/"):
                refs.append(f"+refs/heads/{a.main[7:]}:refs/remotes/{a.main}")
            git("fetch", "-q", "origin", *refs, check=False)
        main_sha = git("rev-parse", a.main).stdout.strip()
    except (RuntimeError, OSError) as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 2
    resultats = [examiner(n, b, main_sha) for n, b in prs]
    texte = tableau(resultats, main_sha, a.tous)
    print(texte, end="")
    if a.sortie:
        a.sortie.parent.mkdir(parents=True, exist_ok=True)
        a.sortie.write_text(texte, encoding="utf-8")
    return 1 if any(r.verdict in (CONFLIT, NUMERO) for r in resultats) else 0


if __name__ == "__main__":
    sys.exit(main())
