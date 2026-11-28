"""Revue S1-02 : l'export FIT d'une fin de séance se fait hors de la boucle à 50 Hz, sans perdre ni tronquer le FIT."""

from __future__ import annotations

import asyncio
import gc
import threading
import time
from pathlib import Path

import pytest

from openride_core import fit_export, recorder
from openride_core.fit_export import iter_records, write_atomic
from openride_core.journal import Record
from openride_core.recorder import FitExporter, FitJob, SessionRecorder

from test_drivers_session import make_session

T0 = 1_700_000_000.0


def _session_recorder(tmp_path: Path, n: int) -> SessionRecorder:
    """Séance fictive de `n` secondes (relevés à 1 Hz, comme la boucle) : aucune donnée réelle."""
    rec = SessionRecorder(tmp_path / "journal", "demo", fit_dir=tmp_path / "act")
    rec.event("start", T0)
    for i in range(n):
        rec.record(Record(ts=T0 + i, t=float(i), distance=i * 9.0, speed=9.0, power=200, cadence=90, hr=140,
                          grade=1.0, mode="SIM", gear=6, grade_sent=1.0, alt=500.0))
    return rec


def test_write_atomic_ok_sans_reste(tmp_path):
    out = tmp_path / "a" / "s.fit"
    write_atomic(b"abc", out)
    assert out.read_bytes() == b"abc"
    assert sorted(p.name for p in out.parent.iterdir()) == ["s.fit"]


def test_write_atomic_echec_ne_laisse_rien_sous_le_vrai_nom(tmp_path, monkeypatch):
    """Panne pendant l'écriture : ni FIT tronqué sous le vrai nom, ni `.part` qui traîne ; l'ancien fichier reste."""
    out = tmp_path / "s.fit"
    out.write_bytes(b"ancien")

    def boom(fd):
        raise OSError("disque plein")

    monkeypatch.setattr(fit_export.os, "fsync", boom)
    with pytest.raises(OSError):
        write_atomic(b"nouveau", out)
    assert out.read_bytes() == b"ancien"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["s.fit"]


def test_close_session_ne_fait_pas_l_export_et_finish_le_fait(tmp_path):
    rec = _session_recorder(tmp_path, 120)
    job, summary, error = rec.close_session(True, ts=T0 + 120)
    assert error is None and isinstance(job, FitJob)
    assert not job.path.exists()                       # rien d'écrit par `close_session`
    assert summary.timer_s == pytest.approx(120, abs=1)
    path, err = job.run()
    assert err is None and path == job.path
    assert sum(1 for _ in iter_records(path)) >= 120

    rec2 = _session_recorder(tmp_path / "b", 60)
    path2, _, err2 = rec2.finish(True, ts=T0 + 60)     # chemin des outils : export tout de suite
    assert err2 is None and path2 is not None and path2.exists()


def test_close_session_sans_relevé_ou_sans_sauvegarde(tmp_path):
    rec = SessionRecorder(tmp_path / "journal", "demo", fit_dir=tmp_path / "act")
    rec.event("start", T0)
    job, _, error = rec.close_session(True, ts=T0 + 5)
    assert job is None and "aucun FIT" in error
    rec2 = _session_recorder(tmp_path / "b", 10)
    assert rec2.close_session(False, ts=T0 + 10)[0] is None


def test_exporter_fil_a_part_et_fin_traitee_par_l_appelant(tmp_path, monkeypatch):
    threads: dict[str, str] = {}
    real = recorder.write_fit

    def spy(*a, **kw):
        threads["export"] = threading.current_thread().name
        return real(*a, **kw)

    monkeypatch.setattr(recorder, "write_fit", spy)
    job, _, _ = _session_recorder(tmp_path, 300).close_session(True, ts=T0 + 300)
    assert gc.isenabled()
    ex = FitExporter()
    done: list[tuple] = []
    ex.submit(job, lambda p, e: done.append((p, e, threading.current_thread().name)))
    assert ex.busy
    assert ex.wait(30)
    ex.close()
    assert threads["export"].startswith("fit-export")
    assert done == [(job.path, None, threading.current_thread().name)]   # jamais dans le fil de l'export
    assert job.path.exists() and not ex.busy
    assert gc.isenabled()   # ramasse-miettes remis après l'export
    assert not list(job.path.parent.glob("*.part"))


def test_exporter_erreur_rendue_sans_lever(tmp_path, monkeypatch):
    def boom(*a, **kw):
        raise ValueError("relevé hors plage")

    monkeypatch.setattr(recorder, "write_fit", boom)
    job, _, _ = _session_recorder(tmp_path, 30).close_session(True, ts=T0 + 30)
    ex = FitExporter()
    done: list[tuple] = []
    ex.submit(job, lambda p, e: done.append((p, e)))
    assert ex.wait(10)
    assert done == [(None, "relevé hors plage")]
    assert gc.isenabled()


def test_la_boucle_ne_s_arrete_plus_pendant_l_export(tmp_path):
    """Une heure de séance : pendant l'export, une boucle asyncio à 50 Hz garde des pas rapprochés (avant : un trou
    de 1,2 à 2,6 s ; 0,04 s mesuré ici). Borne large pour une machine lente : le fil n'a le verrou de Python que par
    tranches, et le ramasse-miettes automatique est coupé pendant l'export (collectes complètes de 0,2 s sinon)."""
    job, _, _ = _session_recorder(tmp_path, 3600).close_session(True, ts=T0 + 3600)

    async def loop() -> tuple[float, float]:
        ex = FitExporter()
        ex.submit(job)
        t_start = last = time.monotonic()
        worst = 0.0
        while ex.busy:
            await asyncio.sleep(0.02)
            now = time.monotonic()
            worst = max(worst, now - last)
            last = now
            ex.poll()
        ex.close()
        return worst, time.monotonic() - t_start

    worst, total = asyncio.run(loop())
    assert job.path.exists()
    print(f"pas max {worst:.3f} s, export {total:.2f} s")
    assert worst < 0.25, f"pas de boucle le plus long {worst:.3f} s pendant un export de {total:.2f} s"


def test_fin_de_seance_en_jeu_fit_hors_boucle(tmp_path, monkeypatch):
    """`_finish` en jeu : bilan tout de suite avec le chemin prévu, FIT écrit par le fil, puis lisible."""
    threads: list[str] = []
    real = recorder.write_fit

    def spy(*a, **kw):
        threads.append(threading.current_thread().name)
        return real(*a, **kw)

    monkeypatch.setattr(recorder, "write_fit", spy)

    async def scenario():
        s = make_session(tmp_path, monkeypatch, base_port=5876)
        s.fit_in_background = True
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        now = 1000.0
        for _ in range(500):
            now += 0.02
            s._step(0.02, now)
        s._on_command("end_session", {"save": True}, 3)
        assert s.state.session_state == "FINISHED"
        planned = s.state.summary["fit_path"]
        assert planned and planned.endswith(".fit")
        assert s.fit_exports.wait(30)
        s.fit_exports.close()
        assert threads and all(t.startswith("fit-export") for t in threads)
        assert Path(planned).exists() and s.state.summary["fit_path"] == planned
        assert not list(Path(planned).parent.glob("*.part"))
    asyncio.run(scenario())


def test_fin_de_seance_en_jeu_fit_rate(tmp_path, monkeypatch):
    """Échec de l'export dans le fil : même erreur `recording_failed` qu'avant, et le bilan ne cite plus de fichier."""
    def boom(*a, **kw):
        raise ValueError("relevé hors plage")

    monkeypatch.setattr(recorder, "write_fit", boom)
    errors: list[tuple[str, str]] = []

    async def scenario():
        s = make_session(tmp_path, monkeypatch, base_port=5878)
        s.server.send_error = lambda code, msg, *a, **kw: errors.append((code, msg))
        s.fit_in_background = True
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        now = 1000.0
        for _ in range(200):
            now += 0.02
            s._step(0.02, now)
        s._on_command("end_session", {"save": True}, 3)
        assert s.state.summary["fit_path"] is not None
        assert not errors
        s.fit_exports.wait(10)
        s.fit_exports.close()
        assert s.state.summary["fit_path"] is None
        assert errors == [("recording_failed", "FIT non produit : relevé hors plage")]
    asyncio.run(scenario())


def test_hors_jeu_fin_de_seance_comme_avant(tmp_path, monkeypatch):
    """Sans `run` (outils, tests) : le FIT est écrit par `_finish` lui-même, rien n'attend dans un fil."""
    async def scenario():
        s = make_session(tmp_path, monkeypatch, base_port=5880)
        assert s.fit_in_background is False
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        now = 1000.0
        for _ in range(200):
            now += 0.02
            s._step(0.02, now)
        s._on_command("end_session", {"save": True}, 3)
        assert Path(s.state.summary["fit_path"]).exists() and not s.fit_exports.busy
    asyncio.run(scenario())


def test_arret_du_jeu_attend_le_fit_en_cours(tmp_path, monkeypatch):
    """Arrêt du core en pleine séance : la séance est close, le FIT (lent ici) est attendu avant la fin de l'arrêt."""
    real = recorder.write_fit

    def slow(*a, **kw):
        time.sleep(0.5)
        return real(*a, **kw)

    monkeypatch.setattr(recorder, "write_fit", slow)

    async def scenario():
        s = make_session(tmp_path, monkeypatch, base_port=5882)
        s.fit_in_background = True
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        now = 1000.0
        for _ in range(200):
            now += 0.02
            s._step(0.02, now)
        await s._shutdown([])
        assert not s.fit_exports.busy
        return s.state.summary["fit_path"]

    planned = asyncio.run(scenario())
    assert planned and Path(planned).exists()
    assert not list(Path(planned).parent.glob("*.part"))
