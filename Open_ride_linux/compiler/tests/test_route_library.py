"""Bibliothèque de parcours (lot O15) : fiche dans le manifeste, tri et filtres de `list`, packs."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import jsonschema
import pytest

from conftest import WORLD_CONTRACTS, gpx_text, straight_north, to_latlon
from openride_compiler import cli
from openride_compiler.errors import CompileError
from openride_compiler.route_pack import install_pack, list_packs


def run(*argv) -> int:
    return cli.main([str(a) for a in argv])


def track_text(length: float) -> str:
    x, z, alt = straight_north(length=length)
    lat, lon = to_latlon(x, z)
    return gpx_text(lat, lon, list(alt))


PACK = {   # trace : (longueur en m, fiche) ; dénivelé = 5 % de la longueur (MNT de test)
    "Col Long.gpx": (1500.0, 'name = "Col long"\ntags = ["col", "classique"]\nregion = "Massif d\'essai"\n'),
    "Col Court.gpx": (900.0, 'name = "Col court"\ntags = ["col"]\n'),
    "Bout Plat.gpx": (1200.0, 'name = "Bout plat"\ntags = ["plat"]\n'),
}


def pack_zip(path: Path, extra: dict[str, str] | None = None, sheets: bool = True) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("essai/pack.toml", 'name = "Pack d\'essai"\ndescription = "Traces synthétiques"\n'
                                       'license = "CC0"\n')
        for name, (length, sheet) in PACK.items():
            zf.writestr(f"essai/{name}", track_text(length))
            if sheets:
                zf.writestr(f"essai/{name[:-4]}.toml", sheet)
        for name, text in (extra or {}).items():
            zf.writestr(name, text)
    return path


def test_build_writes_stats_and_library(make_gpx, tmp_path: Path) -> None:
    gpx = make_gpx("col.gpx", *straight_north(length=2000.0))
    gpx.with_name("col.toml").write_text('name = "Col"\ntags = ["col"]\n', encoding="utf-8")
    assert run("build", gpx, "--out", tmp_path / "routes", "--layers", "route") == 0
    manifest = json.loads((tmp_path / "routes" / "col.world" / "manifest.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, json.loads((WORLD_CONTRACTS / "manifest.schema.json").read_text(encoding="utf-8")))
    st = manifest["stats"]
    assert st["version"] == 1 and st["distance_m"] == pytest.approx(2000.0, abs=5.0)
    assert st["gain_m"] == pytest.approx(100.0, abs=2.0)
    assert st["max_grade_pct"] == pytest.approx(5.0, abs=0.3)
    assert st["main_climb"]["category"] == "4"                  # 2 000 m × 5 % = 10 000
    assert manifest["library"] == {"name": "Col", "tags": ["col"]}
    assert run("verify", tmp_path / "routes" / "col.world") == 0


def test_build_ignores_invalid_sheet(make_gpx, tmp_path: Path, capsys) -> None:
    gpx = make_gpx("col.gpx", *straight_north(length=800.0))
    gpx.with_name("col.toml").write_text('region = "45.10, 6.05"\n', encoding="utf-8")
    assert run("build", gpx, "--out", tmp_path / "routes", "--layers", "route") == 0
    manifest = json.loads((tmp_path / "routes" / "col.world" / "manifest.json").read_text(encoding="utf-8"))
    assert "library" not in manifest
    assert "fiche ignorée" in capsys.readouterr().err


def test_pack_install_build_and_list(tmp_path: Path, capsys) -> None:
    gpx_dir, routes = tmp_path / "GPX", tmp_path / "routes"
    src = pack_zip(tmp_path / "essai.zip")
    assert run("route-pack-install", src, "--gpx-dir", gpx_dir) == 0
    assert sorted(p.name for p in (gpx_dir / "pack-d-essai").iterdir()) == sorted(
        [*PACK, *(n[:-4] + ".toml" for n in PACK), "pack.toml"])
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--layers", "route") == 0
    capsys.readouterr()

    assert run("list", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--tag", "col", "--sort", "deniv",
               "--json", "--ftp", "250") == 0
    first = capsys.readouterr().out
    rows = json.loads(first)
    assert [r["id"] for r in rows] == ["col-court", "col-long"]
    assert [r["library"]["tags"] for r in rows] == [["col"], ["classique", "col"]]
    assert rows[1]["gpx"] == "pack-d-essai/Col Long.gpx" and rows[1]["status"] == "ready"
    assert rows[0]["stats"]["gain_m"] < rows[1]["stats"]["gain_m"]
    assert rows[0]["power_w"] == 250 and rows[0]["duration_s"] > 0
    assert run("list", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--tag", "col", "--sort", "deniv",
               "--json", "--ftp", "250") == 0
    assert capsys.readouterr().out == first                    # sortie JSON stable

    assert run("list", "--gpx-dir", gpx_dir, "--routes-dir", routes, "--sort", "distance", "--reverse",
               "--min-km", "0.95") == 0
    out = capsys.readouterr().out
    assert out.index("col-long") < out.index("bout-plat") and "col-court" not in out and "[classique,col]" in out

    assert run("route-pack-list", "--gpx-dir", gpx_dir, "--json") == 0
    assert json.loads(capsys.readouterr().out) == [{"id": "pack-d-essai", "tracks": 3, "name": "Pack d'essai",
                                                    "description": "Traces synthétiques", "license": "CC0"}]


@pytest.mark.parametrize("extra,needle", [
    ({"../evil.gpx": "<gpx/>"}, "chemin interdit"),
    ({"essai/notes.sh": "echo"}, "non pris en charge"),
    ({"essai/Seule.toml": 'tags = ["col"]\n'}, "fiche sans trace"),
    ({"essai/sous/x.gpx": "<gpx/>"}, "sous-dossier interdit"),
    ({"essai/col-long.fit": "x"}, "même parcours"),
])
def test_refused_pack_writes_nothing(tmp_path: Path, extra: dict, needle: str) -> None:
    gpx_dir = tmp_path / "GPX"
    gpx_dir.mkdir()
    with pytest.raises(CompileError, match=needle):
        install_pack(pack_zip(tmp_path / "mauvais.zip", extra), gpx_dir)
    assert list(gpx_dir.iterdir()) == []


def test_invalid_sheet_refused(tmp_path: Path) -> None:
    src = tmp_path / "dossier"
    src.mkdir()
    (src / "Col.gpx").write_text(track_text(600.0), encoding="utf-8")
    (src / "Col.toml").write_text('region = "48.12; 7.34"\n', encoding="utf-8")
    with pytest.raises(CompileError, match="coordonnées"):
        install_pack(src, tmp_path / "GPX")
    assert not (tmp_path / "GPX").exists() or list((tmp_path / "GPX").iterdir()) == []


def test_symlink_refused(tmp_path: Path) -> None:
    src = tmp_path / "dossier"
    src.mkdir()
    (src / "Col.gpx").write_text(track_text(600.0), encoding="utf-8")
    (src / "lien.gpx").symlink_to(src / "Col.gpx")
    with pytest.raises(CompileError, match="lien symbolique"):
        install_pack(src, tmp_path / "GPX")


def test_force_replaces_and_name_option(tmp_path: Path) -> None:
    gpx_dir = tmp_path / "GPX"
    src = pack_zip(tmp_path / "essai.zip", sheets=False)
    name, count, target = install_pack(src, gpx_dir, name="Mes Cols")
    assert (name, count, target) == ("mes-cols", 3, gpx_dir / "mes-cols")
    with pytest.raises(CompileError, match="déjà installé"):
        install_pack(src, gpx_dir, name="Mes Cols")
    (target / "Bout Plat.gpx").unlink()
    install_pack(src, gpx_dir, name="Mes Cols", force=True)
    assert (target / "Bout Plat.gpx").is_file()
    assert sorted(p.name for p in gpx_dir.iterdir()) == ["mes-cols"]   # aucun dossier temporaire


def test_pack_without_track_or_bad_meta(tmp_path: Path) -> None:
    src = tmp_path / "vide"
    src.mkdir()
    (src / "pack.toml").write_text('name = "Vide"\n', encoding="utf-8")
    with pytest.raises(CompileError, match="aucune trace"):
        install_pack(src, tmp_path / "GPX")
    (src / "Col.gpx").write_text(track_text(600.0), encoding="utf-8")
    (src / "pack.toml").write_text('auteur = "x"\n', encoding="utf-8")
    with pytest.raises(CompileError, match="clé"):
        install_pack(src, tmp_path / "GPX")


def test_zip_size_limit(tmp_path: Path, monkeypatch) -> None:
    from openride_compiler import route_pack

    monkeypatch.setattr(route_pack, "MAX_PACK_BYTES", 1000)
    with pytest.raises(CompileError, match="trop volumineuse"):
        install_pack(pack_zip(tmp_path / "gros.zip"), tmp_path / "GPX")


def test_list_packs_empty_and_broken(tmp_path: Path) -> None:
    assert list_packs(tmp_path / "absent") == []
    (tmp_path / "GPX" / "casse").mkdir(parents=True)
    (tmp_path / "GPX" / "casse" / "pack.toml").write_text("x = [", encoding="utf-8")
    [info] = list_packs(tmp_path / "GPX")
    assert info["id"] == "casse" and info["tracks"] == 0 and "invalide" in info["error"]
