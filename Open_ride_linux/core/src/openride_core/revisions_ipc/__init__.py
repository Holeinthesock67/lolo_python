"""Registre des révisions du contrat IPC (lot CF2, 26 novembre).

`CONTRACT_REV` (ipc_server.py) n'est plus écrit à la main : il vaut la dernière révision de `historique.txt`,
plus une par révision en attente dans `a_numeroter/` (un fichier par lot). Une PR qui change le contrat ajoute
seulement son fichier, à son nom : les PR de protocole ne réécrivent plus la même ligne et ne se bloquent plus.
Le contrat ne change pas : `rev` reste une chaîne « 1.N » et suit toujours l'ordre des fusions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources

LISEZMOI = "LISEZMOI.txt"
NOM_LOT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.txt$")


@dataclass(frozen=True)
class Revision:
    numero: str
    lots: str
    texte: str


def cle(numero: str) -> tuple[int, ...]:
    return tuple(int(x) for x in numero.split("."))


def lire_historique(texte: str) -> list[Revision]:
    revs = []
    for ligne in texte.splitlines():
        if not ligne.strip() or ligne.lstrip().startswith("#"):
            continue
        numero, lots, desc = (m.strip() for m in (ligne.split("|", 2) + ["", ""])[:3])
        revs.append(Revision(numero, lots, desc))
    return revs


def _dossier():
    return resources.files(__name__)


def historique() -> list[Revision]:
    return lire_historique((_dossier() / "historique.txt").read_text(encoding="utf-8"))


def en_attente() -> list[str]:
    """Noms de lot des révisions sans numéro (fichiers de a_numeroter/, triés)."""
    d = _dossier() / "a_numeroter"
    return sorted(f.name[:-4] for f in d.iterdir() if f.name != LISEZMOI and f.name.endswith(".txt"))


def revision(derniere: str, attente: int) -> str:
    major, minor = derniere.split(".")
    return f"{major}.{int(minor) + attente}"


def revision_courante() -> str:
    return revision(historique()[-1].numero, len(en_attente()))
