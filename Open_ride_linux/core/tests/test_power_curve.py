"""Lot PP1 : courbe de puissance sur 6 mois et 6 semaines, séances fabriquées (modèle à 250 W, aucune donnée réelle)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openride_core.tools import estimate_cp as ecp
from openride_core.tools import power_curve as pc

NOW = 1_800_000_000.0
DAY = 86400.0
LIVE = ("live",)


def write_journal(folder: Path, name: str, start_ts: float, blocks, source="live", extra=()):
    """Journal à 1 Hz : `blocks` = [(durée s, watts, erg)] ; `extra` : lignes ajoutées (événements, appareils)."""
    folder.mkdir(parents=True, exist_ok=True)
    lines = [{"kind": "header", "version": 1, "route_id": name, "workout_id": None, "source": source},
             {"kind": "event", "event": "start", "ts": start_ts}]
    t = start_ts
    for block in blocks:
        dur, w = block[0], block[1]
        erg = len(block) > 2 and block[2]
        for _ in range(int(dur)):
            rec = {"kind": "record", "ts": t, "t": t - start_ts, "power": w, "cadence": 90, "speed": 8.0,
                   "distance": 0.0, "mode": "ERG" if erg else "SIM"}
            if erg:
                rec["target_w"] = w
            lines.append(rec)
            t += 1.0
    lines.extend(extra)
    lines.append({"kind": "event", "event": "stop", "ts": t})
    path = folder / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return path


def point(result, seconds, window="months6"):
    return next(p for p in result["windows"][window]["points"] if p["seconds"] == seconds)


def curve(tmp_path, sources=LIVE):
    return pc.compute(tmp_path / "Activities", sources, tmp_path / "cache.json", now=NOW)


def test_thirteen_durations_and_both_windows(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    write_journal(j, "recent", NOW - 10 * DAY, [(600, 150.0), (3600, 230.0), (300, 100.0), (5, 800.0)])
    write_journal(j, "vieux", NOW - 100 * DAY, [(300, 320.0)])        # dans les 6 mois, pas les 6 semaines
    write_journal(j, "trop_vieux", NOW - 200 * DAY, [(60, 600.0)])    # hors des 6 mois
    r = curve(tmp_path)
    assert r["durations"] == list(pc.DURATIONS_S) and len(pc.DURATIONS_S) == 13
    m6 = r["windows"]["months6"]
    assert m6["days"] == 183 and m6["sessions"] == 2 and r["windows"]["weeks6"]["sessions"] == 1
    assert [p["label"] for p in m6["points"]][:4] == ["5 s", "15 s", "30 s", "1 min"]
    assert point(r, 5)["watts"] == 800 and point(r, 3600)["watts"] == 230
    assert point(r, 300)["watts"] == 320 and point(r, 300)["session"]["route_id"] == "vieux"
    assert point(r, 300, "weeks6")["watts"] < 320                    # forme du moment : plus basse
    assert point(r, 60)["watts"] < 600                                # séance de 200 jours écartée
    p = point(r, 3600)
    assert p["effort"] == "libre" and p["date"] and p["session"]["file"] == "recent.jsonl"


def test_window_never_crosses_a_pause(tmp_path):
    """Défaut de R16 : 2 × 10 min à 300 W séparés par une pause donnaient un « 20 min » à 300 W."""
    j = tmp_path / "Activities" / ".journal"
    start = NOW - DAY
    lines = [(600, 300.0)]
    path = write_journal(j, "pause", start, lines)
    # seconde moitié après une pause de 5 min sans relevé
    text = path.read_text(encoding="utf-8").splitlines()[:-1]
    t = start + 600
    extra = [{"kind": "event", "event": "pause", "ts": t, "reason": "user"},
             {"kind": "event", "event": "resume", "ts": t + 300}]
    recs = [{"kind": "record", "ts": t + 300 + i, "power": 300.0, "mode": "SIM"} for i in range(600)]
    path.write_text("\n".join(text + [json.dumps(x) for x in extra + recs]
                              + [json.dumps({"kind": "event", "event": "stop", "ts": t + 900})]) + "\n", encoding="utf-8")
    r = curve(tmp_path)
    assert point(r, 600 if 600 in pc.DURATIONS_S else 480)["watts"] == 300
    assert point(r, 1200)["watts"] is None                            # aucun effort continu de 20 min
    old = ecp.estimate(tmp_path / "Activities", 250.0, 90, tmp_path / "cache.json", now=NOW)
    assert all(d["seconds"] != 1200 for d in (old["estimate"] or {}).get("durations", []))


def test_trainer_loss_and_gaps_cut_the_session(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    start = NOW - DAY
    path = write_journal(j, "coupure", start, [(1200, 280.0)], extra=[
        {"kind": "device", "ts": start + 400, "device": "trainer", "state": "down"},
        {"kind": "device", "ts": start + 410, "device": "trainer", "state": "up"}])
    r = curve(tmp_path)
    assert point(r, 1200)["watts"] is None and point(r, 720)["watts"] == 280
    # trou de 5 s entre deux relevés : coupure aussi
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    lines = [x for x in lines if x.get("kind") != "device" and not (x.get("kind") == "record"
                                                                   and start + 600 <= x["ts"] < start + 605)]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    r = curve(tmp_path)
    assert point(r, 1200)["watts"] is None and point(r, 480)["watts"] == 280


def test_small_gap_is_tolerated_and_spikes_removed(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    path = write_journal(j, "pic", NOW - DAY, [(100, 200.0), (1, 2600.0), (100, 200.0), (1, 1500.0), (100, 200.0)])
    r = curve(tmp_path)
    assert point(r, 5)["watts"] == 200                                # 2 600 W et pic isolé de 1 500 W écartés
    assert point(r, 300)["watts"] == 200
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    lines = [x for x in lines if not (x.get("kind") == "record" and x["ts"] == NOW - DAY + 50)]   # 1 relevé manquant
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    assert point(curve(tmp_path), 300)["watts"] == 200


def test_real_sprint_is_kept(tmp_path):
    write_journal(tmp_path / "Activities" / ".journal", "sprint", NOW - DAY, [(60, 200.0), (10, 1100.0), (60, 200.0)])
    assert point(curve(tmp_path), 5)["watts"] == 1100


def test_erg_points_are_labelled_and_kept_apart(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    write_journal(j, "seuil", NOW - 3 * DAY, [(300, 120.0, True), (1200, 260.0, True)])
    write_journal(j, "libre", NOW - 2 * DAY, [(1200, 240.0), (300, 100.0), (60, 450.0)])
    r = curve(tmp_path)
    p20 = point(r, 1200)
    assert p20["watts"] == 260 and p20["effort"] == "ERG" and p20["session"]["route_id"] == "seuil"
    assert p20["free"]["watts"] == 240 and p20["free"]["session"]["route_id"] == "libre"
    p1 = point(r, 60)
    assert p1["watts"] == 450 and p1["effort"] == "libre"
    # séance mixte : une fenêtre libre ne contient aucune seconde en ERG
    write_journal(j, "mixte", NOW - DAY, [(200, 300.0), (200, 300.0, True)])
    p5 = point(curve(tmp_path), 300)
    assert p5["watts"] == 300 and p5["effort"] == "ERG" and p5["free"]["watts"] < 300


def test_sources_of_the_profile_and_replays(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    write_journal(j, "reel", NOW - 2 * DAY, [(300, 250.0)])
    write_journal(j, "simu", NOW - DAY, [(300, 400.0)], source="simulated")
    write_journal(j, "rejeu", NOW - 3 * DAY, [(300, 500.0)], source="replay")
    assert point(curve(tmp_path, LIVE), 300)["watts"] == 250                       # profil de joueur
    essai = curve(tmp_path, ("live", "simulated"))                                 # profil d'essai
    assert point(essai, 300)["watts"] == 400 and essai["windows"]["months6"]["sessions"] == 2


def test_fit_is_a_fallback_only():
    jsonl = {"fmt": "jsonl", "start_ts": NOW, "source": "live", "all": {}, "free": {}}
    fit_same = {"fmt": "fit", "start_ts": NOW + 5, "source": "", "all": {}, "free": {}}
    fit_alone = {"fmt": "fit", "start_ts": NOW - DAY, "source": "", "all": {"5": 900.0}, "free": {}}
    replay = {"fmt": "jsonl", "start_ts": NOW - 2 * DAY, "source": "replay", "all": {}, "free": {}}
    fit_of_replay = {"fmt": "fit", "start_ts": NOW - 2 * DAY + 3, "source": "", "all": {}, "free": {}}
    found = [(Path(f"{i}"), e) for i, e in enumerate([jsonl, fit_same, fit_alone, replay, fit_of_replay])]
    kept = [e for _, e in pc.kept_sessions(found, LIVE)]
    assert kept == [jsonl, fit_alone]
    w = pc.window_curve(pc.kept_sessions(found, LIVE), 183, NOW)
    assert w["points"][0]["watts"] == 900 and w["points"][0]["effort"] == "inconnu" and w["points"][0]["free"] is None


def test_cache_version_2_replaces_r16_cache(tmp_path, monkeypatch):
    j = tmp_path / "Activities" / ".journal"
    write_journal(j, "a", NOW - DAY, [(300, 250.0)])
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"version": 1, "entries": {"x": {"mmp": {"180": 999}}}}), encoding="utf-8")
    first = curve(tmp_path)
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert data["version"] == 2 and "x" not in data["entries"] and len(data["entries"]) == 1

    def boom(*a, **k):
        raise AssertionError("séance recalculée alors que le cache est à jour")
    monkeypatch.setattr(pc, "_compute_entry", boom)
    assert curve(tmp_path) == first
    # l'estimation de CP lit le même cache
    assert ecp.estimate(tmp_path / "Activities", 250.0, 90, cache, now=NOW)["sessions"] == 1


def test_empty_profile_and_cli(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(ecp, "CACHE_PATH", tmp_path / "cache_cli.json")   # contexte historique (sans profil)
    r = pc.compute(tmp_path / "rien", LIVE, tmp_path / "c.json", now=NOW)
    assert r["windows"]["months6"]["sessions"] == 0 and all(p["watts"] is None for p in r["windows"]["months6"]["points"])
    write_journal(tmp_path / "Activities" / ".journal", "a", 0.0 + 1.0, [(30, 200.0)])
    assert pc.main(["--dir", str(tmp_path / "Activities"), "--sources", "live", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"profile_id", "directory", "sources", "durations", "windows", "warning"}
    assert pc.main(["--dir", str(tmp_path / "Activities")]) == 0
    out = capsys.readouterr().out
    assert "6 mois" in out and "60 min" in out


@pytest.mark.parametrize("seconds,label", [(5, "5 s"), (60, "1 min"), (2700, "45 min")])
def test_labels(seconds, label):
    assert pc.duration_label(seconds) == label


def test_curve_belongs_to_the_current_profile(tmp_path):
    """Sans dossier donné : séances, sources comptées et cache du profil en cours (série MJ)."""
    from openride_core import profiles

    base = tmp_path / "Profils"
    player = profiles.ProfileContext.for_id("cycliste1", base)
    trial = profiles.ProfileContext.for_id(profiles.TRIAL_ID, base)
    write_journal(player.journal_dir, "a", NOW - DAY, [(300, 250.0)])
    write_journal(player.journal_dir, "b", NOW - DAY / 2, [(300, 400.0)], source="simulated")
    write_journal(trial.journal_dir, "c", NOW - DAY, [(300, 300.0)], source="simulated")
    try:
        profiles.activate(player)
        r = pc.compute(now=NOW)
        assert r["profile_id"] == "cycliste1" and point(r, 300)["watts"] == 250 and player.mmp_cache.is_file()
        profiles.activate(trial)
        assert point(pc.compute(now=NOW), 300)["watts"] == 300        # le profil d'essai compte ses séances simulées
    finally:
        profiles.activate(None)


def test_one_hour_session_is_cheap():
    import time

    recs = [{"ts": float(i), "power": 200.0 + (i * 37) % 120, "mode": "SIM"} for i in range(3600)]
    t0 = time.perf_counter()
    all_best, free_best = pc.session_curves(pc.segments(recs))
    assert time.perf_counter() - t0 < 0.5 and set(all_best) == set(pc.DURATIONS_S) and free_best == all_best


def test_ramp_test_lines_are_kept_in_the_cache(tmp_path):
    """Pour PP2 : le résultat d'un test de rampe est gardé avec la séance (FTP fictive)."""
    j = tmp_path / "Activities" / ".journal"
    write_journal(j, "rampe", NOW - DAY, [(600, 200.0, True)], extra=[
        {"kind": "ftp_test", "ts": NOW - DAY + 590, "test": "ramp", "ftp_w": 250, "method": "75 %",
         "ref_power_w": 333, "held_s": 500, "step_w": 340, "warnings": [], "previous_ftp_w": 240}])
    found = pc.session_entries(tmp_path / "Activities", tmp_path / "cache.json")
    (_, e), = found
    assert e["ftp_tests"] == [{"ts": NOW - DAY + 590, "test": "ramp", "ftp_w": 250, "ref_power_w": 333, "warnings": []}]
