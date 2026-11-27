"""Revue de code vague 4, constats de confort K4-07, K4-08 et K4-09 (écriture des `.world`, `verify`)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import straight_north
from openride_compiler import atomic_dir, cli, writer
from openride_compiler.verify import verify_world


def run(*argv) -> int:
    return cli.main([str(a) for a in argv])


def dead_pid() -> int:
    """Pid d'un processus fini (et récolté) : il n'existe plus."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    assert not atomic_dir.pid_alive(proc.pid)
    return proc.pid


# --- K4-07 : temporaires laissés par une compilation tuée ------------------------------------


def test_pid_alive() -> None:
    assert atomic_dir.pid_alive(os.getpid())
    assert not atomic_dir.pid_alive(0)
    assert not atomic_dir.pid_alive(dead_pid())


def test_write_world_efface_les_temporaires_d_un_processus_tue(tmp_path: Path) -> None:
    routes = tmp_path / "routes"
    routes.mkdir()
    pid = dead_pid()
    tmp_mort = routes / f".col.world.tmp-{pid}"
    (tmp_mort / "terrain").mkdir(parents=True)
    (tmp_mort / "terrain" / "tile_0_0.f32").write_bytes(b"\0" * 64)
    old_mort = routes / f".col.world.old-{pid}"
    old_mort.mkdir()
    vivant = routes / f".col.world.tmp-{os.getppid()}"   # processus vivant : on n'y touche pas
    vivant.mkdir()
    autre = routes / f".autre.world.tmp-{pid}"            # autre parcours : pas notre affaire
    autre.mkdir()

    writer.write_world(routes, "col", {"name": "col"}, {"n": 2})
    writer.write_world(routes, "col", {"name": "col"}, {"n": 3}, force=True)

    assert not tmp_mort.exists() and not old_mort.exists()
    assert vivant.is_dir() and autre.is_dir()
    assert json.loads((routes / "col.world" / "route.json").read_text()) == {"n": 3}
    assert sorted(p.name for p in routes.iterdir()) == sorted(
        ["col.world", vivant.name, autre.name])


def test_old_orphelin_sans_original_remis_en_place(tmp_path: Path) -> None:
    """Tué entre les deux renommages : l'ancien parcours est dans `.old-<pid>`, il revient."""
    routes = tmp_path / "routes"
    old_mort = routes / f".col.world.old-{dead_pid()}"
    old_mort.mkdir(parents=True)
    (old_mort / "route.json").write_text('{"ancien": true}')
    touched = atomic_dir.clean_stale(routes / "col.world")
    assert touched == [old_mort]
    assert json.loads((routes / "col.world" / "route.json").read_text()) == {"ancien": True}


def test_couche_terrain_et_manifeste_nettoient_aussi(tmp_path: Path) -> None:
    world = tmp_path / "col.world"
    world.mkdir()
    pid = dead_pid()
    for name in (f".terrain.tmp-{pid}", f".terrain.old-{pid}", f".biome.tmp-{pid}"):
        (world / name).mkdir()
    (world / f".manifest.json.tmp-{pid}").write_text("{")
    (world / "terrain").mkdir()
    from openride_compiler.terrain import replace_terrain_dir
    replace_terrain_dir(world, {})
    writer.replace_manifest(world, {"name": "col"})
    names = sorted(p.name for p in world.iterdir())
    assert names == [f".biome.tmp-{pid}", "manifest.json", "terrain"]   # biome : nettoyé à son tour


def test_echec_d_ecriture_garde_l_ancien(tmp_path: Path) -> None:
    routes = tmp_path / "routes"
    writer.write_world(routes, "col", {"name": "col"}, {"n": 2})

    def casse(folder: Path) -> None:
        raise RuntimeError("panne")

    with pytest.raises(RuntimeError):
        writer.write_world(routes, "col", {"name": "col"}, {"n": 3}, force=True, extra=casse)
    assert json.loads((routes / "col.world" / "route.json").read_text()) == {"n": 2}
    assert [p.name for p in routes.iterdir()] == ["col.world"]


# --- K4-08 : fsync avant le renommage, recompilation des parcours invalides ------------------


def test_fsync_de_chaque_fichier_avant_renommage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    synced: list[str] = []
    real = atomic_dir.fsync_path

    def spy(path: Path) -> None:
        synced.append(Path(path).name)
        real(path)

    real_rename = Path.rename
    renamed_after: list[list[str]] = []

    def rename_spy(self: Path, target):
        renamed_after.append(list(synced))
        return real_rename(self, target)

    monkeypatch.setattr(atomic_dir, "fsync_path", spy)
    monkeypatch.setattr(Path, "rename", rename_spy)
    writer.write_world(tmp_path, "col", {"name": "col"}, {"n": 2})
    assert {"route.json", "manifest.json"} <= set(renamed_after[0])


def test_build_all_recompile_un_parcours_invalide(make_gpx, tmp_path: Path,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    gpx_dir, routes_dir = tmp_path / "GPX", tmp_path / "routes"
    gpx_dir.mkdir()
    gpx = make_gpx("GPX/col.gpx", *straight_north(length=1000.0))
    assert run("build", gpx, "--out", routes_dir, "--layers", "route") == 0
    route_json = routes_dir / "col.world" / "route.json"
    route_json.write_text("")                     # coupure de courant juste après la compilation
    assert verify_world(routes_dir / "col.world")
    capsys.readouterr()

    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes_dir, "--layers", "route") == 0
    assert "1 compilé(s)" in capsys.readouterr().out
    assert verify_world(routes_dir / "col.world") == []


def test_build_all_ignore_un_invalide_sans_trace(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    gpx_dir, routes_dir = tmp_path / "GPX", tmp_path / "routes"
    gpx_dir.mkdir()
    (routes_dir / "seul.world").mkdir(parents=True)
    (routes_dir / "seul.world" / "manifest.json").write_text("{")
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", routes_dir) == 0
    assert "0 compilé(s)" in capsys.readouterr().out


# --- K4-09 : `verify` contrôle `bank_deg` comme le core ----------------------------------------


def _world_with_bank(make_gpx, tmp_path: Path, bank) -> Path:
    gpx = make_gpx("col.gpx", *straight_north(length=1000.0))
    assert run("build", gpx, "--out", tmp_path / "routes", "--layers", "route") == 0
    world = tmp_path / "routes" / "col.world"
    route = json.loads((world / "route.json").read_text())
    route["bank_deg"] = bank(route["n"])
    (world / "route.json").write_text(json.dumps(route))
    return world


@pytest.mark.parametrize("bank, attendu", [
    (lambda n: [0.0] * n, None),
    (lambda n: [12.0] * (n - 1) + [50.0], None),
    (lambda n: None, None),
    (lambda n: [0.0] * (n - 1) + [50.5], "hors de ± 50°"),
    (lambda n: [-60.0] * n, "hors de ± 50°"),
    (lambda n: [0.0] * (n - 1), "doit avoir"),
    (lambda n: 3.0, "doit avoir"),
    (lambda n: [0.0] * (n - 1) + ["x"], "non numériques"),
])
def test_verify_bank_deg(make_gpx, tmp_path: Path, bank, attendu) -> None:
    world = _world_with_bank(make_gpx, tmp_path, bank)
    problems = verify_world(world)
    if attendu is None:
        assert problems == []
    else:
        assert any("bank_deg" in p and attendu in p for p in problems), problems


@pytest.mark.parametrize("bank", [
    lambda n: [0.0] * (n - 1) + [50.5],
    lambda n: [0.0] * (n - 1),
])
def test_verify_et_core_d_accord_sur_bank_deg(make_gpx, tmp_path: Path, bank) -> None:
    core_route = pytest.importorskip("openride_core.route")
    world = _world_with_bank(make_gpx, tmp_path, bank)
    assert verify_world(world)
    with pytest.raises(core_route.WorldError):
        core_route.load_world(world)


def test_contrat_ne_promet_plus_de_sommes_de_controle() -> None:
    contrat = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "world_format_v1.md"
    texte = contrat.read_text(encoding="utf-8")
    assert "sommes de contrôle SHA-256 optionnelles du manifeste et" not in texte
    validation = next(l for l in texte.splitlines() if l.startswith("**Validation.** `openride-compiler verify"))
    assert "bank_deg" in validation
