"""Instabilité et durée des tests (lot X3) : analyse de rapports JUnit fabriqués, JUnit de l'engine."""

import importlib.util
import os
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("stabilite_tests", PROJECT / "scripts" / "stabilite_tests.py")
st = importlib.util.module_from_spec(spec)
sys.modules["stabilite_tests"] = st
spec.loader.exec_module(st)


def junit(path, cases, time_total=None):
    """`cases` : {nom: (statut, durée)} ; statut pass, fail, error ou skip."""
    body = []
    for name, (status, t) in cases.items():
        inner = {"fail": '<failure message="x"/>', "error": '<error message="x"/>', "skip": '<skipped/>'}.get(status, "")
        body.append(f'<testcase classname="tests.test_a" name="{name}" time="{t}">{inner}</testcase>')
    total = time_total if time_total is not None else sum(t for _, t in cases.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'<testsuites><testsuite name="pytest" time="{total}">{"".join(body)}</testsuite></testsuites>')


def test_flaky_test_found_and_always_failing_test_kept_apart(tmp_path):
    for n, flaky in ((1, "pass"), (2, "fail"), (3, "pass")):
        junit(tmp_path / "junit" / f"core_{n}.xml",
              {"test_ok": ("pass", 0.1), "test_flaky": (flaky, 2.0 + n), "test_broken": ("error", 0.5),
               "test_skip": ("skip", 0.0)})
    res = st.analyse(tmp_path)
    assert [t["test"] for t in res["instables"]] == ["tests.test_a::test_flaky"]
    assert res["instables"][0]["echecs"] == 1 and res["instables"][0]["passages"] == 3
    assert [t["test"] for t in res["toujours_en_echec"]] == ["tests.test_a::test_broken"]
    assert all(t["test"] != "tests.test_a::test_skip" for t in res["tests"])


def test_slowest_ranked_by_median_and_suite_totals(tmp_path):
    for n in (1, 2):
        junit(tmp_path / "junit" / f"compiler_{n}.xml",
              {f"test_{i}": ("pass", float(i) + (10.0 if n == 2 and i == 3 else 0.0)) for i in range(25)}, 300.0 + n)
    res = st.analyse(tmp_path)
    slow = res["plus_lents"]
    assert len(slow) == st.SLOWEST and slow[0]["test"].endswith("test_24")
    t3 = next(t for t in res["tests"] if t["test"].endswith("test_3"))
    assert (t3["duree_mediane_s"], t3["duree_max_s"]) == (8.0, 13.0)
    assert res["suites"]["compiler"] == {"passages": 2, "duree_mediane_s": 301.5, "codes": []}


def test_test_missing_from_a_pass_is_counted_as_absent(tmp_path):
    junit(tmp_path / "junit" / "engine_1.xml", {"unit/test_a": ("pass", 1.0), "unit/test_new": ("pass", 2.0)})
    junit(tmp_path / "junit" / "engine_2.xml", {"unit/test_a": ("fail", 1.0)})
    res = st.analyse(tmp_path)
    new = next(t for t in res["tests"] if t["test"].endswith("test_new"))
    assert (new["passages"], new["echecs"], new["absences"]) == (1, 0, 1)
    assert [t["test"] for t in res["instables"]] == ["tests.test_a::unit/test_a"]


def test_files_written_and_analyse_command(tmp_path, capsys):
    junit(tmp_path / "junit" / "core_1.xml", {"test_ok": ("pass", 0.2)})
    (tmp_path / "passages.json").write_text('[{"suite": "core", "pass": 1, "code": 0, "seconds": 1140.0}]')
    assert st.main(["--analyse", str(tmp_path)]) == 0
    assert "durée médiane 19.0 min" in capsys.readouterr().out
    assert (tmp_path / "tests.csv").read_text().splitlines()[0] == \
        "suite;test;passages;echecs;absences;duree_mediane_s;duree_max_s"
    assert (tmp_path / "resume.json").is_file() and (tmp_path / "resume.txt").is_file()
    assert st.main(["--analyse", str(tmp_path / "vide")]) == 2


def test_engine_script_writes_a_valid_junit(tmp_path):
    """run_engine_tests.sh avec un faux Godot qui réussit un test unitaire : JUnit lisible par xml.etree."""
    fake = tmp_path / "godot"
    fake.write_text('#!/bin/sh\nfor a in "$@"; do case "$a" in res://tests/unit/*) n="${a##*/}";; esac; done\n'
                    'echo "${n%.gd} : 3 vérifications, 0 échecs"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    out = tmp_path / "engine.xml"
    env = {**os.environ, "GODOT": str(fake), "UNIT": "test_perf_probe", "ENGINE_JUNIT": str(out)}
    script = PROJECT / "engine" / "tests" / "run_engine_tests.sh"
    assert subprocess.run(["bash", str(script)], env=env, capture_output=True, check=False).returncode == 0
    suite = ET.parse(out).getroot().find("testsuite")
    (case,) = suite.findall("testcase")
    assert suite.get("tests") == "1" and suite.get("failures") == "0"
    assert case.get("name") == "unit/test_perf_probe" and float(case.get("time")) >= 0.0
    env.pop("ENGINE_JUNIT")
    env["UNIT"] = "test_absent"
    assert subprocess.run(["bash", str(script)], env=env, capture_output=True, check=False).returncode == 1
