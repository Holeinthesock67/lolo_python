"""Packs depuis « Réglages › Contenus » (lot O29) : pack des cols, archives de thèmes et de parcours,
thèmes installés, place disque. Le compilateur est remplacé par un faux script (aucun réseau)."""

import json
import sys
import zipfile

from openride_core import contents, launch_compile
from openride_core.contents import COLS_ID, ContentDirs, ContentService
from test_contract_ipc import assert_valid

FAKE_COMPILER = '''
import json, sys
from pathlib import Path
args = sys.argv[1:]
Path(sys.argv[0]).with_name("appels.jsonl").open("a").write(json.dumps(args) + "\\n")
def opt(name):
    return Path(args[args.index(name) + 1])
if args[0] == "route-pack-build":
    gpx = opt("--gpx-dir") / "cols_celebres"
    gpx.mkdir(parents=True, exist_ok=True)
    (gpx / "pack.toml").write_text('name = "Cols célèbres"\\n')
    for i in range(3):
        print(f"  col{i} : 10.0 km, 800 m de dénivelé positif", file=sys.stderr, flush=True)
        (gpx / f"col{i}.gpx").write_text("<gpx/>")
    print("  refusé : col3 : point hors route", file=sys.stderr)
    sys.exit(1)
if args[0] == "theme-install":
    (opt("--themes-dir") / "foret").mkdir(parents=True)
    (opt("--themes-dir") / "foret" / "theme.json").write_text("{}")
if args[0] == "route-pack-install":
    if "casse" in args[1]:
        print("openride-compiler : archive refusée : chemin interdit", file=sys.stderr)
        sys.exit(2)
    d = opt("--gpx-dir") / "vosges"
    d.mkdir(parents=True)
    (d / "pack.toml").write_text('name = "Vosges"\\n')
'''


def setup(tmp_path, monkeypatch):
    script = tmp_path / "compilateur.py"
    script.write_text(FAKE_COMPILER, encoding="utf-8")
    monkeypatch.setattr(launch_compile, "compiler_base_cmd", lambda: [sys.executable, str(script)])
    recipes = tmp_path / "pkg" / "route_packs" / "cols_celebres"
    recipes.mkdir(parents=True)
    (recipes / "pack.toml").write_text('name = "Cols célèbres"\n', encoding="utf-8")
    for i in range(4):
        (recipes / f"col{i}.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(contents, "_compiler_package", lambda: tmp_path / "pkg")
    monkeypatch.setattr(contents, "_demo_names", lambda: [])
    home = tmp_path / "home"
    (home / "Téléchargements").mkdir(parents=True)
    with zipfile.ZipFile(home / "Téléchargements" / "foret.zip", "w") as zf:
        zf.writestr("foret/theme.json", json.dumps({"name": "Forêt"}))
        zf.writestr("foret/sol.jpg", b"x" * 2_000_000)
    with zipfile.ZipFile(home / "Téléchargements" / "vosges.zip", "w") as zf:
        zf.writestr("pack.toml", 'name = "Vosges"\n')
        zf.writestr("ballon.gpx", "<gpx/>")
    (home / "Téléchargements" / "photos.zip").write_bytes(b"pas une archive")
    themes = tmp_path / "Themes"
    (themes / "hiver").mkdir(parents=True)
    (themes / "hiver" / "theme.json").write_text("{}", encoding="utf-8")
    (themes / ".utilisation.json").write_text(json.dumps({"hiver": "2026-10-29T18:00:00"}), encoding="utf-8")
    d = ContentDirs(tmp_path / "Workouts", tmp_path / "Plans", tmp_path / "routes", gpx=tmp_path / "GPX",
                    themes=themes, home=home, themes_max_gb=5.0)
    return ContentService(d), script.with_name("appels.jsonl")


def by_id(svc):
    return {it["id"]: it for it in svc.items()}


def test_listing(tmp_path, monkeypatch):
    svc, _ = setup(tmp_path, monkeypatch)
    items = by_id(svc)
    cols = items[COLS_ID]
    assert cols["network"] and cols["state"] == "missing" and cols["kind"] == "route_pack"
    archives = [it for it in items.values() if it["id"].startswith("archive:")]
    assert sorted(it["label"] for it in archives) == ["Pack de parcours « Vosges »", "Thème « Forêt »"]
    theme = next(it for it in archives if it["kind"] == "theme")
    assert theme["size_mb"] == 1.9 and not theme["network"] and "Téléchargements" in theme["detail"]
    hiver = items["theme:hiver"]
    assert hiver["state"] == "installed" and "29/10/2026" in hiver["detail"]
    msg = svc.message(1)
    assert msg["themes_max_mb"] == 5120.0 and msg["disk_free_mb"] > 0
    assert_valid(msg)


def test_cols_pack_built_installed_and_compiled(tmp_path, monkeypatch):
    svc, calls = setup(tmp_path, monkeypatch)
    seen = []
    job = svc.start(COLS_ID)
    job.set_progress = lambda pct, f=job.set_progress: (seen.append(pct), f(pct))[1]
    svc.run(job)
    assert not job.failed, job.message
    assert job.message == "Pack installé : 3 col(s) sur 4, 1 refusé(s)."
    assert seen[:3] == [20, 40, 60] and 80 in seen
    names = [json.loads(line)[0] for line in calls.read_text().splitlines()]
    assert names == ["route-pack-build", "build-all"]
    items = by_id(svc)
    assert items[COLS_ID]["state"] == "partial" and "routes:cols_celebres" not in [
        i for i in items if i != COLS_ID]   # pas de seconde ligne pour le pack des cols


def test_archives_installed(tmp_path, monkeypatch):
    svc, calls = setup(tmp_path, monkeypatch)
    items = by_id(svc)
    for kind in ("theme", "route_pack"):
        cid = next(i for i, it in items.items() if it["id"].startswith("archive:") and it["kind"] == kind)
        job = svc.start(cid)
        svc.run(job)
        assert not job.failed, job.message
    names = [json.loads(line)[0] for line in calls.read_text().splitlines()]
    assert names == ["theme-install", "route-pack-install", "build-all"]
    after = by_id(svc)
    assert not [i for i in after if i.startswith("archive:")]   # remplacées par les lignes installées
    assert after["theme:foret"]["label"] == "Thème « foret »" and after["theme:foret"]["state"] == "installed"
    assert after["routes:vosges"]["label"] == "Pack de parcours « Vosges »"


def test_compiler_error_reported(tmp_path, monkeypatch):
    svc, _ = setup(tmp_path, monkeypatch)
    bad = tmp_path / "home" / "Téléchargements" / "casse.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("pack.toml", 'name = "Cassé"\n')
    cid = next(i for i, it in by_id(svc).items() if "Cassé" in it["label"])
    job = svc.start(cid)
    svc.run(job)
    assert job.failed and job.message == "Installation impossible : archive refusée : chemin interdit"


def test_without_compiler(tmp_path, monkeypatch):
    svc, _ = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(contents, "_compiler_package", lambda: None)
    assert COLS_ID not in by_id(svc)
