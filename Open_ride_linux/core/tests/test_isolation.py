"""Isolation des suites de tests (`scripts/isolation_tests.py`) : HOME temporaire, fenêtres muettes,
garde-fou d'écriture, une suite à la fois."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from openride_core import config, fit_export

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

FAUTIFS = '''
import contextlib, subprocess, sys
from pathlib import Path

def test_ecrit_dans_le_home():
    (Path.home() / "OpenRide" / "Activities").mkdir(parents=True)
    (Path.home() / "OpenRide" / "Activities" / "seance.fit").write_bytes(b"fit")

def test_sous_processus_dans_le_home():
    subprocess.run([sys.executable, "-c", "import pathlib; (pathlib.Path.home() / 'run.log').write_text('x')"],
                   check=True)

def test_ecrit_hors_du_temporaire():
    with contextlib.suppress(OSError):      # écriture tentée, relevée même si elle échoue
        Path("/openride-hors-tmp/x.txt").write_text("x")

def test_propre(tmp_path):
    (tmp_path / "seance.fit").write_bytes(b"fit")
    assert subprocess.run(["zenity", "--error", "--text=test"]).returncode == 0   # programme muet
'''


def test_home_et_chemins_openride_sont_temporaires():
    home = Path(os.environ["HOME"])
    assert home.name.startswith("openride-tests-home-")
    assert Path.home() == home and str(home).startswith(tempfile.gettempdir())
    assert config.OPENRIDE_HOME == home / "OpenRide"
    assert fit_export.ACTIVITIES_DIR.is_relative_to(home)
    assert os.environ["XDG_CACHE_HOME"] == str(home / ".cache")


def test_fenetres_de_bureau_muettes():
    for nom in ("zenity", "kdialog", "notify-send"):
        assert Path(shutil.which(nom)).parent.name.startswith("openride-tests-bin-")


def test_garde_fait_echouer_les_tests_fautifs(tmp_path):
    (tmp_path / "conftest.py").write_text(
        f"import sys\nsys.path.insert(0, {str(SCRIPTS)!r})\n"
        "from isolation_tests import brancher_pytest\nglobals().update(brancher_pytest())\n")
    (tmp_path / "test_fautifs.py").write_text(FAUTIFS)
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf",
                        str(tmp_path / "test_fautifs.py"), "--rootdir", str(tmp_path)],
                       capture_output=True, text=True, cwd=tmp_path, timeout=60)
    out = r.stdout
    assert "3 failed, 1 passed" in out, out
    assert "OpenRide/Activities/seance.fit" in out
    assert "écrit dans le HOME (sous-processus ?) : ~/run.log" in out
    assert "/openride-hors-tmp/x.txt" in out
    assert "test_propre" not in out.split("short test summary")[-1]


def test_verrou_une_suite_a_la_fois(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS))
    from isolation_tests import VARIABLE_VERROU, verrou_suite

    monkeypatch.delenv(VARIABLE_VERROU)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    env = {**os.environ, "TMPDIR": str(tmp_path)}
    env.pop(VARIABLE_VERROU, None)
    code = (f"import sys, time; sys.path.insert(0, {str(SCRIPTS)!r})\n"
            "from isolation_tests import verrou_suite\n"
            "t = time.monotonic()\n"
            "with verrou_suite('seconde'):\n    print(f'attendu {time.monotonic() - t:.1f}')\n")
    with verrou_suite("premiere"):
        assert os.environ[VARIABLE_VERROU] == str(os.getpid())
        seconde = subprocess.Popen([sys.executable, "-c", code], env=env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(1.5)
        assert seconde.poll() is None             # la seconde suite attend
    out, err = seconde.communicate(timeout=10)
    assert "premiere, pid" in err and "attend sa fin" in err
    assert float(out.split()[-1]) >= 1.0
    assert VARIABLE_VERROU not in os.environ
