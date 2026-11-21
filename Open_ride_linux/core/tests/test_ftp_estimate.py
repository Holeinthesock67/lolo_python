"""Lot PP2 : FTP estimée depuis la courbe, proposée sans rien écrire (séances fabriquées, FTP fictive 250 W)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from openride_core.tools import estimate_cp as ecp
from openride_core.tools import ftp_estimate as fe

NOW = datetime(2026, 11, 20, 12, 0).timestamp()
DAY = 86400.0
CP, WP = 250.0, 20000.0


def write_journal(folder: Path, name: str, start_ts: float, blocks, source="live", extra=()):
    folder.mkdir(parents=True, exist_ok=True)
    lines = [{"kind": "header", "version": 1, "route_id": name, "workout_id": None, "source": source},
             {"kind": "event", "event": "start", "ts": start_ts}]
    t = start_ts
    for block in blocks:
        dur, w = block[0], block[1]
        erg = len(block) > 2 and block[2]
        for _ in range(int(dur)):
            rec = {"kind": "record", "ts": t, "power": w, "mode": "ERG" if erg else "SIM"}
            if erg:
                rec["target_w"] = w
            lines.append(rec)
            t += 1.0
    lines.extend(extra)
    lines.append({"kind": "event", "event": "stop", "ts": t})
    (folder / f"{name}.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")


def est(tmp_path, ftp=250.0, now=NOW):
    return fe.estimate(tmp_path / "Activities", ftp, ("live",), tmp_path / "cache.json", now=now)


def journal(tmp_path):
    return tmp_path / "Activities" / ".journal"


def model_history(folder, erg=False, ago=5):
    for i, t in enumerate((180, 300, 480, 720, 1200)):
        write_journal(folder, f"m{i}", NOW - DAY * (ago + i), [(60, 100.0), (t, CP + WP / t, erg), (120, 80.0)])


def test_cp_from_free_efforts_is_reliable(tmp_path):
    model_history(journal(tmp_path))
    r = est(tmp_path, 240.0)
    e = r["estimate"]
    assert e["source"] == "cp" and e["confidence"] == "Fiable" and abs(e["ftp_w"] - CP) <= 5
    assert "puissance critique" in e["source_text"] and "3 min à 20 min" in e["source_text"]
    assert r["proposal"] == {"ftp_w": e["ftp_w"], "text": f"Utiliser {e['ftp_w']} W comme FTP"}
    assert r["delta_pct"] > 0 and r["review"] is False and len(r["warnings"]) == 2


def test_erg_sessions_never_count(tmp_path):
    """Décision Q1 : une séance ERG ne « prouve » pas la FTP qui l'a réglée."""
    model_history(journal(tmp_path), erg=True)
    r = est(tmp_path)
    assert r["estimate"] is None and r["confidence"] == "Pas assez de données"
    assert r["reason"] == "aucun effort libre de plus de 2 min depuis 6 semaines" and r["proposal"] is None   # échauffements


def test_best_20_min_fallback_and_reason(tmp_path):
    write_journal(journal(tmp_path), "vingt", NOW - 3 * DAY, [(1200, 270.0)])
    r = est(tmp_path)
    e = r["estimate"]
    assert e["source"] == "best20" and e["confidence"] == "Indicative" and e["ftp_w"] == round(270 * 0.95)
    assert "95 % de 270 W" in e["source_text"] and r["proposal"]["ftp_w"] == 256
    write_journal(journal(tmp_path), "vingt", NOW - 3 * DAY, [(700, 270.0)])   # remplacée : 11 min 40 s
    r = est(tmp_path)
    assert r["estimate"] is None and r["reason"] == "aucun effort libre de plus de 8 min depuis 6 semaines"


def test_old_efforts_do_not_estimate_today(tmp_path):
    model_history(journal(tmp_path), ago=60)                                  # plus de 6 semaines
    r = est(tmp_path)
    assert r["estimate"] is None and r["reason"] == "aucun effort libre depuis 6 semaines"


def test_recent_ramp_test_wins(tmp_path):
    model_history(journal(tmp_path))
    ramp = {"kind": "ftp_test", "ts": NOW - 2 * DAY + 900, "test": "ramp", "ftp_w": 262, "method": "75 %",
            "ref_power_w": 349, "held_s": 800, "step_w": 360, "warnings": [], "previous_ftp_w": 250}
    write_journal(journal(tmp_path), "rampe", NOW - 2 * DAY, [(1000, 200.0, True)], extra=[ramp])
    r = est(tmp_path)
    assert r["estimate"]["source"] == "ramp" and r["estimate"]["ftp_w"] == 262 and r["estimate"]["confidence"] == "Fiable"
    assert "test de rampe du" in r["estimate"]["source_text"] and "75 % de 349 W" in r["estimate"]["source_text"]
    assert r["review"] is False and r["delta_pct"] == 4.8
    # rampe douteuse (pause pendant l'effort) : écartée, retour à la CP
    ramp["warnings"] = ["paused"]
    write_journal(journal(tmp_path), "rampe", NOW - 2 * DAY, [(1000, 200.0, True)], extra=[ramp])
    assert est(tmp_path)["estimate"]["source"] == "cp"


def test_review_signal_above_5_percent_and_no_proposal_when_equal(tmp_path):
    write_journal(journal(tmp_path), "vingt", NOW - 3 * DAY, [(1200, 300.0)])
    r = est(tmp_path, 250.0)
    assert r["estimate"]["ftp_w"] == 285 and r["review"] is True and r["delta_pct"] == 14.0
    r = est(tmp_path, 285.0)
    assert r["proposal"] is None and r["review"] is False


def test_monthly_evolution(tmp_path):
    j = journal(tmp_path)
    write_journal(j, "sept", datetime(2026, 9, 10, 18).timestamp(), [(1200, 240.0)])
    write_journal(j, "nov5", datetime(2026, 11, 3, 18).timestamp(), [(300, 320.0)])
    write_journal(j, "nov20", datetime(2026, 11, 4, 18).timestamp(), [(1200, 260.0)])
    m = est(tmp_path)["monthly"]
    assert [x["month"] for x in m] == ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]
    assert m[3] == {"month": "2026-09", "best_5min_w": 240, "best_20min_w": 240, "ftp_w": 228}
    assert m[4]["ftp_w"] is None and m[5]["best_5min_w"] == 320 and m[5]["ftp_w"] == 247


def test_accept_writes_only_the_current_proposal(tmp_path, monkeypatch):
    monkeypatch.setattr(ecp, "CACHE_PATH", tmp_path / "cache_legacy.json")
    write_journal(journal(tmp_path), "vingt", NOW - 3 * DAY, [(1200, 270.0)])
    cfg = tmp_path / "config.toml"
    cfg.write_text("[rider]\nftp_w = 250\n", encoding="utf-8")
    act = tmp_path / "Activities"
    try:
        fe.accept(250, cfg, act, now=NOW)
        raise AssertionError("une valeur qui n'est pas la proposition a été acceptée")
    except fe.AcceptError as exc:
        assert "256" in str(exc)
    assert "250" in cfg.read_text(encoding="utf-8")
    assert fe.accept(256, cfg, act, now=NOW) is True
    assert "ftp_w = 256" in cfg.read_text(encoding="utf-8")


def test_cli(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(ecp, "CACHE_PATH", tmp_path / "cache_legacy.json")
    cfg = tmp_path / "config.toml"
    cfg.write_text("[rider]\nftp_w = 250\n", encoding="utf-8")
    assert fe.main(["--dir", str(tmp_path / "rien"), "--config", str(cfg), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"profile_id", "ftp_set_w", "estimate", "confidence", "reason", "proposal", "review",
                         "delta_pct", "monthly", "warnings"}
    assert fe.main(["--dir", str(tmp_path / "rien"), "--config", str(cfg)]) == 0
    assert "Pas assez de données" in capsys.readouterr().out
    assert fe.main(["--dir", str(tmp_path / "rien"), "--config", str(cfg), "--accept", "260"]) == 1
    assert "ftp_w = 250" in cfg.read_text(encoding="utf-8")
