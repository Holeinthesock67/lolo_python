"""Parties de la CI (audit du 22 novembre, P1) : tests du core et du compilateur répartis en N parties
par `OPENRIDE_TESTS_PARTIE` (`scripts/isolation_tests.py`), banc des menus par `--partie` (menu_bench.py).
Les N parties doivent couvrir chaque test exactement une fois."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJET = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJET / "scripts"))

import isolation_tests  # noqa: E402
import durees_tests  # noqa: E402


def test_repartition_couvre_chaque_fichier_une_fois() -> None:
    fichiers = [f"core/tests/test_{i:03d}.py" for i in range(40)]
    durees = {f: float(i % 7 + 1) * (10 if i == 3 else 1) for i, f in enumerate(fichiers[:30])}
    for n in (1, 2, 3, 5):
        parts = isolation_tests.repartir_fichiers(fichiers, n, durees)
        assert set(parts) == set(fichiers) and set(parts.values()) <= set(range(n))
        assert parts == isolation_tests.repartir_fichiers(list(reversed(fichiers)), n, durees)   # même partout


def test_repartition_equilibree() -> None:
    durees = {f"f{i}": float(d) for i, d in enumerate([60, 50, 40, 30, 20, 10, 10, 10, 5, 5])}
    parts = isolation_tests.repartir_fichiers(list(durees), 3, durees)
    charges = [sum(d for f, d in durees.items() if parts[f] == k) for k in range(3)]
    assert max(charges) - min(charges) <= 10


def test_partie_mal_ecrite_arrete_la_suite() -> None:
    assert isolation_tests.lire_partie(None) is None and isolation_tests.lire_partie("2/3") == (2, 3)
    for faux in ("0/3", "4/3", "deux", "1-3"):
        with pytest.raises(SystemExit):
            isolation_tests.lire_partie(faux)


def test_fichier_des_durees_lisible() -> None:
    durees = isolation_tests.lire_durees()
    assert durees, "scripts/durees_tests.json absent ou vide"
    assert all(k.startswith(("core/tests/", "compiler/tests/")) and k.endswith(".py") for k in durees)


def test_parties_de_la_suite_couvrent_tout(tmp_path) -> None:
    """Vraie collecte pytest d'une petite suite en 3 parties : réunion = suite entière, sans doublon."""
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "conftest.py").write_text(
        f"import sys\nsys.path.insert(0, {str(PROJET / 'scripts')!r})\n"
        "from isolation_tests import brancher_pytest\nglobals().update(brancher_pytest())\n", encoding="utf-8")
    for i in range(7):
        (suite / f"test_m{i}.py").write_text("".join(f"def test_{j}():\n    pass\n" for j in range(i + 1)),
                                             encoding="utf-8")
    vus: list[str] = []
    for k in (1, 2, 3):
        env = {**os.environ, "OPENRIDE_TESTS_PARTIE": f"{k}/3", isolation_tests.VARIABLE_VERROU: "1"}
        res = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only",
                              str(suite)], capture_output=True, text=True, env=env, cwd=suite)
        assert res.returncode == 0, res.stdout + res.stderr
        vus += [ligne for ligne in res.stdout.splitlines() if "::test_" in ligne]
    assert len(vus) == len(set(vus)) == sum(range(1, 8))


def test_durees_lues_dans_un_rapport_junit(tmp_path) -> None:
    rapport = tmp_path / "core.xml"
    rapport.write_text('<testsuites><testsuite><testcase classname="tests.test_a" name="t1" time="1.5"/>'
                       '<testcase classname="tests.test_a.TestB" name="t2" time="2"/>'
                       '<testcase classname="test_c" name="t3" time="0.25"/></testsuite></testsuites>',
                       encoding="utf-8")
    sortie = tmp_path / "durees.json"
    assert durees_tests.main([str(rapport), "--sortie", str(sortie)]) == 0
    assert json.loads(sortie.read_text(encoding="utf-8"))["fichiers"] == {"core/tests/test_a.py": 3.5,
                                                                          "core/tests/test_c.py": 0.2}


def _menu_bench():
    spec = importlib.util.spec_from_file_location("menu_bench_parties", PROJET / "engine/tests/menu_bench.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_partie_du_banc_des_menus() -> None:
    mb = _menu_bench()
    assert mb.parse_partie(None) is None and mb.parse_partie("3/3") == (3, 3)
    for faux in ("0/2", "3/2", "x"):
        with pytest.raises(ValueError):
            mb.parse_partie(faux)
