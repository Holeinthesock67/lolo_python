"""Lot RC24, contenus et packs (revue de code, vague 4, K4-01 et K4-03), côté core : messages de
« Réglages › Contenus ». Le compilateur est remplacé par un faux script (aucun réseau)."""

import json

from test_contenus_packs import FAKE_COMPILER, by_id, setup

EXTRA = '''
if args[0] == "build-all":
    print("openride-compiler : erreur (vieille.gpx) : trace trop courte", file=sys.stderr)
    print("Résumé : 2 compilé(s), 1 ignoré(s), 1 en erreur")
    sys.exit(1)
if args[0] == "theme-install":
    print("avertissement : bibliothèque des thèmes au-delà de son plafond : pack « hiver » retiré "
          "(le moins récemment utilisé)")
'''


def _run(svc, kind):
    cid = next(i for i, it in by_id(svc).items() if i.startswith("archive:") and it["kind"] == kind)
    job = svc.start(cid)
    svc.run(job)
    return job


def test_pack_installed_even_if_another_track_fails(tmp_path, monkeypatch):
    svc, calls = setup(tmp_path, monkeypatch)
    (tmp_path / "compilateur.py").write_text(FAKE_COMPILER + EXTRA, encoding="utf-8")
    job = _run(svc, "route_pack")
    assert not job.failed, job.message
    assert "Vosges" in job.message and "installé" in job.message
    assert "1 trace(s)" in job.message and "en erreur" in job.message
    assert [json.loads(line)[0] for line in calls.read_text().splitlines()] == ["route-pack-install", "build-all"]


def test_cols_pack_reports_track_errors_without_failing(tmp_path, monkeypatch):
    from openride_core.contents import COLS_ID
    svc, _ = setup(tmp_path, monkeypatch)
    (tmp_path / "compilateur.py").write_text(FAKE_COMPILER + EXTRA, encoding="utf-8")
    job = svc.start(COLS_ID)
    svc.run(job)
    assert not job.failed, job.message
    assert "3 col(s) sur 4" in job.message and "en erreur" in job.message


def test_themes_removed_by_cleanup_are_said_on_screen(tmp_path, monkeypatch):
    svc, _ = setup(tmp_path, monkeypatch)
    (tmp_path / "compilateur.py").write_text(FAKE_COMPILER + EXTRA, encoding="utf-8")
    job = _run(svc, "theme")
    assert not job.failed, job.message
    assert "retiré" in job.message and "hiver" in job.message
