"""Lot PP4 : records de puissance de la séance et signal « FTP à revoir » au bilan (séances fabriquées, modèle
à 250 W, aucune donnée réelle)."""

from __future__ import annotations

import time

from openride_core import profiles
from openride_core.tools import courbe_fictive, power_records as pr

from test_power_curve import DAY, LIVE, NOW, write_journal
from test_profils_joueurs import home, make  # noqa: F401  (fixture `home`)


def report(tmp_path, journal, ftp=250.0, sources=LIVE):
    return pr.session_report(journal, ftp, tmp_path / "Activities", tmp_path / "cache.json", sources, now=NOW)


def test_records_against_six_months(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    write_journal(j, "avant", NOW - 20 * DAY, [(300, 300.0), (300, 100.0), (5, 700.0)])
    write_journal(j, "trop_vieux", NOW - 200 * DAY, [(300, 400.0)])      # hors des 6 mois : ne compte pas
    cur = write_journal(j, "seance", NOW - 600, [(300, 310.0), (300, 100.0), (5, 650.0), (100, 90.0),
                                                (1200, 220.0)])
    r = report(tmp_path, cur)
    by_s = {x["s"]: x for x in r["records"]}
    assert 300 in by_s and by_s[300] == {"s": 300, "w": 310, "prev_w": 300, "e": "libre"}
    assert 5 not in by_s                                                  # 650 W < 700 W : pas de record
    assert by_s[1200]["prev_w"] is None                                   # premier effort de 20 min
    assert len(r["records"]) <= pr.MAX_RECORDS and [x["s"] for x in r["records"]] == sorted(by_s)


def test_first_session_and_uncounted_session_announce_nothing(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    first = write_journal(j, "premiere", NOW - 600, [(300, 300.0)])
    assert report(tmp_path, first) == {"records": [], "ftp_review": None}
    sim = write_journal(j, "simulee", NOW - 300, [(300, 400.0)], source="simulated")
    assert report(tmp_path, sim) is None                                  # séance simulée d'un joueur
    assert report(tmp_path, sim, sources=("live", "simulated"))["records"][0]["w"] == 400   # profil d'essai


def test_erg_record_says_erg(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    write_journal(j, "avant", NOW - 5 * DAY, [(3600, 200.0)])
    cur = write_journal(j, "seuil", NOW - 4000, [(3600, 240.0, True)])
    rec = next(x for x in report(tmp_path, cur)["records"] if x["s"] == 3600)
    assert rec["e"] == "ERG" and rec["w"] == 240 and rec["prev_w"] == 200


def test_ftp_review_only_beyond_five_percent(tmp_path):
    jdir = tmp_path / "Activities" / ".journal"
    courbe_fictive.write_sessions(jdir, NOW)                              # cycliste fictif, CP 250 W
    last = max(jdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    fr = report(tmp_path, last, ftp=200.0)["ftp_review"]
    assert fr is not None and fr["ftp_set_w"] == 200 and abs(fr["estimate_w"] - 250) <= 6
    assert fr["delta_pct"] > 5 and fr["confidence"] in ("Fiable", "Indicative")
    assert report(tmp_path, last, ftp=250.0)["ftp_review"] is None      # FTP réglée juste : rien


def test_summary_gets_records_after_the_session(home, monkeypatch):
    jdir = profiles.ProfileContext.for_id("cycliste-a", home / "Profils").journal_dir
    now = time.time()
    write_journal(jdir, "avant", now - 3 * DAY, [(300, 250.0)])
    cur = write_journal(jdir, "seance", now - 400, [(300, 280.0)])
    s, _frames = make(home, monkeypatch)
    s.state.summary = {"duration_s": 300}
    s._after_session_power(cur)                                           # hors boucle : calcul direct
    assert s.state.summary["power_records"][0]["s"] in (5, 15, 30, 60, 120, 180, 300)
    assert any(x["s"] == 300 and x["w"] == 280 and x["prev_w"] == 250 for x in s.state.summary["power_records"])
    assert "ftp_review" not in s.state.summary or s.state.summary["ftp_review"]["ftp_set_w"] == 200
    s.state.summary = {"duration_s": 300}
    s._after_session_power(jdir / "absent.jsonl")                         # séance inconnue : rien
    assert s.state.summary == {"duration_s": 300}
