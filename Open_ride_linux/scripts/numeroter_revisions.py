#!/usr/bin/env python3
"""Numéroter les révisions IPC en attente (lot CF2, 26 novembre) : à jouer par le fil de fusion sur la branche du train.

Une PR qui change le contrat ajoute `core/src/openride_core/revisions_ipc/a_numeroter/LOT.txt` (une ligne : ce qui
change) et écrit sa ligne au journal de `docs/contracts/ipc_v1.md` avec « révision à la fusion, lot LOT ». Elle ne
touche ni `CONTRACT_REV` ni `historique.txt`, donc plusieurs PR de protocole passent dans le même train. Ce script,
une fois les PR assemblées sur la branche du train :
  - donne à chaque révision en attente le numéro suivant, dans l'ordre d'arrivée sur la branche (date du commit qui a
    ajouté le fichier, puis nom), ou dans l'ordre `--ordre LOT1,LOT2` ;
  - ajoute les lignes à `historique.txt`, supprime les fichiers en attente ;
  - remplace « révision à la fusion, lot LOT » par « révision 1.N, lot LOT » dans `docs/contracts/ipc_v1.md`.
`CONTRACT_REV` ne change pas de valeur (il comptait déjà les révisions en attente) : la numérotation fige seulement
quel lot a quel numéro.

    python3 scripts/numeroter_revisions.py            # à blanc : affiche les numéros
    python3 scripts/numeroter_revisions.py --ecrire   # écrit, puis : git commit -am "Révisions IPC numérotées"

PR ouverte d'avant le registre (CONTRACT_REV écrit à la main) : sur sa branche, `git merge origin/main`, puis
    python3 scripts/numeroter_revisions.py --migrer LOT
qui écrit a_numeroter/LOT.txt (texte tiré du commentaire de son CONTRACT_REV), règle les conflits de
`ipc_server.py` et `test_contract_ipc.py` qui portent sur CONTRACT_REV en gardant la version de main, et les
ajoute à l'index ; il reste à finir le commit de fusion (ou à régler les autres conflits).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJET = Path(__file__).resolve().parents[1]
REGISTRE = PROJET / "core" / "src" / "openride_core" / "revisions_ipc"
JOURNAL = PROJET / "docs" / "contracts" / "ipc_v1.md"
LISEZMOI = "LISEZMOI.txt"
FICHIERS_REV = ("core/src/openride_core/ipc_server.py", "core/tests/test_contract_ipc.py")


def derniere(historique: str) -> str:
    lignes = [l for l in historique.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    return lignes[-1].split("|", 1)[0].strip()


def date_ajout(fichier: Path) -> int:
    p = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ct", "--", str(fichier)], cwd=PROJET,
                       capture_output=True, text=True, check=False)
    dates = [int(x) for x in p.stdout.split()]
    return min(dates) if dates else 0


def en_attente(registre: Path, ordre: list[str] | None) -> list[Path]:
    fichiers = [f for f in (registre / "a_numeroter").glob("*.txt") if f.name != LISEZMOI]
    if ordre:
        par_lot = {f.stem: f for f in fichiers}
        inconnus = [lot for lot in ordre if lot not in par_lot]
        oublies = sorted(set(par_lot) - set(ordre))
        if inconnus or oublies:
            raise SystemExit(f"--ordre : lots inconnus {inconnus}, lots oubliés {oublies}")
        return [par_lot[lot] for lot in ordre]
    return sorted(fichiers, key=lambda f: (date_ajout(f), f.stem))


def numeroter(registre: Path, journal: Path | None, ordre: list[str] | None, ecrire: bool) -> list[tuple[str, str]]:
    histo = registre / "historique.txt"
    texte = histo.read_text(encoding="utf-8")
    numero = derniere(texte)
    major, minor = numero.split(".")
    attribues, lignes = [], []
    for i, f in enumerate(en_attente(registre, ordre), start=1):
        rev = f"{major}.{int(minor) + i}"
        desc = " ".join(f.read_text(encoding="utf-8").split()) or "—"
        attribues.append((f.stem, rev))
        lignes.append(f"{rev} | {f.stem} | {desc}")
    if ecrire and attribues:
        histo.write_text(texte.rstrip("\n") + "\n" + "\n".join(lignes) + "\n", encoding="utf-8")
        for lot, _ in attribues:
            (registre / "a_numeroter" / f"{lot}.txt").unlink()
        if journal and journal.exists():
            j = journal.read_text(encoding="utf-8")
            for lot, rev in attribues:
                j = j.replace(f"révision à la fusion, lot {lot}", f"révision {rev}, lot {lot}")
            journal.write_text(j, encoding="utf-8")
    return attribues


def resoudre_conflits_rev(texte: str) -> tuple[str, int]:
    """Blocs de conflit qui portent sur CONTRACT_REV : garder le côté de main (le bas, `git merge origin/main`)."""
    sortie, regles, i = [], 0, 0
    lignes = texte.splitlines(keepends=True)
    while i < len(lignes):
        if not lignes[i].startswith("<<<<<<< "):
            sortie.append(lignes[i])
            i += 1
            continue
        j = next(k for k in range(i, len(lignes)) if lignes[k].startswith("======="))
        k = next(k for k in range(j, len(lignes)) if lignes[k].startswith(">>>>>>> "))
        bloc = lignes[i:k + 1]
        if any("CONTRACT_REV" in l for l in bloc):
            sortie.extend(lignes[j + 1:k])
            regles += 1
        else:
            sortie.extend(bloc)
        i = k + 1
    return "".join(sortie), regles


def texte_de_la_branche(source: str) -> str:
    """« 1.41 : temps gagné … (lot TT2) ; 1.36 : … » → « temps gagné … (lot TT2) »."""
    import re
    m = re.search(r"^CONTRACT_REV\s*=\s*[\"'][^\"']+[\"']\s*#\s*(.*)$", source, re.M)
    if not m:
        return ""
    premier = m.group(1).split(" ; ")[0]
    return re.sub(r"^\d+\.\d+\s*(\([^)]*\))?\s*:\s*", "", premier).strip()


def migrer(lot: str) -> int:
    attente = REGISTRE / "a_numeroter" / f"{lot}.txt"
    if not attente.exists():
        p = subprocess.run(["git", "show", f"HEAD:{PROJET.name}/{FICHIERS_REV[0]}"], cwd=PROJET,
                           capture_output=True, text=True, check=False)
        attente.write_text((texte_de_la_branche(p.stdout) or f"révision du lot {lot}") + "\n", encoding="utf-8")
        print(f"écrit : a_numeroter/{lot}.txt : {attente.read_text(encoding='utf-8').strip()}")
    for rel in FICHIERS_REV:
        f = PROJET / rel
        texte, regles = resoudre_conflits_rev(f.read_text(encoding="utf-8"))
        if regles:
            f.write_text(texte, encoding="utf-8")
            print(f"{rel} : {regles} conflit(s) sur CONTRACT_REV réglé(s) avec la version de main")
        if "<<<<<<< " not in texte:
            subprocess.run(["git", "add", rel], cwd=PROJET, check=False)
    subprocess.run(["git", "add", str(attente)], cwd=PROJET, check=False)
    reste = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=PROJET, capture_output=True,
                           text=True, check=False).stdout.split()
    print("conflits restants : " + (", ".join(reste) if reste else "aucun (git commit pour finir la fusion)"))
    return 1 if reste else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--ecrire", action="store_true", help="écrire historique.txt et le journal (sinon : à blanc)")
    p.add_argument("--ordre", help="lots dans l'ordre voulu, séparés par des virgules")
    p.add_argument("--migrer", metavar="LOT", help="PR d'avant le registre, pendant un `git merge origin/main`")
    a = p.parse_args(argv)
    if a.migrer:
        return migrer(a.migrer)
    attribues = numeroter(REGISTRE, JOURNAL, a.ordre.split(",") if a.ordre else None, a.ecrire)
    if not attribues:
        print("aucune révision IPC en attente")
        return 0
    for lot, rev in attribues:
        print(f"{lot} : révision {rev}")
    print("écrit : historique.txt, a_numeroter/, ipc_v1.md" if a.ecrire else "à blanc (--ecrire pour écrire)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
