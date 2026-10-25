"""Lot N12 : appairage côté core, matériel trouvé écrit dans la configuration locale.

Adresses simulées uniquement (`C1:1C:00:00:00:0x`, trainer et ceinture du Bluetooth simulé).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from openride_core import config as config_mod
from openride_core import pairing
from openride_core.__main__ import main
from openride_core.config import Config, ConfigError
from openride_core.mock_driver import MockDriver
from openride_core.input_providers import NullProvider
from openride_core.pairing import PairedDevices, PairingError
from openride_core.session import CoreSession
from openride_core.sim_scenarios import MINUS_ADDRESS, PLUS_ADDRESS
from openride_core.tools import devices

START = """# Ma configuration (commentaire gardé)
[rider]
ftp_w = 210   # FTP de test
mass_kg = 70

[drivers]
trainer = "ftms"
cle_inconnue = "garde-moi"
click_address = ""   # rempli par devices --save

[render]
quality = "low"
"""


def run_save(capsys, cfg: Path, *extra: str) -> tuple[int, str]:
    code = main(["devices", "--sim-scenario", "demo", "--timeout", "1.0", "--save", "--yes",
                 "--config", str(cfg), *extra])
    return code, capsys.readouterr().out


def test_demo_save_writes_devices_then_nothing_changes(tmp_path: Path, capsys):
    """Critère 2 : trainer, deux boîtiers et ceinture écrits ; un second appel ne change rien."""
    cfg = tmp_path / "config.toml"
    code, out = run_save(capsys, cfg)
    assert code == 0, out
    data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    d = data["drivers"]
    assert {d["click_address"], d["click_minus_address"]} == {PLUS_ADDRESS, MINUS_ADDRESS}
    assert d["trainer_address"] and d["hr_address"] and d["hr_name"]
    assert data["trainer"]["device_name"].startswith("HomeTrainer")
    loaded = config_mod.load(cfg)
    assert loaded.drivers.click_minus_address == d["click_minus_address"]

    code, out = run_save(capsys, cfg)
    assert code == 0 and "Aucun changement" in out


def test_comments_sections_and_unknown_keys_are_kept(tmp_path: Path):
    """Critère 3 : seules les clés d'appareils changent ; `.bak` contient l'ancien fichier."""
    cfg = tmp_path / "config.toml"
    cfg.write_text(START, encoding="utf-8")
    paired = PairedDevices(trainer_name="HomeTrainer 0001", trainer_address="C1:1C:00:00:00:10",
                           click_plus_address=PLUS_ADDRESS, click_minus_address=MINUS_ADDRESS)
    changed = pairing.save(paired, cfg)
    assert len(changed) == 4
    new = cfg.read_text(encoding="utf-8")
    assert (tmp_path / "config.toml.bak").read_text(encoding="utf-8") == START
    for keep in ("# Ma configuration (commentaire gardé)", "ftp_w = 210   # FTP de test",
                 'cle_inconnue = "garde-moi"', '[render]\nquality = "low"'):
        assert keep in new
    assert f'click_address = "{PLUS_ADDRESS}"   # rempli par devices --save' in new
    old_lines = [ln for ln in START.splitlines() if "click_address" not in ln]
    new_lines = new.splitlines()
    assert all(ln in new_lines for ln in old_lines)
    data = tomllib.loads(new)
    assert data["drivers"]["trainer_address"] == "C1:1C:00:00:00:10"
    assert data["trainer"]["device_name"] == "HomeTrainer 0001"


def test_invalid_address_writes_nothing(tmp_path: Path, capsys, monkeypatch):
    """Critère 4 : adresse mal formée, aucune écriture, message clair, code non nul."""
    cfg = tmp_path / "config.toml"
    cfg.write_text(START, encoding="utf-8")
    with pytest.raises(PairingError, match="mal formée"):
        pairing.save(PairedDevices(trainer_address="pas-une-adresse"), cfg)
    assert cfg.read_text(encoding="utf-8") == START
    assert not (tmp_path / "config.toml.bak").exists()

    monkeypatch.setattr(pairing, "from_inventory", lambda inv, plus=None: PairedDevices(hr_address="ZZ"))
    code = main(["devices", "--sim-scenario", "demo", "--timeout", "1.0", "--save", "--yes",
                 "--config", str(cfg)])
    err = capsys.readouterr().err
    assert code == 1 and "mal formée" in err
    assert cfg.read_text(encoding="utf-8") == START


def test_config_rejects_malformed_address(tmp_path: Path):
    with pytest.raises(ConfigError, match="click_minus_address"):
        config_mod.from_dict({"drivers": {"click_minus_address": "C1:1C:00"}})
    assert config_mod.from_dict({"drivers": {"hr_address": "c1:1c:00:00:00:0a"}}).drivers.hr_address


def test_plus_press_on_second_box_goes_to_click_address(tmp_path: Path, capsys):
    """Critère 5 : appui « + » sur le second boîtier trouvé : c'est lui le « + »."""
    cfg = tmp_path / "config.toml"
    seen: list[list[str]] = []

    async def waiter(addresses: list[str], timeout: float) -> str:
        seen.append(addresses)
        return addresses[1]

    code = devices.run(1.0, config_path=cfg, sim_scenario="demo", save=True, assume_yes=True,
                       plus_waiter=waiter)
    assert code == 0
    out = capsys.readouterr().out
    assert "Appuyez sur le bouton + du Click" in out
    d = tomllib.loads(cfg.read_text(encoding="utf-8"))["drivers"]
    assert d["click_address"] == seen[0][1] and d["click_minus_address"] == seen[0][0]


def test_no_press_keeps_search_order_and_says_so(tmp_path: Path, capsys):
    cfg = tmp_path / "config.toml"

    async def waiter(addresses: list[str], timeout: float) -> None:
        return None

    assert devices.run(1.0, config_path=cfg, sim_scenario="demo", save=True, assume_yes=True,
                       plus_waiter=waiter) == 0
    assert "Aucun appui reçu" in capsys.readouterr().out


def test_confirmation_refused_writes_nothing(tmp_path: Path, capsys):
    cfg = tmp_path / "config.toml"
    result = {"devices": [{"role": "trainer", "name": "HomeTrainer 0001",
                           "address": "C1:1C:00:00:00:10", "rssi": -50}], "connected": []}
    assert devices.save_devices(result, cfg, False, None, ask=lambda q: "n") == 1
    assert not cfg.exists()
    assert devices.save_devices(result, cfg, False, None, ask=lambda q: "o") == 0
    assert "C1:1C:00:00:00:10" in cfg.read_text(encoding="utf-8")


def test_from_inventory_prefers_strap_and_best_trainer():
    inv = {"devices": [
        {"role": "trainer", "name": "HomeTrainer A", "address": "c1:1c:00:00:00:11", "rssi": -80},
        {"role": "trainer", "name": "HomeTrainer B", "address": "C1:1C:00:00:00:12", "rssi": -40},
        {"role": "hr_watch", "name": "Montre", "address": "C1:1C:00:00:00:21", "rssi": -30},
        {"role": "hr_strap", "name": "Ceinture", "address": "C1:1C:00:00:00:22", "rssi": -70},
        {"role": "click", "name": "Click", "address": PLUS_ADDRESS, "rssi": -60},
    ], "connected": []}
    p = pairing.from_inventory(inv)
    assert (p.trainer_name, p.trainer_address) == ("HomeTrainer B", "C1:1C:00:00:00:12")
    assert (p.hr_name, p.hr_address) == ("Ceinture", "C1:1C:00:00:00:22")
    assert p.click_plus_address == PLUS_ADDRESS and p.click_minus_address == ""


def test_session_click_device_follows_configured_plus(tmp_path: Path):
    """Critère 6 : `click_address` différent de l'adresse simulée du « + »."""
    cfg = Config()
    cfg.drivers.input = "click"
    cfg.drivers.click_address = MINUS_ADDRESS   # ici, le « + » est l'autre boîtier
    s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()], journal_dir=tmp_path / "j",
                    routes_root=tmp_path / "r")
    assert s._click_device(MINUS_ADDRESS.lower()) == "click_plus"
    assert s._click_device(PLUS_ADDRESS) == "click_minus"

    cfg2 = Config()
    cfg2.drivers.input = "click"   # rien de configuré : premier vu = « + »
    s2 = CoreSession(cfg2, driver=MockDriver(), inputs=[NullProvider()], journal_dir=tmp_path / "j",
                     routes_root=tmp_path / "r")
    assert s2._click_device("C1:1C:00:00:00:05") == "click_plus"
    assert s2._click_device("C1:1C:00:00:00:06") == "click_minus"
    assert s2._click_device("C1:1C:00:00:00:05") == "click_plus"


def test_log_scenario_uses_configured_plus():
    from openride_core.tools.log_scenario import _box

    assert _box(MINUS_ADDRESS, None, plus=MINUS_ADDRESS) == "click_plus"
    assert _box(PLUS_ADDRESS, None, plus=MINUS_ADDRESS) == "click_minus"
    assert _box(PLUS_ADDRESS, None) == "click_plus"
