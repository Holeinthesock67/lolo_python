"""Réseau dégradé du monde ouvert (lot X28) : faux serveur, recul des tuiles, scénarios de netcheck.

Les scénarios complets lancent le vrai générateur (sous-processus) sur le faux serveur : une
vingtaine de secondes chacun. Le critère 2 du cahier (un générateur qui ne réessaie pas échoue au
scénario `erreurs`) est joué avec `TILE_RETRY_S = ()` dans le sous-processus.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from openride_compiler.errors import CompileError
from openride_compiler.worldgen import mvt, netcheck, vector_tiles as vt
from openride_compiler.worldgen.fake_tile_server import FakeTileServer, ScenarioError, validate_server
from openride_compiler.worldgen.measure import Net
from openride_compiler.worldgen.store import WorldCache


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def _source(tmp_path: Path, server: FakeTileServer, clock: Clock) -> vt.TileSource:
    cache = WorldCache(tmp_path / "cache", 10**9, log=lambda _m: None)
    net = Net(timeout_s=5.0, sleep=lambda _s: None)
    return vt.TileSource(cache, net, True, log=lambda _m: None, tilejson_url=f"{server.url}/planet",
                         monotonic=clock, sleep=lambda s: setattr(clock, "t", clock.t + s))


def _bbox() -> tuple[float, float, float, float]:
    lat, lon = netcheck.start_point()
    return lon - 0.001, lat - 0.001, lon + 0.001, lat + 0.001


def test_fake_server_serves_tilejson_tiles_and_relief() -> None:
    with FakeTileServer() as s:
        tj = json.loads(urllib.request.urlopen(f"{s.url}/planet").read())
        assert tj["tiles"][0] == f"{s.url}/t/{{z}}/{{x}}/{{y}}.pbf"
        layers = mvt.decode_tile(urllib.request.urlopen(f"{s.url}/t/14/8401/5960.pbf").read())
        assert set(layers) == {"transportation", "building"}
        name = "Copernicus_DSM_COG_10_N43_00_E004_00_DEM"
        assert name in urllib.request.urlopen(f"{s.url}/dem/tileList.txt").read().decode()
        assert urllib.request.urlopen(f"{s.url}/dem/{name}/{name}.tif").read()[:2] in (b"II", b"MM")
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(f"{s.url}/ailleurs")
        assert [r["outcome"] for r in s.log] == [200, 200, 200, 200, 404]


def test_fake_server_faults_errors_cut_and_truncation() -> None:
    with FakeTileServer({"erreurs": {"codes": [429, 503], "par_chemin": 2}, "chemins": ["tuile"]}) as s:
        codes = []
        for _ in range(3):
            try:
                urllib.request.urlopen(f"{s.url}/t/14/1/2.pbf").read()
                codes.append(200)
            except urllib.error.HTTPError as exc:
                codes.append(exc.code)
        assert codes == [429, 503, 200]
        urllib.request.urlopen(f"{s.url}/planet").read()                 # chemin non touché
    with FakeTileServer({"coupure_s": [0, 30]}) as s:
        s.arm()
        with pytest.raises(OSError):
            urllib.request.urlopen(f"{s.url}/planet", timeout=5).read()
        assert s.log[-1]["outcome"] == "coupure"
    with FakeTileServer({"tronque": {"par_chemin": 1, "part": 0.5}}) as s:
        with pytest.raises(CompileError, match="incomplète"):
            Net(timeout_s=5.0).get(f"{s.url}/planet")                    # IncompleteRead → CompileError
        assert s.log[-1]["outcome"] == "tronque"


@pytest.mark.parametrize("spec, msg", [
    ({"latence": 1}, "inconnue"),
    ({"latence_s": [2, 1]}, "latence_s"),
    ({"coupure_s": [5]}, "coupure_s"),
    ({"erreurs": {"codes": [200]}}, "codes"),
    ({"tronque": {"part": 1.5}}, "part"),
    ({"chemins": ["osm"]}, "chemins"),
])
def test_bad_server_scenario_is_named(spec: dict, msg: str) -> None:
    with pytest.raises(ScenarioError, match=msg):
        validate_server(spec)


def test_bad_trip_is_named(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"trajet": {"vitesse": 3}}), encoding="utf-8")
    with pytest.raises(ScenarioError, match="inconnue"):
        netcheck.load_scenario(str(p))
    p.write_text(json.dumps({"trajet": {"remplissage_mo": 30}}), encoding="utf-8")
    with pytest.raises(ScenarioError, match="remplissage_mo"):
        netcheck.load_scenario(str(p))
    for name in netcheck.SCENARIOS:
        assert netcheck.load_scenario(name)[0] == name


def test_tile_source_backs_off_then_retries(tmp_path: Path) -> None:
    clock = Clock()
    with FakeTileServer({"erreurs": {"codes": [503], "par_chemin": 2}, "chemins": ["tuile"]}) as s:
        src = _source(tmp_path, s, clock)
        assert src.ensure(_bbox()) == 0 and src.failures >= 1
        n_req = len(s.log)
        assert src.ensure(_bbox()) == 0 and len(s.log) == n_req          # recul pas écoulé : rien demandé
        clock.t += vt.TILE_RETRY_S[0]
        assert src.ensure(_bbox()) == 0                                   # 2ᵉ erreur : recul doublé
        k = vt.tiles_for_bbox(_bbox())[0]
        assert src.next_try(k) == pytest.approx(clock.t + vt.TILE_RETRY_S[1])
        clock.t += vt.TILE_RETRY_S[1]
        assert src.ensure(_bbox()) >= 1 and not src.missing(_bbox())
        assert src.due(k)


def test_open_waits_for_retries_but_ride_never_does(tmp_path: Path) -> None:
    clock = Clock()
    with FakeTileServer({"erreurs": {"codes": [500], "par_chemin": 1}}) as s:
        src = _source(tmp_path, s, clock)
        assert src.ensure(_bbox(), wait_s=20.0) >= 1                      # départ : TileJSON puis tuiles reprises
        assert clock.t > 100.0
        assert {r["outcome"] for r in s.log} == {500, 200}


def test_truncated_tile_is_dropped_and_retried(tmp_path: Path) -> None:
    clock = Clock()
    with FakeTileServer({"tronque": {"par_chemin": 1, "part": 0.5}, "chemins": ["tuile"]}) as s:
        src = _source(tmp_path, s, clock)
        assert src.ensure(_bbox()) == 0 and src.missing(_bbox())
        clock.t += vt.TILE_RETRY_S[0]
        assert src.ensure(_bbox()) >= 1


def test_request_checks_spot_missing_retry_and_bursts() -> None:
    reqs = [{"t": 1.0, "path": "/t/14/1/1.pbf", "outcome": 503}, {"t": 3.2, "path": "/t/14/1/1.pbf", "outcome": 200},
            {"t": 1.0, "path": "/t/14/1/2.pbf", "outcome": "coupure"},
            {"t": 1.1, "path": "/planet", "outcome": 429}, {"t": 1.3, "path": "/planet", "outcome": 200}]
    retry, gap = netcheck.request_checks(reqs, end_t=60.0, max_backoff_s=32.0)
    assert retry[0] is False and "2/3" in retry[2] and "/t/14/1/2.pbf" in retry[2]
    assert gap[0] is False and "0.20 s (/planet)" in gap[2]
    retry, _ = netcheck.request_checks(reqs[:3], end_t=20.0, max_backoff_s=32.0)
    assert retry[0] is True                                               # panne trop proche de la fin


@pytest.mark.parametrize("name", netcheck.SCENARIOS)
def test_scenario_passes_on_the_real_generator(name: str, tmp_path: Path) -> None:
    r = netcheck.run_scenario(name, work=tmp_path, log=lambda _m: None)
    assert r.ok, [c for c in r.checks if c[0] is False]
    assert r.elapsed_s < netcheck.MAX_SCENARIO_S


def test_generator_without_retry_fails_errors_scenario(tmp_path: Path) -> None:
    """Critère 2 : le même générateur, recul supprimé (une tuile en échec n'est plus jamais redemandée)."""
    cmd = [sys.executable, "-c", "import sys; from openride_compiler.worldgen import vector_tiles as vt; "
           "vt.TILE_RETRY_S = (); from openride_compiler.worldgen.process import main; sys.exit(main())"]
    r = netcheck.run_scenario("erreurs", generator=cmd, work=tmp_path, log=lambda _m: None)
    assert not r.ok
    failed = {label for ok, label, _ in r.checks if ok is False}
    assert "départ : première route publiée" in failed
