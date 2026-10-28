"""Lot X42 : matrice des boutons et des réglages, par mode et par phase (outil `matrice_boutons`)."""

from __future__ import annotations

import json

import pytest

from openride_core import session as session_mod
from openride_core.rogue import mode as rogue_mode
from openride_core.tools import matrice_boutons as tool
from openride_core.zwift_click import InputEvent


def failed(rep: tool.Report) -> list[str]:
    return [f"{c.mode} · {c.phase} · {c.event} : {c.detail}" for c in rep.cells if c.ok is not True] + \
        [f"{c.key} · {c.phase} : {c.detail}" for c in rep.settings if not c.ok]


def test_plan_is_read_from_the_specification():
    plan = tool.read_plan()
    assert len(plan) == len(InputEvent) * len(tool.COLUMNS)
    assert plan[(InputEvent.PLUS_LONG, "SIM")] == ("Braquet ± 10", 1)
    assert plan[(InputEvent.MINUS_SHORT, "ERG")][1] == -1
    assert plan[(InputEvent.UP_SHORT, "ERG")] == plan[(InputEvent.UP_SHORT, "SIM")]      # « idem »
    assert tool.expect_of(*plan[(InputEvent.Z_SHORT, "ERG")], "ERG") == tool.Expect("block")
    assert tool.expect_of("Biais ± 2 % ; braquet ± 1 en roue libre", -1, "ERG", freeride=True) == tool.Expect("gear", -1)
    assert tool.expect_of("Une action inventée", 1, "SIM") is None                     # case non décrite


def test_unreadable_plan_is_named(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Rien\n\n### 7.2 Autre\n", "utf-8")
    with pytest.raises(tool.MatrixError, match="7.1"):
        tool.read_plan(spec)


@pytest.mark.parametrize("modes", [("sim", "erg"), ("rogue",), ("monde",)])
def test_every_button_in_every_phase_follows_the_plan(modes):
    rep = tool.run("boutons", modes)
    assert rep.cells and not failed(rep), failed(rep)
    phases = {c.phase for c in rep.cells}
    assert {"pause", "bilan"} <= phases or modes == ("monde",)
    if "erg" in modes:
        assert {"roue libre", "dernier bloc", "fin de l'entraînement"} <= phases
    if "rogue" in modes:
        assert {"échauffement", "salle", "couloir, carte choisie", "boss", "retour au calme", "résultats"} <= phases


def test_every_setting_in_every_phase():
    rep = tool.run("reglages")
    assert len(rep.settings) == 6 * len(tool.settings_mod.SETTINGS)
    assert not failed(rep), failed(rep)


def test_arrows_ignored_in_the_corridor_are_caught(monkeypatch):
    """Défaut trouvé par l'outil : les flèches ne choisissaient pas la carte du couloir (§7.1)."""
    monkeypatch.setattr(rogue_mode, "GAME_BUTTONS", ("Z_SHORT", "Z_LONG", "A_SHORT", "A_LONG"))
    rep = tool.run("boutons", ("rogue",))
    bad = {(c.phase, c.event) for c in rep.cells if c.ok is False}
    assert ("couloir, carte choisie", "LEFT_SHORT") in bad and ("couloir, carte choisie", "RIGHT_SHORT") in bad


def test_wind_not_rebuilt_and_view_refused_in_session_are_caught(monkeypatch):
    """Défauts trouvés par l'outil : vent réglé jamais appliqué sans relancer, vue de caméra refusée en route."""
    build = session_mod.CoreSession._build_wind
    monkeypatch.setattr(session_mod.CoreSession, "_build_wind",
                        lambda self: None if hasattr(self, "wind") else build(self))   # vent du lancement seulement
    original = session_mod.CoreSession._set_setting

    def busy_in_session(self, args, cmd_id):
        if self.state.session_state in ("RUNNING", "PAUSED"):
            self.server.send_error("busy", "Réglage impossible pendant une séance (terminer d'abord).")
            return
        original(self, args, cmd_id)
    monkeypatch.setattr(session_mod.CoreSession, "_set_setting", busy_in_session)
    rep = tool.run("reglages")
    bad = {(c.phase, c.key) for c in rep.settings if not c.ok}
    assert ("accueil", "wind.mode") in bad and ("en route", "render.camera") in bad
    assert ("pause", "audio.master_pct") in bad and ("en route", "rider.ftp_w") not in bad


def test_bad_call_and_exit_codes(capsys):
    with pytest.raises(tool.MatrixError, match="mode"):
        tool.run("boutons", ("course",))
    assert tool.main(["--partie", "rien"]) == 2
    assert tool.main(["--partie", "boutons", "--mode", "sim", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and len(out["boutons"]) == len(InputEvent) * len(out["phases"])
