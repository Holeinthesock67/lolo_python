"""Recette du PC en une commande (lot X4) : enchaînement, résumé, comparaison au passage précédent."""

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "recette_pc.py"
spec = importlib.util.spec_from_file_location("recette_pc", SCRIPT)
rp = importlib.util.module_from_spec(spec)
sys.modules["recette_pc"] = rp
spec.loader.exec_module(rp)


def fake_commands(outcomes):
    """Chaque étape devient un petit programme Python qui écrit une sortie et rend un code."""
    def build(rapide, out):
        cmds = {}
        for name in rp.STEPS:
            text, rc = outcomes.get(name, ("RÉSULTAT : tous les tests de l'engine passent", 0))
            code = f"import sys; print({text!r}); sys.exit({rc})"
            cmds[name] = ([sys.executable, "-c", code], Path.cwd())
        return cmds
    return build


def test_all_steps_pass_and_summary_written(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "step_commands", fake_commands({"core": ("== 600 passed, 2 skipped in 12.3s ==", 0)}))
    out = tmp_path / "r1"
    assert rp.main(["--out", str(out)]) == 0
    summary = json.loads((out / "resume.json").read_text(encoding="utf-8"))
    assert summary["ok"] and [s["status"] for s in summary["steps"]] == ["OK"] * len(rp.STEPS)
    core = summary["steps"][0]
    assert core["detail"] == "600 passed, 2 skipped" and (out / "core.log").is_file()
    assert "Premier passage" in (out / "resume.txt").read_text(encoding="utf-8")


def test_failure_and_comparison_with_previous_run(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "step_commands", fake_commands({}))
    assert rp.main(["--out", str(tmp_path / "2026-10-26_100000")]) == 0
    monkeypatch.setattr(rp, "step_commands", fake_commands({"engine": ("RÉSULTAT : ÉCHEC", 1)}))
    out = tmp_path / "2026-10-26_110000"
    assert rp.main(["--out", str(out)]) == 1
    text = (out / "resume.txt").read_text(encoding="utf-8")
    assert "engine : OK → ÉCHEC" in text and "RÉSULTAT : ÉCHEC" in text


def test_step_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "step_commands", fake_commands({}))
    out = tmp_path / "r"
    assert rp.main(["--out", str(out), "--seulement", "core,engine", "--sans", "engine"]) == 0
    steps = {s["name"]: s["status"] for s in json.loads((out / "resume.json").read_text())["steps"]}
    assert steps["core"] == "OK" and steps["engine"] == "SAUTÉ" and steps["visual"] == steps["menus"] == "SAUTÉ"


def test_rapide_skips_visual_and_slow_tests(tmp_path):
    cmds = rp.step_commands(True, tmp_path)
    assert cmds["core"][0][-2:] == ["-m", "not slow"]
    assert rp.parse_steps("core, visual") == ["core", "visual"]


def test_unknown_step_is_refused(capsys):
    import pytest
    with pytest.raises(SystemExit) as err:
        rp.main(["--seulement", "inconnue"])
    assert err.value.code == 2
    assert "étape inconnue" in capsys.readouterr().err


def test_menus_step_runs_the_menu_bench(tmp_path):
    """Banc des menus (clavier, souris, Click simulé) dans la recette, rapport dans le dossier du passage."""
    cmd, _ = rp.step_commands(False, tmp_path)["menus"]
    assert cmd[1].endswith("engine/tests/menu_bench.py") and cmd[-2:] == ["--out", str(tmp_path / "menus")]
    assert rp.detail_of("menus", "reglages clavier OK\nOK\n") == "OK"
    assert rp.detail_of("menus", "2 passage(s) en échec sur 39\n") == "2 passage(s) en échec sur 39"
