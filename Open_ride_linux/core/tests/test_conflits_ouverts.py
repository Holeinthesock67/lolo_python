"""PR ouvertes mises en conflit par la dernière fusion (scripts/conflits_ouverts.py, lot CF1, 26 novembre)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("conflits_ouverts", ROOT / "scripts" / "conflits_ouverts.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["conflits_ouverts"] = mod
    spec.loader.exec_module(mod)
    return mod


co = _load()
IPC = "core/src/openride_core/ipc_server.py"


def _git(depot, *args):
    subprocess.run(["git", *args], cwd=depot, check=True, capture_output=True, text=True)


def _ecrire(depot, chemin, texte, message):
    f = depot / "Open_ride_linux" / chemin
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(texte)
    _git(depot, "add", "-A")
    _git(depot, "commit", "-q", "-m", message)


def _depot(tmp_path, monkeypatch):
    """Dépôt jetable : main a fusionné la révision IPC 1.37 et changé a.txt ; trois branches de PR."""
    d = tmp_path / "depot"
    d.mkdir()
    _git(d, "init", "-q", "-b", "main")
    _git(d, "config", "user.email", "t@example.invalid")
    _git(d, "config", "user.name", "t")
    _ecrire(d, IPC, 'CONTRACT_REV = "1.36"\n', "base")
    _ecrire(d, "a.txt", "un\n", "a")
    for branche, chemin, texte in (("conflit", "a.txt", "deux\n"), ("numero", IPC, 'CONTRACT_REV = "1.37"\n'),
                                   ("ok", "b.txt", "b\n")):
        _git(d, "checkout", "-q", "-b", branche, "main")
        _ecrire(d, chemin, texte, branche)
        _git(d, "update-ref", f"refs/remotes/origin/{branche}", branche)
    _git(d, "checkout", "-q", "main")
    _ecrire(d, "a.txt", "trois\n", "main a")
    _ecrire(d, IPC, 'CONTRACT_REV = "1.37"\n', "main ipc")
    monkeypatch.setattr(co, "PROJET", d / "Open_ride_linux")
    monkeypatch.setattr(co.ap, "PROJET", d / "Open_ride_linux")
    monkeypatch.setattr(co.ap, "SOUS_DOSSIER", "Open_ride_linux")
    return d


def test_lire_liste():
    texte = "# PR du train\n1095 claude/a\n#1096 claude/b\n\nnimporte quoi\n 1097   claude/c  \n"
    assert co.lire_liste(texte) == [("1095", "claude/a"), ("1096", "claude/b"), ("1097", "claude/c")]


def test_verdicts_sur_depot_jetable(tmp_path, monkeypatch):
    _depot(tmp_path, monkeypatch)
    res = {r.branche: r for r in (co.examiner(n, b, "main") for n, b in
                                  (("1", "conflit"), ("2", "numero"), ("3", "ok"), ("4", "absente")))}
    assert res["conflit"].verdict == co.CONFLIT and "a.txt" in res["conflit"].details[0]
    assert res["numero"].verdict == co.NUMERO and "renuméroter en 1.38" in res["numero"].details[0]
    assert res["ok"].verdict == co.OK and res["ok"].details == []
    assert res["absente"].verdict == co.ERREUR


def test_main_code_de_sortie_et_tableau(tmp_path, monkeypatch, capsys):
    d = _depot(tmp_path, monkeypatch)
    liste = tmp_path / "prs.txt"
    liste.write_text("1 conflit\n3 ok\n")
    sortie = tmp_path / "out" / "conflits.md"
    assert co.main(["--liste", str(liste), "--main", "main", "--sans-reseau", "--sortie", str(sortie)]) == 1
    texte = sortie.read_text()
    assert "| #1 | `conflit` | CONFLIT |" in texte and "#3" not in texte and "1 PR à prévenir sur 2" in texte
    liste.write_text("3 ok\n")
    assert co.main(["--liste", str(liste), "--main", "main", "--sans-reseau", "--tous"]) == 0
    assert "| #3 | `ok` | OK | — |" in capsys.readouterr().out
    liste.write_text("")
    assert co.main(["--liste", str(liste), "--main", "main", "--sans-reseau"]) == 2
    assert d.exists()
