"""Zone privée au départ (lot PZ1) : aucune position à moins de 500 m du départ dans le FIT et le GPX.

Traces FICTIVES uniquement : un aller-retour plein nord en plein océan Atlantique (0° N, 20° O), jamais une
position réelle ni un vrai fichier FIT ou GPX.
"""

import math
import xml.etree.ElementTree as ET

import pytest
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage

from openride_core import config as config_mod
from openride_core import fit_export, settings
from openride_core.config import Config
from openride_core.demo_world import build_route
from openride_core.fit_export import iter_records, journal_to_fit, write_fit
from openride_core.journal import JournalWriter, Record
from openride_core.open_world_save import save_ride
from openride_core.privacy_zone import (
    RADIUS_M,
    distance_m,
    mask_records,
    radius_m,
    trim_points,
)
from openride_core.route import Route
from openride_core.tools import fit_check

T0 = 1_790_000_000.0
LAT0, LON0 = 0.0, -20.0            # en mer, loin de toute côte
STEP_M = 10.0
DEG_PER_M = 1.0 / 111_000.0     # pas de 10,02 m : aucun relevé pile à 500 m
NS = "{http://www.topografix.com/GPX/1/1}"


def out_and_back(n_out=150):
    """Aller de `n_out` × 10 m plein nord puis retour au départ, un relevé par seconde."""
    offs = list(range(n_out + 1)) + list(range(n_out - 1, -1, -1))
    records = []
    for i, k in enumerate(offs):
        records.append({"ts": T0 + i, "t": float(i), "lat": LAT0 + k * STEP_M * DEG_PER_M, "lon": LON0,
                        "alt": 10.0 + k * 0.1, "distance": STEP_M * i, "speed": 10.0, "power": 200 + i % 7,
                        "cadence": 88, "hr": 130})
    events = [{"event": "start", "ts": T0}, {"event": "stop", "ts": records[-1]["ts"]}]
    return records, events


def far(r):
    return distance_m(LAT0, LON0, r["lat"], r["lon"]) >= RADIUS_M


def test_setting_is_off_by_default_and_follows_the_profile():
    assert Config().privacy.hide_start == "off" and radius_m(Config()) == 0.0
    cfg = Config()
    cfg.privacy.hide_start = "on"
    assert radius_m(cfg) == RADIUS_M == 500.0
    s = next(x for x in settings.SETTINGS if x.key == "privacy.hide_start")
    assert s.group == "advanced" and s.scope == "profil" and "500 m" in s.help
    assert settings.choices(s) == ["on", "off"]
    with pytest.raises(config_mod.ConfigError):
        config_mod.from_dict({"privacy": {"hide_start": "peut-etre"}})


def test_haversine_is_right_at_the_equator():
    assert distance_m(0.0, 0.0, 0.0, 1.0) == pytest.approx(111_195.0, rel=1e-3)
    assert distance_m(LAT0, LON0, LAT0 + 500 * DEG_PER_M, LON0) == pytest.approx(500.9, rel=1e-3)


def test_mask_records_hides_the_zone_at_the_start_and_on_the_way_back():
    records, _ = out_and_back()
    masked, n = mask_records(records, RADIUS_M)
    assert n == 50 + 50                              # 0 à 490 m à l'aller, 490 à 0 m au retour
    for src, got in zip(records, masked):
        if far(src):
            assert got is src
        else:
            assert "lat" not in got and "lon" not in got
            assert {k: v for k, v in src.items() if k not in ("lat", "lon")} == got   # le reste ne change pas
    assert all("lat" in r for r in records)          # entrée intacte
    assert mask_records(records, 0.0) == (records, 0)
    assert mask_records([{"ts": T0, "distance": 0.0}], RADIUS_M)[1] == 0   # parcours sans GPS


def test_fit_has_no_position_near_the_start_and_the_same_totals(tmp_path):
    records, events = out_and_back()
    plain = write_fit(records, events, tmp_path / "plain.fit")
    priv = write_fit(records, events, tmp_path / "prive.fit", private_start_m=RADIUS_M)
    assert priv == plain                             # résumé du bilan identique

    def read(path):
        msgs = [r.message for r in iter_records(path)]
        return [m for m in msgs if isinstance(m, RecordMessage)], next(m for m in msgs if isinstance(m, SessionMessage))

    recs_a, sess_a = read(tmp_path / "plain.fit")
    recs_b, sess_b = read(tmp_path / "prive.fit")
    assert len(recs_a) == len(recs_b) == len(records)
    for src, r in zip(records, recs_b):
        if far(src):
            assert r.position_lat == pytest.approx(src["lat"], abs=1e-6)
        else:
            assert r.position_lat is None and r.position_long is None
        assert r.power == src["power"] and r.distance == pytest.approx(src["distance"], abs=0.01)
    for f in ("total_distance", "total_timer_time", "avg_power", "normalized_power", "total_work", "total_ascent"):
        assert getattr(sess_b, f) == getattr(sess_a, f), f

    messages, errors, ok = fit_check.decode(tmp_path / "prive.fit")
    lines = {ln["controle"]: ln for ln in fit_check.check(messages, errors, ok)}
    assert lines["positions"]["niveau"] == "OK" and lines["positions"]["detail"].startswith("100 relevé(s)")
    assert lines["compatibilité Garmin Connect et GoldenCheetah"]["niveau"] == "OK"
    messages, errors, ok = fit_check.decode(tmp_path / "plain.fit")
    assert "positions" not in {ln["controle"] for ln in fit_check.check(messages, errors, ok)}


def test_journal_to_fit_reads_the_setting(tmp_path, monkeypatch):
    records, _ = out_and_back(80)
    with JournalWriter(tmp_path / "j.jsonl", route_id="essai") as j:
        j.event("start", T0)
        for r in records:
            j.record(Record(ts=r["ts"], t=r["t"], lat=r["lat"], lon=r["lon"], alt=r["alt"], distance=r["distance"],
                            speed=r["speed"], power=float(r["power"]), cadence=88, hr=130, grade=0.0, gear=12))
        j.event("stop", records[-1]["ts"])
    cfg = Config()
    cfg.privacy.hide_start = "on"
    monkeypatch.setattr(config_mod, "load", lambda *a, **k: cfg)
    path, _ = journal_to_fit(tmp_path / "j.jsonl", tmp_path / "on.fit")
    recs = [r.message for r in iter_records(path) if isinstance(r.message, RecordMessage)]
    assert sum(1 for r in recs if r.position_lat is None) == 100
    cfg.privacy.hide_start = "off"
    path, _ = journal_to_fit(tmp_path / "j.jsonl", tmp_path / "off.fit")
    recs = [r.message for r in iter_records(path) if isinstance(r.message, RecordMessage)]
    assert all(r.position_lat is not None for r in recs)
    path, _ = journal_to_fit(tmp_path / "j.jsonl", tmp_path / "force.fit", private_start_m=RADIUS_M)
    recs = [r.message for r in iter_records(path) if isinstance(r.message, RecordMessage)]
    assert sum(1 for r in recs if r.position_lat is None) == 100


def test_configured_radius_keeps_positions_if_the_config_is_broken(monkeypatch):
    def broken(*a, **k):
        raise config_mod.ConfigError("illisible")
    monkeypatch.setattr(config_mod, "load", broken)
    assert fit_export.configured_private_start_m() == 0.0


def test_trim_points_cuts_the_start_and_the_end_only():
    pts = [(LAT0 + k * STEP_M * DEG_PER_M, LON0, 0.0) for k in list(range(101)) + list(range(99, -1, -1))]
    got = trim_points(pts, RADIUS_M)
    assert got == pts[50:-50]
    assert all(distance_m(LAT0, LON0, la, lo) >= RADIUS_M for la, lo, _ in got[:1] + got[-1:])
    assert trim_points(pts[:40], RADIUS_M) == []           # jamais sorti de la zone
    assert trim_points(pts, 0.0) == pts


def test_open_world_gpx_starts_outside_the_zone(tmp_path):
    route = Route(build_route(3000.0, origin_lat=LAT0, origin_lon=LON0))
    path = save_ride(route, 2000.0, "ow-prive", tmp_path, ts=T0, private_start_m=RADIUS_M)
    root = ET.parse(path).getroot()
    pts = [(float(p.get("lat")), float(p.get("lon"))) for p in root.iter(NS + "trkpt")]
    start = route.sample(0.0)
    assert distance_m(start.lat, start.lon, *pts[0]) >= RADIUS_M
    assert all(distance_m(start.lat, start.lon, la, lo) >= RADIUS_M for la, lo in pts[:5])
    plain = save_ride(route, 2000.0, "ow-plain", tmp_path, ts=T0)
    assert len(list(ET.parse(plain).getroot().iter(NS + "trkpt"))) > len(pts)
    # Balade restée près du départ : rien d'enregistré
    assert save_ride(route, 600.0, "ow-court", tmp_path, ts=T0, private_start_m=5000.0) is None
    assert not (tmp_path / "ow-court.gpx").exists()
    assert math.isfinite(pts[-1][0])
