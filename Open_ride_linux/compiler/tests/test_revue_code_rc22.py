"""Lot RC22, téléchargements sûrs (revue de code, vague 4, K1-01, K1-02, K1-03, K1-06, K4-04).

Une donnée téléchargée abîmée (coupée, page d'erreur servie en 200) ne doit pas entrer dans le cache, et une
copie abîmée déjà en cache doit être redemandée au lieu d'être refusée à chaque lancement. Sans réseau.
"""

from __future__ import annotations

import gzip
import http.client
import io
import json
import os
import time

import numpy as np
import pytest

from openride_compiler import cache, osm
from openride_compiler.cache import Downloader
from openride_compiler.elevation import (CopernicusGlo30Provider, check_tile_list, check_tiff,
                                         copernicus_tile_name)
from openride_compiler.errors import CompileError
from openride_compiler.worldgen import mvt, vector_tiles as vt
from openride_compiler.worldgen.store import WorldCache

from test_elevation import write_fake_tile

N45 = copernicus_tile_name(45, 6)
N46 = copernicus_tile_name(46, 6)
QUIET = lambda _m: None  # noqa: E731


class Resp(io.BytesIO):
    """Réponse HTTP factice avec en-têtes (Content-Length annoncé, éventuellement faux)."""

    def __init__(self, data: bytes, announced: int | None = None) -> None:
        super().__init__(data)
        self.headers = {} if announced is None else {"Content-Length": str(announced)}


class FakeHttp:
    def __init__(self, answers) -> None:
        self.answers = list(answers)
        self.calls: list[str] = []

    def __call__(self, url, timeout=None):
        self.calls.append(getattr(url, "full_url", url))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer if isinstance(answer, io.BytesIO) else Resp(answer)


@pytest.fixture
def fake_http(monkeypatch):
    def install(answers):
        fake = FakeHttp(answers)
        monkeypatch.setattr(cache.urllib.request, "urlopen", fake)
        return fake
    return install


def dl(**kw) -> tuple[Downloader, list[float]]:
    sleeps: list[float] = []
    return Downloader(log=QUIET, sleep=sleeps.append, **kw), sleeps


# --- K1-01 : téléchargeur ----------------------------------------------------------------------

def test_short_download_against_content_length_is_retried(fake_http, tmp_path):
    fake = fake_http([Resp(b"moit", announced=8), Resp(b"complete", announced=8)])
    d, sleeps = dl()
    dest = tmp_path / "f.bin"
    d.fetch("http://x/f.bin", dest)
    assert dest.read_bytes() == b"complete"
    assert len(fake.calls) == 2 and sleeps == [2.0]
    assert [p.name for p in tmp_path.iterdir()] == ["f.bin"]


def test_short_download_every_time_gives_up_without_cache_file(fake_http, tmp_path):
    fake_http([Resp(b"moit", announced=8)] * 4)
    d, _ = dl()
    with pytest.raises(CompileError, match="après 3 reprises"):
        d.fetch("http://x/f.bin", tmp_path / "f.bin")
    assert list(tmp_path.iterdir()) == []


def test_error_page_served_in_200_is_not_cached(fake_http, tmp_path):
    tif = tmp_path / "src.tif"
    write_fake_tile(tif, 45, 6, size=11)
    fake = fake_http([b"<html>maintenance</html>", tif.read_bytes()])
    d, _ = dl()
    dest = tmp_path / "c" / "t.tif"
    d.fetch("http://x/t.tif", dest, validate=check_tiff)
    assert dest.read_bytes()[:4] == b"II*\x00"
    assert len(fake.calls) == 2


def test_bad_cached_file_is_replaced_online(fake_http, tmp_path):
    dest = tmp_path / "t.tif"
    dest.write_bytes(b"<html>")
    tif = tmp_path / "src.tif"
    write_fake_tile(tif, 45, 6, size=11)
    fake = fake_http([tif.read_bytes()])
    d, _ = dl()
    d.fetch("http://x/t.tif", dest, validate=check_tiff)
    assert dest.read_bytes() == tif.read_bytes() and len(fake.calls) == 1


def test_bad_cached_file_offline_says_how_to_fix(fake_http, tmp_path):
    dest = tmp_path / "t.tif"
    dest.write_bytes(b"<html>")
    fake = fake_http([])
    d, _ = dl(offline=True)
    with pytest.raises(CompileError, match="sans --offline"):
        d.fetch("http://x/t.tif", dest, validate=check_tiff)
    assert dest.is_file() and fake.calls == []       # rien d'effacé hors ligne


def test_without_validator_cached_file_is_kept_as_before(fake_http, tmp_path):
    (tmp_path / "f").write_bytes(b"deja")
    fake = fake_http([])
    dl()[0].fetch("http://x/f", tmp_path / "f")
    assert fake.calls == []


# --- K1-01 : relief Copernicus -----------------------------------------------------------------

def test_tile_list_check(tmp_path):
    f = tmp_path / "tileList.txt"
    for bad in ("", "<html>\n", f"{N45}\nCopernicus_DSM_CO", "\xff"):
        f.write_bytes(bad.encode("latin-1"))
        with pytest.raises(ValueError):
            check_tile_list(f)
    f.write_text(f"{N45}\n{N46}\n")
    check_tile_list(f)


def test_truncated_tile_list_is_not_sea(fake_http, tmp_path):
    """Liste coupée au milieu d'un nom : refusée et redemandée, la tuile n'est pas prise pour de la mer."""
    tif = tmp_path / "src.tif"
    write_fake_tile(tif, 46, 6, size=11, func=lambda la, lo: 0 * la + 777.0)
    full = f"{N45}\n{N46}\n".encode()
    fake = fake_http([full[:len(N45) + 8], full, tif.read_bytes()])
    p = CopernicusGlo30Provider(cache_dir=tmp_path / "dem", log=QUIET,
                                downloader=Downloader(log=QUIET, sleep=lambda s: None))
    assert p.elevations(np.array([46.5]), np.array([6.5]))[0] == pytest.approx(777.0)
    assert len(fake.calls) == 3


def test_unreadable_cached_tile_is_downloaded_again(fake_http, tmp_path):
    """Tuile qui commence comme un TIFF mais coupée : supprimée et retéléchargée une fois."""
    root = tmp_path / "dem"
    d = root / "copernicus_glo30"
    write_fake_tile(d / f"{N45}.tif", 45, 6, size=11)
    good = (d / f"{N45}.tif").read_bytes()
    (d / f"{N45}.tif").write_bytes(good[:200])
    (d / "tileList.txt").write_text(f"{N45}\n")
    fake = fake_http([good])
    p = CopernicusGlo30Provider(cache_dir=root, log=QUIET,
                                downloader=Downloader(log=QUIET, sleep=lambda s: None))
    assert np.isfinite(p.elevations(np.array([45.5]), np.array([6.5]))[0])
    assert len(fake.calls) == 1


# --- K1-03 et K4-04 : Overpass -----------------------------------------------------------------

RUNTIME = json.dumps({"elements": [], "remark": "runtime error: Query timed out in \"query\""}).encode()
GOOD = json.dumps({"elements": [{"type": "node", "id": 1, "lat": 0.0, "lon": 0.0}]}).encode()


class Truncated(io.BytesIO):
    def read(self, *a):
        raise http.client.IncompleteRead(b"{\"elem", 100)


def overpass(tmp_path, answers, offline=False):
    fake = FakeHttp(answers)
    return osm.OverpassClient(cache_dir=tmp_path, offline=offline, log=QUIET, sleep=lambda s: None,
                              urlopen=fake), fake


def test_overpass_runtime_error_not_cached_and_retried(tmp_path):
    client, fake = overpass(tmp_path, [RUNTIME, GOOD])
    assert client.fetch_query("q")["elements"]
    assert len(fake.calls) == 2
    assert json.loads(client.cache_path_for("q").read_text())["elements"]


def test_overpass_runtime_error_in_cache_is_refetched_online_only(tmp_path):
    client, _ = overpass(tmp_path, [])
    client.cache_path_for("q").write_bytes(RUNTIME)
    offline, fake = overpass(tmp_path, [], offline=True)
    assert offline.fetch_query("q")["elements"] == [] and fake.calls == []
    online, fake = overpass(tmp_path, [GOOD])
    assert online.fetch_query("q")["elements"] and len(fake.calls) == 1


def test_overpass_answer_cut_while_reading_is_retried(tmp_path):
    client, fake = overpass(tmp_path, [Truncated(), GOOD])
    assert client.fetch_query("q")["elements"]
    assert len(fake.calls) == 2


# --- K1-06 : TileJSON --------------------------------------------------------------------------

class TileJsonNet:
    def __init__(self, answers) -> None:
        self.answers = list(answers)

    def get(self, url):
        return self.answers.pop(0)


def test_invalid_tilejson_never_overwrites_good_copy(tmp_path):
    c = WorldCache(tmp_path / "cache", 10**9, log=QUIET)
    good = json.dumps({"tiles": ["https://t.invalid/{z}/{x}/{y}.pbf"]}).encode()
    cached = c.root / "brut" / "tuiles" / "tilejson.json"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(good)
    old = time.time() - 2 * vt.TILEJSON_MAX_AGE_S
    os.utime(cached, (old, old))                        # copie trop vieille : redemandée
    src = vt.TileSource(c, TileJsonNet([b"<html>portail</html>"]), log=QUIET)
    assert src.template() == "https://t.invalid/{z}/{x}/{y}.pbf"
    assert cached.read_bytes() == good


def test_invalid_fresh_tilejson_in_cache_is_asked_again(tmp_path):
    c = WorldCache(tmp_path / "cache", 10**9, log=QUIET)
    cached = c.root / "brut" / "tuiles" / "tilejson.json"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"<html>")
    good = json.dumps({"tiles": ["https://t.invalid/{z}/{x}/{y}.pbf"]}).encode()
    src = vt.TileSource(c, TileJsonNet([good]), log=QUIET)
    assert src.template().startswith("https://t.invalid/")
    assert cached.read_bytes() == good


# --- K1-02 : tuile gzip coupée -----------------------------------------------------------------

def test_truncated_gzip_tile_is_an_mvt_error():
    data = gzip.compress(mvt.encode_tile({"transportation": []}) + b"x" * 200)
    with pytest.raises(mvt.MvtError):
        mvt.decode_tile(data[:len(data) // 2])
