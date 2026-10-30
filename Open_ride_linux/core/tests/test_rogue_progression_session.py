"""Fin de la série R : progression du Cyber-Rogue branchée dans la séance du core.

Châssis débloqués et vies (lot R9), W' estimé des séances passées (lot R16) et dernière run reprise au
menu de départ (lot R13) arrivent dans `hello_ack.config.rogue` ; les vies utilisées pendant une run sont
retirées du profil.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.profile import load_profile
from openride_core.rogue.progress import run_event
from openride_core.session import CoreSession
from openride_core.tools import estimate_cp

from test_progression import write_journal

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
ROGUE_SCHEMA = json.loads((IPC_DIR / "hello_ack.schema.json").read_text("utf-8"))["properties"]["config"]["properties"]["rogue"]


def rogue_line(objective: str, duration: int, chassis: str = "standard", boss: str = "won") -> dict:
    summary = {"result": "victory", "objective": objective, "duration_min": duration, "seed": 1, "rooms_won": 3,
               "rooms_fled": 0, "rooms_skipped": 0, "rooms_total": 4, "defeats": 0, "boss": boss, "gold": 120,
               "cards": [], "perfect_shifts": 4, "unlocks": []}
    return {**run_event(summary, 44.0, 0, chassis), "ts": 0.0}


@pytest.fixture
def make(tmp_path, monkeypatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "Activities")

    def build(profile: dict | None = None) -> CoreSession:
        profile_path = tmp_path / "profile.json"
        if profile is not None:
            profile_path.write_text(json.dumps({"version": 1, **profile}), encoding="utf-8")
        s = CoreSession(Config(), driver=MockDriver(), inputs=[NullProvider()],
                        journal_dir=tmp_path / "Activities" / ".journal", routes_root=tmp_path / "routes",
                        workouts_dir=tmp_path / "Workouts", records_path=tmp_path / "records.json",
                        powerups_path=tmp_path / "powerups.toml", config_path=tmp_path / "config.toml",
                        profile_path=profile_path)
        s.server.send_raw = lambda m, max_size=None: None
        s.mmp_cache_path = tmp_path / "mmp.json"
        return s
    return build


def test_first_launch_has_no_last_run_and_the_standard_chassis(make):
    s = make()
    block = s.server.hello_config["rogue"]
    jsonschema.validate(block, ROGUE_SCHEMA)
    assert block["last"] is None and block["chassis"] == {"unlocked": ["standard"], "selected": "standard"}
    assert block["lives"] == 0 and block["w_prime_estimate_j"] is None


def test_last_run_unlocked_chassis_and_lives_come_back_at_the_next_launch(make, tmp_path):
    journal = tmp_path / "Activities" / ".journal"
    journal.mkdir(parents=True)
    write_journal(journal / "a.jsonl", start_ts=1_760_000_000.0, extra_lines=[rogue_line("endurance", 30)])
    write_journal(journal / "b.jsonl", start_ts=1_760_100_000.0, extra_lines=[rogue_line("vo2max", 60, "blinde")])
    s = make({"lives": {"bought": 2, "used": 0, "spent": 60}})
    block = s.server.hello_config["rogue"]
    jsonschema.validate(block, ROGUE_SCHEMA)
    assert block["last"] == {"objective": "vo2max", "duration_min": 60}
    assert "blinde" in block["chassis"]["unlocked"] and block["chassis"]["selected"] == "blinde"
    assert block["lives"] == 2
    # Le châssis débloqué est accepté par start_run (il était refusé tant que la progression n'était pas branchée).
    s._on_command("start_run", {"objective": "vo2max", "duration_min": 60, "seed": 3, "chassis": "blinde"}, 1)
    assert s.rogue is not None and s.rogue.chassis_id == "blinde" and s.rogue.engine.lives == 2


def test_lives_used_in_a_run_leave_the_profile(make, tmp_path):
    s = make({"lives": {"bought": 2, "used": 0, "spent": 60}})
    s.progress_svc.use_lives(1)
    assert load_profile(tmp_path / "profile.json").lives_left == 1
    s._publish_rogue()
    assert s.server.hello_config["rogue"]["lives"] == 1
    s.progress_svc.use_lives(5)   # plus que la réserve : refusé sans rien écrire
    assert load_profile(tmp_path / "profile.json").lives_left == 1


def test_w_prime_estimate_is_published_once_computed(make, monkeypatch, tmp_path):
    s = make()
    seen = {}

    def fake(directory, ftp_w, **kw):
        seen["dir"], seen["cache"] = directory, kw.get("cache_path")
        return 18400.0
    monkeypatch.setattr(estimate_cp, "estimate_w_prime", fake)
    asyncio.run(s._publish_w_prime_estimate())
    assert seen == {"dir": tmp_path / "Activities", "cache": tmp_path / "mmp.json"}
    block = s.server.hello_config["rogue"]
    jsonschema.validate(block, ROGUE_SCHEMA)
    assert block["w_prime_estimate_j"] == 18400.0


def test_w_prime_estimate_failure_leaves_none(make, monkeypatch):
    s = make()

    def broken(*a, **kw):
        raise OSError("disque illisible")
    monkeypatch.setattr(estimate_cp, "estimate_w_prime", broken)
    asyncio.run(s._publish_w_prime_estimate())
    assert s.server.hello_config["rogue"]["w_prime_estimate_j"] is None
