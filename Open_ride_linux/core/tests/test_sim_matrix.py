"""Recette sans matériel (lot M6) : chaque scénario simulé joué en séance complète.

Chaque scénario de `sim_scenarios.SCENARIOS` est joué deux fois, en ERG (`.zwo` court écrit par
le test) et en SIM, sur le parcours `demo`, avec le trainer, le Click et la ceinture simulés,
pendant la durée du scénario plus 10 s (au plus 130 s), puis arrêté proprement. Un scénario
ajouté plus tard est joué sans modifier ce fichier.

Les séances tournent en parallèle, chacune dans son processus (`spawn`) : le verrou BLE est
propre à chaque boucle asyncio, et les gestionnaires de signaux de la séance demandent le fil
principal. La matrice entière dure donc à peu près la plus longue séance (~2 min 15 s).

Les invariants restent vrais avant et après M1 : le nombre de reconnexions de `erreur_0x80`
n'est pas vérifié.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import struct
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import pytest

from openride_core import ftms
from openride_core.sim_scenarios import SCENARIOS

pytestmark = pytest.mark.slow

MAX_SESSION_S = 130.0
EXTRA_S = 10.0
FTP_W = 250.0
BASE_PORT = 6300
SHORT_ZWO = """<workout_file><name>Matrice M6</name><workout>
<Warmup Duration="60" PowerLow="0.5" PowerHigh="0.7"/>
<SteadyState Duration="600" Power="0.8"/>
</workout></workout_file>
"""
LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"   # celui de `__main__.py`

# Lignes ERROR attendues, par scénario (toute autre ligne ERROR fait échouer la matrice).
EXPECTED_ERRORS: dict[str, set[str]] = {
    "controle_refuse": {"Le trainer refuse le contrôle FTMS après deux reprises."},
}
# Durée minimale de séance (s), quand la fin des connexions dépasse le dernier événement.
MIN_DURATION_S: dict[str, float] = {"connexions_retardees": 30.0, "reveil_tardif": 45.0}


def _expect_reconnects(r: dict) -> list[str]:
    out = []
    if r["trainer_connections"] < 2:
        out.append(f"au moins une reconnexion du trainer attendue ({r['trainer_connections']} connexion(s))")
    if r["click_connections"].get("-", 0) < 2:
        out.append(f"au moins une reconnexion du Click « − » attendue ({r['click_connections']})")
    return out


def _expect_late_power(r: dict) -> list[str]:
    t = r["first_power_t"]
    return [] if t is not None and t >= 6.0 else [f"premier échantillon avec puissance à {t} s (≥ 6 s attendu)"]


def _expect_no_reconnect(r: dict) -> list[str]:
    ok = r["trainer_connections"] == 1 and r["reconnect_count"] == 0
    return [] if ok else [f"aucune reconnexion attendue ({r['trainer_connections']} connexion(s))"]


def _expect_att_error_seen(r: dict) -> list[str]:
    return [] if r["att_failures"] >= 1 else ["l'erreur ATT simulée n'a jamais été levée"]


def _expect_hr_connected(r: dict) -> list[str]:
    out = [] if r["hr_seen"] else ["la ceinture ne s'est jamais connectée"]
    return out + ([] if r["trainer_connections"] >= 1 else ["trainer jamais connecté"])


def _expect_refused(r: dict) -> list[str]:
    return [] if "trainer_control_refused" in r["errors"] else [
        f"erreur trainer_control_refused attendue (reçues : {r['errors']})"]


# Attentes propres à chaque scénario (un scénario absent de la table n'a que les invariants).
EXPECTATIONS = {
    "coupures": _expect_reconnects,
    "reveil_tardif": _expect_late_power,
    "nominal": _expect_no_reconnect,
    "demo": _expect_no_reconnect,
    "erreur_0x80": _expect_att_error_seen,
    "connexions_retardees": _expect_hr_connected,
    "controle_refuse": _expect_refused,
}
FINAL_STATE = {"controle_refuse": "ERROR"}


def session_duration(name: str, spec: dict) -> float:
    last = max([float(e["t"]) for e in spec.get("events") or []] or [0.0])
    appear = max([float((spec.get(k) or {}).get("appear_at", 0.0)) for k in ("trainer", "click", "hr")])
    return min(max(max(last, appear) + EXTRA_S, MIN_DURATION_S.get(name, 0.0)), MAX_SESSION_S)


# --- une séance (processus enfant) -------------------------------------------------------

class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.setFormatter(logging.Formatter(LOG_FORMAT))
        self.lines: list[str] = []
        self.errors: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))
        if record.levelno >= logging.ERROR:
            self.errors.append(record.getMessage())


def play(name: str, spec: dict, mode: str, port: int, workdir: str) -> dict[str, Any]:
    """Joue une séance et renvoie ce qu'il faut pour vérifier les invariants (données simples)."""
    from garmin_fit_sdk import Decoder, Stream
    from fit_tool.profile.messages.record_message import RecordMessage

    from openride_core import fit_export
    from openride_core import sim_scenarios
    from openride_core.config import Config
    from openride_core.fit_export import iter_records
    from openride_core.journal import read_journal
    from openride_core.session import CoreSession
    from openride_core.tools.log_report import analyse
    from openride_core.tools.session_summary import compute_summary, load_session

    work = Path(workdir)
    sim_scenarios.SCENARIOS[name] = copy.deepcopy(spec)
    fit_export.ACTIVITIES_DIR = work / "act"
    wdir = work / "workouts"
    wdir.mkdir(parents=True, exist_ok=True)
    (wdir / "matrice.zwo").write_text(SHORT_ZWO, encoding="utf-8")
    handler = _Lines()
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    cfg = Config()
    cfg.rider.ftp_w = FTP_W
    cfg.drivers.trainer = cfg.drivers.input = cfg.drivers.hr = "sim"
    cfg.drivers.sim_scenario = name
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    duration = session_duration(name, spec)
    errors: list[str] = []
    out: dict[str, Any] = {"name": name, "mode": mode, "duration_s": duration}

    async def run() -> CoreSession:
        s = CoreSession(cfg, journal_dir=work / "journal", routes_root=work / "routes",
                        workouts_dir=wdir)
        send_error = s.server.send_error

        def spy(code: str, message: str) -> None:
            errors.append(code)
            send_error(code, message)
        s.server.send_error = spy   # type: ignore[method-assign]
        task = asyncio.create_task(s.run(autostart=True, route_id="demo",
                                         workout_id="matrice" if mode == "ERG" else None))
        hr_seen = False
        end = asyncio.get_running_loop().time() + duration
        while asyncio.get_running_loop().time() < end and not task.done():
            hr_seen = hr_seen or bool(s.hr and s.hr.connected)
            await asyncio.sleep(0.1)
        out["hr_seen"] = hr_seen
        s.stop_event.set()
        await asyncio.wait_for(task, 20)
        return s

    try:
        s = asyncio.run(run())
    except BaseException as exc:   # rendu au parent comme un échec lisible
        out["crash"] = f"{type(exc).__name__}: {exc}"
        return out
    finally:
        root.removeHandler(handler)

    trainer = s.sim.trainer
    out["final_state"] = s.state.session_state
    out["errors"] = errors
    out["error_lines"] = handler.errors
    out["trainer_connections"] = trainer.connections
    out["reconnect_count"] = s.driver.reconnect_count
    out["click_connections"] = {b.role: b.connections for b in s.sim.clicks}
    out["att_failures"] = sum(1 for c in trainer.commands if c.result is None)
    out["ops"] = [c.op for c in trainer.commands]
    out["released"] = {"control": trainer.control, "client": trainer.client is not None,
                       "mode": trainer.mode, "last_grade": None}
    sims = [c for c in trainer.commands if c.op == ftms.OP_SET_SIM_PARAMS]
    if sims:
        out["released"]["last_grade"] = struct.unpack_from("<h", sims[-1].payload, 3)[0] / 100.0
    lo, hi, _ = trainer.power_range
    out["erg_out_of_range"] = [struct.unpack_from("<h", c.payload, 1)[0] for c in trainer.commands
                               if c.op == ftms.OP_SET_TARGET_POWER
                               and not lo <= struct.unpack_from("<h", c.payload, 1)[0] <= hi]
    gmin, gmax = cfg.trainer.grade_min_pct, cfg.trainer.grade_max_pct
    out["grade_out_of_range"] = [g for g in (struct.unpack_from("<h", c.payload, 3)[0] / 100.0
                                             for c in sims) if not gmin - 0.01 <= g <= gmax + 0.01]

    journals = sorted((work / "journal").glob("*.jsonl"))
    out["journals"] = len(journals)
    lines = [ln for j in journals for ln in read_journal(j)]
    records = [ln for ln in lines if ln.get("kind") == "record"]
    out["records"] = len(records)
    start = next((ln["ts"] for ln in lines if ln.get("event") == "start"), None)
    first = next((r for r in records if (r.get("power") or 0) > 0), None)
    out["first_power_t"] = round(first["ts"] - start, 1) if first and start else None

    fit_path = (s.state.summary or {}).get("fit_path")
    out["fit"] = None
    if fit_path and Path(fit_path).is_file():
        stream = Stream.from_file(fit_path)
        dec = Decoder(stream)
        ok = dec.is_fit() and dec.check_integrity()
        stream.reset()
        _, sdk_errors = dec.read()
        n = sum(1 for r in iter_records(Path(fit_path)) if isinstance(r.message, RecordMessage))
        out["fit"] = {"sdk_ok": ok and not sdk_errors, "sdk_errors": [str(e) for e in sdk_errors],
                      "records": n}
    try:
        compute_summary(load_session(journals[-1]), FTP_W)
        analyse(handler.lines)
        out["readers_ok"] = True
    except Exception as exc:
        out["readers_ok"] = f"{type(exc).__name__}: {exc}"
    return out


def run_matrix(cases: list[tuple[str, dict, str]], base_dir: Path) -> dict[tuple[str, str], dict]:
    ctx = get_context("spawn")
    with ProcessPoolExecutor(max_workers=len(cases), mp_context=ctx) as pool:
        futures = {(name, mode): pool.submit(play, name, spec, mode, BASE_PORT + 2 * i,
                                             str(base_dir / f"{name}_{mode}"))
                   for i, (name, spec, mode) in enumerate(cases)}
        return {k: f.result() for k, f in futures.items()}


def check_invariants(r: dict) -> list[str]:
    """Liste des invariants non tenus (vide si tout va bien)."""
    name = r["name"]
    if "crash" in r:
        return [f"exception non rattrapée : {r['crash']}"]
    bad = []
    allowed = EXPECTED_ERRORS.get(name, set())
    unexpected = [e for e in r["error_lines"] if e not in allowed]
    if unexpected:
        bad.append(f"lignes ERROR inattendues : {unexpected}")
    want = FINAL_STATE.get(name, "FINISHED")
    if r["final_state"] != want:
        bad.append(f"état final {r['final_state']} au lieu de {want}")
    if r["fit"] is None:
        bad.append("aucun FIT produit")
    else:
        if not r["fit"]["sdk_ok"]:
            bad.append(f"FIT refusé par le SDK Garmin : {r['fit']['sdk_errors']}")
        if r["fit"]["records"] != r["records"]:
            bad.append(f"FIT : {r['fit']['records']} échantillons pour {r['records']} lignes record")
    rel = r["released"]
    if r["ops"][-2:] != [ftms.OP_SET_SIM_PARAMS, ftms.OP_RESET] or rel["last_grade"] != 0.0:
        bad.append(f"relâche absente (dernières commandes {[hex(o) for o in r['ops'][-3:]]})")
    if rel["control"] or rel["client"]:
        bad.append(f"trainer encore contrôlé ou connecté après l'arrêt ({rel})")
    if r["erg_out_of_range"]:
        bad.append(f"consignes ERG hors plage : {r['erg_out_of_range']}")
    if r["grade_out_of_range"]:
        bad.append(f"pentes hors des bornes de la configuration : {r['grade_out_of_range']}")
    if r["readers_ok"] is not True:
        bad.append(f"summary ou log_report en échec : {r['readers_ok']}")
    expect = EXPECTATIONS.get(name)
    if expect is not None:
        bad += expect(r)
    return bad


CASES = [(name, mode) for name in SCENARIOS for mode in ("ERG", "SIM")]


@pytest.fixture(scope="module")
def matrix(tmp_path_factory) -> dict[tuple[str, str], dict]:
    cases = [(name, SCENARIOS[name], mode) for name, mode in CASES]
    return run_matrix(cases, tmp_path_factory.mktemp("matrice"))


@pytest.mark.parametrize("name, mode", CASES, ids=[f"{n}-{m}" for n, m in CASES])
def test_scenario_session(matrix, name, mode):
    r = matrix[(name, mode)]
    bad = check_invariants(r)
    assert not bad, f"scénario {name}, mode {mode} : " + " ; ".join(bad)


def test_added_scenario_is_played_without_changes(tmp_path, monkeypatch):
    """Critère 4 : un scénario ajouté à SCENARIOS est joué par le même code."""
    fake = {"trainer": {"appear_at": 0.2, "connect_delay_s": 0.1},
            "click": {"appear_at": 0.2, "connect_delay_s": 0.1},
            "hr": {"appear_at": 0.2, "connect_delay_s": 0.1},
            "events": [{"t": 2.0, "action": "press", "button": "+"}]}
    monkeypatch.setitem(SCENARIOS, "factice_m6", fake)
    cases = [(n, SCENARIOS[n], m) for n in SCENARIOS if n == "factice_m6" for m in ("ERG", "SIM")]
    assert len(cases) == 2
    results = run_matrix(cases, tmp_path)
    for (name, mode), r in results.items():
        assert r["duration_s"] == 12.0
        assert not check_invariants(r), (name, mode, check_invariants(r))
