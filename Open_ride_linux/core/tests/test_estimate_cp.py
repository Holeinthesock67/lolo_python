"""Lot R16 : estimation de CP et W' depuis des séances fabriquées (aucune donnée personnelle)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from openride_core.tools import estimate_cp as ecp

NOW = 1_800_000_000.0
CP, WP = 250.0, 20000.0


def write_session(folder: Path, name: str, start_ts: float, efforts, source="simulated", warm_s=60, warm_w=100.0):
    """Journal à 1 Hz : échauffement puis efforts [(durée s, watts)] séparés de 120 s à 80 W."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.jsonl"
    lines = [{"kind": "header", "version": 1, "route_id": "demo", "workout_id": None, "source": source},
             {"kind": "event", "event": "start", "ts": start_ts}]
    t = start_ts
    for dur, w in [(warm_s, warm_w)] + [x for e in efforts for x in ((e[0], e[1]), (120, 80.0))]:
        for _ in range(int(dur)):
            lines.append({"kind": "record", "ts": t, "power": w, "cadence": 90, "speed": 8.0, "distance": 0.0})
            t += 1.0
    lines.append({"kind": "event", "event": "stop", "ts": t})
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return path


def model_efforts():
    return [(t, CP + WP / t) for t in (180, 300, 480, 720, 1200)]


def build_history(tmp_path: Path):
    act = tmp_path / "Activities" / ".journal"
    for i, (t, w) in enumerate(model_efforts()):
        write_session(act, f"s{i}", NOW - 86400 * (5 + i), [(t, w)])
    return tmp_path / "Activities"


def test_recovers_model_parameters(tmp_path):
    act = build_history(tmp_path)
    r = ecp.estimate(act, 250.0, 90, tmp_path / "cache.json", now=NOW)
    e = r["estimate"]
    assert e is not None and abs(e["cp_w"] - CP) / CP <= 0.03 and abs(e["w_prime_j"] - WP) / WP <= 0.10
    assert e["r2"] > 0.99 and [d["seconds"] for d in e["durations"]] == [180, 300, 480, 720, 1200]
    assert ecp.estimate_w_prime(act, 250.0, cache_path=tmp_path / "cache.json", now=NOW) == e["w_prime_j"]


def test_no_long_effort_gives_readable_reason(tmp_path):
    act = tmp_path / "Activities" / ".journal"
    write_session(act, "short", NOW - 86400, [(50, 400.0)], warm_s=0)      # 170 s : aucune fenêtre de 3 min
    r = ecp.estimate(tmp_path / "Activities", 250.0, 90, tmp_path / "c.json", now=NOW)
    assert r["estimate"] is None and "3 min" in r["reason"] and "90" in r["reason"]
    empty = ecp.estimate(tmp_path / "nothing", 250.0, 90, tmp_path / "c2.json", now=NOW)
    assert empty["estimate"] is None and empty["sessions"] == 0


def test_too_few_durations_and_implausible_models(tmp_path):
    act = tmp_path / "Activities" / ".journal"
    write_session(act, "a", NOW - 86400, [(180, 330.0)], warm_s=0)       # 300 s en tout : deux durées
    r = ecp.estimate(tmp_path / "Activities", 250.0, 90, tmp_path / "c.json", now=NOW)
    assert r["estimate"] is None and "2 durée" in r["reason"]
    # efforts incohérents : la puissance remonte avec la durée
    act2 = tmp_path / "A2" / ".journal"
    for i, (t, w) in enumerate([(180, 250.0), (300, 320.0), (480, 260.0), (720, 330.0)]):
        write_session(act2, f"x{i}", NOW - 86400 * (i + 1), [(t, w)])
    r = ecp.estimate(tmp_path / "A2", 250.0, 90, tmp_path / "c2.json", now=NOW)
    assert r["estimate"] is None and r["reason"]
    # CP hors de 0,8 à 1,2 FTP
    act3 = tmp_path / "A3" / ".journal"
    for i, (t, w) in enumerate(model_efforts()):
        write_session(act3, f"y{i}", NOW - 86400 * (i + 1), [(t, w)])
    r = ecp.estimate(tmp_path / "A3", 150.0, 90, tmp_path / "c3.json", now=NOW)
    assert r["estimate"] is None and "FTP" in r["reason"]


def test_replay_and_old_sessions_excluded(tmp_path):
    act = tmp_path / "Activities" / ".journal"
    for i, (t, w) in enumerate(model_efforts()):
        write_session(act, f"s{i}", NOW - 86400 * (5 + i), [(t, w)])
    base = ecp.estimate(tmp_path / "Activities", 250.0, 90, tmp_path / "c.json", now=NOW)["estimate"]
    write_session(act, "replay", NOW - 86400, [(300, 600.0)], source="replay")      # séance rejouée
    write_session(act, "old", NOW - 86400 * 120, [(300, 600.0)])                    # trop ancienne
    again = ecp.estimate(tmp_path / "Activities", 250.0, 90, tmp_path / "c.json", now=NOW)
    assert again["estimate"] == base and again["sessions"] == 5
    wide = ecp.estimate(tmp_path / "Activities", 250.0, 200, tmp_path / "c.json", now=NOW)
    assert wide["estimate"] is None or wide["estimate"]["durations"][1]["mmp_w"] == pytest.approx(600.0, abs=1.0)


def test_200_sessions_second_run_is_fast_thanks_to_cache(tmp_path):
    act = tmp_path / "Activities" / ".journal"
    for i in range(200):
        write_session(act, f"s{i:03d}", NOW - 3600 * (i + 1), [(200, 200.0 + i % 40)], warm_s=100)
    cache = tmp_path / "cache.json"
    ecp.estimate(tmp_path / "Activities", 250.0, 90, cache, now=NOW)
    t0 = time.perf_counter()
    r = ecp.estimate(tmp_path / "Activities", 250.0, 90, cache, now=NOW)
    assert time.perf_counter() - t0 < 5.0 and r["sessions"] == 200


def test_cli_text_and_json(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(ecp, "CACHE_PATH", tmp_path / "cache.json")
    act = build_history(tmp_path)
    cfg = tmp_path / "config.toml"
    cfg.write_text("[rider]\nftp_w = 250\n", encoding="utf-8")
    assert ecp.main(["--dir", str(act), "--json", "--config", str(cfg)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"directory", "ftp_w", "days", "sessions", "estimate", "reason", "warning"}
    assert ecp.main(["--dir", str(act), "--config", str(cfg), "--ftp", "250"]) == 0
    assert "efforts maximaux" in capsys.readouterr().out
