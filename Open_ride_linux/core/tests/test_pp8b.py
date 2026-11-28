"""Lot PP8b : intervalles calés sur ton meilleur 1 min ou 5 min, courbe avant et après un plan. Séances fabriquées,
cycliste fictif à FTP 250 W, aucune donnée réelle."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from test_power_curve import DAY, LIVE, NOW, write_journal

from openride_core import ipc_lists, workout_menu
from openride_core.tools import power_curve as pc

ARGS = {"warmup_min": 10, "reps": 6, "on_s": 60, "on_pct": 95, "off_s": 120, "off_pct": 50, "cooldown_min": 5}


def test_interval_on_your_best_minute_is_written_in_watts_and_ftp_percent(tmp_path):
    seen = []

    def best_of(seconds):
        seen.append(seconds)
        return 360.0, 250.0                     # meilleur 1 min fictif, FTP fictive

    res = workout_menu.create_interval_workout(tmp_path, dict(ARGS, on_ref="best_60"), best_of)
    assert seen == [60] and res["target_w"] == 342 and res["created"]
    assert res["name"] == "Intervalles 6 × 1 min à 342 W (95 % de ton 1 min)"
    assert res["workout_id"] == "intervalles_6x60s_137"        # 342 W = 137 % de 250 W
    text = (tmp_path / "intervalles_6x60s_137.zwo").read_text(encoding="utf-8")
    assert 'OnPower="1.37"' in text and "342 W" in text
    again = workout_menu.create_interval_workout(tmp_path, dict(ARGS, on_ref="best_60"), best_of)
    assert again["workout_id"] == res["workout_id"] and not again["created"]


def test_five_minute_base_and_ftp_default_unchanged(tmp_path):
    res = workout_menu.create_interval_workout(tmp_path, dict(ARGS, on_ref="best_300", on_s=300, on_pct=100),
                                               lambda s: (300.0, 250.0))
    assert res["target_w"] == 300 and res["name"].endswith("(100 % de ton 5 min)")
    plain = workout_menu.create_interval_workout(tmp_path, ARGS)
    assert plain == {"workout_id": "intervalles_6x60s_95", "name": "Intervalles 6 × 1 min à 95 %", "created": True}
    assert workout_menu.create_interval_workout(tmp_path, dict(ARGS, on_ref="ftp"))["workout_id"] == plain["workout_id"]


@pytest.mark.parametrize("bad", [{"on_ref": "best_20"}, {"on_ref": "best_60", "on_pct": 130},
                                 {"on_ref": "best_60", "on_pct": True}, {"on_ref": "best_60", "on_pct": 40}])
def test_bad_reference_refused(tmp_path, bad):
    with pytest.raises(workout_menu.WorkoutMenuError) as exc:
        workout_menu.create_interval_workout(tmp_path, dict(ARGS, **bad), lambda s: (360.0, 250.0))
    assert exc.value.code == "bad_args"
    assert not list(tmp_path.iterdir())


def test_ftp_target_clamped_to_interval_bounds(tmp_path):
    res = workout_menu.create_interval_workout(tmp_path, dict(ARGS, on_ref="best_60", on_pct=120),
                                               lambda s: (900.0, 250.0))
    assert res["workout_id"].endswith("_200") and res["target_w"] == 500   # 200 % de la FTP au plus


def test_plan_curve_before_and_after(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    start = NOW - 30 * DAY
    write_journal(j, "avant", start - 20 * DAY, [(300, 280.0)])
    write_journal(j, "tres_vieux", start - 300 * DAY, [(300, 400.0)])        # hors des 6 mois d'avant
    write_journal(j, "pendant", NOW - 2 * DAY, [(300, 300.0), (60, 200.0)])
    kept = pc.kept_sessions(pc.session_entries(tmp_path / "Activities", tmp_path / "c.json"), LIVE)
    change = {c["s"]: c for c in pc.plan_curve_change(kept, start)}
    assert change[300] == {"s": 300, "before": 280, "after": 300}
    assert change[60]["after"] == 300 and change[60]["before"] == 280       # 1 min dans le bloc de 5 min
    assert 5 in change and 1200 not in change                                # pas de 20 min depuis le début


def test_plans_message_carries_the_curve(tmp_path, monkeypatch):
    from openride_core.tools import history

    monkeypatch.setattr(history, "CACHE_PATH", tmp_path / "history-cache.json")   # séances faites du plan
    w = tmp_path / "Workouts"
    w.mkdir()
    (w / "ss.zwo").write_text('<workout_file><name>SS</name><workout><SteadyState Duration="600" Power="0.9"/>'
                              "</workout></workout_file>")
    plans_dir = tmp_path / "Plans"
    plans_dir.mkdir()
    (plans_dir / "essai.toml").write_text('[plan]\nname = "Essai"\ndays_per_week = 1\n'
                                          '[[week]]\ndays = [ { day = "jour1", workout = "ss" } ]\n')
    state = tmp_path / "plan_state.toml"
    start = date.fromtimestamp(NOW - 10 * DAY)
    state.write_text(f'[active]\nplan = "essai"\nstart = "{start.isoformat()}"\n')
    act = tmp_path / "Activities"
    start_ts = datetime.combine(start, datetime.min.time()).timestamp()
    write_journal(act / ".journal", "pendant", start_ts + DAY, [(300, 260.0)])
    msg = ipc_lists.build_plans_message(1, 250.0, plans_dir, w, state, act, date.fromtimestamp(NOW),
                                        tmp_path / "c.json", LIVE)
    assert msg["active"] is not None and {"s": 300, "before": None, "after": 260} in msg["active"]["curve"]
    plain = ipc_lists.build_plans_message(1, 250.0, plans_dir, w, state, act, date.fromtimestamp(NOW))
    assert "curve" not in plain["active"]


def test_best_effort_over_six_months(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    write_journal(j, "recent", NOW - 10 * DAY, [(60, 330.0)])
    write_journal(j, "vieux", NOW - 300 * DAY, [(60, 450.0)])                 # hors des 6 mois
    act, cache = tmp_path / "Activities", tmp_path / "c.json"
    assert ipc_lists.best_effort_w(act, cache, LIVE, 60, NOW) == 330
    assert ipc_lists.best_effort_w(act, cache, LIVE, 1200, NOW) is None
