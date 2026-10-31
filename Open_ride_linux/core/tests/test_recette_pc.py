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
    expected = ["SAUTÉ" if n in rp.OPTIONAL_STEPS else "OK" for n in rp.STEPS]   # deps : seulement si nommée
    assert summary["ok"] and [s["status"] for s in summary["steps"]] == expected
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


def test_seances_step_runs_the_simulated_sessions(tmp_path):
    """Séances simulées de la recette T11 et de l'essai J7 (lots X33 et Z2) dans la recette du PC."""
    cmd, _ = rp.step_commands(False, tmp_path)["seances"]
    assert cmd[1].endswith("engine/tests/sim_bench.py") and cmd[-2:] == ["--out", str(tmp_path / "seances")]
    assert [cmd[i + 1] for i, a in enumerate(cmd) if a == "--scenario"] == ["serie_t", "erg_boutons", "course_bots"]
    assert rp.detail_of("seances", "[OK] x\nRÉSULTAT : ÉCHEC (1 vérification(s))\n") == "RÉSULTAT : ÉCHEC (1 vérification(s))"


def test_rapide_skips_menus_and_simulated_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "step_commands", fake_commands({}))
    out = tmp_path / "r"
    assert rp.main(["--out", str(out), "--rapide"]) == 0
    steps = {s["name"]: s["status"] for s in json.loads((out / "resume.json").read_text())["steps"]}
    assert steps["visual"] == steps["menus"] == steps["seances"] == "SAUTÉ" and steps["core"] == "OK"


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


def test_deps_step_is_optional_and_skipped_without_network(tmp_path, monkeypatch):
    """Audit des dépendances (lot X24) : seulement avec --seulement deps ; code 75 sans réseau = SAUTÉ."""
    cmd, _ = rp.step_commands(False, tmp_path)["deps"]
    assert cmd[1].endswith("scripts/audit_dependances.py") and cmd[-2:] == ["--out", str(tmp_path / "deps")]
    monkeypatch.setattr(rp, "step_commands", fake_commands(
        {"deps": ("audit_dependances : pas de réseau vers PyPI, audit sauté", rp.EXIT_SKIPPED)}))
    out = tmp_path / "r"
    assert rp.main(["--out", str(out), "--seulement", "deps"]) == 0
    steps = {s["name"]: s for s in json.loads((out / "resume.json").read_text())["steps"]}
    assert steps["deps"]["status"] == "SAUTÉ" and steps["deps"]["detail"].startswith("audit_dependances : pas de réseau")
    monkeypatch.setattr(rp, "step_commands", fake_commands({"deps": ("Vulnérabilités connues : 1", 1)}))
    assert rp.main(["--out", str(tmp_path / "r2"), "--seulement", "deps"]) == 1
