"""Revue de code, vague 4 (compilateur), lot RC23 « cache du monde ouvert » : constats K1-04, K1-05 et K1-12.

- K1-04 : un carré généré alors qu'une tuile vectorielle de son emprise manquait était marqué prêt et jamais refait ;
- K1-05 : la base OSM de la séance (région ou tuiles) n'était pas en usage et partait la première au plafond ;
- K1-12 : les dossiers `seances/` n'étaient jamais supprimés ni comptés dans le plafond.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from openride_compiler.elevation import SyntheticProvider
from openride_compiler.errors import CompileError
from openride_compiler.worldgen import vector_tiles as vt
from openride_compiler.worldgen.process import FakeClock, WorldSession
from openride_compiler.worldgen.squares import square_versions
from openride_compiler.worldgen.store import SESSIONS_KEPT, WorldCache

from test_vector_tiles import LAT, LON, S_LAT, S_LON, TX, FakeNet

QUIET = lambda _m: None  # noqa: E731


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def _write(path: Path, nbytes: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * nbytes)
    return path


# --- K1-05 : base OSM de la séance ---------------------------------------------------------------

def test_region_base_never_evicted_by_the_cap(tmp_path) -> None:
    logs: list[str] = []
    c = WorldCache(tmp_path / "monde", 3_000, clock=Clock(), dem_dir=tmp_path / "dem", log=logs.append)
    base = _write(c.osm_db_path("region-a"), 2_000)
    c.add("osm:region-a", "osm", base, {"schema": 1}, region="region-a")      # ajoutée tôt : la plus ancienne
    sq = c.square_dir("31T", 0, 4890)
    _write(sq / "near.f32", 1_500)
    key = c.square_key("31T", 0, 4890)
    c.add(key, "square", sq, {"worldgen": 1})
    removed = c.evict(in_use={key})
    assert removed == [] and base.is_file() and c.get("osm:region-a") is not None
    assert any("bases régionales" in m for m in logs)            # dépassement annoncé au journal
    assert c.clean(generated_only=False) and not base.exists()   # cache-clean --all les retire toujours


def test_session_holds_its_osm_base(tmp_path) -> None:
    c = WorldCache(tmp_path / "cache", 10**9, log=QUIET)
    rec: list[dict] = []
    s = WorldSession(c, SyntheticProvider(LAT, LON), rec.append, {}, tmp_path / "s.world", network=True,
                     clock=FakeClock(), log=QUIET)
    s.tile_net = FakeNet()
    s.handle({"type": "open", "lat": S_LAT, "lon": S_LON, "heading_deg": 90, "nav": "ride", "target": None,
              "loop_km": None, "seed": 1, "network": True})
    assert rec[-1]["type"] == "revision"
    assert s.osm_key == "osm:tuiles" and "osm:tuiles" in s.in_use()


def test_region_key_found_from_its_path(tmp_path) -> None:
    c = WorldCache(tmp_path / "monde", 10**9, clock=Clock(), log=QUIET)
    base = _write(c.osm_db_path("alsace"), 10)
    c.add("osm:alsace", "osm", base, region="alsace")
    before = c.get("osm:alsace").last_used
    assert c.key_of(base) == "osm:alsace" and c.key_of(tmp_path / "ailleurs.sqlite") is None
    c.touch("osm:alsace")
    assert c.get("osm:alsace").last_used > before


# --- K1-04 : carré sans toutes ses tuiles --------------------------------------------------------

class FlakyNet(FakeNet):
    """Tuiles à l'est de TX + 1 refusées (503) tant que `down` est vrai."""

    def __init__(self) -> None:
        super().__init__()
        self.down = True

    def download(self, url: str, dest: Path) -> int:
        x = int(url.rsplit("/", 2)[-2])
        if self.down and x >= TX + 2:
            raise CompileError(f"{url} : 503")
        return super().download(url, dest)


def test_partial_square_is_marked_and_redone_when_tiles_arrive(tmp_path) -> None:
    c = WorldCache(tmp_path / "cache", 10**9, log=QUIET)
    rec: list[dict] = []
    logs: list[str] = []
    s = WorldSession(c, SyntheticProvider(LAT, LON), rec.append, {}, tmp_path / "s.world", network=True,
                     clock=FakeClock(), log=logs.append)
    net = FlakyNet()
    s.tile_net = net
    s.handle({"type": "open", "lat": S_LAT, "lon": S_LON, "heading_deg": 90, "nav": "ride", "target": None,
              "loop_km": None, "seed": 1, "network": True})
    assert rec[-1]["type"] == "revision"
    assert s.partial_squares, "un carré au moins touche une tuile refusée"
    key = sorted(s.partial_squares, key=lambda k: (k.ix, k.i_n))[0]
    entry = c.get(key.cache_key)
    assert entry.versions.get("tiles") == "partial"
    complete = square_versions(s.db, s.provider)
    assert "tiles" not in complete and not c.is_valid(key.cache_key, complete)   # une séance suivante le refait
    # Le réseau revient : recul écoulé, tuiles redemandées, carrés partiels remis en file et refaits.
    net.down = False
    s.tiles._backoff.clear()
    s._retry_tiles()
    assert key not in s.ready and key not in s.partial_squares
    while s.work(publish=False):
        pass
    assert key in s.ready and c.is_valid(key.cache_key, complete)
    assert any("tuiles arrivées, refait" in m for m in logs)


def test_complete_square_in_cache_kept_when_tiles_are_missing(tmp_path) -> None:
    """Un carré complet déjà en cache n'est pas remplacé par un carré partiel pendant une coupure."""
    c = WorldCache(tmp_path / "cache", 10**9, log=QUIET)
    rec: list[dict] = []
    s = WorldSession(c, SyntheticProvider(LAT, LON), rec.append, {}, tmp_path / "a.world", network=True,
                     clock=FakeClock(), log=QUIET)
    s.tile_net = FakeNet()
    s.handle({"type": "open", "lat": S_LAT, "lon": S_LON, "heading_deg": 90, "nav": "ride", "target": None,
              "loop_km": None, "seed": 1, "network": True})
    done = {k: c.get(k.cache_key).versions for k in s.ready}
    assert done and all("tiles" not in v for v in done.values())
    from openride_compiler.worldgen.squares import generate_square
    k = next(iter(done))
    mtime = (c.square_dir(k.zone, k.ix, k.i_n) / "meta.json").stat().st_mtime_ns
    generate_square(k, s.db, s.provider, c, tiles_complete=False)
    assert c.get(k.cache_key).versions == done[k]
    assert (c.square_dir(k.zone, k.ix, k.i_n) / "meta.json").stat().st_mtime_ns == mtime


# --- K1-12 : dossiers des séances ----------------------------------------------------------------

def _session(c: WorldCache, name: str, t: float, lat: float = 48.5) -> Path:
    d = c.sessions_dir() / f"{name}.world"
    part = d / "route" / "part_0.json"
    part.parent.mkdir(parents=True)
    part.write_text(json.dumps({"lat": [lat, lat + 0.001], "lon": [7.1, 7.101], "x": [0, 10]}), encoding="utf-8")
    _write(d / "route" / "part_1.json", 5_000)
    _write(d / "terrain" / "near" / "tile_0_0.f32", 40_000)
    for p in (part, d):
        os.utime(p, (t, t))
    return d


def test_old_sessions_reduced_to_their_start(tmp_path) -> None:
    c = WorldCache(tmp_path / "monde", 10**9, log=QUIET)
    dirs = [_session(c, f"ow-202611{i:02d}-100000", 1_790_000_000 + i * 86_400, lat=48.0 + i / 100)
            for i in range(SESSIONS_KEPT + 3)]
    current = c.sessions_dir() / "ow-20261130-100000.world"
    before = c.sessions_bytes()
    reduced = c.prune_sessions(current=current)
    assert reduced == dirs[:3]
    for d in dirs[:3]:
        files = [f for f in d.rglob("*") if f.is_file()]
        assert files == [d / "route" / "part_0.json"]
        start = json.loads(files[0].read_text(encoding="utf-8"))
        assert set(start) == {"lat", "lon"} and len(start["lat"]) == 1 and start["lon"] == [7.1]
    for d in dirs[3:]:
        assert (d / "terrain" / "near" / "tile_0_0.f32").is_file()      # les plus récentes gardées entières
    starts = vt.past_starts(c)                                       # préchargement : tous les départs encore là
    assert len(starts) == len(dirs) and round(starts[0][0], 2) == 48.0
    assert c.sessions_bytes() < before
    assert c.prune_sessions(current=current) == []                   # déjà réduites : rien de plus


def test_session_bytes_count_in_the_cap(tmp_path) -> None:
    c = WorldCache(tmp_path / "monde", 100_000, clock=Clock(), log=QUIET)
    sq = c.square_dir("31T", 0, 4890)
    _write(sq / "near.f32", 60_000)
    c.add(c.square_key("31T", 0, 4890), "square", sq, {"worldgen": 1})
    assert c.evict() == []
    _session(c, "ow-20261101-100000", 1_790_000_000)                 # 45 Ko de séance : plafond dépassé
    assert c.evict(extra_bytes=c.sessions_bytes()) == [c.square_key("31T", 0, 4890)]


def test_session_open_prunes_old_sessions_but_not_its_own(tmp_path) -> None:
    c = WorldCache(tmp_path / "cache", 10**9, log=QUIET)
    old = [_session(c, f"ow-202610{i:02d}-100000", 1_780_000_000 + i) for i in range(SESSIONS_KEPT + 1)]
    rec: list[dict] = []
    s = WorldSession(c, SyntheticProvider(LAT, LON), rec.append, {}, None, network=True,
                     clock=FakeClock(), log=QUIET)
    s.tile_net = FakeNet()
    s.handle({"type": "open", "lat": S_LAT, "lon": S_LON, "heading_deg": 90, "nav": "ride", "target": None,
              "loop_km": None, "seed": 1, "network": True})
    assert rec[-1]["type"] == "revision"
    assert not (old[0] / "terrain").exists() and (old[0] / "route" / "part_0.json").is_file()
    assert (old[1] / "terrain" / "near" / "tile_0_0.f32").is_file()
    assert (s.session_dir / "route" / "part_0.json").is_file()
