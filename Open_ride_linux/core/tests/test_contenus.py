"""Contenus installables depuis le menu (lot O25) : contenus de départ, commandes IPC, premier lancement."""

import asyncio

import jsonschema

from openride_core import contents, plans
from openride_core.contents import ContentDirs, ContentError, ContentService
from openride_core.tools.workouts import BUILTIN_WORKOUTS_DIR
from test_contract_ipc import assert_valid, make_session, schema


def dirs(tmp_path) -> ContentDirs:
    return ContentDirs(tmp_path / "Workouts", tmp_path / "Plans", tmp_path / "routes")


def no_demos(monkeypatch):
    """Parcours de démonstration remplacés par un faux générateur rapide (sans compilateur)."""
    monkeypatch.setattr(contents, "_demo_names", lambda: ["demo-biomes-a", "demo-biomes-b"])

    def fake(out):
        for n in ("demo-biomes-a", "demo-biomes-b"):
            (out / f"{n}.world").mkdir(parents=True)
            (out / f"{n}.world" / "manifest.json").write_text("{}", encoding="utf-8")
        return []

    monkeypatch.setattr("openride_core.demo_world.write_biome_demo_worlds", fake)


def test_starter_installs_everything_once_and_never_overwrites(tmp_path, monkeypatch):
    no_demos(monkeypatch)
    d = dirs(tmp_path)
    svc = ContentService(d)
    assert svc.items()[0]["state"] == "missing"
    d.workouts.mkdir(parents=True)
    mine = d.workouts / "endurance_60.zwo"
    mine.write_text("<mon entraînement>", encoding="utf-8")
    assert svc.items()[0]["state"] == "partial"
    job = svc.start("starter")
    svc.run(job)
    assert job.done and not job.failed and job.progress_pct == 100
    assert mine.read_text(encoding="utf-8") == "<mon entraînement>"   # fichier du joueur gardé
    builtin = {p.name for p in BUILTIN_WORKOUTS_DIR.iterdir() if p.is_file()}
    assert builtin <= {p.name for p in d.workouts.iterdir()}
    assert {p.name for p in plans.BUILTIN_PLANS_DIR.glob("*.toml")} == {p.name for p in d.plans.glob("*.toml")}
    assert (d.routes / "demo-biomes-a.world" / "manifest.json").is_file()
    item = svc.items()[0]
    assert item["state"] == "installed" and item["progress_pct"] is None
    assert "2 plans de départ" in item["detail"] and "2 parcours" in item["detail"]
    again = svc.start("starter")
    svc.run(again)
    assert again.message.startswith("Ajouté : 0 entraînement(s), 0 plan(s), 0 parcours")


def test_demo_routes_skipped_without_compiler(tmp_path, monkeypatch):
    monkeypatch.setattr(contents, "_demo_names", lambda: ["demo-biomes-a"])

    def missing(out):
        raise ImportError("openride_compiler")

    monkeypatch.setattr("openride_core.demo_world.write_biome_demo_worlds", missing)
    svc = ContentService(dirs(tmp_path))
    job = svc.start("starter")
    svc.run(job)
    assert not job.failed and "compilateur absent" in job.message
    assert svc.items()[0]["state"] == "partial"


def test_one_install_at_a_time_and_unknown_id(tmp_path, monkeypatch):
    no_demos(monkeypatch)
    svc = ContentService(dirs(tmp_path))
    svc.start("starter")
    assert svc.items()[0]["state"] == "installing"
    for content_id in ("starter", "inconnu"):
        try:
            svc.start(content_id)
        except ContentError:
            pass
        else:
            raise AssertionError(content_id)


def test_ipc_list_and_install(tmp_path, monkeypatch):
    no_demos(monkeypatch)

    async def scenario():
        s, cap = make_session(tmp_path, monkeypatch, port=5980)
        s.workouts_dir, s.plans_dir = tmp_path / "Workouts", tmp_path / "Plans"
        s._on_command("list_contents", {}, 1)
        await asyncio.sleep(0.05)
        assert cap.of("contents")[-1]["items"][0]["state"] == "missing"
        s._on_command("install_content", {"id": "starter"}, 2)
        s._on_command("install_content", {"id": "starter"}, 3)   # une seule à la fois
        s._on_command("install_content", {"id": "pack_inconnu"}, 4)
        for _ in range(100):
            await asyncio.sleep(0.05)
            if not s._contents.busy:
                break
        await asyncio.sleep(0.05)
        msgs = cap.of("contents")
        assert msgs[1]["busy"] == "starter" and msgs[1]["items"][0]["state"] == "installing"
        assert msgs[-1]["busy"] is None and msgs[-1]["items"][0]["state"] == "installed"
        assert msgs[-1]["message"].startswith("Ajouté :")
        assert [e["code"] for e in cap.of("error")] == ["content_invalid", "content_invalid"]
        for m in msgs + cap.of("error"):
            assert_valid(m)
        s._on_command("select_route", {"route_id": "demo"}, 5)
        s._on_command("start", {}, 6)
        s._on_command("install_content", {"id": "starter"}, 7)
        assert cap.of("error")[-1]["code"] == "busy"
    asyncio.run(scenario())


def test_first_run_installs_starter(tmp_path, monkeypatch):
    no_demos(monkeypatch)

    async def scenario():
        s, cap = make_session(tmp_path, monkeypatch, port=5984)
        s.workouts_dir, s.plans_dir = tmp_path / "Workouts", tmp_path / "Plans"
        s.first_run = True
        s.server.start = lambda: None

        async def loop():
            for _ in range(100):
                await asyncio.sleep(0.05)
                if s._contents is not None and not s._contents.busy:
                    break
            await asyncio.sleep(0.05)

        s._loop = loop
        await s.run()
        assert cap.of("contents")[-1]["items"][0]["state"] == "installed"
    asyncio.run(scenario())


def test_contents_schema_rejects_unknown_state():
    msg = {"type": "contents", "v": 1, "request_cmd_id": 1, "busy": None, "message": "", "items": [
        {"id": "starter", "kind": "starter", "label": "x", "detail": "", "state": "done", "network": False,
         "size_mb": None, "progress_pct": None}]}
    assert list(jsonschema.Draft202012Validator(schema("contents")).iter_errors(msg))
