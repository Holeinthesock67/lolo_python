"""Registre des révisions du contrat IPC (lot CF2, 26 novembre) et numérotation à la fusion."""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

from openride_core import ipc_server, revisions_ipc

ROOT = Path(__file__).resolve().parents[2]
REGISTRE = ROOT / "core" / "src" / "openride_core" / "revisions_ipc"


def _numeroter():
    spec = importlib.util.spec_from_file_location("numeroter_revisions", ROOT / "scripts" / "numeroter_revisions.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["numeroter_revisions"] = mod
    spec.loader.exec_module(mod)
    return mod


nr = _numeroter()


def test_historique_croissant_et_contract_rev_calcule():
    revs = revisions_ipc.historique()
    cles = [revisions_ipc.cle(r.numero) for r in revs]
    assert cles == sorted(cles) and len(set(cles)) == len(cles)
    assert all(re.fullmatch(r"1\.\d+", r.numero) and r.lots and r.texte for r in revs)
    assert ipc_server.CONTRACT_REV == revisions_ipc.revision(revs[-1].numero, len(revisions_ipc.en_attente()))
    assert revisions_ipc.cle(ipc_server.CONTRACT_REV) >= (1, 36)       # jamais en dessous de la dernière à la main


def test_fichiers_en_attente_bien_formes():
    deja = {lot.strip() for r in revisions_ipc.historique() for lot in r.lots.split(",")}
    for f in (REGISTRE / "a_numeroter").iterdir():
        assert revisions_ipc.NOM_LOT_RE.match(f.name), f"{f.name} : un fichier LOT.txt par révision"
        if f.name != revisions_ipc.LISEZMOI:
            assert f.read_text(encoding="utf-8").strip(), f"{f.name} vide : écrire ce qui change"
            assert f.stem not in deja, f"{f.stem} déjà numéroté dans historique.txt"


def test_contract_rev_pas_ecrit_a_la_main():
    source = (ROOT / "core" / "src" / "openride_core" / "ipc_server.py").read_text(encoding="utf-8")
    assert re.search(r"^CONTRACT_REV = revisions_ipc\.revision_courante\(\)$", source, re.M)
    assert not re.search(r"^CONTRACT_REV\s*=\s*[\"']", source, re.M)


def test_revision():
    assert revisions_ipc.revision("1.36", 0) == "1.36"
    assert revisions_ipc.revision("1.36", 3) == "1.39"
    assert revisions_ipc.revision("1.9", 1) == "1.10"


def _registre(tmp_path, attente):
    reg = tmp_path / "revisions_ipc"
    (reg / "a_numeroter").mkdir(parents=True)
    (reg / "historique.txt").write_text("# en-tête\n1.35 | PP3 | puissance\n1.36 | SV1 | copies\n")
    (reg / "a_numeroter" / "LISEZMOI.txt").write_text("# aide\n")
    for lot, texte in attente.items():
        (reg / "a_numeroter" / f"{lot}.txt").write_text(texte)
    return reg


def test_numeroter_a_blanc_puis_ecrit(tmp_path):
    reg = _registre(tmp_path, {"DG1": "diagnostic\n", "BA1": "attaque des bots\n"})
    journal = tmp_path / "ipc_v1.md"
    journal.write_text("| 1 (révision à la fusion, lot BA1) | x |\n| 1 (révision à la fusion, lot DG1) | y |\n")
    assert nr.numeroter(reg, journal, ["DG1", "BA1"], ecrire=False) == [("DG1", "1.37"), ("BA1", "1.38")]
    assert (reg / "a_numeroter" / "DG1.txt").exists()                   # à blanc : rien d'écrit
    nr.numeroter(reg, journal, ["DG1", "BA1"], ecrire=True)
    histo = (reg / "historique.txt").read_text()
    assert histo.endswith("1.37 | DG1 | diagnostic\n1.38 | BA1 | attaque des bots\n")
    assert sorted(f.name for f in (reg / "a_numeroter").iterdir()) == ["LISEZMOI.txt"]
    assert "révision 1.38, lot BA1" in journal.read_text() and "révision 1.37, lot DG1" in journal.read_text()
    assert nr.numeroter(reg, journal, None, ecrire=True) == []          # plus rien en attente


def test_ordre_incomplet_refuse(tmp_path):
    reg = _registre(tmp_path, {"DG1": "a", "BA1": "b"})
    try:
        nr.numeroter(reg, None, ["DG1"], ecrire=False)
    except SystemExit as exc:
        assert "BA1" in str(exc)
    else:
        raise AssertionError("ordre incomplet accepté")


def test_conflit_contract_rev_regle_avec_main():
    texte = ("a\n<<<<<<< HEAD\nCONTRACT_REV = \"1.41\"   # 1.41 : bonus (lot TT2)\n=======\n"
             "CONTRACT_REV = revisions_ipc.revision_courante()\n>>>>>>> origin/main\n"
             "<<<<<<< HEAD\nx = 1\n=======\nx = 2\n>>>>>>> origin/main\nz\n")
    sortie, regles = nr.resoudre_conflits_rev(texte)
    assert regles == 1
    assert sortie.startswith("a\nCONTRACT_REV = revisions_ipc.revision_courante()\n<<<<<<< HEAD\nx = 1\n")
    assert nr.texte_de_la_branche('CONTRACT_REV = "1.41"   # 1.41 (provisoire) : bonus (lot TT2) ; 1.36 : x\n') \
        == "bonus (lot TT2)"


def test_registre_embarque_dans_le_paquet():
    pyproject = (ROOT / "core" / "pyproject.toml").read_text(encoding="utf-8")
    assert '"revisions_ipc/*.txt", "revisions_ipc/a_numeroter/*.txt"' in pyproject
    sortie = subprocess.run([sys.executable, str(ROOT / "scripts" / "numeroter_revisions.py")],
                            capture_output=True, text=True, check=True).stdout
    assert "révision" in sortie
