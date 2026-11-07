"""Vélodrome (série VD) : générateur de la piste (lot VD2), lecture de `bank_deg`, de `wood` et de la couche
`venue` (lot VD1, partie format), physique en piste (lot VD3 : bois, air de la salle, vent coupé, distance)."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export, surface_physics, velodrome
from openride_core.__main__ import main
from openride_core.config import Config, ConfigError, from_layers
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.physics import PhysicsParams, RiderPhysics, air_density
from openride_core.route import Route, WorldError, load_world
from openride_core.session import CoreSession

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = velodrome.TRACKS[velodrome.TRACK_ID]
SCHEMAS = REPO_ROOT / "docs" / "contracts" / "world"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return velodrome.write_velodrome(tmp_path_factory.mktemp("routes"))


# --- générateur (VD2) ------------------------------------------------------------------------------


def test_spline_length_closure_and_flat(world) -> None:
    w = load_world(world)
    r = w.route
    assert r.is_loop and r.length_m == 250.0 and r.ds_m == velodrome.DS_M
    assert (r.x[0], r.z[0]) == (r.x[-1], r.z[-1])               # premier point = dernier
    length, prev = 0.0, r.sample(0.0)
    for i in range(1, 25001):
        cur = r.sample(i * 0.01)
        length += math.dist((prev.x, prev.z), (cur.x, cur.z))
        prev = cur
    assert length == pytest.approx(250.0, abs=0.05)              # longueur à la ligne de mesure
    assert max(abs(g) for g in r.grade_pct) <= 1e-6               # pente nulle partout
    assert len(set(r.alt_m)) == 1


def test_integration_closes_without_correction() -> None:
    geo = velodrome.TrackGeometry(SPEC)
    s_values = [min(i * velodrome.DS_M, 250.0) for i in range(1001)]
    x, z = geo.positions(s_values)[-1]
    assert math.hypot(x, z) < 1e-6                               # bouclage exact avant le recollage
    assert geo.turned(250.0) == pytest.approx(2.0 * math.pi)
    assert geo.heading_deg(0.0) == pytest.approx(90.0)


def test_shape_matches_plan() -> None:
    assert SPEC.straight_m == pytest.approx(34.74, abs=0.01)
    assert SPEC.arc_m == pytest.approx(54.26, abs=0.01)
    geo = velodrome.TrackGeometry(SPEC)
    assert geo.bank_deg(0.0) == pytest.approx(12.0)               # milieu de la droite d'arrivée
    apex = 0.5 * SPEC.straight_m + SPEC.transition_m + 0.5 * SPEC.arc_m
    assert geo.bank_deg(apex) == pytest.approx(42.0)
    assert geo.curvature(apex) == pytest.approx(1.0 / 23.0)


def test_bank_and_curvature_continuous(world) -> None:
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    bank = route["bank_deg"]
    assert max(abs(a - b) for a, b in zip(bank, bank[1:])) < 0.5     # sauts sous 0,5° par point
    assert min(bank) == pytest.approx(12.0) and max(bank) == pytest.approx(42.0)
    geo = velodrome.TrackGeometry(SPEC)
    k = [geo.curvature(i * 0.25) for i in range(1000)]
    assert max(abs(a - b) for a, b in zip(k, k[1:])) < 0.25 / (SPEC.transition_m * SPEC.radius_m) + 1e-9
    heads = route["heading_deg"]
    steps = [((b - a + 180.0) % 360.0) - 180.0 for a, b in zip(heads, heads[1:])]
    assert all(st <= 1e-9 for st in steps)                       # virages à gauche seulement
    assert max(abs(st) for st in steps) < 0.7


def test_two_writes_identical(tmp_path) -> None:
    a = velodrome.write_velodrome(tmp_path / "a")
    b = velodrome.write_velodrome(tmp_path / "b")
    for name in ("manifest.json", "route.json", "venue.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    velodrome.write_velodrome(tmp_path / "a")                    # réécriture : remplacée, rien ne traîne
    assert sorted(p.name for p in (tmp_path / "a").iterdir()) == ["velodrome-250.world"]


@pytest.mark.parametrize("change, message", [
    ({"length_m": 150.0}, "impossible"),
    ({"transition_m": 80.0}, "arc négatif"),
    ({"bank_bend_deg": 55.0}, "hors de 0 à 50"),
    ({"bank_straight_deg": -1.0}, "hors de 0 à 50"),
    ({"bank_straight_deg": 30.0, "bank_bend_deg": 20.0}, "moins relevés"),
    ({"radius_m": 0.0}, "positifs"),
    ({"sprinters_line_m": 3.0}, "lignes peintes"),
])
def test_impossible_shapes(change, message) -> None:
    with pytest.raises(velodrome.VelodromeError, match=message):
        velodrome.check_spec(replace(SPEC, **change))


def test_other_length_is_a_table_line() -> None:
    geo = velodrome.TrackGeometry(replace(SPEC, id="v333", length_m=333.33, radius_m=28.0))
    s_values = [min(i * 0.25, 333.33) for i in range(int(333.33 / 0.25) + 2)]
    x, z = geo.positions(s_values)[-1]
    assert math.hypot(x, z) < 1e-6


def test_unknown_track() -> None:
    with pytest.raises(velodrome.VelodromeError, match="inconnue"):
        velodrome.geometry("velodrome-400")


def test_schemas(world) -> None:
    for name, schema in (("route.json", "route.schema.json"), ("venue.json", "venue.schema.json"),
                         ("manifest.json", "manifest.schema.json")):
        data = json.loads((world / name).read_text(encoding="utf-8"))
        jsonschema.validate(data, json.loads((SCHEMAS / schema).read_text(encoding="utf-8")))


def test_venue_counter_examples(world) -> None:
    schema = json.loads((SCHEMAS / "venue.schema.json").read_text(encoding="utf-8"))
    venue = json.loads((world / "venue.json").read_text(encoding="utf-8"))
    for bad in ({**venue, "kind": "stadium"}, {**venue, "track_width_m": -1},
                {k: v for k, v in venue.items() if k != "geometry"}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)
    route_schema = json.loads((SCHEMAS / "route.schema.json").read_text(encoding="utf-8"))
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**route, "bank_deg": [60.0] * route["n"]}, route_schema)


def test_manifest_library_and_stats(world) -> None:
    m = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    assert m["format_version"] == "1.7" and m["layers"]["venue"]["present"]
    assert m["library"]["tags"] == ["velodrome"]
    assert m["stats"]["gain_m"] == 0.0 and m["stats"]["surface_pct"] == {"wood": 100.0}
    assert m["layers"]["terrain"]["present"] is False


def test_cli(tmp_path, capsys) -> None:
    assert main(["velodromes", "--out", str(tmp_path), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["route"] == "velodrome-250" and (tmp_path / "velodrome-250.world" / "venue.json").is_file()


# --- lecture du format (VD1) -----------------------------------------------------------------------


def _small_route(**extra) -> dict:
    n = 11
    return {"version": "1.0", "ds_m": 10.0, "n": n, "length_m": 100.0, "type": "open",
            "lat": [45.0] * n, "lon": [6.0 + i * 1e-4 for i in range(n)], "alt_m": [100.0] * n,
            "x": [10.0 * i for i in range(n)], "z": [0.0] * n, "grade_pct": [0.0] * n,
            "heading_deg": [90.0] * n, **extra}


def test_route_without_bank_unchanged() -> None:
    r = Route(_small_route())
    assert r.bank_deg is None and r.bank_at(55.0) == 0.0


def test_bank_interpolated_like_altitude() -> None:
    r = Route(_small_route(bank_deg=[float(i) for i in range(11)], surface=["wood"] * 11))
    assert r.bank_at(55.0) == pytest.approx(5.5) and r.surface_at(55.0) == "wood"


@pytest.mark.parametrize("bank, message", [([0.0] * 5, "11 valeurs"), ([51.0] * 11, "± 50"),
                                           (["x"] * 11, "mal typé")])
def test_bank_invalid(bank, message) -> None:
    with pytest.raises(WorldError, match=message):
        Route(_small_route(bank_deg=bank))


def test_bad_venue_ignored(world, tmp_path, caplog) -> None:
    import shutil

    copy = tmp_path / "v.world"
    shutil.copytree(world, copy)
    (copy / "venue.json").write_text('{"version": "2.0", "kind": "velodrome"}', encoding="utf-8")
    w = load_world(copy)
    assert w.venue is None and w.route.bank_at(100.0) > 12.0
    assert "couche venue ignorée" in caplog.text


# --- physique en piste (VD3) -----------------------------------------------------------------------


def test_one_metre_higher_costs_4_to_6_m() -> None:
    geo = velodrome.TrackGeometry(SPEC)
    assert geo.lap_length_at(0.0) == pytest.approx(250.0, abs=1e-6)
    assert 4.0 <= geo.lap_length_at(1.0) - 250.0 <= 6.0
    assert geo.progress_factor(0.0, 3.0) == 1.0                    # droite : aucune différence


def test_hall_air() -> None:
    alt = velodrome.hall_altitude_m(0.0, 24.0)
    assert air_density(alt) == pytest.approx(1.225 * 288.15 / 297.15, rel=1e-9)
    assert velodrome.hall_altitude_m(200.0, 15.0) == pytest.approx(200.0)


def test_wood_factor_and_offset() -> None:
    cfg = Config()
    for mode in surface_physics.MODES:
        assert surface_physics.effective_surface("wood", mode) == "wood"
    assert surface_physics.crr_factor("wood", cfg.gravel, cfg.velodrome.factor_wood) == pytest.approx(0.6)
    assert surface_physics.grade_offset_pct(0.004, 0.6, 0.0) == pytest.approx(-0.16)
    r = Route(_small_route(surface=["wood"] * 11))
    assert surface_physics.blended_factor(r, 50.0, "off", cfg.gravel) == 1.0          # hors piste : comme avant
    assert surface_physics.blended_factor(r, 50.0, "off", cfg.gravel, wood_factor=0.6) == pytest.approx(0.6)
    assert surface_physics.blended_factor(r, 50.0, "dirt", cfg.gravel, wood_factor=0.6) == pytest.approx(0.6)


def test_lap_time_on_wood_shorter_than_paved() -> None:
    """84 kg à 250 W : tour plus court sur le bois, écart conforme au facteur à ± 10 % (critère 3 de VD3)."""
    def lap_time(crr: float) -> float:
        p = RiderPhysics(PhysicsParams(mass_kg=84.0, crr=crr), v=13.0)
        t = 0.0
        while p.s < 2500.0:      # 10 tours lancés
            p.step(250.0, 0.0, velodrome.hall_altitude_m(200.0, 24.0))
            t += 0.02
        return t / 10.0

    paved, wood = lap_time(0.004), lap_time(0.004 * 0.6)
    assert wood < paved
    # écart attendu : même puissance, roulement en moins de 0,4 × crr × m g v, estimé à la vitesse du bitume
    v = 250.0 / paved
    rho = air_density(velodrome.hall_altitude_m(200.0, 24.0))
    df = 0.4 * 0.004 * 84.0 * 9.80665                     # force de roulement économisée (N)
    dv = df * v / (1.5 * rho * 0.32 * v ** 2 + 0.004 * 0.6 * 84.0 * 9.80665)   # d(η P)/dv sur le bois
    expected = paved - 250.0 / (v + dv)
    assert paved - wood == pytest.approx(expected, rel=0.10)


def test_config_section() -> None:
    cfg = from_layers({"velodrome": {"factor_wood": 0.5, "temperature_c": 20.0}}, {}, "c", "p")
    assert cfg.velodrome.factor_wood == 0.5 and cfg.velodrome.temperature_c == 20.0
    with pytest.raises(ConfigError):
        from_layers({"velodrome": {"factor_wood": 1.5}}, {}, "c", "p")


def _session(tmp_path, monkeypatch, port, wind=None):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    cfg.trainer.difficulty_pct = 100.0
    for key, value in (wind or {}).items():
        setattr(cfg.wind, key, value)
    routes = tmp_path / "routes"
    velodrome.write_velodrome(routes)
    drv = MockDriver(base_power_w=250.0, ramp_amplitude_w=0.0)
    s = CoreSession(cfg, driver=drv, inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=routes, workouts_dir=tmp_path / "wk")
    s._on_command("select_route", {"route_id": velodrome.TRACK_ID}, 1)
    s._on_command("start", {}, 2)
    return s, drv


def _run(s, n, t0=100.0):
    for i in range(n):
        s._step(0.02, t0 + i * 0.02)


def test_session_on_track(tmp_path, monkeypatch) -> None:
    s, drv = _session(tmp_path, monkeypatch, 7460, wind={"mode": "fixed", "speed_kmh": 30.0})
    assert s._track is not None and not s.wind.active                # salle couverte : vent coupé
    _run(s, 3000)
    assert s._gravel_factor == pytest.approx(0.6)
    assert s.physics.p.crr == pytest.approx(0.004 * 0.6)
    assert s._gravel_offset == pytest.approx(-0.16, abs=0.005)
    assert s.state.grade == 0.0                                       # pente du parcours nulle partout
    assert s.physics.s > 250.0                                        # la boucle reboucle


def test_session_distance_rule(tmp_path, monkeypatch) -> None:
    """Rouler plus haut : la distance comptée sur la ligne de mesure avance moins vite dans les virages."""
    s, _ = _session(tmp_path, monkeypatch, 7462)
    s._lane.m = 0.0
    s._lane.auto = False
    s.physics.s, s.physics.v = 30.0, 12.0
    s0 = s.physics.s
    _run(s, 1)
    low = s.physics.s - s0
    s.physics.s, s.physics.v = 30.0, 12.0
    s._lane.m = 2.0
    _run(s, 1, t0=200.0)
    high = s.physics.s - 30.0
    assert high < low


def test_road_unchanged_by_track_code(tmp_path, monkeypatch) -> None:
    """Une route classique garde vent et roulement d'avant (aucune piste chargée)."""
    from openride_core.demo_world import write_world

    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = 7464, 7465
    cfg.wind.mode, cfg.wind.speed_kmh = "fixed", 20.0
    routes = tmp_path / "routes"
    routes.mkdir()
    write_world(routes, "plat", 3000.0, created="2026-10-30T00:00:00+00:00", grade=lambda s: 0.0)
    s = CoreSession(cfg, driver=MockDriver(base_power_w=200.0, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal", routes_root=routes, workouts_dir=tmp_path / "wk")
    s._on_command("select_route", {"route_id": "plat"}, 1)
    s._on_command("start", {}, 2)
    _run(s, 200)
    assert s._track is None and s.wind.active and s.physics.p.crr == pytest.approx(0.004)
