"""Validation de `config.toml` : types, bornes, clés inconnues, erreurs lisibles (lot J3)."""

from __future__ import annotations

import logging
import re
import tomllib
from pathlib import Path

import pytest

from openride_core import __main__ as cli
from openride_core.config import BOUNDS, CHOICES, Config, ConfigError, from_dict, load

SRS_PATH = Path(__file__).resolve().parents[2] / "docs" / "SRS_v1.1.md"


def _with(section: str, key: str, value) -> dict:
    return {section: {key: value}}


@pytest.mark.parametrize("section,key", sorted(BOUNDS))
def test_each_bound_rejects_just_outside(section: str, key: str) -> None:
    lo, hi = BOUNDS[(section, key)]
    current = getattr(getattr(Config(), section), key)
    step = 1 if isinstance(current, int) else 1e-6 * max(1.0, abs(hi))
    for bad in (lo - step, hi + step):
        with pytest.raises(ConfigError) as exc:
            from_dict(_with(section, key, bad))
        assert f"[{section}] {key}" in str(exc.value)


@pytest.mark.parametrize("section,key", sorted(BOUNDS))
def test_each_bound_accepts_inside(section: str, key: str) -> None:
    """La valeur par défaut est dans les bornes (les cohérences croisées sont testées à part)."""
    lo, hi = BOUNDS[(section, key)]
    current = getattr(getattr(Config(), section), key)
    assert lo <= current <= hi
    from_dict(_with(section, key, current))


@pytest.mark.parametrize("section,key", sorted(CHOICES))
def test_choices(section: str, key: str) -> None:
    for ok in CHOICES[(section, key)]:
        from_dict(_with(section, key, ok))
    with pytest.raises(ConfigError, match=re.escape(f"[{section}] {key}")):
        from_dict(_with(section, key, "inconnu"))


@pytest.mark.parametrize("data,where", [
    ({"rider": {"ftp_w": "abc"}}, "[rider] ftp_w"),
    ({"rider": {"ftp_w": True}}, "[rider] ftp_w"),
    ({"gearing": {"n_gears": 12.5}}, "[gearing] n_gears"),
    ({"drivers": {"trainer": 3}}, "[drivers] trainer"),
    ({"rider": 250}, "[rider]"),
    ({"gearing": {"start_gear": 30}}, "[gearing] start_gear"),
    ({"gearing": {"ratio_min": 2.0, "ratio_max": 1.0}}, "[gearing] ratio_min"),
    ({"trainer": {"grade_min_pct": 0.0, "grade_max_pct": 0.0}}, "[trainer] grade_min_pct"),
    ({"ipc": {"port_state": 6000, "port_commands": 6000}}, "[ipc] port_commands"),
])
def test_invalid_values_name_section_and_key(data: dict, where: str) -> None:
    with pytest.raises(ConfigError) as exc:
        from_dict(data)
    assert where in str(exc.value)


def test_int_written_as_float_is_accepted() -> None:
    assert from_dict({"gearing": {"n_gears": 20.0, "start_gear": 10}}).gearing.n_gears == 20


def test_toml_syntax_error_gives_line(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text("[rider]\nftp_w = 250\nmass_kg = = 70\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load(f)
    assert "line 3" in str(exc.value) and str(f) in str(exc.value)


def test_unknown_key_warns_and_loads(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="config"):
        cfg = from_dict({"rider": {"ftp": 260}, "riderr": {}})
    assert cfg.rider.ftp_w == 250.0
    assert "[rider] ftp" in caplog.text and "[riderr]" in caplog.text


def test_srs_example_loads_without_warning(caplog: pytest.LogCaptureFixture) -> None:
    text = SRS_PATH.read_text(encoding="utf-8")
    after = text[re.search(r"^## 11\..*$", text, flags=re.MULTILINE).end():]
    block = re.search(r"```toml\r?\n(.*?)```", after, flags=re.DOTALL).group(1)
    with caplog.at_level(logging.WARNING, logger="config"):
        from_dict(tomllib.loads(block))
    assert caplog.records == []


def test_run_with_invalid_config_returns_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[rider]\nftp_w = "abc"\n', encoding="utf-8")
    assert cli.main(["run", "--config", str(f), "--trainer", "mock", "--input", "none"]) == 1
    assert "[rider] ftp_w" in capsys.readouterr().err


@pytest.mark.parametrize("gear", ["0", "99"])
def test_run_with_gear_out_of_range_returns_2(gear: str, tmp_path: Path,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["run", "--config", str(tmp_path / "absent.toml"), "--gear", gear,
                     "--trainer", "mock", "--input", "none"]) == 2
    assert "--gear" in capsys.readouterr().err


def test_release_trainer_with_invalid_config_returns_1(tmp_path: Path,
                                                      capsys: pytest.CaptureFixture[str]) -> None:
    """`release-trainer` (PR #28) lit la même configuration : même message, sans trace."""
    f = tmp_path / "config.toml"
    f.write_text("[ipc]\nport_state = 80\n", encoding="utf-8")
    assert cli.main(["release-trainer", "--config", str(f)]) == 1
    assert "[ipc] port_state" in capsys.readouterr().err


def test_open_world_section_lot_w2() -> None:
    """Section [open_world] (lot W2) : valeurs par défaut, cohérences croisées, types."""
    ow = Config().open_world
    assert (ow.cache_max_gb, ow.horizon_m, ow.offer_m, ow.lock_m, ow.preview_m) == (5.0, 3000.0, 300.0, 30.0, 500.0)
    assert from_dict({"open_world": {"cache_max_gb": 20, "network": False}}).open_world.network is False
    for bad, key in (({"lock_m": 300.0}, "lock_m"), ({"preview_m": 2000.0, "horizon_m": 1500.0}, "preview_m"),
                     ({"cache_dir": "  "}, "cache_dir"), ({"cache_max_gb": -1}, "cache_max_gb")):
        with pytest.raises(ConfigError, match=rf"\[open_world\] {key}"):
            from_dict({"open_world": bad})
    with pytest.raises(ConfigError, match="booléen"):
        from_dict({"open_world": {"network": "oui"}})
