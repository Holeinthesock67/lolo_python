"""Lot TT1 : contrat IPC 1.13 des bonus tactiques (valeurs, champ `refused`, réglage à trois choix)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from openride_core import config as config_mod
from openride_core import ipc_budget, settings

STATE = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc" / "state.schema.json"
TACTICAL = ("feather", "anvil", "draft_plus", "aero", "power", "breakaway", "roller")
REASONS = ("no_bots", "no_descent", "near_finish", "no_gravel", "erg")


def powerup_schema() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8"))["properties"]["powerup"]


def errors(pu: dict) -> list[str]:
    return [e.message for e in jsonschema.Draft202012Validator(powerup_schema()).iter_errors(pu)]


@pytest.mark.parametrize("kind", [*TACTICAL, "light"])
def test_every_kind_is_valid_in_held_and_active(kind):
    assert errors({"held": kind, "active": kind, "remaining_s": 3.0}) == []


@pytest.mark.parametrize("reason", REASONS)
def test_refused_reasons(reason):
    assert errors({"held": "anvil", "active": None, "remaining_s": 0.0,
                   "refused": {"kind": "anvil", "reason": reason}}) == []


def test_refused_rejects_unknown_reason_and_missing_kind():
    assert errors({"held": None, "active": None, "remaining_s": 0.0, "refused": {"kind": "anvil", "reason": "x"}})
    assert errors({"held": None, "active": None, "remaining_s": 0.0, "refused": {"reason": "erg"}})
    assert errors({"held": "lightweight", "active": None, "remaining_s": 0.0})   # nom interne, jamais au contrat


def test_mode_has_three_choices_classiques_by_default():
    assert config_mod.CHOICES[("powerups", "mode")] == ("off", "classiques", "tactiques")
    assert config_mod.Config().powerups.mode == "classiques"
    assert settings.choices(settings.get("powerups.mode")) == ["off", "classiques", "tactiques"]


def test_old_on_value_reads_as_classiques():
    cfg = config_mod.from_dict({"powerups": {"mode": "on"}})
    assert cfg.powerups.mode == "classiques"
    assert config_mod.from_dict({"powerups": {"mode": "off"}}).powerups.mode == "off"
    with pytest.raises(config_mod.ConfigError):
        config_mod.from_dict({"powerups": {"mode": "oui"}})


def test_worst_frame_1_13_fits_and_validates():
    """La pire trame 1.13 (piste de la 1.7, sans bonus) et la pire trame avec bonus (peloton de la 1.6, qui porte
    `devices`) avec la réserve, le bonus actif et le refus les plus longs : valides et sous la limite."""
    validator = jsonschema.Draft202012Validator(json.loads(STATE.read_text(encoding="utf-8")))
    with_bonus = ipc_budget.worst_peloton_devices()
    ipc_budget._extras_1_13(with_bonus)
    assert "refused" in with_bonus["powerup"]
    for frame in (ipc_budget.worst_state("1.13"), with_bonus):
        assert [e.message for e in validator.iter_errors(frame)] == []
        assert ipc_budget.size(frame) <= ipc_budget.state_limit("1.13")
