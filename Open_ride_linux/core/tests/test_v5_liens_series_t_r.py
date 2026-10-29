"""Lot V5 : progression branchée sur les séries T (segments, records, maillots, bots) et R (runs).

Critères du cahier `docs/lots/LOT_V5_liens_series_T_R.md` §7 :
2. Journal synthétique avec deux segments (dont un record) et un maillot à pois : expérience et
   pièces de plus qu'une séance sans événement, défi « premier maillot à pois » réussi.
3. Calibrage d'un bot au même niveau avec et sans équipement aéro sur un parcours plat : temps
   d'arrivée du bot identique à celui du cycliste simulé équipé (à 1 % près).
4. Passage de segment : équipement noté dans le record, `equipment_gain_s` nul avec l'équipement
   de départ.
Et : la run Cyber-Rogue roule sans l'équipement de la série V (les châssis en tiennent lieu).
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from openride_core.bots import PROFILES, ProfileBot, RefRider, RouteProfile, calibrate, ride_time
from openride_core.classic import ClassicRace
from openride_core.coins import coin_table, coins_by_session
from openride_core.equipment import apply_equipment, load_catalogue, segment_time_gain
from openride_core.journal import JournalWriter, Record, read_journal
from openride_core.physics import PhysicsParams
from openride_core.progression import load_table, recompute
from openride_core.records import RecordBook, RecordEntry
from openride_core.segment_timing import SegmentPass

from test_profile_bots import FakeRoute, seg
from test_progression import write_journal

AERO = {"frame": "frame_tt", "wheels": "wheels_disc"}
START = {"frame": "frame_allround", "wheels": "wheels_standard"}


@pytest.fixture(scope="module")
def table():
    return load_table(user_path=None)


@pytest.fixture(scope="module")
def cat(table):
    return load_catalogue(table)


# --- critère 2 : événements du journal → expérience, pièces, défis ----------------------------

def test_segments_and_kom_jersey_earn_xp_coins_and_challenge(tmp_path, table):
    plain_dir, event_dir = tmp_path / "plain", tmp_path / "events"
    plain_dir.mkdir()
    event_dir.mkdir()
    write_journal(plain_dir / "s.jsonl")
    write_journal(event_dir / "s.jsonl", extra_lines=[
        {"kind": "segment", "ts": 1, "segment_id": "climb1", "lap": 0, "type": "climb", "category": "2",
         "time_s": 300.0, "bonuses": [], "pr": True},
        {"kind": "segment", "ts": 2, "segment_id": "sprint1", "lap": 0, "type": "sprint", "category": None,
         "time_s": 20.0, "bonuses": [], "pr": False},
        {"kind": "jersey", "ts": 3, "jersey": "kom"}])
    plain, events = recompute(plain_dir, table), recompute(event_dir, table)
    xp = table.data["xp"]
    assert events.total_xp - plain.total_xp == 2 * xp["per_segment"] + xp["per_segment_pr"] + xp["per_jersey"]
    assert events.total_xp - plain.total_xp == 50 + 50 + 100 + 200
    gains = {g["source"]: g["points"] for g in events.counted[0].gains.as_list()}
    assert (gains["segment"], gains["segment_pr"], gains["jersey"]) == (100, 100, 200)

    ct = coin_table(table)
    extra = coins_by_session(events, ct)["s.jsonl"] - coins_by_session(plain, ct)["s.jsonl"]
    assert extra == 5 + 5 + 10 + 20   # deux segments, record de segment (27 octobre), maillot à pois

    done = {c.id for c in events.challenges}
    assert "kom_first" in done and "kom_first" not in {c.id for c in plain.challenges}
    assert events.stats["jerseys_kom"] == 1 and events.stats["segment_prs"] == 1


def test_hc_climb_and_first_boss_challenges(tmp_path, table):
    write_journal(tmp_path / "s.jsonl", extra_lines=[
        {"kind": "segment", "ts": 1, "segment_id": "col", "lap": 0, "type": "climb", "category": "HC",
         "time_s": 1800.0, "bonuses": [], "pr": False},
        {"kind": "rogue_run", "minutes": 30.0, "bosses": ["chimere_centrale"], "gold": 0}])
    done = {c.id: c.reward for c in recompute(tmp_path, table).challenges}
    assert done["hc_first"] == "frame_climber" and done["rogue_boss_first"] == "kit_neon"


# --- critère 3 : calibrage des bots avec l'équipement du cycliste ----------------------------

@pytest.mark.parametrize("loadout", [START, AERO])
def test_bot_calibrated_on_equipped_rider_finishes_with_him(loadout, cat):
    plain = PhysicsParams(mass_kg=79.0)
    equipped = apply_equipment(plain, loadout, cat)
    route = FakeRoute(20000.0)
    prof = RouteProfile(route)
    level, ftp = 100.0, 250.0
    rider_t = ride_time(prof, equipped, power_w=ftp * level / 100.0)
    for profile in PROFILES:
        k = calibrate(profile, route, level, RefRider(ftp, equipped), bike_mass_kg=9.0, prof=prof, bot_params=plain)
        bot = ProfileBot(profile, params=plain, bike_mass_kg=9.0, scale=k)   # le bot roule sans équipement
        assert ride_time(prof, bot.params, bot=bot) == pytest.approx(rider_t, rel=0.01), profile
    if loadout is AERO:
        assert equipped.cda_m2 < plain.cda_m2
        assert rider_t < ride_time(prof, plain, power_w=ftp)   # l'équipement aéro rend le bot plus fort


# --- critère 4 : records et temps gagné par l'équipement -----------------------------------------

def _pass(time_s: float = 120.0) -> SegmentPass:
    return SegmentPass("climb1", 0, 10.0, 10.0 + time_s, time_s, 250.0, 3.4, 30.0, ())


def test_record_keeps_loadout_and_stays_a_record(tmp_path):
    book = RecordBook()
    first = book.add("demo", "climb1", _pass(120.0), "2026-10-28 08:00", {**AERO, "mass_delta_kg": 1.0})
    second = book.add("demo", "climb1", _pass(125.0), "2026-10-28 09:00", START)
    assert first.is_record and not second.is_record   # l'équipement ne change pas le rang
    best = book.best("demo", "climb1", False)
    assert dict(best.loadout) == AERO   # cadre et roues seulement
    path = tmp_path / "records.json"
    book.save(path)
    rows = json.loads(path.read_text(encoding="utf-8"))["routes"]["demo"]["climb1"]["no_bonus"]
    assert rows[0]["loadout"] == AERO and rows[1]["loadout"] == START
    assert RecordBook.load(path).best("demo", "climb1", False).loadout == best.loadout
    # Fichier d'avant le lot V5 : pas de `loadout`, relu sans erreur et réécrit sans le champ
    old = RecordEntry.from_dict({"time_s": 100.0, "date": "2026-10-27 18:05"})
    assert old.loadout is None and "loadout" not in old.to_dict()


def test_rebuild_reads_loadout_from_journal_header(tmp_path):
    path = tmp_path / "s.jsonl"
    with JournalWriter(path, route_id="flat", source="live", progression={"ftp_w": 250, "loadout": AERO}) as w:
        w.event("start", 1_760_000_000.0)
        for i in range(1, 61):
            w.record(Record(ts=1_760_000_000.0 + i, t=float(i), distance=10.0 * i, power=250.0, mode="SIM"))
    book = RecordBook.rebuild("flat", [path], [seg("sprint", 100.0, 400.0)], 600.0)
    assert dict(book.best("flat", "sprint1", False).loadout) == AERO


def _race(gain_mode: str, loadout: dict | None) -> ClassicRace:
    return ClassicRace(route_id="flat", segments=(seg("sprint", 100.0, 400.0),), length_m=1000.0,
                       powerups_on=False, loadout=loadout, gain_mode=gain_mode)


def _ride(race: ClassicRace, to_s: float = 450.0) -> list[dict]:
    t, s = 0.0, 0.0
    race.start(t, s)
    out: list[dict] = []
    while s < to_s:
        t, s = t + 0.02, s + 0.2
        race.step(t, 0.02, s, 250.0, ())
        for job in race.take_gain_jobs():
            job.resolve(-1.234)
        out += race.due_results(t)
    return out


def test_segment_result_gain_null_without_progression_zero_with_start_equipment():
    assert _ride(_race("off", None))[0]["equipment_gain_s"] is None
    race = _race("zero", START)
    msg = _ride(race)[0]
    assert msg["equipment_gain_s"] == 0.0
    assert dict(race.book.best("flat", "sprint1", False).loadout) == START
    assert race.journal and race.journal[0]["kind"] == "segment"


def test_segment_result_waits_for_computed_gain():
    race = _race("compute", AERO)
    race.start(0.0, 0.0)
    t, s = 0.0, 0.0
    while s < 401.0:
        t, s = t + 0.02, s + 0.2
        race.step(t, 0.02, s, 250.0, ())
    jobs = race.take_gain_jobs()
    assert len(jobs) == 1 and (jobs[0].s_start, jobs[0].s_end) == (100.0, 400.0)
    assert race.due_results(t + 5.0) == []   # rien ne part sans le temps gagné
    jobs[0].resolve(-1.234)
    (msg,) = race.due_results(t)
    assert msg["equipment_gain_s"] == -1.2


def test_segment_time_gain_aero_on_flat(cat):
    plain = PhysicsParams(mass_kg=79.0)
    aero = apply_equipment(plain, AERO, cat)
    records = [{"kind": "record", "t": float(i), "distance": 10.0 * i, "grade": 0.0, "alt": 100.0,
                "power": 250.0, "speed": 10.0} for i in range(0, 80)]
    gain = segment_time_gain(records, aero, plain, 20.3, 60.1, 203.0, 601.0)
    assert gain is not None and -4.0 < gain < 0.0   # 400 m de plat : un peu plus d'une seconde
    assert segment_time_gain(records, plain, plain, 20.3, 60.1, 203.0, 601.0) == 0.0
    assert segment_time_gain(records[:1], aero, plain, 20.3, 60.1, 203.0, 601.0) is None


# --- séance : calibrage, segments et run Cyber-Rogue -------------------------------------------

@pytest.fixture
def equipped_env(tmp_path, monkeypatch):
    """Séance de `test_session_serie_t` avec un profil de progression équipé aéro (cadre et roues)."""
    from openride_core import garage
    from openride_core.profile import Profile, save_profile

    profile_path = tmp_path / "profile.json"

    def equip(loadout: dict) -> None:
        p = Profile()
        p.equipped.update(loadout)   # pièces offertes : le profil ne vérifie pas l'achat
        save_profile(p, profile_path)

    monkeypatch.setattr(garage, "PROFILE_PATH", profile_path)
    return equip


def test_session_segment_gain_and_rogue_without_equipment(env, equipped_env, cat):
    make, run, tmp = env
    equipped_env(AERO)
    s, sent = make(7200)
    assert s._base_params.cda_m2 < PhysicsParams.from_config(s.cfg).cda_m2
    s._on_command("start", {}, 2)
    journal = s._rec.path
    run(s, 900.0)
    msgs = [m for m in sent if m.get("type") == "segment_result"]
    assert msgs and all(m["equipment_gain_s"] is not None for m in msgs)
    gain = {m["segment_id"]: m["equipment_gain_s"] for m in msgs}
    assert gain["sprint1"] < 0.0 < gain["climb1"]   # aéro : gagne au sprint, 1 kg de plus perd en montée
    head = next(read_journal(journal))
    assert head["loadout"]["frame"] == "frame_tt"
    book = json.loads((tmp / "records.json").read_text(encoding="utf-8"))["routes"]["demo"]
    assert book["climb1"]["no_bonus"][0]["loadout"] == AERO

    # Run Cyber-Rogue : physique sans équipement, en-tête sans `loadout`
    s._on_command("start_run", {"objective": "threshold", "duration_min": 30, "seed": 5}, 3)
    assert not [m for m in sent if m.get("type") == "error"]
    assert s.state.session_state == "READY" and s.rogue is not None
    assert s.physics.p.cda_m2 == PhysicsParams.from_config(s.cfg).cda_m2
    s._on_command("start", {}, 4)
    head = next(read_journal(s._rec.path))
    assert head["loadout"] is None
    run(s, 2.0)
    s._on_command("end_session", {}, 5)
    assert s.state.session_state == "FINISHED" and s.rogue is None
    assert s.physics.p.cda_m2 == s._base_params.cda_m2   # l'équipement revient après la run


from test_session_serie_t import env  # noqa: E402,F401  (fixture partagée)
