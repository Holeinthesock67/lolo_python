"""Pack « Cols célèbres » livré dans le paquet (lot PK1) : manifeste, contrôle, installation sans réseau ni
écrasement, contenus de départ et écran Contenus (crédits). Faux paquet construit dans le dossier du test."""

import hashlib
import json

import pytest

from openride_core import catalog, contents, launch_compile, pack_bundle
from openride_core.contents import COLS_ID, STARTER_ID, ContentDirs, ContentService
from openride_core.demo_world import write_world
from test_contract_ipc import assert_valid

COLS = ("col-a", "col-b")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_bundle(root, cols=COLS):
    """Paquet `root/packs/cols_celebres` : traces, fiches, pack.toml et vrais .world compilés de ces traces."""
    pdir = root / "packs" / "cols_celebres"
    gpx = pdir / "gpx" / "cols_celebres"
    gpx.mkdir(parents=True)
    (gpx / "pack.toml").write_text('name = "Cols célèbres"\nlicense = "ODbL 1.0 (données OpenStreetMap)"\n',
                                   encoding="utf-8")
    for i, c in enumerate(cols):
        (gpx / f"{c}.gpx").write_text(f"<gpx>{c}</gpx>", encoding="utf-8")
        (gpx / f"{c}.toml").write_text(f'name = "Col {i}"\n', encoding="utf-8")
        world = write_world(pdir / "routes", c, 2000.0 + 500 * i, title=f"Col {i}")
        man = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
        man["source"] = {"gpx": f"{c}.gpx", "gpx_sha256": _sha(gpx / f"{c}.gpx")}
        (world / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
    pack_bundle.write_manifest(pdir, {"col-a": 42.0})
    return pdir


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENRIDE_PAQUET", str(tmp_path / "paquet"))
    return make_bundle(tmp_path / "paquet")


def test_manifest_lists_routes_sizes_hashes_and_credits(bundle):
    man = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in man["routes"]] == list(COLS)
    assert man["routes"][0]["build_s"] == 42.0 and "build_s" not in man["routes"][1]
    assert all(r["bytes"] > 0 for r in man["routes"])
    assert man["total_bytes"] == sum(f["bytes"] for f in man["files"])
    assert "manifest.json" not in {f["path"] for f in man["files"]}
    for word in ("OpenStreetMap", "ODbL", "Copernicus"):
        assert word in man["credits"]
    pack = pack_bundle.load()
    assert pack is not None and pack.folder == "cols_celebres" and pack_bundle.verify(pack) == []


def test_manifest_refuses_world_built_from_another_trace(bundle):
    (bundle / "gpx" / "cols_celebres" / "col-a.gpx").write_text("<gpx>autre</gpx>", encoding="utf-8")
    with pytest.raises(pack_bundle.BundleError, match="empreinte"):
        pack_bundle.write_manifest(bundle)


def test_no_bundle_means_none(tmp_path):
    assert pack_bundle.load(tmp_path / "rien") is None
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "manifest.json").write_text('{"format": 99}', encoding="utf-8")
    assert pack_bundle.load(tmp_path / "x") is None


def test_install_copies_once_and_routes_are_ready_without_compiling(bundle, tmp_path):
    pack = pack_bundle.load()
    gpx, routes = tmp_path / "GPX", tmp_path / "routes"
    seen = []
    copied_gpx, copied = pack_bundle.install(pack, gpx, routes, seen.append)
    assert copied_gpx and copied == list(COLS) and seen[-1] == 100
    assert (gpx / "cols_celebres" / "pack.toml").is_file()
    entries = {e.id: e for e in catalog.list_routes(routes, gpx)}
    assert all(entries[c].status == "ready" for c in COLS)   # même empreinte : pas de recompilation
    # Deuxième passage : rien n'est copié, rien n'est écrasé.
    mine = routes / "col-a.world" / "note.txt"
    mine.write_text("à moi", encoding="utf-8")
    assert pack_bundle.install(pack, gpx, routes) == (False, [])
    assert mine.read_text(encoding="utf-8") == "à moi"


def test_install_keeps_a_pack_built_from_the_network(bundle, tmp_path):
    """Pack déjà construit chez le joueur (autres traces) : ni ses traces ni ses parcours ne sont remplacés."""
    gpx, routes = tmp_path / "GPX", tmp_path / "routes"
    mine = gpx / "cols-celebres"
    mine.mkdir(parents=True)
    (mine / "pack.toml").write_text('name = "Cols célèbres"\n', encoding="utf-8")
    (mine / "col-a.gpx").write_text("<gpx>reseau</gpx>", encoding="utf-8")
    (mine / "col-b.gpx").write_text((bundle / "gpx" / "cols_celebres" / "col-b.gpx").read_text(encoding="utf-8"),
                                    encoding="utf-8")
    copied_gpx, copied = pack_bundle.install(pack_bundle.load(), gpx, routes)
    assert not copied_gpx and copied == ["col-b"]
    assert not (gpx / "cols_celebres").exists()
    assert (mine / "col-a.gpx").read_text(encoding="utf-8") == "<gpx>reseau</gpx>"


def test_damaged_bundle_installs_nothing(bundle, tmp_path):
    target = next((bundle / "routes" / "col-b.world").iterdir())
    target.write_bytes(target.read_bytes()[:-1] + b"#")
    pack = pack_bundle.load()
    assert pack_bundle.verify(pack)
    with pytest.raises(pack_bundle.BundleError, match="abîmé"):
        pack_bundle.install(pack, tmp_path / "GPX", tmp_path / "routes")
    assert not (tmp_path / "GPX").exists() and not (tmp_path / "routes").exists()


def _service(tmp_path, monkeypatch):
    monkeypatch.setattr(contents, "_demo_names", lambda: [])
    monkeypatch.setattr(contents, "_velodrome_names", lambda: [])
    monkeypatch.setattr(launch_compile, "compiler_base_cmd", lambda: pytest.fail("compilateur appelé"))
    return ContentService(ContentDirs(tmp_path / "Workouts", tmp_path / "Plans", tmp_path / "routes",
                                      gpx=tmp_path / "GPX"))


def test_starter_installs_the_bundled_pack_without_network(bundle, tmp_path, monkeypatch):
    svc = _service(tmp_path, monkeypatch)
    items = {it["id"]: it for it in svc.items()}
    assert "2 cols célèbres" in items[STARTER_ID]["detail"] and items[STARTER_ID]["state"] == "missing"
    cols = items[COLS_ID]
    assert cols["network"] is False and cols["state"] == "missing" and "livrées avec le jeu" in cols["detail"]
    for word in ("OpenStreetMap", "ODbL", "Copernicus"):
        assert word in cols["detail"]
    job = svc.start(STARTER_ID)
    svc.run(job)
    assert not job.failed and "2 col(s) célèbre(s)" in job.message, job.message
    msg = svc.message(3)
    assert_valid(msg)
    items = {it["id"]: it for it in msg["items"]}
    assert items[STARTER_ID]["state"] == "installed" and items[COLS_ID]["state"] == "installed"
    assert items[COLS_ID]["size_mb"] is not None
    assert not any(it["id"].startswith("routes:") and it["id"] != COLS_ID for it in msg["items"])


def test_cols_line_installs_from_the_bundle(bundle, tmp_path, monkeypatch):
    svc = _service(tmp_path, monkeypatch)
    job = svc.start(COLS_ID)
    svc.run(job)
    assert not job.failed and job.message == "Pack installé : 2 col(s) sur 2."


def test_starter_reports_a_damaged_bundle(bundle, tmp_path, monkeypatch):
    (bundle / "gpx" / "cols_celebres" / "col-a.gpx").write_text("<gpx>abîmé</gpx>", encoding="utf-8")
    svc = _service(tmp_path, monkeypatch)
    job = svc.start(STARTER_ID)
    svc.run(job)
    assert not job.failed and "Cols célèbres impossibles" in job.message


def test_network_pack_line_also_carries_credits(tmp_path, monkeypatch):
    recipes = tmp_path / "pkg" / "route_packs" / "cols_celebres"
    recipes.mkdir(parents=True)
    (recipes / "col0.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(contents, "_compiler_package", lambda: tmp_path / "pkg")
    item = contents.cols_item(ContentDirs(tmp_path / "W", tmp_path / "P", tmp_path / "R", gpx=tmp_path / "GPX"))
    assert item["network"] is True and "ODbL" in item["detail"] and "Copernicus" in item["detail"]


def test_cli_info_and_verify(bundle, capsys):
    assert pack_bundle.main(["verify", str(bundle)]) == 0
    assert pack_bundle.main(["info", str(bundle)]) == 0
    out = capsys.readouterr().out
    assert "col-a" in out and "construit en 42.0 s" in out and "Total : 2 col(s)" in out


FAKE_COMPILER = '''
import hashlib, json, shutil, sys
from pathlib import Path
from openride_core.demo_world import write_world
from openride_core.pack_bundle import route_id
args = sys.argv[1:]
def opt(name):
    return Path(args[args.index(name) + 1])
if args[0] == "route-pack-build":
    cid = route_id(args[args.index("--only") + 1] + ".gpx")
    if cid == "ticlio":
        print("  refusé : ticlio : longueur hors tolérance", file=sys.stderr)
        sys.exit(1)
    out = opt("--out") / "cols-celebres"   # comme route_recipe.build_pack : nom normalisé (tiret)
    out.mkdir(parents=True, exist_ok=True)
    (out / "pack.toml").write_text('name = "Cols célèbres"\\n', encoding="utf-8")
    (out / f"{cid}.gpx").write_text(f"<gpx>{cid}</gpx>", encoding="utf-8")
    print(f"  {cid} : 10.0 km, 800 m de dénivelé positif", file=sys.stderr)
elif args[0] == "route-pack-install":
    shutil.copytree(Path(args[1]), opt("--gpx-dir") / "cols-celebres", dirs_exist_ok=True)
elif args[0] == "build":
    gpx = Path(args[1])
    world = write_world(opt("--out"), route_id(gpx.name), 3000.0)
    man = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    man["source"] = {"gpx": gpx.name, "gpx_sha256": hashlib.sha256(gpx.read_bytes()).hexdigest()}
    (world / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
'''


def test_build_script_with_a_fake_compiler(tmp_path):
    """`scripts/build_pack_base.sh` de bout en bout : un col refusé, deux rangés, manifeste contrôlé."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    project = Path(__file__).resolve().parents[2]
    fake = tmp_path / "compilateur.py"
    fake.write_text(FAKE_COMPILER, encoding="utf-8")
    out = tmp_path / "paquet"
    env = dict(os.environ, OPENRIDE_COMPILER=f"{sys.executable} {fake}", OPENRIDE_PYTHON=sys.executable,
               ONLY="alpe_d_huez,ticlio,teide_vilaflor", TMPDIR=str(tmp_path))
    proc = subprocess.run(["bash", str(project / "scripts" / "build_pack_base.sh"), str(out)], env=env,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 1, proc.stdout + proc.stderr   # ticlio refusé
    assert "REFUSÉ : ticlio" in proc.stdout and "1 col(s) refusé(s) : ticlio" in proc.stdout
    pack = pack_bundle.load(out / "packs" / "cols_celebres")
    assert pack is not None and pack.folder == "cols-celebres"
    assert [r.id for r in pack.routes] == ["alpe-d-huez", "teide-vilaflor"]
    assert pack_bundle.verify(pack) == []
    assert all("build_s" in r for r in pack.manifest["routes"])
    assert "Total : 2 col(s)" in proc.stdout
    assert not any(p.name.startswith("openride-pack-base") for p in tmp_path.iterdir())   # travail effacé
