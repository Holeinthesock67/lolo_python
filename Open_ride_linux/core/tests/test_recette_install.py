"""Recette de l'installation sur un système propre (lot X29) : résumé, refus, essai complet en HOME temporaire."""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "recette_install.py"
spec = importlib.util.spec_from_file_location("recette_install", SCRIPT)
ri = importlib.util.module_from_spec(spec)
sys.modules["recette_install"] = ri
spec.loader.exec_module(ri)


def fake_godot(tmp_path: Path) -> Path:
    godot = tmp_path / "godot" / "Godot_v4.3-stable_linux.x86_64"
    godot.parent.mkdir()
    godot.write_text("#!/bin/sh\necho 4.3.stable.official.essai\n")
    godot.chmod(0o755)
    return godot


def test_summarize_reads_checks_and_result():
    log = "== 1\n[OK] clone\nbruit\n[ÉCHEC] icône : absente\n\n2 vérifications, 1 échec(s)\nRÉSULTAT : ÉCHEC\n"
    lines, result = ri.summarize(log)
    assert lines == ["[OK] clone", "[ÉCHEC] icône : absente"] and result == "RÉSULTAT : ÉCHEC"
    assert ri.summarize("rien")[1] == "RÉSULTAT : ?"


def test_refuses_without_godot_or_docker(tmp_path, monkeypatch):
    assert ri.main(["--mode", "home", "--godot", str(tmp_path / "absent"), "--out", str(tmp_path / "o")]) == 2
    monkeypatch.setattr(ri.shutil, "which", lambda *_a, **_k: None)
    assert ri.main(["--mode", "docker", "--godot", str(fake_godot(tmp_path)), "--out", str(tmp_path / "o")]) == 2


@pytest.mark.slow   # clone, installation sans pip, premier démarrage et mise à jour : une trentaine de secondes
@pytest.mark.skipif(shutil.which("git") is None, reason="git requis")
def test_fresh_install_in_temporary_home(tmp_path):
    out = tmp_path / "recette"
    rc = ri.main(["--mode", "home", "--sans-pip", "--godot", str(fake_godot(tmp_path)), "--out", str(out)])
    resume = (out / "resume_home.txt").read_text(encoding="utf-8")
    assert rc == 0, resume
    for label in ("install.sh sans terminal", "raccourci openride.desktop", "core lancé sur le trainer simulé",
                  "scripts/update.sh", "parcours, séances et config.toml inchangés"):
        assert f"[OK] {label}" in resume
    assert "installation neuve OK" in resume
