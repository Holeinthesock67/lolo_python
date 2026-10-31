"""Lot X51 : partie automatique de la recette du Cyber-Rogue (outil `rogue_recette`, fiche R14)."""

from __future__ import annotations

import pytest

from openride_core.rogue import firewall as firewall_mod
from openride_core.rogue import mode as rogue_mode
from openride_core.tools import rogue_recette as tool

pytest.importorskip("garmin_fit_sdk")


def failed(rep) -> list[str]:
    return [f"{label} : {detail}" for ok, label, detail in rep.checks if ok is False]


def test_calendar_runs_hold_if_schedule_and_fit():
    reps = tool.essai_calendrier(5, "moyen")
    assert [r.objective for r in reps] == ["endurance", "threshold", "vo2max"]
    for rep in reps:
        assert rep.ok, (rep.objective, failed(rep))
        assert rep.summary["result"] in ("victory", "defeat")


@pytest.mark.parametrize("essai", ["abandon", "click", "plantage"])
def test_incident_scenarios_pass(essai):
    rep = tool.run(essai)[0]
    assert rep.ok, failed(rep)
    assert rep.wall_s < 30.0


def test_abandon_gives_abandoned_summary():
    rep = tool.essai_abandon(5, "moyen")
    assert rep.summary["result"] == "abandoned"


def test_firewall_running_without_click_is_caught(monkeypatch):
    """Le Firewall qui roule pendant la coupure du Click doit faire échouer l'essai."""
    step = firewall_mod.Firewall.step

    def ignore_loss(self, dt, player_s, paused=False, input_lost=False):
        return step(self, dt, player_s, paused=paused, input_lost=False)
    monkeypatch.setattr(firewall_mod.Firewall, "step", ignore_loss)
    rep = tool.essai_click(5, "moyen")
    assert [f.split(" : ")[0] for f in failed(rep)] == ["Firewall arrêté pendant la coupure"]


def test_resume_at_wrong_phase_is_caught(monkeypatch):
    """Une reprise qui ne remet pas la salle à son début doit faire échouer l'essai."""
    restore = rogue_mode.RogueMode.restore

    def late(self, line):
        restore(self, line)
        self.engine.t_phase = 42.0
    monkeypatch.setattr(rogue_mode.RogueMode, "restore", late)
    rep = tool.essai_plantage(5, "moyen")
    assert "reprise au début de la salle en cours" in [f.split(" : ")[0] for f in failed(rep)]


def test_unknown_essai_or_profile_is_refused(capsys):
    assert tool.main(["--essai", "inconnu"]) == 2
    assert tool.main(["--profil", "pro"]) == 2
