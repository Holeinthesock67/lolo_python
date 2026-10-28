"""Persistance des réglages (lot X37) : chaque réglage de `settings.SETTINGS`, changé par l'IPC ou depuis la
pause, survit à l'arrêt du core et à sa relance sur le même `config.toml`.

La liste est lue dans `settings.py`, pas recopiée : un réglage ajouté plus tard est couvert sans retouche.
"""

from __future__ import annotations

from pathlib import Path

from openride_core import config as config_mod
from openride_core import config_edit, settings
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession


def _session(tmp_path: Path, path: Path) -> tuple[CoreSession, list[dict], list[tuple[str, str]]]:
    """Core « relancé » : configuration relue dans `path`, comme au démarrage."""
    s = CoreSession(config_mod.load(path), driver=MockDriver(), inputs=[NullProvider()],
                    journal_dir=tmp_path / "j", routes_root=tmp_path / "routes", config_path=path)
    sent: list[dict] = []
    errors: list[tuple[str, str]] = []
    s.server.send_raw = lambda m, max_size=None: sent.append(m)
    s.server.send_error = lambda code, msg: errors.append((code, msg))
    return s, sent, errors


def other_value(item: dict):
    """Valeur permise différente de la valeur actuelle : choix suivant, ou un pas plus haut (plus bas en butée)."""
    if item["type"] == "choice":
        ch = item["choices"]
        others = [c for c in ch if c != item["value"]]
        return others[0] if others else None
    up = item["value"] + item["step"]
    return up if up <= item["max"] else item["value"] - item["step"]


def lost_settings(tmp_path: Path) -> tuple[list[str], dict]:
    """Réglages dont la valeur changée n'est pas relue après relance ; et les valeurs choisies."""
    path = tmp_path / "config.toml"
    path.write_text("# configuration de l'essai\n", encoding="utf-8")
    s, sent, errors = _session(tmp_path, path)
    s._on_command("list_settings", {}, 1)
    wanted = {}
    for k, item in enumerate(sent[-1]["items"], start=2):
        value = other_value(item)
        if value is None:            # un seul choix possible (thème sans pack installé) : rien à changer
            continue
        s._on_command("set_setting", {"key": item["key"], "value": value}, k)
        assert not errors, errors
        wanted[item["key"]] = value
    s2, sent2, _ = _session(tmp_path, path)
    s2._on_command("list_settings", {}, 99)
    got = {it["key"]: it["value"] for it in sent2[-1]["items"]}
    return [k for k, v in wanted.items() if got.get(k) != v], wanted


def test_every_setting_survives_a_restart(tmp_path: Path):
    lost, wanted = lost_settings(tmp_path)
    assert lost == [], f"réglages non relus après relance : {lost}"
    assert set(wanted) >= set(settings.KEYS) - {"render.theme"}   # tous changés, sauf un thème sans choix


def test_difficulty_from_pause_survives_a_restart(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text("[rider]\nftp_w = 250\n", encoding="utf-8")
    s, _, errors = _session(tmp_path, path)
    s.state.session_state = "PAUSED"                       # écran de pause d'une séance
    s._on_command("set_difficulty", {"pct": 30}, 1)
    assert not errors
    s2, sent, _ = _session(tmp_path, path)
    assert s2.difficulty_pct == 30.0
    s2._on_command("list_settings", {}, 2)
    assert {it["key"]: it["value"] for it in sent[-1]["items"]}["trainer.difficulty_pct"] == 30


def test_a_setting_not_written_is_named(tmp_path: Path, monkeypatch):
    """Critère 1 : un réglage volontairement non écrit dans config.toml fait échouer le contrôle en le nommant."""
    real = config_edit.update_config

    def forgetful(path, values):
        return real(path, [v for v in values if (v[0], v[1]) != ("audio", "events_pct")])

    monkeypatch.setattr(config_edit, "update_config", forgetful)
    lost, _ = lost_settings(tmp_path)
    assert lost == ["audio.events_pct"]
