"""Parité entre le catalogue du core et le repli du compilateur (lot J6).

`openride-compiler list` et `build-all` utilisent `openride_core.catalog.list_routes` quand le
core est installé, sinon `cli.fallback_catalog`. Les deux doivent donner le même résultat, champ
par champ, dans le même ordre. Seul le texte de l'erreur d'un `.world` invalide peut différer
(`load_world` côté core, `verify_world` côté compilateur).
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import require_core, straight_north
from openride_compiler import cli
from openride_compiler.writer import normalize_name

core_catalog = require_core("openride_core.catalog")
core_demo = require_core("openride_core.demo_world")


def run(*argv) -> int:
    return cli.main([str(a) for a in argv])


def build(make_gpx, routes: Path, name: str, length: float = 1000.0, *extra: str) -> Path:
    gpx = make_gpx(f"GPX/{name}", *straight_north(length=length))
    assert run("build", gpx, "--out", routes, "--layers", "route", *extra) == 0
    return gpx


# Situations du cahier J6 §4 : chacune prépare `routes/` et `GPX/` dans tmp_path. Chaque trace a
# une longueur différente pour que deux GPX n'aient jamais le même SHA-256 dans « toutes ».

def s_compiled(make_gpx, routes, tmp):
    build(make_gpx, routes, "col_ok.gpx")
    gpx = make_gpx("GPX/relief.gpx", *straight_north(length=800.0))
    assert run("build", gpx, "--out", routes) == 0              # avec terrain
    build(make_gpx, routes, "aller_retour.gpx", 600.0, "--out-and-back")


def s_modified(make_gpx, routes, tmp):
    build(make_gpx, routes, "modifie.gpx", 1010.0)
    make_gpx("GPX/modifie.gpx", *straight_north(length=1200.0))


def s_never_compiled(make_gpx, routes, tmp):
    make_gpx("GPX/Nouveau Parcours Été.gpx", *straight_north(length=500.0))
    make_gpx("GPX/AUTRE.GPX", *straight_north(length=510.0))
    (tmp / "GPX" / "notes.txt").write_text("pas une trace", encoding="utf-8")


def s_renamed(make_gpx, routes, tmp):
    gpx = build(make_gpx, routes, "ancien_nom.gpx", 1020.0)
    gpx.rename(gpx.with_name("nouveau_nom.gpx"))               # retrouvé par SHA-256


def s_corrupted(make_gpx, routes, tmp):
    bad = routes / "casse.world"
    bad.mkdir(parents=True)
    (bad / "manifest.json").write_text("{json invalide", encoding="utf-8")
    gpx = build(make_gpx, routes, "sans_route.gpx", 1030.0)
    (routes / "sans-route.world" / "route.json").unlink()      # manifeste lisible, route absente
    (routes / "vide.world").mkdir()
    assert gpx.exists()


def s_gpx_gone(make_gpx, routes, tmp):
    build(make_gpx, routes, "orphelin.gpx", 1040.0).unlink()
    gpx = build(make_gpx, routes, "sans_sha.gpx", 1050.0)
    manifest_path = routes / "sans-sha.world" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source"]["gpx_sha256"] = None                    # ancien format : outdated
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert gpx.exists()


def s_demo(make_gpx, routes, tmp):
    core_demo.write_world(routes, core_demo.DEMO_NAME, core_demo.DEMO_LENGTH_M)   # route et segments
    make_gpx("GPX/demo.gpx", *straight_north(length=520.0))  # même id : rattaché à demo
    (routes / ".cache.world").mkdir()                          # dossier caché : ignoré


def s_empty(make_gpx, routes, tmp):
    shutil.rmtree(routes, ignore_errors=True)                  # aucun dossier : demo seul


def s_garmin(make_gpx, routes, tmp):
    """Lot O5 : FIT, TCX compressé, archive .zip, conflit d'identifiant, fichier non trace."""
    import gzip
    import io
    import zipfile

    from test_track_formats import fit_bytes, tcx_activity

    gpx_dir = tmp / "GPX"
    gpx = make_gpx("GPX/garmin_fit.gpx", *straight_north(length=530.0))
    gpx.with_name("garmin_fit.FIT").write_bytes(b"conflit : la trace .gpx gagne")
    (gpx_dir / "sortie_fit.fit").write_bytes(fit_bytes([45.0, 45.006], [6.0, 6.0], [1000.0, 1001.0]))
    (gpx_dir / "Sortie TCX.tcx.gz").write_bytes(gzip.compress(tcx_activity([45.0, 45.007], [6.0, 6.0], [1000.0, 1002.0]).encode()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.fit", fit_bytes([45.0, 45.008], [6.0, 6.0], [1000.0, 1003.0]))
    (gpx_dir / "export.zip").write_bytes(buf.getvalue())
    (gpx_dir / "seul.gz").write_bytes(b"pas une trace")
    assert run("build", gpx_dir / "export.zip", "--out", routes, "--layers", "route") == 0


def s_library(make_gpx, routes, tmp):
    """Lot O15 : pack en sous-dossier, fiches .toml (valide, invalide), .world sans fiche calculée."""
    gpx = build(make_gpx, routes, "fiche_ok.gpx", 1060.0)
    gpx.with_name("fiche_ok.toml").write_text('name = "Fiche"\ntags = ["col"]\n', encoding="utf-8")
    (tmp / "GPX" / "pack-essai").mkdir()
    make_gpx("GPX/pack-essai/Col Pack.gpx", *straight_north(length=1070.0))
    (tmp / "GPX" / "pack-essai" / "Col Pack.toml").write_text('region = "Vosges"\n', encoding="utf-8")
    (tmp / "GPX" / "pack-essai" / "pack.toml").write_text('name = "Essai"\n', encoding="utf-8")
    bad = make_gpx("GPX/fiche_ko.gpx", *straight_north(length=1080.0))
    bad.with_name("fiche_ko.toml").write_text('tags = "pas une liste"\n', encoding="utf-8")
    old = build(make_gpx, routes, "ancien_world.gpx", 1090.0)
    manifest_path = routes / "ancien-world.world" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["stats"]                                      # compilé avant le lot O15
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert old.exists()


SITUATIONS = [s_compiled, s_modified, s_never_compiled, s_renamed, s_corrupted, s_gpx_gone,
              s_demo, s_garmin, s_library, s_empty]


def _rows(entries) -> list[dict]:
    rows = []
    for e in entries:
        row = dataclasses.asdict(e)
        row["error"] = row["error"] is not None
        rows.append(row)
    return rows


def _fallback(monkeypatch, routes: Path, gpx_dir: Path) -> list:
    """Passe par `_catalog_entries` avec le core masqué, comme sur un poste sans core."""
    monkeypatch.setitem(sys.modules, "openride_core.catalog", None)
    entries = cli._catalog_entries(routes, gpx_dir)
    monkeypatch.undo()
    assert all(isinstance(e, cli.CatalogEntry) for e in entries)
    return entries


@pytest.mark.parametrize("situation", [*SITUATIONS, "toutes"],
                         ids=[*(f.__name__[2:] for f in SITUATIONS), "toutes"])
def test_fallback_matches_core(situation, make_gpx, tmp_path: Path, monkeypatch) -> None:
    routes, gpx_dir = tmp_path / "routes", tmp_path / "GPX"
    routes.mkdir()
    gpx_dir.mkdir()
    for prepare in (SITUATIONS[:-1] if situation == "toutes" else [situation]):
        prepare(make_gpx, routes, tmp_path)

    core = core_catalog.list_routes(routes, gpx_dir)
    fallback = _fallback(monkeypatch, routes, gpx_dir)
    assert _rows(fallback) == _rows(core)
    assert core[0].id == core_demo.DEMO_NAME


def test_expected_statuses_of_combined_situation(make_gpx, tmp_path: Path, monkeypatch) -> None:
    """Garde-fou : la parité ne vaut que si les situations donnent bien les statuts attendus."""
    routes, gpx_dir = tmp_path / "routes", tmp_path / "GPX"
    routes.mkdir()
    gpx_dir.mkdir()
    for prepare in SITUATIONS[:-1]:
        prepare(make_gpx, routes, tmp_path)
    by_id = {e.id: e for e in _fallback(monkeypatch, routes, gpx_dir)}
    expected = {
        "demo": "ready", "col-ok": "ready", "relief": "ready", "aller-retour": "ready",
        "modifie": "outdated", "nouveau-parcours-ete": "to_compile", "autre": "to_compile",
        "ancien-nom": "ready", "casse": "invalid", "sans-route": "invalid", "vide": "invalid",
        "orphelin": "ready", "sans-sha": "outdated",
        "garmin-fit": "to_compile", "sortie-fit": "to_compile", "sortie-tcx": "to_compile", "export": "ready",
        "fiche-ok": "ready", "col-pack": "to_compile", "fiche-ko": "to_compile", "ancien-world": "ready",
    }
    assert {k: e.status for k, e in by_id.items()} == expected
    assert by_id["ancien-nom"].gpx_path == gpx_dir / "nouveau_nom.gpx"
    assert by_id["sans-route"].gpx_path == gpx_dir / "sans_route.gpx"
    assert by_id["orphelin"].gpx_path is None
    assert by_id["demo"].gpx_path == gpx_dir / "demo.gpx"
    assert by_id["relief"].has_terrain and not by_id["col-ok"].has_terrain
    assert by_id["aller-retour"].route_type == "out_and_back"
    assert by_id["fiche-ok"].library == {"name": "Fiche", "tags": ["col"]}
    assert by_id["col-pack"].library == {"region": "Vosges"}
    assert by_id["fiche-ko"].library is None
    assert by_id["ancien-world"].stats["gain_m"] == pytest.approx(0.05 * 1090.0, abs=2.0)
    assert by_id["fiche-ok"].stats["distance_m"] == pytest.approx(1060.0, abs=5.0)
    assert by_id["nouveau-parcours-ete"].stats is None


def test_route_stats_module_is_identical_in_core() -> None:
    """`route_stats.py` est copié tel quel dans le compilateur (lot O15) : fiches identiques sans le core."""
    from openride_compiler import route_stats

    core_stats = require_core("openride_core.route_stats")
    assert Path(route_stats.__file__).read_bytes() == Path(core_stats.__file__).read_bytes()


NAMES = [
    "Col du Galibier", "Alpe d'Huez", "  espaces  ", "Été à Évian", "ÇA-VA", "über_straße",
    "Mont Ventoux (2024)", "---", "", "Œuvre", "ß", "tour_de_l'île", "A.B.C", "café__crème",
    "日本語", "Ñandú 3", "x" * 80, "L'Étape du Tour #3", "MAJUSCULES", "déjà-vu..",
]


@pytest.mark.parametrize("name", NAMES)
def test_normalize_name_matches_core(name: str) -> None:
    assert normalize_name(name) == core_catalog._normalize_name(name)


@pytest.mark.parametrize("name", ["col.gpx", "COL.Fit", "a.fit.gz", "b.TCX.gz", "c.tcx", "d.zip",
                                  "e.gpx.gz", "f.gz", ".zip", "notes.txt", "x.fit.zip"])
def test_track_rules_match_core(name: str) -> None:
    from openride_compiler import track_formats

    assert track_formats.TRACK_SUFFIXES == core_catalog.TRACK_SUFFIXES
    assert track_formats.track_stem(name) == core_catalog.track_stem(name)


def test_conflicts_match_core(make_gpx, tmp_path: Path) -> None:
    gpx_dir = tmp_path / "GPX"
    for name in ("col.zip", "col.fit", "Col.gpx", "col.tcx.gz", "autre.fit"):
        gpx_dir.mkdir(exist_ok=True)
        (gpx_dir / name).write_bytes(b"x")
    from openride_compiler import track_formats

    assert track_formats.scan_tracks(gpx_dir) == core_catalog.scan_tracks(gpx_dir)
    kept, conflicts = core_catalog.scan_tracks(gpx_dir)
    assert kept == [gpx_dir / "Col.gpx", gpx_dir / "autre.fit"]
    assert [lost.name for lost, _ in conflicts] == ["col.fit", "col.tcx.gz", "col.zip"]


def test_demo_constants_and_fields_match_core() -> None:
    assert (cli.DEMO_NAME, cli.DEMO_LENGTH_M) == (core_demo.DEMO_NAME, core_demo.DEMO_LENGTH_M)
    assert [f.name for f in dataclasses.fields(cli.CatalogEntry)] == \
        [f.name for f in dataclasses.fields(core_catalog.RouteEntry)]
