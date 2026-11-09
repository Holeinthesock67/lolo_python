"""Lot P33 : vent d'après la météo du jour (Open-Meteo), lu par le lanceur, repli sans vent hors ligne.

Aucun accès réseau : réponses simulées et serveur local muet. Positions de test : parcours de
démonstration (Alpes, 45,09 / 6,06), jamais une position réelle d'un joueur.
"""

from __future__ import annotations

import io
import json
import socket
import threading
import time
import urllib.error
from pathlib import Path

import pytest

from openride_core import fit_export, local_weather, settings
from openride_core.config import Config
from openride_core.launcher import Supervisor, local_wind_reader
from openride_core.mock_driver import MockDriver
from openride_core.input_providers import NullProvider
from openride_core.profiles import ProfileContext
from openride_core.session import CoreSession
from openride_core.wind import WindModel

DEMO = (45.1, 6.1)   # maille du départ du parcours de démonstration (45,09 / 6,06)
NOW = 1_800_000_000.0


def answer(speed=20.0, direction=250.0, gusts=30.0) -> dict:
    return {"latitude": 45.1, "longitude": 6.1, "current": {
        "time": "2027-01-15T08:00", "wind_speed_10m": speed, "wind_direction_10m": direction,
        "wind_gusts_10m": gusts}}


class FakeOpener:
    """Remplace `urllib.request.urlopen` : note la requête et renvoie `payload` (ou lève `error`)."""

    def __init__(self, payload=None, error: Exception | None = None) -> None:
        self.payload, self.error, self.calls = payload, error, []

    def __call__(self, req, timeout):
        self.calls.append((req.full_url, timeout))
        if self.error is not None:
            raise self.error
        return io.BytesIO(json.dumps(self.payload).encode())


def world(root: Path, name: str, lat: float, lon: float) -> None:
    d = root / f"{name}.world"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"format": "openride-world", "origin": {
        "lat": lat, "lon": lon, "alt_m": 300.0}}), encoding="utf-8")


# --- positions, requête, conversion ------------------------------------------------------------------

def test_positions_rounded_to_10_km_before_anything_leaves():
    assert local_weather.cell(45.0912, 6.0634) == DEMO
    assert local_weather.cell(-33.874, 151.21) == (-33.9, 151.2)
    url = local_weather.request_url([DEMO, (44.0, 5.0)])
    assert "latitude=45.1,44.0" in url and "longitude=6.1,5.0" in url
    assert "wind_speed_10m" in url and "wind_gusts_10m" in url and "wind_speed_unit=kmh" in url
    assert url.startswith("https://api.open-meteo.com/v1/forecast?")
    assert "45.09" not in url and "6.06" not in url


def test_conversion_to_rider_height_and_gusts():
    speed, direction, gust = local_weather.convert(20.0, 610.0, 30.0)
    assert speed == pytest.approx(12.0) and direction == 250.0 and gust == 50.0
    assert local_weather.convert(200.0, 0.0, 400.0) == (60.0, 0.0, 100.0)   # bornes de [wind]
    assert local_weather.convert(0.0, 90.0, 5.0)[2] == 0.0                 # calme : pas de rafales
    assert local_weather.convert(10.0, 90.0, None)[2] == 0.0


def test_parse_single_and_multiple_points():
    one = local_weather.parse_response(answer(), [DEMO], NOW)
    assert one == [local_weather.LocalWind(45.1, 6.1, 12.0, 250.0, 50.0, NOW)]
    two = local_weather.parse_response([answer(), answer(10.0, 90.0, 10.0)], [DEMO, (44.0, 5.0)], NOW)
    assert [(w.lat, w.speed_kmh, w.from_deg) for w in two] == [(45.1, 12.0, 250.0), (44.0, 6.0, 90.0)]
    with pytest.raises(local_weather.WeatherError):
        local_weather.parse_response([answer()], [DEMO, (44.0, 5.0)], NOW)
    with pytest.raises(local_weather.WeatherError):
        local_weather.parse_response({"error": True, "reason": "x"}, [DEMO], NOW)


def test_fetch_uses_short_timeout_and_reports_offline():
    op = FakeOpener(answer())
    assert local_weather.fetch([DEMO], NOW, op)[0].speed_kmh == 12.0
    assert op.calls[0][1] == local_weather.TIMEOUT_S == 5.0
    for err in (urllib.error.URLError("hors ligne"), TimeoutError("délai"), OSError("réseau")):
        with pytest.raises(local_weather.WeatherError):
            local_weather.fetch([DEMO], NOW, FakeOpener(error=err))
    assert local_weather.fetch([], NOW, FakeOpener(error=AssertionError("pas d'appel"))) == []


def silent_server():
    """Serveur local qui accepte la connexion et ne répond jamais (critère 1 du cahier)."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    held: list[socket.socket] = []

    def accept() -> None:
        try:
            while True:
                held.append(srv.accept()[0])
        except OSError:
            pass

    threading.Thread(target=accept, daemon=True).start()
    return srv, held


def test_silent_server_times_out(monkeypatch):
    srv, held = silent_server()
    monkeypatch.setattr(local_weather, "SOURCE_URL", f"http://127.0.0.1:{srv.getsockname()[1]}/v1/forecast")
    t0 = time.monotonic()
    with pytest.raises(local_weather.WeatherError):
        local_weather.fetch([DEMO], NOW, timeout_s=0.3)
    assert time.monotonic() - t0 < 3.0
    srv.close()
    for c in held:
        c.close()


# --- départs des parcours, cache, recherche du core ---------------------------------------------------

def test_route_cells_from_manifests(tmp_path):
    world(tmp_path, "a", 45.0912, 6.0634)
    world(tmp_path, "b", 45.1301, 6.1102)     # même maille que a
    world(tmp_path, "c", 44.02, 4.98)
    bad = tmp_path / "d.world"
    bad.mkdir()
    (bad / "manifest.json").write_text("{illisible", encoding="utf-8")
    world(tmp_path, "e", float("nan"), 6.0)
    assert sorted(local_weather.route_cells(tmp_path)) == [(44.0, 5.0), DEMO]
    assert local_weather.route_cells(tmp_path / "absent") == []


def test_cache_lookup_fresh_stale_and_other_cell(tmp_path):
    path = tmp_path / "meteo_vent.json"
    local_weather.write_cache([local_weather.LocalWind(45.1, 6.1, 12.0, 250.0, 50.0, NOW)], path)
    assert not path.with_name("meteo_vent.json.tmp").exists()
    found = local_weather.lookup(45.0912, 6.0634, path, NOW + 3600)
    assert found is not None and found.speed_kmh == 12.0
    assert local_weather.lookup(45.0912, 6.0634, path, NOW + 3 * 3600 + 1) is None   # plus de 3 h
    assert local_weather.lookup(44.0, 5.0, path, NOW) is None
    path.write_text("pas du json", encoding="utf-8")
    assert local_weather.lookup(45.09, 6.06, path, NOW) is None
    assert "sans vent" in local_weather.status(path, NOW)


def test_refresh_reads_only_missing_cells_and_keeps_cache_offline(tmp_path):
    routes, path = tmp_path / "routes", tmp_path / "meteo_vent.json"
    world(routes, "a", 45.09, 6.06)
    op = FakeOpener(answer())
    line = local_weather.refresh(routes, path, NOW, op)
    assert "Open-Meteo" in line and "45.09" not in line and len(op.calls) == 1
    assert local_weather.refresh(routes, path, NOW + 600, op) is None and len(op.calls) == 1   # cache frais
    world(routes, "c", 44.02, 4.98)
    op2 = FakeOpener([answer(10.0, 90.0, 10.0)])
    local_weather.refresh(routes, path, NOW + 700, op2)
    assert "latitude=44.0&" in op2.calls[0][0]                         # seule la nouvelle maille
    assert {(e.lat, e.lon) for e in local_weather.read_cache(path)} == {DEMO, (44.0, 5.0)}
    saved = path.read_text(encoding="utf-8")
    with pytest.raises(local_weather.WeatherError):
        local_weather.refresh(routes, path, NOW + 4 * 3600, FakeOpener(error=OSError("hors ligne")))
    assert path.read_text(encoding="utf-8") == saved
    assert "45.09" not in saved and "6.06" not in saved                # positions arrondies seulement


# --- modèle de vent, séance, menu ---------------------------------------------------------------------

def test_wind_model_local_mode():
    cfg = Config()
    assert cfg.wind.mode == "off"   # décision du propriétaire du 8 novembre : coupé par défaut
    cfg.wind.mode = "local"
    assert not WindModel.from_config(cfg.wind).active
    model = WindModel.from_config(cfg.wind, None, local_weather.LocalWind(45.1, 6.1, 18.0, 270.0, 40.0, NOW))
    assert model.active and model.gusty and model.mode == "local"
    assert model.base_mps == pytest.approx(5.0) and model.from_deg == 270.0 and model.gust_frac == 0.4


def make_session(tmp_path, monkeypatch, port, mode="local"):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    monkeypatch.setattr(local_weather, "CACHE_FILE", tmp_path / "cache" / "meteo_vent.json")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    cfg.wind.mode = mode
    s = CoreSession(cfg, driver=MockDriver(base_power_w=250.0, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes")
    s.server.send_raw = lambda m: None
    return s


def ride(s, n=300):
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {}, 2)
    for i in range(n):
        s._step(0.02, 100.0 + i * 0.02)


def test_offline_session_is_identical_to_off(tmp_path, monkeypatch, caplog):
    local = make_session(tmp_path / "local", monkeypatch, 6770)
    with caplog.at_level("WARNING"):
        ride(local)
    assert not local.wind.active and local.state.wind is None
    assert any("indisponible" in r.getMessage() for r in caplog.records)
    off = make_session(tmp_path / "off", monkeypatch, 6772, mode="off")
    ride(off)
    assert (local._head_mps, local._wind_offset, local.physics.p.wind_mps) == (0.0, 0.0, 0.0)
    assert local.physics.s == pytest.approx(off.physics.s) and local.physics.v == pytest.approx(off.physics.v)


def test_session_uses_cached_wind_of_route_start(tmp_path, monkeypatch):
    s = make_session(tmp_path, monkeypatch, 6774)
    local_weather.write_cache([local_weather.LocalWind(45.1, 6.1, 25.0, 0.0, 20.0, time.time())])
    ride(s, 500)
    assert s.wind.active and s.wind.mode == "local"
    assert s.wind.base_mps == pytest.approx(25.0 / 3.6) and s._head_mps != 0.0


def test_menu_value_and_status(tmp_path, monkeypatch):
    monkeypatch.setattr(local_weather, "CACHE_FILE", tmp_path / "meteo_vent.json")
    cfg = Config()
    items = {i["key"]: i for i in settings.current(cfg)}
    assert "local" in items["wind.mode"]["choices"] and "Open-Meteo" in items["wind.mode"]["help"]
    assert "Aucune lecture" not in items["wind.mode"]["help"]   # pas d'état de lecture en mode off
    cfg.wind.mode = "local"
    help_ = {i["key"]: i for i in settings.current(cfg)}["wind.mode"]["help"]
    assert help_.endswith("la séance roule sans vent.")
    local_weather.write_cache([local_weather.LocalWind(45.1, 6.1, 12.0, 250.0, 50.0, time.time())])
    help_ = {i["key"]: i for i in settings.current(cfg)}["wind.mode"]["help"]
    assert "Lue à" in help_ and "1 départ de parcours" in help_


# --- lanceur ------------------------------------------------------------------------------------------

def test_reader_touches_network_only_in_local_mode(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text("[wind]\nmode = \"off\"\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr(local_weather, "refresh", lambda *a, **k: calls.append(a) or "lu")
    monkeypatch.setattr("openride_core.profiles.read_active", lambda path=None: None)
    read = local_wind_reader(config, ProfileContext.legacy(), tmp_path / "routes", tmp_path / "c.json")
    assert read() is None and calls == []
    config.write_text("[wind]\nmode = \"local\"\n", encoding="utf-8")
    assert read() == "lu" and calls[0][0] == tmp_path / "routes"


def test_launcher_never_waits_for_a_silent_server(tmp_path, monkeypatch):
    """Critère 1 : la lecture tourne dans un fil ; le lanceur, donc le départ du core, n'attend pas."""
    srv, held = silent_server()
    monkeypatch.setattr(local_weather, "SOURCE_URL", f"http://127.0.0.1:{srv.getsockname()[1]}/v1/forecast")
    routes = tmp_path / "routes"
    world(routes, "a", 45.09, 6.06)
    said: list[str] = []
    sup = Supervisor(core_cmd=["true"], engine_cmd=["true"], release_cmd=["true"], log_path=tmp_path / "l.log",
                     say=said.append, echo=lambda: True,
                     local_wind=lambda: local_weather.refresh(routes, tmp_path / "c.json", timeout_s=0.5))
    t0 = time.monotonic()
    sup._local_wind_tick(force=True)
    sup._local_wind_tick()   # lecture en cours : pas de deuxième fil
    assert time.monotonic() - t0 < 0.2
    sup._local_wind_thread.join(5.0)
    assert any("vent du jour indisponible" in m for m in said)
    assert sup._next_local_wind >= sup.clock() + sup.local_wind_retry_s - 5.0   # nouvel essai dans 15 min
    srv.close()
    for c in held:
        c.close()
