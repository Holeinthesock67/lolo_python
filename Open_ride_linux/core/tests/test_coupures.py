"""Coupures volontaires (lot X10) : attendu contre obtenu sur des journaux fabriqués, essai simulé."""

import json
import os
import shutil
import signal
import subprocess
import time

from openride_core.tools import coupures as cp

T0 = 1793190000.0


def log_line(t, msg):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) + f",{int(t % 1 * 1000):03d}"
    return f"{stamp} INFO    {msg}"


def trainer_cut(up_after):
    """Trainer coupé de T0+10 à T0+15 ; « up » et reprise `up_after` s après la fin (None : jamais)."""
    a = cp.actions(False, 15.0)["trainer"]
    done = [cp.entry(a, T0 + 10, T0 + 15)]
    journal = [{"kind": "device", "ts": T0 + 11.2, "device": "trainer", "state": "down"},
               {"kind": "event", "ts": T0 + 14.2, "event": "pause"}]
    if up_after is not None:
        journal += [{"kind": "device", "ts": T0 + 15 + up_after, "device": "trainer", "state": "up"},
                    {"kind": "event", "ts": T0 + 15 + up_after, "event": "resume"}]
    return done, journal


def verdicts(rep):
    return [(r["attendu"], r["ok"], r["delai_s"]) for r in rep["lignes"]]


def test_cut_followed_by_its_recovery():
    done, journal = trainer_cut(2.0)
    rep = cp.compare(done, cp.timeline(journal, []))
    assert rep["ok"] and [r["delai_s"] for r in rep["lignes"]] == [1.2, 4.2, 2.0, 2.0]


def test_late_recovery_fails():
    done, journal = trainer_cut(45.0)
    rep = cp.compare(done, cp.timeline(journal, []))
    assert not rep["ok"]
    assert ("trainer : « up » au journal", False, 45.0) in verdicts(rep)


def test_missing_recovery_fails_and_next_action_does_not_count():
    done, journal = trainer_cut(None)
    click = cp.actions(False, 15.0)["click_droit"]
    done.append(cp.entry(click, T0 + 40, T0 + 50))
    journal += [{"kind": "device", "ts": T0 + 52, "device": "trainer", "state": "up"},   # pendant le Click
                {"kind": "device", "ts": T0 + 40.5, "device": "click_plus", "state": "down"},
                {"kind": "device", "ts": T0 + 51, "device": "click_plus", "state": "up"}]
    rep = cp.compare(done, cp.timeline(journal, []))
    assert ("trainer : « up » au journal", False, None) in verdicts(rep)
    assert all(ok for label, ok, _ in verdicts(rep) if label.startswith("boîtier droit"))
    assert "absent après la fin de la coupure" in cp.report_text(rep)


def test_timeline_reads_launcher_log_and_hr_changes():
    journal = [{"kind": "record", "ts": T0 + i, "hr": None if 5 <= i < 9 else 120} for i in range(12)]
    log = [log_line(T0 + 3.25, "[openride] l'engine a planté (code 137) : relance 1/3"),
           "[engine] ligne sans heure", log_line(T0 + 6.5, "ipc_server Reçu 'hello' de l'engine version 0.9.0")]
    events = cp.timeline(journal, log)
    assert [k for _, k in events] == [
        "log INFO    [openride] l'engine a planté (code 137) : relance 1/3", "fc absente",
        "log INFO    ipc_server Reçu 'hello' de l'engine version 0.9.0", "fc presente"]
    assert events[0][0] == T0 + 3.25
    godot = cp.actions(False, 15.0)["godot"]
    rep = cp.compare([cp.entry(godot, T0 + 3.0, T0 + 3.0)], events)
    assert rep["ok"] and [r["delai_s"] for r in rep["lignes"]] == [0.2, 3.5]


def test_relayed_hr_gets_the_freeze_delay():
    assert cp.actions(True, 15.0)["ceinture"].expects[0].max_s == 17.0
    assert cp.actions(False, 15.0)["ceinture"].expects[0].max_s == 10.0


def test_analyse_folder(tmp_path, capsys):
    done, journal = trainer_cut(45.0)
    (tmp_path / "actions.jsonl").write_text("".join(json.dumps(d) + "\n" for d in done))
    (tmp_path / "journal.jsonl").write_text("".join(json.dumps(j) + "\n" for j in journal))
    assert cp.main(["--analyse", str(tmp_path)]) == 1
    assert "[ÉCHEC] trainer      trainer : « up » au journal : 45.0 s" in capsys.readouterr().out
    assert json.loads((tmp_path / "rapport.json").read_text())["ok"] is False
    assert cp.main(["--analyse", str(tmp_path / "vide")]) == 2


def test_engine_kill_only_under_root(tmp_path):
    fake = tmp_path / "Godot_v4.3-test"
    # bash et non sleep : le sleep d'uutils (Ubuntu 25.10) refuse d'être lancé sous un autre nom.
    fake.symlink_to(shutil.which("bash"))
    p = subprocess.Popen([str(fake), "-c", "read -r _"], stdin=subprocess.PIPE)   # attend sans enfant
    try:
        time.sleep(0.2)
        assert p.pid in cp.engine_pids(os.getpid())
        assert p.pid not in cp.engine_pids(1 << 30)   # racine inconnue : rien
        assert cp.kill_engine(os.getpid()) == [p.pid]
        assert p.wait(5) == -signal.SIGKILL
    finally:
        if p.poll() is None:
            p.kill()


def test_sim_without_engine(tmp_path):
    """Critère 2 : trainer et ceinture sur le Bluetooth simulé, core seul (environ 45 s)."""
    code = cp.main(["--sim", "--sans-engine", "--court", "--actions", "godot,trainer,ceinture",
                    "--config", str(tmp_path / "absent.toml"), "--out", str(tmp_path / "out")])
    rep = json.loads((tmp_path / "out" / "rapport.json").read_text(encoding="utf-8"))
    assert code == 0, cp.report_text(rep)
    assert {r["action"] for r in rep["lignes"]} == {"trainer", "ceinture"}   # godot sauté sans engine
    assert (tmp_path / "out" / "journal.jsonl").is_file() and (tmp_path / "out" / "lanceur.log").is_file()


def test_trial_in_guide():
    from openride_core.tools.guide import TRIALS
    assert "coupures" in TRIALS
