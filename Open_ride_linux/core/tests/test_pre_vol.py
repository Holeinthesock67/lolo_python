"""Pré-vol avant une séance vélo (lot X36) : chaque étape avec des commandes simulées (OK, échec, sautée)."""

import json
from pathlib import Path

import pre_vol as pv   # scripts/ est dans le chemin (conftest.py)


class FakeRunner:
    """Répond aux commandes d'après le début de leur argv ; garde les appels."""

    def __init__(self, answers: dict[str, tuple[int, str]]) -> None:
        self.answers = answers
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(self, cmd, cwd, extra_env):
        self.calls.append((cmd, extra_env))
        key = " ".join(Path(c).name if c.startswith("/") else c for c in cmd)
        for prefix, answer in self.answers.items():
            if prefix in key:
                return answer
        return 0, ""


GIT_OK = {"rev-parse": (0, "main\n"), "status --porcelain": (0, ""), "fetch": (0, ""), "rev-list": (0, "0\n")}
SEANCE = {"titre": "essai", "pytest_marque": "recette_sans_velo", "engine_unit": ["test_key_map"],
          "sim_scenarios": [], "parcours": ["demo"], "appareils": ["trainer", "click"],
          "poser": [{"chemin": "~/OpenRide/powerups.toml", "contenu": "[obtain]\n"}], "retirer": []}


def test_known_sessions_are_valid():
    seances = pv.load_seances()
    assert {"t11_j7", "p27", "erg", "recette_1_0"} <= set(seances)
    assert all(s["pytest_marque"] == "recette_sans_velo" for s in seances.values())


def test_open_bike_blocks_have_a_pre_flight_and_known_tests():
    """Lot X48 : chaque bloc vélo encore ouvert a sa séance du pré-vol ; ses tests Godot et ses
    scénarios simulés existent."""
    from openride_core.sim_scenarios import SCENARIOS
    seances = pv.load_seances()
    assert {"garmin_braquets", "erg_libre_50w", "abri_as1", "v10"} <= set(seances)
    unit_dir = Path(__file__).resolve().parents[2] / "engine" / "tests" / "unit"
    for name, s in seances.items():
        for unit in s["engine_unit"]:
            assert (unit_dir / f"{unit}.gd").is_file(), f"{name} : {unit}.gd introuvable"
        assert set(s["sim_scenarios"]) <= set(SCENARIOS), name


def test_unknown_key_in_sessions_is_refused(tmp_path: Path):
    f = tmp_path / "s.toml"
    f.write_text('[x]\ntitre = "a"\nvelo = 1\n', encoding="utf-8")
    try:
        pv.load_seances(f)
    except ValueError as e:
        assert "velo" in str(e)
    else:
        raise AssertionError("clé inconnue acceptée")


def test_git_up_to_date_and_clean():
    r = pv.step_git(FakeRunner(GIT_OK), fetch=True)
    assert (r.status, r.blockers) == ("OK", [])
    assert r.detail == "branche main, à jour, rien de non commité"


def test_git_behind_and_dirty_blocks():
    run = FakeRunner({**GIT_OK, "status --porcelain": (0, " M Open_ride_linux/x.py\n"), "rev-list": (0, "3\n")})
    r = pv.step_git(run, fetch=True)
    assert r.status == "ÉCHEC"
    assert "3 commit(s) de retard sur origin/main (git pull --ff-only)" in r.blockers
    assert r.blockers[0].startswith("1 fichier(s) modifié(s) non commité(s)")


def test_git_without_network_does_not_fetch():
    run = FakeRunner(GIT_OK)
    r = pv.step_git(run, fetch=False)
    assert r.status == "OK" and "non vérifié" in r.detail
    assert not any("fetch" in c for c, _ in run.calls)


def test_tests_ok_fail_and_missing_marker(tmp_path: Path):
    ok = pv.step_tests(FakeRunner({"pytest": (0, "....\n4 passed, 1500 deselected in 3.2s\n")}), SEANCE, tmp_path)
    assert ok.status == "OK" and ok.detail.startswith("4 passed")
    ko = pv.step_tests(FakeRunner({"pytest": (1, "1 failed, 3 passed in 3.0s\n")}), SEANCE, tmp_path)
    assert ko.status == "ÉCHEC" and "1 failed" in ko.blockers[0]
    none = pv.step_tests(FakeRunner({"pytest": (5, "no tests ran\n")}), SEANCE, tmp_path)
    assert none.status == "ÉCHEC" and "aucun test ne porte la marque recette_sans_velo" in none.blockers[0]
    assert (tmp_path / "tests.log").is_file()
    assert pv.step_tests(FakeRunner({}), {**SEANCE, "pytest_marque": ""}, tmp_path).status == "SAUTÉ"


def test_engine_units_run_one_by_one(tmp_path: Path):
    run = FakeRunner({"run_engine_tests": (0, "RÉSULTAT : tous les tests de l'engine passent\n")})
    r = pv.step_engine(run, {**SEANCE, "engine_unit": ["test_key_map", "test_living_decor"]}, tmp_path, True)
    assert r.status == "OK"
    assert [env["UNIT"] for _, env in run.calls] == ["test_key_map", "test_living_decor"]
    ko = pv.step_engine(FakeRunner({"run_engine_tests": (1, "")}), SEANCE, tmp_path, True)
    assert ko.blockers == ["test Godot test_key_map en échec (engine.log)"]
    assert pv.step_engine(run, SEANCE, tmp_path, False).detail == "--sans-engine"


def test_simulated_session_skipped_without_scenarios_and_run_with(tmp_path: Path):
    assert "lot X33" in pv.step_simulee(FakeRunner({}), SEANCE, tmp_path, True).detail
    run = FakeRunner({"sim_bench": (0, "")})
    r = pv.step_simulee(run, {**SEANCE, "sim_scenarios": ["nominal", "t11"]}, tmp_path, True)
    assert r.status == "OK" and run.calls[0][0][-4:] == ["--scenario", "nominal", "--scenario", "t11"]
    assert pv.step_simulee(FakeRunner({"sim_bench": (1, "")}), {**SEANCE, "sim_scenarios": ["x"]},
                           tmp_path, True).status == "ÉCHEC"


def test_files_backup_config_check_routes_and_place_files(tmp_path: Path):
    home = tmp_path / "home"
    routes = home / "routes"
    (routes / "demo.world").mkdir(parents=True)
    config = home / "OpenRide" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text("[render]\n", encoding="utf-8")
    old = home / "OpenRide" / "vieux.toml"
    old.write_text("x", encoding="utf-8")
    seance = {**SEANCE, "retirer": ["~/OpenRide/vieux.toml"]}
    r = pv.step_fichiers("t11_j7", seance, home, routes, config, "2026-10-28_100000")
    assert r.status == "OK", r.blockers
    assert (home / "OpenRide" / "config.toml.t11_j7").read_text(encoding="utf-8") == "[render]\n"
    assert (home / "OpenRide" / "powerups.toml").read_text(encoding="utf-8") == "[obtain]\n"
    assert not old.exists() and (home / "OpenRide" / "vieux.toml.pre_vol-2026-10-28_100000").is_file()
    missing = pv.step_fichiers("p27", {**SEANCE, "parcours": ["grand-ballon"], "poser": []}, home, routes, config, "s")
    assert missing.status == "ÉCHEC" and missing.blockers[0].startswith("parcours grand-ballon non compilé")


def _devices(*roles: str) -> str:
    return "Recherche…\n" + json.dumps({"source": "ble", "devices": [{"role": r} for r in roles], "connected": []})


def test_bluetooth_sees_trainer_and_click_or_names_the_missing_one():
    assert pv.step_bluetooth(FakeRunner({"devices": (0, _devices("trainer", "click"))}), SEANCE, True).status == "OK"
    r = pv.step_bluetooth(FakeRunner({"devices": (0, _devices("trainer"))}), SEANCE, True)
    assert r.status == "ÉCHEC" and r.blockers == ["click invisible en Bluetooth (réveiller l'appareil, pédaler un tour)"]
    off = pv.step_bluetooth(FakeRunner({"devices": (1, "org.bluez.Error.NotReady")}), SEANCE, True)
    assert "Bluetooth allumé" in off.blockers[0]
    assert pv.step_bluetooth(FakeRunner({}), SEANCE, False).status == "SAUTÉ"


def test_whole_pre_flight_ready_then_not_ready(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    (home / ".local" / "share" / "openride" / "routes" / "demo.world").mkdir(parents=True)
    answers = {**GIT_OK, "pytest": (0, "4 passed in 1s\n"), "run_engine_tests": (0, ""),
               "devices": (0, _devices("trainer", "click"))}
    out = tmp_path / "out"
    assert pv.main(["--seance", "t11_j7", "--out", str(out), "--muet"], run=FakeRunner(answers), home=home) == 0
    assert "PRÊT À ROULER" in (out / "resume.txt").read_text(encoding="utf-8")
    assert json.loads((out / "resume.json").read_text(encoding="utf-8"))["ok"] is True
    answers["devices"] = (0, _devices("trainer"))
    out2 = tmp_path / "out2"
    assert pv.main(["--seance", "t11_j7", "--out", str(out2), "--muet"], run=FakeRunner(answers), home=home) == 1
    text = (out2 / "resume.txt").read_text(encoding="utf-8")
    assert "PAS PRÊT" in text and "click invisible" in text


def test_cloud_command_without_bluetooth_nor_engine(tmp_path: Path):
    home = tmp_path / "home"
    (home / ".local" / "share" / "openride" / "routes" / "demo.world").mkdir(parents=True)
    run = FakeRunner({**GIT_OK, "pytest": (0, "4 passed in 1s\n")})
    code = pv.main(["--seance", "t11_j7", "--sans-bluetooth", "--sans-engine", "--sans-reseau", "--out",
                    str(tmp_path / "o"), "--muet"], run=run, home=home)
    assert code == 0
    assert not any("run_engine_tests" in " ".join(c) or "devices" in c for c, _ in run.calls)


def test_invalid_calls():
    assert pv.main(["--seance", "inconnue"]) == 2
    assert pv.main([]) == 2
    assert pv.main(["--liste"]) == 0
