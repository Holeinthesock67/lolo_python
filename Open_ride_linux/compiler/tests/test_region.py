"""Extrait régional Geofabrik (lot W3) : téléchargement, conversion par pyosmium, cache, sans réseau."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from openride_compiler import cli
from openride_compiler.errors import CompileError
from openride_compiler.worldgen import osmdb, region
from openride_compiler.worldgen.osmdb import OsmDb
from openride_compiler.worldgen.store import WorldCache

DATA = Path(__file__).parent / "data" / "mini_region.osm"
REGION = "europe/test/mini-region"
URL = f"{region.GEOFABRIK_URL}/{REGION}-latest.osm.pbf"


class Resp(io.BytesIO):
    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None) -> None:
        super().__init__(body)
        self.status = status
        self.headers = headers or {}


class FakeServer:
    """Sert des fichiers par URL ; `cut` coupe la première réponse après n octets (reprise)."""

    def __init__(self, files: dict[str, bytes], last_modified: str = "Mon, 26 Oct 2026 20:00:00 GMT") -> None:
        self.files = files
        self.last_modified = last_modified
        self.calls: list[tuple[str, dict, str]] = []
        self.cut: int | None = None

    def __call__(self, url: str, headers: dict, method: str = "GET"):
        self.calls.append((url, dict(headers), method))
        if url not in self.files:
            raise CompileError(f"{url} : erreur HTTP 404")
        body = self.files[url]
        hdr = {"Last-Modified": self.last_modified}
        if method == "HEAD":
            return Resp(b"", headers=hdr)
        start = int(headers["Range"][6:-1]) if "Range" in headers else 0
        status = 206 if start else 200
        if self.cut is not None:
            cut, self.cut = self.cut, None
            return _Broken(body[start:start + cut], status, hdr)
        return Resp(body[start:], status, hdr)


class _Broken(Resp):
    def read(self, n: int = -1) -> bytes:
        data = super().read(n)
        if not data:
            raise ConnectionError("connexion coupée")
        return data


def _pbf(tmp_path: Path) -> bytes:
    osmium = pytest.importorskip("osmium")
    out = tmp_path / "source.osm.pbf"
    w = osmium.SimpleWriter(str(out))
    for obj in osmium.FileProcessor(str(DATA)):
        w.add(obj)
    w.close()
    return out.read_bytes()


def _server(body: bytes, md5: str | None = None) -> FakeServer:
    md5 = md5 or hashlib.md5(body).hexdigest()
    return FakeServer({URL: body, URL + ".md5": f"{md5}  mini-region-latest.osm.pbf\n".encode()})


@pytest.fixture
def cache(tmp_path) -> WorldCache:
    return WorldCache(tmp_path / "monde", 10**9, dem_dir=tmp_path / "dem", log=lambda _: None)


def test_conversion_of_mini_region(tmp_path) -> None:
    pytest.importorskip("osmium")
    out = tmp_path / "mini.sqlite"
    counts = region.convert(DATA, out, "test/mini", log=lambda _: None)
    assert counts == {"roads": 13, "areas": 5, "lines": 1, "points": 5}
    with OsmDb(out) as db:
        classes = {r.osm_id: r.road_class for r in db.roads_in((-180, -90, 180, 90), include_excluded=True)}
        highway = {r.osm_id: r.highway for r in db.roads_in((-180, -90, 180, 90), include_excluded=True)}
        assert [classes[i] for i in sorted(classes)] == ["p", "s", "t", "m", "x", "c", "c", "x", "k", "x", "x", "x", "x"]
        assert highway[11] == "motorway" and classes[11] == "x"          # autoroute
        assert highway[13] == "unclassified" and classes[13] == "x"      # chemin surface=gravel
        assert "footway" not in highway.values()
        roads = {r.osm_id: r for r in db.roads_in((-180, -90, 180, 90))}
        assert roads[2].bridge and roads[2].layer == 1 and roads[3].tunnel and roads[3].layer == -1
        assert roads[4].oneway == 1 and roads[1].name == "Route principale" and len(roads[1].nodes) == 3
        areas = {a.osm_id: a for a in db.areas_in((-180, -90, 180, 90))}
        assert {a.kind for a in areas.values()} == {"building", "wood", "water", "scrub"}
        court = areas["r1"]
        assert court.kind == "building" and len(court.holes) == 1 and len(court.outer) >= 4
        assert court.tags == {"building": "yes", "height": "12 m"}                   # ni fixme ni type
        assert areas["w15"].tags == {"building": "house", "building:levels": "2"}    # ni source ni adresse
        (river,) = db.lines_in((-180, -90, 180, 90))
        assert river.kind == "river" and river.tags == {"name": "La Rivière"}
        assert {p.kind for p in db.points_in((-180, -90, 180, 90))} == \
            {"town", "village", "hamlet", "mountain_pass", "viewpoint"}
        assert [p.name for p in db.search_places("evian")] == ["Évian-les-Bains"]
        assert db.meta["osm_date"] == "2026-10-21T09:30:00Z" and db.meta["region"] == "test/mini"


def test_interrupted_conversion_leaves_nothing(tmp_path, monkeypatch) -> None:
    pytest.importorskip("osmium")

    def boom(*a, **k):
        raise RuntimeError("panne injectée")

    monkeypatch.setattr(osmdb.OsmDbWriter, "add_area", boom)
    with pytest.raises(RuntimeError, match="panne"):
        region.convert(DATA, tmp_path / "out" / "mini.sqlite", "test/mini", log=lambda _: None)
    assert list((tmp_path / "out").iterdir()) == []


def test_region_add_update_list(tmp_path, cache, capsys) -> None:
    server = _server(_pbf(tmp_path))
    dl = region.Downloader(server, log=lambda _: None)
    res = region.region_add(REGION, cache, dl, log=lambda _: None)
    db_path = cache.osm_db_path("mini-region")
    assert res["region"] == "mini-region" and db_path.is_file()
    assert not (db_path.parent / "mini-region.osm.pbf").exists()                 # pbf supprimé
    assert sorted(p.name for p in db_path.parent.iterdir()) == ["mini-region.sqlite"]
    entry = cache.get("osm:mini-region")
    assert entry.kind == "osm" and entry.region == "mini-region"
    assert entry.versions == {"schema_version": 1, "osm_date": "2026-10-21T09:30:00Z",
                              "last_modified": server.last_modified}
    (r,) = region.region_list(cache)
    assert r["id"] == "mini-region" and r["database"] and r["bbox"][0] < r["bbox"][2]

    gets = len([c for c in server.calls if c[2] == "GET"])
    assert region.region_update(REGION, cache, dl, log=lambda _: None) is None   # déjà à jour : HEAD seul
    assert len([c for c in server.calls if c[2] == "GET"]) == gets
    server.last_modified = "Tue, 27 Oct 2026 20:00:00 GMT"
    assert region.region_update(REGION, cache, dl, log=lambda _: None)["region"] == "mini-region"
    assert cache.get("osm:mini-region").versions["last_modified"] == server.last_modified

    region.region_add(REGION, cache, dl, keep_pbf=True, log=lambda _: None)
    assert (db_path.parent / "mini-region.osm.pbf").is_file()


def test_wrong_md5_writes_nothing(tmp_path, cache) -> None:
    pytest.importorskip("osmium")
    body = b"pas vraiment un pbf" * 100
    dl = region.Downloader(_server(body, md5="0" * 32), log=lambda _: None)
    with pytest.raises(CompileError, match="MD5"):
        region.region_add(REGION, cache, dl, log=lambda _: None)
    assert [p for p in (cache.root / "brut").rglob("*") if p.is_file()] == []
    assert cache.get("osm:mini-region") is None


def test_download_resumes_after_cut(tmp_path) -> None:
    body = bytes(range(256)) * 20_000
    server = _server(body)
    server.cut = 1_000_000
    sleeps: list[float] = []
    dl = region.Downloader(server, log=lambda _: None, sleep=sleeps.append)
    dest = tmp_path / "x.osm.pbf"
    dl.download(URL, dest, hashlib.md5(body).hexdigest())
    assert dest.read_bytes() == body and not (tmp_path / "x.osm.pbf.part").exists()
    gets = [c for c in server.calls if c[0] == URL]
    assert "Range" not in gets[0][1] and gets[1][1]["Range"] == "bytes=1000000-" and sleeps == [2.0]


def test_missing_pyosmium_message(monkeypatch, cache) -> None:
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "osmium":
            raise ImportError("absent")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(CompileError, match=r"compiler\[worldgen\]"):
        region.region_add(REGION, cache, region.Downloader(_server(b"x")), log=lambda _: None)


def test_region_id_validation() -> None:
    assert region.region_id("europe/france/alsace") == "alsace"
    for bad in ("", "/", "https://exemple/alsace", "europe/.."):
        with pytest.raises(CompileError):
            region.region_id(bad)


def test_region_list_command(tmp_path, capsys) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[open_world]\ncache_dir = "{tmp_path / "monde"}"\n')
    assert cli.main(["region-list", "--config", str(cfg)]) == 0
    assert "Aucune région" in capsys.readouterr().out
    assert cli.main(["region-list", "--config", str(cfg), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []
