"""Pile gdb d'un Godot qui ne se ferme pas (lot X58) : Godot lancé sous gdb par le banc des menus (`--gdb`), code de
sortie gardé quand il sort seul, pile de tous les fils écrite sur SIGINT, résumé d'une ligne par fil."""

import importlib.util
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "engine" / "tests"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pg = _load("pile_gdb")

SAMPLE = """  Id   Target Id                                 Frame
* 1    Thread 0x7f01 (LWP 10) "Godot_v4.7.2-st" 0x7f in __futex_abstimed_wait_common () from /lib/x86_64-linux-gnu/libc.so.6

Thread 3 (Thread 0x7f03 (LWP 12) "vkcomp"):
#0  0x00007f in __futex_abstimed_wait_common () from /lib/x86_64-linux-gnu/libc.so.6
#1  0x00007f in pthread_cond_wait@@GLIBC_2.3.2 () from /lib/x86_64-linux-gnu/libc.so.6
#2  0x00007f in ?? () from /lib/x86_64-linux-gnu/libnvidia-glcore.so.580.95.05

Thread 2 (Thread 0x7f02 (LWP 11) "vkcomp"):
#0  0x00007f in __futex_abstimed_wait_common () from /lib/x86_64-linux-gnu/libc.so.6
#1  0x00007f in pthread_cond_wait@@GLIBC_2.3.2 () from /lib/x86_64-linux-gnu/libc.so.6
#2  0x00007f in ?? () from /lib/x86_64-linux-gnu/libnvidia-glcore.so.580.95.05

Thread 1 (Thread 0x7f01 (LWP 10) "Godot_v4.7.2-st"):
#0  0x00007f in __futex_abstimed_wait_common () from /lib/x86_64-linux-gnu/libc.so.6
#1  0x00007f in pthread_join () from /lib/x86_64-linux-gnu/libc.so.6
#2  0x00007f in ?? () from /lib/x86_64-linux-gnu/libnvidia-glcore.so.580.95.05
#3  0x00007f in __run_exit_handlers (status=0) at ./stdlib/exit.c:113
#4  0x00007f in exit () from /lib/x86_64-linux-gnu/libc.so.6
"""


def test_resume_principal_d_abord_et_fils_identiques_groupes():
    lines = pg.resume_pile(SAMPLE)
    assert lines[0].startswith("principal Godot_v4.7.2-st : __futex_abstimed_wait_common (libc.so.6) ← pthread_join")
    assert "??@libnvidia-glcore.so.580.95.05 ← __run_exit_handlers (exit.c) ← exit (libc.so.6)" in lines[0]
    assert lines[1].startswith("vkcomp ×2 : ")
    assert len(lines) == 2


def test_extraire_entre_les_reperes():
    lines = ["[engine] avant", pg.DEBUT, "Thread 1 (x):", pg.FIN, "après"]
    assert pg.extraire(lines) == "Thread 1 (x):\n"
    assert pg.extraire(["rien"]) == ""


def test_code_pile_n_est_pas_un_code_d_openride():
    assert pg.CODE_PILE not in (0, 1, 64, 65)


@pytest.mark.skipif(shutil.which("gdb") is None, reason="gdb absent")
def test_sous_gdb_code_garde_et_pile_sur_sigint(tmp_path):
    prog = tmp_path / "prog.py"
    prog.write_text("import sys, threading, time\n"
                    "if sys.argv[1] == 'sortie': sys.exit(7)\n"
                    "threading.Thread(target=lambda: threading.Event().wait(), daemon=True).start()\n"
                    "print('pret', flush=True)\n"
                    "time.sleep(600)\n", encoding="utf-8")
    prefix = pg.gdb_prefix(tmp_path / "pile.gdb")
    assert prefix is not None
    done = subprocess.run([*prefix, sys.executable, str(prog), "sortie"], capture_output=True, text=True, timeout=60, check=False)
    if "ptrace" in done.stdout + done.stderr and done.returncode != 7:
        pytest.skip("ptrace refusé dans ce conteneur")
    assert done.returncode == 7
    p = subprocess.Popen([*prefix, sys.executable, str(prog), "bloque"], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    deadline = time.monotonic() + 30
    child = None
    while time.monotonic() < deadline and child is None:
        kids = Path(f"/proc/{p.pid}/task/{p.pid}/children").read_text().split()
        child = int(kids[0]) if kids else None
        time.sleep(0.5)
    assert child is not None
    time.sleep(2.0)   # programme lancé, son fil en attente
    os.kill(child, signal.SIGINT)
    out, _ = p.communicate(timeout=60)
    assert p.returncode == pg.CODE_PILE
    text = pg.extraire(out.splitlines())
    summary = pg.resume_pile(text)
    assert summary and summary[0].startswith("principal ")
    assert any(re.search(r"futex|sem_wait|pthread_cond", line) for line in summary[1:])


def test_banc_des_menus_documente_les_options_et_main_gd_les_modes():
    bench = (TESTS / "menu_bench.py").read_text(encoding="utf-8")
    for opt in ("--repeter", "--fermeture-stricte", "--gdb", "--fermeture", "--engine-arg", "--qualite"):
        assert f'"{opt}"' in bench and opt in bench.split('"""', 2)[1], opt
    main = (ROOT / "engine" / "scripts" / "main.gd").read_text(encoding="utf-8")
    modes = re.search(r"const QUIT_MODES := \[(.*)\]", main).group(1)
    assert [m.strip().strip('"') for m in modes.split(",")] == ["", "differe", "liberer"]
    assert 'OS.get_environment("OPENRIDE_QUIT_MODE")' in main
