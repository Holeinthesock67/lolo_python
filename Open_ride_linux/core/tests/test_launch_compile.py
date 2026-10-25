"""Tests de la compilation au lancement d'OpenRide (Lot N11, SRS §7 et §11)."""

import json
import os
import sys
import time
from pathlib import Path

import pytest

from openride_core import launch_compile
from openride_core.catalog import list_routes
from openride_core.launch_compile import (
    find_compiler_cmd,
    get_pending_routes,
    run_startup_compilation,
)
from openride_core.launcher import Supervisor, extract_launcher_args


SAMPLE_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <trk>
    <name>{name}</name>
    <trkseg>
      <trkpt lat="48.8566" lon="2.3522"><ele>35.0</ele></trkpt>
      <trkpt lat="48.8570" lon="2.3530"><ele>36.0</ele></trkpt>
    </trkseg>
  </trk>
</gpx>
"""


def _create_mock_world(routes_dir: Path, name: str, gpx_name: str, gpx_sha: str) -> Path:
    world_dir = routes_dir / f"{name}.world"
    world_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "1.0",
        "name": name,
        "route": {"file": "route.json"},
        "source": {"gpx": gpx_name, "gpx_sha256": gpx_sha},
        "layers": {},
    }
    (world_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    route = {
        "length_m": 1000.0,
        "n": 2,
        "type": "open",
        "points": [
            {"s_m": 0.0, "x_m": 0.0, "y_m": 0.0, "z_m": 35.0, "grade_pct": 0.0},
            {"s_m": 1000.0, "x_m": 1000.0, "y_m": 0.0, "z_m": 36.0, "grade_pct": 0.1},
        ],
    }
    (world_dir / "route.json").write_text(json.dumps(route), encoding="utf-8")
    return world_dir


def test_extract_launcher_args():
    args = ["--no-compile", "--trainer", "ftms", "--compile-timeout", "15.5", "--input", "keyboard"]
    core_args, no_compile, compile_only, compile_timeout = extract_launcher_args(args)
    assert no_compile is True
    assert compile_only is False
    assert compile_timeout == 15.5
    assert core_args == ["--trainer", "ftms", "--input", "keyboard"]

    # --compile-timeout=10
    core_args2, no_c, comp_only, c_timeout = extract_launcher_args(["--compile-timeout=42", "--compile-only"])
    assert no_c is False
    assert comp_only is True
    assert c_timeout == 42.0
    assert core_args2 == []

    # invalid timeout
    with pytest.raises(ValueError):
        extract_launcher_args(["--compile-timeout"])


def test_no_pending_routes_does_nothing(tmp_path: Path):
    routes_dir = tmp_path / "routes"
    gpx_dir = tmp_path / "gpx"
    routes_dir.mkdir()
    gpx_dir.mkdir()

    notifications: list[str] = []
    messages: list[str] = []

    res = run_startup_compilation(
        routes_dir=routes_dir,
        gpx_dir=gpx_dir,
        compiler_cmd=[sys.executable, "-c", "import sys; sys.exit(0)"],
        say=messages.append,
        notify=notifications.append,
    )
    assert res == 0
    assert notifications == []
    assert messages == []


def test_compile_two_new_and_one_existing(tmp_path: Path):
    routes_dir = tmp_path / "routes"
    gpx_dir = tmp_path / "gpx"
    routes_dir.mkdir()
    gpx_dir.mkdir()

    # Trace 1 : déjà compilée
    gpx1 = gpx_dir / "trace1.gpx"
    gpx1.write_text(SAMPLE_GPX.format(name="Trace 1"), encoding="utf-8")
    import hashlib
    sha1 = hashlib.sha256(gpx1.read_bytes()).hexdigest()
    _create_mock_world(routes_dir, "trace1", "trace1.gpx", sha1)

    # Traces 2 et 3 : nouvelles
    gpx2 = gpx_dir / "trace2.gpx"
    gpx2.write_text(SAMPLE_GPX.format(name="Trace 2"), encoding="utf-8")
    gpx3 = gpx_dir / "trace3.gpx"
    gpx3.write_text(SAMPLE_GPX.format(name="Trace 3"), encoding="utf-8")

    # Vérifie que get_pending_routes en trouve bien 2
    pending = get_pending_routes(routes_dir, gpx_dir)
    assert len(pending) == 2
    assert {p.id for p in pending} == {"trace2", "trace3"}

    # Faux compilateur qui simule build-all avec succès
    fake_compiler = tmp_path / "fake_compiler.py"
    fake_compiler.write_text(
        "import sys\n"
        "print('compilation ok')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )

    notifications: list[str] = []
    messages: list[str] = []

    res = run_startup_compilation(
        routes_dir=routes_dir,
        gpx_dir=gpx_dir,
        compiler_cmd=[sys.executable, str(fake_compiler)],
        say=messages.append,
        notify=notifications.append,
    )
    assert res == 0
    assert notifications == ["Compilation de 2 traces…", "2 parcours prêts"]
    assert any("compilation de 2 traces" in m for m in messages)


def test_compiler_timeout_stops_cleanly(tmp_path: Path):
    routes_dir = tmp_path / "routes"
    gpx_dir = tmp_path / "gpx"
    routes_dir.mkdir()
    gpx_dir.mkdir()

    gpx = gpx_dir / "hanging.gpx"
    gpx.write_text(SAMPLE_GPX.format(name="Hanging"), encoding="utf-8")

    # Compilateur qui boucle indéfiniment
    hanging_compiler = tmp_path / "hang.py"
    hanging_compiler.write_text(
        "import time\n"
        "while True:\n"
        "    time.sleep(0.1)\n",
        encoding="utf-8",
    )

    notifications: list[str] = []
    messages: list[str] = []
    warnings: list[str] = []

    t0 = time.monotonic()
    res = run_startup_compilation(
        routes_dir=routes_dir,
        gpx_dir=gpx_dir,
        timeout_s=1.0,
        compiler_cmd=[sys.executable, str(hanging_compiler)],
        say=messages.append,
        say_warning=warnings.append,
        notify=notifications.append,
    )
    duration = time.monotonic() - t0

    assert res == 1
    assert 0.9 <= duration < 5.0
    assert any("délai de compilation dépassé" in w for w in warnings)
    assert any("Compilation interrompue" in n for n in notifications)


def test_missing_compiler_warns_and_continues(tmp_path: Path):
    routes_dir = tmp_path / "routes"
    gpx_dir = tmp_path / "gpx"
    routes_dir.mkdir()
    gpx_dir.mkdir()

    gpx = gpx_dir / "route.gpx"
    gpx.write_text(SAMPLE_GPX.format(name="Route"), encoding="utf-8")

    notifications: list[str] = []
    messages: list[str] = []

    res = run_startup_compilation(
        routes_dir=routes_dir,
        gpx_dir=gpx_dir,
        compiler_cmd=[str(tmp_path / "non_existent_compiler_binary")],
        say=messages.append,
        notify=notifications.append,
    )
    assert res == 0
    assert any("impossible de lancer le compilateur" in m for m in messages)


def test_supervisor_compile_only_and_no_compile(tmp_path: Path):
    routes_dir = tmp_path / "routes"
    gpx_dir = tmp_path / "gpx"
    routes_dir.mkdir()
    gpx_dir.mkdir()

    gpx = gpx_dir / "route.gpx"
    gpx.write_text(SAMPLE_GPX.format(name="Route"), encoding="utf-8")

    fake_compiler = tmp_path / "fake_compiler.py"
    fake_compiler.write_text("import sys; sys.exit(0)\n", encoding="utf-8")

    notifications: list[str] = []
    said: list[str] = []

    # 1. Avec compile_only=True : compile puis quitte sans démarrer core ni engine
    sup = Supervisor(
        core_cmd=[sys.executable, "-c", "import sys; sys.exit(1)"],  # Si appelé, échouerait
        engine_cmd=[sys.executable, "-c", "import sys; sys.exit(1)"],
        release_cmd=[sys.executable, "-c", "import sys; sys.exit(0)"],
        log_path=tmp_path / "test.log",
        compile_enabled=True,
        compile_only=True,
        routes_dir=routes_dir,
        gpx_dir=gpx_dir,
        compiler_cmd=[sys.executable, str(fake_compiler)],
        notify=notifications.append,
        say=said.append,
    )
    ret = sup.run()
    assert ret == 0
    assert notifications == ["Compilation de 1 trace…", "1 parcours prêt"]
    assert sup.started_pids == []  # Aucun sous-processus core/engine démarré

    # 2. Avec compile_enabled=False (--no-compile) : saute la compilation
    notifications.clear()
    sup2 = Supervisor(
        core_cmd=[sys.executable, "-c", "import sys; sys.exit(0)"],
        engine_cmd=[sys.executable, "-c", "import sys; sys.exit(0)"],
        release_cmd=[sys.executable, "-c", "import sys; sys.exit(0)"],
        log_path=tmp_path / "test2.log",
        compile_enabled=False,
        routes_dir=routes_dir,
        gpx_dir=gpx_dir,
        compiler_cmd=[sys.executable, str(fake_compiler)],
        notify=notifications.append,
        say=said.append,
    )
    # sup2 commence directement par _start_core
    assert sup2.compile_enabled is False
    assert len(notifications) == 0


def test_supervisor_compiles_then_starts_core(tmp_path: Path):
    """Critère 2 : 2 traces nouvelles et 1 déjà compilée : appel de build-all, notifications, puis core."""
    routes_dir = tmp_path / "routes"
    gpx_dir = tmp_path / "gpx"
    routes_dir.mkdir()
    gpx_dir.mkdir()

    # 1 déjà compilée
    gpx1 = gpx_dir / "trace1.gpx"
    gpx1.write_text(SAMPLE_GPX.format(name="Trace 1"), encoding="utf-8")
    import hashlib
    sha1 = hashlib.sha256(gpx1.read_bytes()).hexdigest()
    _create_mock_world(routes_dir, "trace1", "trace1.gpx", sha1)

    # 2 nouvelles
    (gpx_dir / "trace2.gpx").write_text(SAMPLE_GPX.format(name="Trace 2"), encoding="utf-8")
    (gpx_dir / "trace3.gpx").write_text(SAMPLE_GPX.format(name="Trace 3"), encoding="utf-8")

    # Script d'appel pour vérifier qu'il est appelé une seule fois
    compiler_calls = tmp_path / "compiler_calls.txt"
    fake_compiler = tmp_path / "compiler.py"
    fake_compiler.write_text(
        f"from pathlib import Path\n"
        f"Path({str(compiler_calls)!r}).write_text('called\\n')\n"
        f"import sys; sys.exit(0)\n",
        encoding="utf-8",
    )

    core_started = tmp_path / "core_started.txt"
    fake_core = tmp_path / "core.py"
    fake_core.write_text(
        f"from pathlib import Path\n"
        f"import sys, time\n"
        f"Path({str(core_started)!r}).write_text('core_ok\\n')\n"
        f"time.sleep(2.0)\n"
        f"sys.exit(0)\n",
        encoding="utf-8",
    )

    fake_engine = tmp_path / "engine.py"
    fake_engine.write_text(
        "import sys, time\n"
        "time.sleep(0.2)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )

    notifications: list[str] = []
    said: list[str] = []

    sup = Supervisor(
        core_cmd=[sys.executable, str(fake_core)],
        engine_cmd=[sys.executable, str(fake_engine)],
        release_cmd=[sys.executable, "-c", "import sys; sys.exit(0)"],
        log_path=tmp_path / "run.log",
        startup_grace_s=0.1,
        stop_timeout_s=1.0,
        compile_enabled=True,
        compile_timeout_s=10.0,
        routes_dir=routes_dir,
        gpx_dir=gpx_dir,
        compiler_cmd=[sys.executable, str(fake_compiler)],
        notify=notifications.append,
        say=said.append,
    )
    code = sup.run()
    assert code == 0
    assert compiler_calls.read_text().strip() == "called"
    assert core_started.read_text().strip() == "core_ok"
    assert notifications == ["Compilation de 2 traces…", "2 parcours prêts"]


def test_supervisor_compilation_timeout_alert_and_core_started(tmp_path: Path):
    """Critère 4 : compilateur qui ne rend pas la main : arrêté au délai, core démarré, alerte dans le journal."""
    routes_dir = tmp_path / "routes"
    gpx_dir = tmp_path / "gpx"
    routes_dir.mkdir()
    gpx_dir.mkdir()

    (gpx_dir / "trace_hang.gpx").write_text(SAMPLE_GPX.format(name="Hang"), encoding="utf-8")

    fake_hang_compiler = tmp_path / "hang_compiler.py"
    fake_hang_compiler.write_text(
        "import time, sys\n"
        "while True:\n"
        "    time.sleep(0.1)\n",
        encoding="utf-8",
    )

    core_marker = tmp_path / "core_marker.txt"
    fake_core = tmp_path / "core.py"
    fake_core.write_text(
        f"from pathlib import Path\n"
        f"import sys, time\n"
        f"Path({str(core_marker)!r}).write_text('core_running\\n')\n"
        f"time.sleep(2.0)\n"
        f"sys.exit(0)\n",
        encoding="utf-8",
    )

    fake_engine = tmp_path / "engine.py"
    fake_engine.write_text(
        "import sys, time\n"
        "time.sleep(0.2)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )

    notifications: list[str] = []
    said: list[str] = []
    log_file = tmp_path / "run_timeout.log"

    sup = Supervisor(
        core_cmd=[sys.executable, str(fake_core)],
        engine_cmd=[sys.executable, str(fake_engine)],
        release_cmd=[sys.executable, "-c", "import sys; sys.exit(0)"],
        log_path=log_file,
        startup_grace_s=0.1,
        stop_timeout_s=1.0,
        compile_enabled=True,
        compile_timeout_s=1.0,
        routes_dir=routes_dir,
        gpx_dir=gpx_dir,
        compiler_cmd=[sys.executable, str(fake_hang_compiler)],
        notify=notifications.append,
        say=said.append,
    )
    code = sup.run()
    assert code == 0
    assert core_marker.read_text().strip() == "core_running"

    # Vérification de la ligne d'alerte dans le journal
    log_content = log_file.read_text(encoding="utf-8", errors="replace")
    assert "WARNING" in log_content
    assert "délai de compilation dépassé" in log_content
