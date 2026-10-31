"""Lot N16, décision D4 de l'audit IPC : entraînements créés ou importés par le core depuis le menu ERG."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import jsonschema
import pytest

from openride_core import workout_menu
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.workout import list_workouts, load_workout

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
PARAMS = {"warmup_min": 10, "reps": 5, "on_s": 240, "on_pct": 105, "off_s": 180, "off_pct": 55, "cooldown_min": 10}
ERG_TEXT = "[COURSE HEADER]\nMINUTES WATTS\n[END COURSE HEADER]\n[COURSE DATA]\n0 120\n10 120\n10 220\n20 220\n[END COURSE DATA]\n"


def assert_valid(msg: dict) -> None:
    schema = json.loads((IPC_DIR / f"{msg['type']}.schema.json").read_text(encoding="utf-8"))
    errors = [e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(msg)]
    assert not errors, f"{msg['type']} invalide : {errors}"


def test_create_interval_workout_is_readable_and_idempotent(tmp_path: Path):
    res = workout_menu.create_interval_workout(tmp_path, PARAMS)
    assert res == {"workout_id": "intervalles_5x240s_105", "name": "Intervalles 5 × 4 min à 105 %", "created": True}
    w = load_workout(tmp_path / "intervalles_5x240s_105.zwo")
    assert w.duration_s == pytest.approx(600 + 5 * 420 + 600)
    again = workout_menu.create_interval_workout(tmp_path, PARAMS)
    assert again["created"] is False and len(list(tmp_path.iterdir())) == 1
    # Sans échauffement ni retour au calme : seul le bloc d'intervalles.
    short = workout_menu.create_interval_workout(tmp_path, {**PARAMS, "warmup_min": 0, "cooldown_min": 0, "on_s": 30})
    assert load_workout(tmp_path / f"{short['workout_id']}.zwo").duration_s == pytest.approx(5 * 210)


@pytest.mark.parametrize("bad", [{**PARAMS, "reps": 0}, {**PARAMS, "on_pct": 250}, {**PARAMS, "on_s": 30.5},
                                 {**PARAMS, "reps": True}, {k: v for k, v in PARAMS.items() if k != "off_s"}, None])
def test_create_rejects_bad_params(tmp_path: Path, bad):
    with pytest.raises(workout_menu.WorkoutMenuError) as exc:
        workout_menu.create_interval_workout(tmp_path, bad)
    assert exc.value.code == "bad_args"
    assert not list(tmp_path.iterdir())


def test_import_candidates_and_copy_without_overwrite(tmp_path: Path):
    home, wdir = tmp_path / "home", tmp_path / "Workouts"
    (home / "Téléchargements").mkdir(parents=True)
    (home / "OpenRide" / "Import").mkdir(parents=True)
    old = home / "Téléchargements" / "seuil.erg"
    old.write_text(ERG_TEXT, encoding="utf-8")
    os.utime(old, (1_000_000, 1_000_000))
    (home / "OpenRide" / "Import" / "notes.txt").write_text("pas un entraînement", encoding="utf-8")
    sub = home / "Téléchargements" / "sous-dossier"
    sub.mkdir()
    (sub / "cache.erg").write_text(ERG_TEXT, encoding="utf-8")
    recent = home / "OpenRide" / "Import" / "seuil.zwo"
    workout_menu.create_interval_workout(tmp_path, PARAMS)
    recent.write_bytes((tmp_path / "intervalles_5x240s_105.zwo").read_bytes())

    items = workout_menu.import_candidates(home, wdir)
    assert [(i["file"], i["source"], i["imported"]) for i in items] == [
        ("seuil.zwo", "OpenRide/Import", False), ("seuil.erg", "Téléchargements", False)]

    first = workout_menu.import_file(old, wdir)
    assert first == {"workout_id": "seuil", "name": "seuil", "created": True}
    assert workout_menu.import_file(old, wdir)["created"] is False   # identique : pas de seconde copie
    second = workout_menu.import_file(recent, wdir)   # même nom, autre contenu : jamais écrasé
    assert second["workout_id"] == "seuil_2" and second["created"] is True
    assert sorted(w.id for w in list_workouts(wdir)) == ["seuil", "seuil_2"]
    assert all(i["imported"] for i in workout_menu.import_candidates(home, wdir))


def test_import_rejects_invalid_file(tmp_path: Path):
    bad = tmp_path / "casse.zwo"
    bad.write_text("<workout_file><workout>", encoding="utf-8")
    with pytest.raises(workout_menu.WorkoutMenuError) as exc:
        workout_menu.import_file(bad, tmp_path / "Workouts")
    assert exc.value.code == "workout_invalid"
    assert not (tmp_path / "Workouts").exists()


def test_session_commands_answer_with_schema_valid_messages(tmp_path: Path):
    """Commandes IPC : imports, workout_saved, busy pendant une séance, chemin non proposé refusé."""
    home = tmp_path / "home"
    (home / "Downloads").mkdir(parents=True)
    (home / "Downloads" / "seuil.erg").write_text(ERG_TEXT, encoding="utf-8")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = 5796, 5797
    s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=tmp_path / "routes", workouts_dir=tmp_path / "Workouts")
    s.import_home = home
    sent: list[dict] = []
    s.server.send_raw = lambda m, max_size=None: sent.append(m)   # type: ignore[method-assign]

    async def run(name: str, args: dict, cmd_id: int) -> list[dict]:
        mark = len(sent)
        s._on_command(name, args, cmd_id)
        while s._bg_tasks:
            await asyncio.sleep(0.01)
        return sent[mark:]

    async def scenario() -> None:
        refused = await run("import_workout", {"path": str(home / "Downloads" / "seuil.erg")}, 1)
        assert refused[0]["type"] == "error" and refused[0]["code"] == "workout_invalid"
        listing = await run("list_imports", {}, 2)
        assert listing[0]["type"] == "imports" and listing[0]["items"][0]["file"] == "seuil.erg"
        imported = await run("import_workout", {"path": listing[0]["items"][0]["path"]}, 3)
        created = await run("create_workout", PARAMS, 4)
        bad = await run("create_workout", {**PARAMS, "reps": 99}, 5)
        for m in listing + imported + created + bad:
            assert_valid(m)
        assert imported[0] == {"type": "workout_saved", "v": 1, "request_cmd_id": 3, "workout_id": "seuil",
                               "name": "seuil", "created": True}
        assert created[0]["workout_id"] == "intervalles_5x240s_105" and created[0]["request_cmd_id"] == 4
        assert bad[0]["code"] == "bad_args"
        s.state.session_state = "RUNNING"
        busy = await run("create_workout", PARAMS, 6)
        assert busy[0]["code"] == "busy"

    asyncio.run(scenario())
    assert sorted(p.name for p in (tmp_path / "Workouts").iterdir()) == ["intervalles_5x240s_105.zwo", "seuil.erg"]


def test_create_interval_workout_never_replaces_another(tmp_path: Path):
    """Lot O20 : même nom mais autre récupération, un second fichier `_2` ; le premier reste intact."""
    first = workout_menu.create_interval_workout(tmp_path, PARAMS)
    before = (tmp_path / "intervalles_5x240s_105.zwo").read_bytes()
    other = workout_menu.create_interval_workout(tmp_path, {**PARAMS, "off_s": 120})
    assert other["workout_id"] == "intervalles_5x240s_105_2" and other["created"] is True
    assert (tmp_path / "intervalles_5x240s_105.zwo").read_bytes() == before
    assert load_workout(tmp_path / "intervalles_5x240s_105_2.zwo").duration_s == pytest.approx(600 + 5 * 360 + 600)
    # Les mêmes réglages retrouvent leur fichier, sans troisième copie.
    assert workout_menu.create_interval_workout(tmp_path, {**PARAMS, "off_s": 120}) == {**other, "created": False}
    assert workout_menu.create_interval_workout(tmp_path, PARAMS) == {**first, "created": False}
    assert len(list(tmp_path.iterdir())) == 2


def test_import_qwk_file(tmp_path: Path):
    """Lot O20 : un `.qwk` (QWKcode de GoldenCheetah) s'importe et se lit comme les autres formats."""
    dl = tmp_path / "Téléchargements"
    dl.mkdir()
    (dl / "seuil.qwk").write_text("# Seuil 4 × 5\n10m@130-220\n4x 5m@280 r3m@140\n10m@130\n", encoding="utf-8")
    wdir = tmp_path / "OpenRide" / "Workouts"
    cands = workout_menu.import_candidates(tmp_path, wdir)
    assert [c["file"] for c in cands] == ["seuil.qwk"]
    res = workout_menu.import_file(dl / "seuil.qwk", wdir)
    assert res == {"workout_id": "seuil", "name": "Seuil 4 × 5", "created": True}
    [info] = list_workouts(wdir)
    assert info.selectable and info.duration_s == pytest.approx(600 + 4 * 480 + 600)
    (dl / "faux.qwk").write_text("4x 5m280\n", encoding="utf-8")
    with pytest.raises(workout_menu.WorkoutMenuError, match="ligne 1"):
        workout_menu.import_file(dl / "faux.qwk", wdir)
