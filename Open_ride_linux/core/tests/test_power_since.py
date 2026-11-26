"""Remise à zéro des statistiques (lot RZ1) et série PP : `since` filtre la courbe affichée, les records du bilan,
le profil et le défi ; le coach, la FTP estimée et la courbe des bots lisent toutes les séances. Séances fabriquées,
modèle à 250 W, aucune donnée réelle."""

from __future__ import annotations

from openride_core import coach, ipc_lists
from openride_core.tools import courbe_fictive, power_curve as pc, power_records as pr

from test_power_curve import DAY, LIVE, NOW, write_journal


def test_kept_sessions_drops_sessions_before_the_reset(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    write_journal(j, "avant", NOW - 20 * DAY, [(300, 300.0)])
    write_journal(j, "apres", NOW - 2 * DAY, [(300, 250.0)])
    found = pc.session_entries(tmp_path / "Activities", tmp_path / "c.json")
    assert len(pc.kept_sessions(found, LIVE)) == 2
    assert len(pc.kept_sessions(found, LIVE, None)) == 2                 # sans remise à zéro : tout compte
    kept = pc.kept_sessions(found, LIVE, NOW - 10 * DAY)
    assert [e["route_id"] for _, e in kept] == ["apres"]


def test_records_start_again_but_ftp_review_reads_everything(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    courbe_fictive.write_sessions(j, NOW - 30 * DAY)                    # cycliste fictif, CP 250 W, avant la remise à zéro
    cur = write_journal(j, "seance", NOW - 600, [(300, 240.0), (1200, 200.0)])
    args = (cur, 200.0, tmp_path / "Activities", tmp_path / "cache.json", LIVE)
    before = pr.session_report(*args, now=NOW)
    assert all(x["s"] != 300 for x in before["records"])               # 240 W en 5 min : sous l'ancien record
    after = pr.session_report(*args, now=NOW, since=NOW - DAY)
    assert after["records"] == []                                      # première séance après la remise à zéro
    assert after["ftp_review"] == before["ftp_review"] and after["ftp_review"] is not None   # FTP : tout lu
    write_journal(j, "suivante", NOW - 300, [(300, 245.0)])
    nxt = pr.session_report(j / "suivante.jsonl", *args[1:], now=NOW, since=NOW - DAY)
    assert {"s": 300, "w": 245, "prev_w": 240, "e": "libre"} in nxt["records"]


def test_power_screen_curve_restarts_but_estimate_does_not(tmp_path, monkeypatch):
    monkeypatch.setattr(coach, "_cache_path", lambda: tmp_path / "coach.json")   # courbe de forme FO1 : cache ici
    j = tmp_path / "Activities" / ".journal"
    courbe_fictive.write_sessions(j, NOW)
    act, cache = tmp_path / "Activities", tmp_path / "c.json"
    full = ipc_lists.build_power_curve_message(1, 200.0, act, cache, LIVE, "x", NOW)
    reset = ipc_lists.build_power_curve_message(1, 200.0, act, cache, LIVE, "x", NOW, since=NOW + DAY)
    assert full["sessions"]["m6"] > 0 and reset["sessions"] == {"m6": 0, "w6": 0}
    assert all(p["m6"] is None and p["w6"] is None for p in reset["points"])   # courbe vide
    assert reset["profile"]["kind"] is None and reset["challenge"] is None      # profil PP5 et défi PP7
    for key in ("estimate", "confidence", "proposal_w", "review", "monthly"):   # FTP estimée : tout lu
        assert reset[key] == full[key]
