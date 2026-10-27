"""Lot R7 : table d'équilibrage en données et runs simulées."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import fields
from pathlib import Path

import pytest

from openride_core.rogue.balance import (DEFAULT_BALANCE, EMBEDDED_PATH, BalanceError, RogueBalance,
                                         apply_overrides, balance_hash, load_balance)
from openride_core.rogue.run import RunEngine, RunInputs
from openride_core.rogue.rooms import RoomRider
from openride_core.rogue.scenario import compose_run
from openride_core.tools import rogue_sim as sim

TABLES = ("calendars", "reservoirs", "room_profiles")
NOWHERE = Path("/nonexistent/rogue_balance.toml")


def test_embedded_table_equals_defaults():
    assert load_balance(NOWHERE) == DEFAULT_BALANCE


def test_every_field_is_in_the_file_with_a_french_comment():
    text = EMBEDDED_PATH.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    assert {f.name for f in fields(RogueBalance)} == set(data)
    for f in fields(RogueBalance):
        if f.name in TABLES:
            header = re.search(rf"^((?:#.*\n)+)\[{f.name}[\].]", text, re.M)
            assert header, f"{f.name} : commentaire au-dessus de la table manquant"
        else:
            line = re.search(rf"^{f.name} = .*?#\s*(\S.*)$", text, re.M)
            assert line, f"{f.name} : commentaire manquant"


def write(tmp_path, body: str) -> Path:
    p = tmp_path / "rogue_balance.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_override_changes_only_named_keys(tmp_path):
    p = write(tmp_path, "hp_factor = 1.1\nwin_gold = 40\n\n[calendars]\n\"45\" = [8.0, 5, 3.0, 2.0, 10.0, [3.0, 4.0, 1.5], 5.0]\n"
                        "[reservoirs]\nthreshold = [\"diesel\", \"grimpeur\"]\n"
                        "[room_profiles.diesel.threshold]\nfw = 0.95\n")
    b = load_balance(p)
    assert b.hp_factor == 1.1 and b.win_gold == 40.0
    assert b.calendars[45][1] == 5 and b.calendars[30] == DEFAULT_BALANCE.calendars[30]
    assert b.reservoirs["threshold"] == ("diesel", "grimpeur")
    assert b.reservoirs["endurance"] == DEFAULT_BALANCE.reservoirs["endurance"]
    assert b.room_profiles["diesel"]["threshold"]["fw"] == 0.95
    assert b.room_profiles["diesel"]["threshold"]["g0"] == DEFAULT_BALANCE.room_profiles["diesel"]["threshold"]["g0"]
    assert b.room_profiles["diesel"]["endurance"] == DEFAULT_BALANCE.room_profiles["diesel"]["endurance"]
    assert DEFAULT_BALANCE.hp_factor == 0.9 and DEFAULT_BALANCE.room_profiles["diesel"]["threshold"]["fw"] == 0.90


@pytest.mark.parametrize("body, needle", [
    ("hp_facteur = 1.0\n", "hp_facteur : clé inconnue"),
    ("hp_factor = 50\n", "hp_factor : 50.0 hors bornes"),
    ("hp_factor = \"beaucoup\"\n", "hp_factor : un nombre est attendu"),
    ("gear_max = 12.5\n", "gear_max : un entier est attendu"),
    ("gear_max = 99\n", "gear_max : 99 hors bornes"),
    ("boss_phase_s = [1.0, 2.0]\n", "boss_phase_s : une liste de 3 éléments"),
    ("[calendars]\n\"50\" = [1.0]\n", "calendars.50 : clé inconnue"),
    ("[calendars]\n\"45\" = [1.0]\n", "calendars.45 : une liste de 7 éléments"),
    ("[reservoirs]\nthreshold = [\"dragon\"]\n", "reservoirs.threshold"),
    ("[reservoirs]\nsprint = [\"diesel\"]\n", "reservoirs.sprint : objectif inconnu"),
    ("[room_profiles.diesel.threshold]\nfoo = 1.0\n", "room_profiles.diesel.threshold.foo : clé inconnue"),
    ("[room_profiles.diesel.threshold]\nfw = 99999.0\n", "room_profiles.diesel.threshold.fw"),
    ("hp_factor = = 1\n", "TOML invalide"),
])
def test_bad_override_gives_readable_error(tmp_path, body, needle):
    with pytest.raises(BalanceError) as exc:
        load_balance(write(tmp_path, body))
    assert needle in str(exc.value)
    assert "rogue_balance.toml" in str(exc.value)


def test_bounds_allow_negative_grades_only_where_expected():
    assert apply_overrides(DEFAULT_BALANCE, {"room_grade_min": -5.0}).room_grade_min == -5.0
    with pytest.raises(BalanceError):
        apply_overrides(DEFAULT_BALANCE, {"win_gold": -1.0})


def test_hash_is_stable_short_and_follows_the_values():
    h = balance_hash(DEFAULT_BALANCE)
    assert re.fullmatch(r"[0-9a-f]{8}", h) and h == balance_hash(load_balance(NOWHERE))
    assert balance_hash(apply_overrides(DEFAULT_BALANCE, {"hp_factor": 1.0})) != h
    assert balance_hash(apply_overrides(DEFAULT_BALANCE, {"room_profiles": {"diesel": {"threshold": {"fw": 0.91}}}})) != h


def test_run_journal_notes_the_table_hash_once():
    rider = RoomRider(ftp_w=250.0, params=sim.PHYSICS)
    e = RunEngine(compose_run("threshold", 30, 1, rider), rider, 20000.0, 250.0)
    inp = RunInputs(power_w=150.0, cadence_rpm=85.0, gear=6, ftp_w=250.0)
    first = e.step(1.0, inp).journal
    second = e.step(1.0, inp).journal
    assert f"rogue balance hash={balance_hash(DEFAULT_BALANCE)}" in first
    assert not any("balance hash" in line for line in second)


def test_package_data_ships_the_table():
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert "rogue/*.toml" in pyproject


# --- outil de simulation -------------------------------------------------------------------------

def test_simulate_is_deterministic_and_complete():
    a = sim.simulate("threshold", 30, 5, sim.PROFILES["moyen"])
    b = sim.simulate("threshold", 30, 5, sim.PROFILES["moyen"])
    assert a == b and a["finished"] and a["rooms_total"] >= 2
    assert 0.3 < a["if"] < 1.2


def test_profiles_follow_the_cahier():
    p = sim.PROFILES
    assert (p["debutant"].ftp_w, p["debutant"].w_prime_j) == (150.0, 12000.0)
    assert (p["moyen"].ftp_w, p["moyen"].w_prime_j) == (250.0, 20000.0)
    assert (p["confirme"].ftp_w, p["confirme"].w_prime_j) == (330.0, 25000.0)
    assert p["fatigue"].fatigue_after_s == 1800.0 and p["fatigue"].ftp_w == 250.0


def test_fatigue_profile_loses_power_after_thirty_minutes():
    moyen = sim.simulate("endurance", 45, 3, sim.PROFILES["moyen"])
    tired = sim.simulate("endurance", 45, 3, sim.PROFILES["fatigue"])
    assert tired["if"] < moyen["if"]


def test_batch_report_is_identical_with_one_or_two_jobs():
    one = sim.run_batch("endurance", 30, 4, 7, "moyen", DEFAULT_BALANCE, jobs=1)
    two = sim.run_batch("endurance", 30, 4, 7, "moyen", DEFAULT_BALANCE, jobs=2)
    assert one == two and one["runs"] == 4


def test_targets_listed_with_measure_and_range():
    report = sim.build_report("vo2max", 30, 4, 1, ["debutant", "moyen", "confirme"], DEFAULT_BALANCE, 1, False, 0)
    labels = [t["label"] for t in report["targets"]]
    assert any("Boss battu" in x for x in labels) and any("Écart" in x for x in labels)
    assert any("1,10 FTP" in x for x in labels)
    assert all(set(t) >= {"label", "value", "low", "high", "ok"} for t in report["targets"])
    text = sim.format_report(report)
    assert "Cibles :" in text and report["balance_hash"] in text


def test_sensitivity_names_constants_for_missed_targets():
    targets = [{"label": "Salles gagnées, Moyen (%)", "key": "rooms_won_pct", "profile": "moyen", "ok": False},
               {"label": "déjà tenue", "key": "defeats", "profile": "moyen", "ok": True}]
    out = sim.sensitivity("threshold", 30, 4, 1, DEFAULT_BALANCE, targets, 1, constants=["hp_factor", "win_gold"])
    assert list(out) == ["Salles gagnées, Moyen (%)"]
    rows = out["Salles gagnées, Moyen (%)"]
    assert rows[0]["constant"] == "hp_factor" and rows[0]["value"] == 0.9   # win_gold ne change pas le taux de victoire
    assert all(set(r) == {"constant", "value", "minus20", "plus20"} for r in rows)


def test_cli_writes_text_and_json(tmp_path, capsys):
    out = tmp_path / "rapport.json"
    rc = sim.main(["--objective", "endurance", "--duration", "30", "--runs", "3", "--profiles", "moyen",
                   "--json", str(out)])
    assert rc == 0
    assert "Cyber-Rogue : endurance, 30 min" in capsys.readouterr().out
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["objective"] == "endurance" and "moyen" in data["profiles"]


def test_cli_refuses_unknown_profile_and_bad_table(tmp_path, capsys):
    assert sim.main(["--profiles", "dieu", "--runs", "1"]) == 2
    assert sim.main(["--runs", "1", "--balance", str(tmp_path / "absent.toml")]) == 2
    bad = tmp_path / "bad.toml"
    bad.write_text("hp_factor = 99\n", encoding="utf-8")
    assert sim.main(["--runs", "1", "--balance", str(bad)]) == 2
    assert "hp_factor" in capsys.readouterr().err
