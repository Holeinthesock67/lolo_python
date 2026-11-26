"""Constats forts de la revue de code du 22 novembre, lot RC2 (trainer et FIT) :
S2-02 vent FTMS remis à zéro, S6-01 « occupé » levé en résistance calculée, S1-05b réglages du
trainer après un changement de profil, S6-03 mesures invraisemblables écartées, S7-01 FIT écrit
malgré une valeur hors plage, S7-04 totaux des tours. Aucun vrai fichier d'activité : tout est
fabriqué (FTP fictive de 250 W, pas de position)."""

from __future__ import annotations

import struct

import pytest

from openride_core import config as config_mod
from openride_core import fit_export, ftms, profiles
from openride_core.config import BikeConfig, TrainerConfig
from openride_core.fit_export import fit_safe_records, write_fit
from openride_core.ftms_driver import FtmsDriver
from openride_core.hr_monitor import HeartRateProvider
from openride_core.input_providers import NullProvider
from openride_core.session import CoreSession
from openride_core.tools import fit_check

from test_profils_joueurs import base, home, make  # noqa: F401 (fixture « home » réutilisée)
from test_wind import make_session, run, start

T0 = 1_790_000_000.0


# --- S2-02 : vent FTMS ---------------------------------------------------------------------------

def test_ftms_wind_is_zeroed_at_pause_and_on_a_route_without_wind(tmp_path, monkeypatch):
    s, drv, _ = make_session(tmp_path, monkeypatch, 6420, mode="fixed", speed_kmh=28.0,
                             from_deg=0.0, feel="ftms")
    start(s)
    run(s, 200)
    assert drv.sim_wind_mps != 0.0
    s._on_command("pause", {}, 3)
    assert drv.sim_wind_mps == 0.0          # pause : trainer relâché, vent compris
    s._on_command("resume", {}, 4)
    run(s, 50, 300.0)
    assert drv.sim_wind_mps != 0.0
    s.cfg.wind.mode = "off"                  # parcours sans vent (vélodrome couvert, vent coupé)
    s._build_wind()
    assert not s.wind.active
    run(s, 5, 400.0)
    assert drv.sim_wind_mps == 0.0


def test_ftms_wind_is_zeroed_when_the_feel_changes_to_grade(tmp_path, monkeypatch):
    s, drv, _ = make_session(tmp_path, monkeypatch, 6422, mode="fixed", speed_kmh=28.0,
                             from_deg=0.0, feel="ftms")
    start(s)
    run(s, 100)
    assert drv.sim_wind_mps != 0.0
    s.cfg.wind.feel = "grade"
    run(s, 5, 300.0)
    assert drv.sim_wind_mps == 0.0


# --- S6-01 : résistance calculée et Control Point occupé ----------------------------------------

def test_accepted_resistance_level_clears_busy_and_refusals():
    drv = FtmsDriver(TrainerConfig(control="resistance"), BikeConfig(), clock=lambda: 100.0)
    drv.busy, drv._busy_streak, drv._refusals, drv.control_refused = True, 2, 2, False
    drv._on_response(ftms.ControlResponse(ftms.OP_SET_TARGET_RESISTANCE, 0x01))
    assert not drv.busy and drv._busy_streak == 0 and drv._refusals == 0 and not drv.control_refused


# --- S1-05b : réglages du trainer après un changement de profil -------------------------------

def test_trainer_setting_reaches_the_driver_after_a_profile_change(home, monkeypatch):  # noqa: F811
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", home / "act")
    ctx = profiles.ProfileContext.for_id("cycliste-a", base(home))
    profiles.activate(ctx)
    cfg = config_mod.load(home / "config.toml")
    cfg.ipc.port_state, cfg.ipc.port_commands = 6424, 6425
    driver = FtmsDriver(cfg.trainer, cfg.bike)   # jamais connecté : seule sa configuration compte
    s = CoreSession(cfg, driver=driver, inputs=[NullProvider()], routes_root=home / "routes",
                    config_path=home / "config.toml")
    s.profiles_base = base(home)
    s.active_profile_path = home / profiles.ACTIVE_FILE
    s.profile_lock = profiles.ProfileLock(ctx)
    s.profile_lock.acquire()
    s.server.send_raw = lambda _f: None
    s._on_command("select_profile", {"id": "cycliste-b"}, 9)
    assert s.driver is driver and driver.cfg is s.cfg.trainer
    assert s.gearing.cfg is s.cfg.gearing
    s._on_command("set_setting", {"key": "trainer.control", "value": "resistance"}, 10)
    assert s.cfg.trainer.control == "resistance" and driver.cfg.control == "resistance"


# --- S6-03 : mesures invraisemblables -----------------------------------------------------------

def _ibd(power_w: int, cadence_raw: int, hr: int | None = None) -> bytearray:
    flags = 0x0004 | 0x0040 | (0x0200 if hr is not None else 0)   # vitesse, cadence, puissance (+ FC)
    data = struct.pack("<HHHh", flags, 3000, cadence_raw, power_w)
    return bytearray(data + (struct.pack("<B", hr) if hr is not None else b""))


def test_absurd_trainer_measures_keep_the_previous_value(caplog):
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: 100.0)
    drv._on_ibd(None, _ibd(210, 180, 140))   # 90 tr/min
    assert drv._raw_power == 210 and drv._cadence == 90 and drv._hr_ibd == 140
    for _ in range(5):
        drv._on_ibd(None, _ibd(32767, 0xFFFF, 255))
    assert drv._raw_power == 210 and drv._cadence == 90 and drv._hr_ibd == 140
    lines = [r for r in caplog.records if "invraisemblable" in r.getMessage()]
    assert len(lines) == 3                    # une ligne par sorte, pas une par trame
    drv._on_ibd(None, _ibd(1200, 220))        # sprint réel au-dessus de la plage annoncée : accepté
    assert drv._raw_power == 1200 and drv._cadence == 110


def test_absurd_heart_rate_from_the_strap_is_ignored():
    hr = HeartRateProvider(clock=lambda: 100.0)
    hr._on_hr(None, bytearray([0x00, 132]))
    assert hr._bpm == 132
    hr._on_hr(None, bytearray([0x01]) + struct.pack("<H", 65535))   # FC 16 bits
    assert hr._bpm == 132


# --- S7-01 et S7-04 : export FIT ---------------------------------------------------------------

def _records(n=60, **over):
    recs = [{"ts": T0 + i, "alt": 200.0, "distance": 8.0 * (i + 1), "speed": 8.0,
             "power": 250, "cadence": 90, "hr": 140} for i in range(n)]
    for i, fields in over.items():
        recs[int(i)].update(fields)
    return recs


@pytest.mark.parametrize("bad", [{"cadence": 300}, {"hr": 400}, {"alt": -600.0}, {"alt": 20000.0},
                                 {"speed": 70.0}, {"power": 70000}, {"distance": -5.0}])
def test_one_out_of_range_value_no_longer_costs_the_fit(tmp_path, bad):
    records = _records(**{"30": bad})
    path = tmp_path / "seance.fit"
    write_fit(records, [{"event": "start", "ts": T0}, {"event": "stop", "ts": T0 + 59}], path)
    _, errors, ok = fit_check.decode(path)
    assert ok and errors == []
    assert records[30] == {**_records()[30], **bad}   # relevés de l'appelant (journal) intacts


def test_fit_safe_records_drops_only_the_bad_field():
    out, fixed = fit_safe_records(_records(n=3, **{"1": {"cadence": 300, "hr": 400}}))
    assert fixed == 1
    assert out[1]["cadence"] is None and out[1]["hr"] is None and out[1]["power"] == 250
    assert out[0] == _records(n=3)[0]


def test_lap_totals_add_up_and_skip_pauses(tmp_path):
    # 5 tours de 20 s à 12,5 m/s, relevés à 1 Hz décalés de 0,4 s par rapport à la ligne.
    records = [{"ts": T0 + 0.4 + i, "distance": 12.5 * (i + 1.4), "speed": 12.5, "power": 250,
                "cadence": 90} for i in range(100)]
    laps = [T0 + 20 * k for k in range(1, 5)]
    events = [{"event": "start", "ts": T0}, {"event": "stop", "ts": T0 + 100.4}]
    path = tmp_path / "piste.fit"
    write_fit(records, events, path, laps)
    messages, errors, ok = fit_check.decode(path)
    assert ok and errors == []
    lap_msgs, sess = messages["lap"], messages["session"][0]
    assert sum(lap["total_distance"] for lap in lap_msgs) == pytest.approx(sess["total_distance"], abs=0.05)
    for lap in lap_msgs[1:4]:
        assert lap["total_distance"] == pytest.approx(250.0, abs=0.05)

    # Pause de 600 s dans le deuxième tour : son temps chronométré n'en tient pas compte.
    rec2 = [{"ts": T0 + i, "distance": 10.0 * i, "speed": 10.0, "power": 200, "cadence": 85}
            for i in range(30)]
    rec2 += [{"ts": T0 + 630 + i, "distance": 300.0 + 10.0 * i, "speed": 10.0, "power": 200,
              "cadence": 85} for i in range(20)]
    ev2 = [{"event": "start", "ts": T0}, {"event": "pause", "ts": T0 + 30},
           {"event": "resume", "ts": T0 + 630}, {"event": "stop", "ts": T0 + 649}]
    path2 = tmp_path / "pause.fit"
    write_fit(rec2, ev2, path2, [T0 + 10, T0 + 640])
    messages, errors, ok = fit_check.decode(path2)
    assert ok and errors == []
    lap2 = messages["lap"][1]
    assert lap2["total_timer_time"] == pytest.approx(30.0, abs=0.01)   # 20 s + 10 s, sans les 600 s
    assert lap2["total_elapsed_time"] == pytest.approx(630.0, abs=0.01)
