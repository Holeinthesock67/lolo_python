"""Processus `openride-worldgen` (lot W8) : ouverture, horizon, carrefours, choix, hors ligne, cache."""

from __future__ import annotations

import json
import math
import resource
import subprocess
import sys
import threading
import time
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from openride_compiler.elevation import SyntheticProvider
from openride_compiler.worldgen import process
from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter
from openride_compiler.worldgen.process import WorldSession
from openride_compiler.worldgen.squares import zone_frame
from openride_compiler.worldgen.store import WorldCache

SCHEMAS = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "world"
ZONE = "31T"
FRAME = zone_frame(ZONE)
E_REF, N_REF = 680_000, 4_890_000


def validator(name: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(json.loads((SCHEMAS / name).read_text(encoding="utf-8")))


def lonlat(e: float, n: float) -> tuple[float, float]:
    lat, lon = FRAME.to_latlon(np.array([e]), np.array([-n]))
    return float(lon[0]), float(lat[0])


def latlon(e: float, n: float) -> tuple[float, float]:
    lon, lat = lonlat(e, n)
    return lat, lon


class Relief(SyntheticProvider):
    """Relief analytique ; `limit_e` : relief « sur le PC » seulement à l'ouest de cette abscisse."""

    def __init__(self, limit_e: float | None = None) -> None:
        lat, lon = latlon(E_REF, N_REF)
        super().__init__(lat, lon)
        self.limit_e = limit_e

    def has_data(self, lat: float, lon: float) -> bool:
        if self.limit_e is None:
            return True
        x, _ = FRAME.to_xz(np.array([lat]), np.array([lon]))
        return float(x[0]) < self.limit_e


def grid_db(path: Path, step: int = 500, east_km: int = 26, half_km: int = 9) -> Path:
    """Grille de routes : lignes est-ouest tertiaires, colonnes nord-sud résidentielles."""
    w = OsmDbWriter(path, "test", "test/grille")
    es = list(range(E_REF - 2000, E_REF + east_km * 1000 + 1, step))
    ns = list(range(N_REF - half_km * 1000, N_REF + half_km * 1000 + 1, step))
    nid = {(i, j): 1 + i * len(ns) + j for i in range(len(es)) for j in range(len(ns))}
    for j, n in enumerate(ns):
        w.add_road(100_000 + j, {"highway": "tertiary"}, [nid[(i, j)] for i in range(len(es))],
                   [lonlat(e, n) for e in es])
    for i, e in enumerate(es):
        w.add_road(200_000 + i, {"highway": "residential"}, [nid[(i, j)] for j in range(len(ns))],
                   [lonlat(e, n) for n in ns])
    w.finish(osm_date="2026-10-20T00:00:00Z")
    return path


def line_db(path: Path) -> Path:
    """Une seule route est-ouest coupée tous les kilomètres (classes alternées) : pas d'autre branche."""
    w = OsmDbWriter(path, "test", "test/ligne")
    for k in range(-10, 10):
        e0, e1 = E_REF + 1000 * k, E_REF + 1000 * (k + 1)
        nodes = [10_000 + 10 * k + d for d in range(11)]
        nodes[-1] = 10_000 + 10 * (k + 1)
        w.add_road(500 + k, {"highway": "tertiary" if k % 2 else "residential"}, nodes,
                   [lonlat(e0 + 100 * d, N_REF) for d in range(11)])
    w.finish(osm_date="2026-10-20T00:00:00Z")
    return path


@pytest.fixture(scope="module")
def grid(tmp_path_factory) -> Path:
    return grid_db(tmp_path_factory.mktemp("grille") / "grille.sqlite")


class Recorder:
    def __init__(self) -> None:
        self.msgs: list[dict] = []

    def __call__(self, msg: dict) -> None:
        json.dumps(msg)                     # toujours sérialisable
        self.msgs.append(msg)

    def of(self, kind: str) -> list[dict]:
        return [m for m in self.msgs if m["type"] == kind]


def session(tmp_path: Path, db_path: Path, provider=None, network: bool = True) -> tuple[WorldSession, Recorder]:
    cache = WorldCache(tmp_path / "cache", 10**10, log=lambda _m: None)
    rec = Recorder()
    s = WorldSession(cache, provider or Relief(), rec, {}, tmp_path / "seance.world", network=network,
                     clock=process.FakeClock(), log=lambda _m: None, db=OsmDb(db_path))
    return s, rec


def open_msg(e: float = E_REF + 250, n: float = N_REF, heading: float = 90.0, network: bool = True) -> dict:
    lat, lon = latlon(e, n)
    return {"type": "open", "lat": lat, "lon": lon, "heading_deg": heading, "nav": "ride", "target": None,
            "loop_km": None, "seed": 7, "network": network}


def test_open_snaps_start_and_publishes(grid, tmp_path) -> None:
    s, rec = session(tmp_path, grid)
    s.handle(open_msg())
    phases = [m["phase"] for m in rec.of("status")]
    assert phases[0] == "osm" and phases[-1] == "ready" and "generate" in phases
    (rev,) = rec.of("revision")
    assert rec.msgs[-1] is rev and rev["rev"] == 1 and rev["length_m"] >= 3000 and rev["junctions"] >= 1
    d = tmp_path / "seance.world"
    manifest = json.loads((d / "manifest.json").read_text())
    validator("manifest.schema.json").validate(manifest)
    assert manifest["live"] and manifest["grid"]["e0"] % 5000 == 0 and manifest["origin"]["utm_zone"] == ZONE
    live = json.loads((d / "live.json").read_text())
    validator("live.schema.json").validate(live)
    part0 = json.loads((d / "route" / "part_0.json").read_text())
    validator("route_part.schema.json").validate(part0)
    validator("junctions.schema.json").validate(json.loads((d / "junctions.json").read_text()))
    # Départ accroché sur la ligne N_REF, 250 m à l'est du coin, vers l'est ; repère de séance.
    assert part0["x"][0] == pytest.approx(E_REF + 250 - manifest["grid"]["e0"], abs=0.5)
    assert part0["z"][0] == pytest.approx(manifest["grid"]["n0"] - N_REF, abs=0.5)
    assert part0["heading_deg"][1] == pytest.approx(90, abs=1)
    # Carrés à moins de 1 500 m de la route, liés dans la séance.
    assert len(live["tiles"]["near"]) >= 12 and live["layer_tiles"] == live["tiles"]["near"]
    ix, iz = live["tiles"]["near"][0]
    assert (d / "terrain" / "near" / f"tile_{ix}_{iz}.f32").is_symlink()
    assert len(live["tiles"]["far"]) >= 9


def test_twenty_km_horizon_junctions_and_atomic_parts(grid, tmp_path) -> None:
    s, rec = session(tmp_path, grid)
    s.handle(open_msg())
    d = tmp_path / "seance.world"
    stop = threading.Event()
    reads = {"ok": 0, "bad": []}

    def reader() -> None:                      # lecteur concurrent : jamais de JSON partiel
        while not stop.is_set():
            for p in [d / "live.json", d / "junctions.json", *sorted((d / "route").glob("part_*.json"))]:
                try:
                    json.loads(p.read_text(encoding="utf-8"))
                    reads["ok"] += 1
                except FileNotFoundError:
                    pass                       # partie supprimée entre la liste et la lecture
                except ValueError as exc:
                    reads["bad"].append(f"{p.name}: {exc}")

    th = threading.Thread(target=reader, daemon=True)
    th.start()
    first_seen: dict[str, float] = {}
    s_m, v = 0.0, 60 / 3.6
    t0 = time.perf_counter()
    while s_m < 20_000:
        s_m += v * 0.5
        s.handle({"type": "progress", "s_m": s_m, "v_mps": v})
        assert s.length_m - s_m >= 3000
        for jid, j in s.junctions.items():
            first_seen.setdefault(jid, s_m)
        if s.has_work():
            s.work()
    dt = time.perf_counter() - t0
    stop.set()
    th.join(2)
    assert not reads["bad"] and reads["ok"] > 100
    late = {jid: (first_seen[jid], j) for jid, j in s.junctions.items() if first_seen[jid] > j.s_m - 300}
    assert not late
    passed = [jid for jid in first_seen if int(jid.split("-")[1]) < len(s.legs) - 1]
    assert len(passed) >= 20                    # une grille de 500 m : un carrefour tous les 500 m
    revs = rec.of("revision")
    assert [r["rev"] for r in revs] == list(range(1, len(revs) + 1))
    assert all(r["changed_from_part"] >= max(0, math.floor((r["length_m"] - 5000) / 1000)) for r in revs[1:])
    mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"20 km simulés en {dt:.1f} s, {len(revs)} révisions, {len(s.ready)} carrés, mémoire max {mem:.0f} Mo")


def test_choose_rewrites_after_junction_and_locks(grid, tmp_path) -> None:
    s, rec = session(tmp_path, grid)
    s.handle(open_msg())
    j = min((j for j in s.junctions.values() if j.s_m > 600), key=lambda j: j.s_m)
    s_m = j.s_m - 100
    s.handle({"type": "progress", "s_m": s_m, "v_mps": 8})
    j = s.junctions[j.id]
    other = next(k for k in range(len(j.branches)) if k != j.default)
    n_rev = len(rec.of("revision"))
    t0 = time.perf_counter()
    s.handle({"type": "choose", "junction_id": j.id, "branch": other})
    assert time.perf_counter() - t0 < 1.0
    rev = rec.of("revision")[n_rev]
    assert rev["changed_from_part"] == math.floor((j.s_m - 100) / 1000)
    br = j.branches[other]
    assert s.legs[j.leg + 1].key == (br.edge.id, br.forward) and s.length_m - s_m >= 3000
    data = json.loads((tmp_path / "seance.world" / "junctions.json").read_text())
    entry = next(x for x in data["junctions"] if x["id"] == j.id)
    assert entry["chosen"] == other and entry["default"] == j.default and not entry["locked"]
    # Les parties avant le carrefour n'ont pas bougé ; la route suit l'amorce de la branche choisie.
    part = json.loads((tmp_path / "seance.world" / "route" / f"part_{math.floor(j.s_m / 1000)}.json").read_text())
    pv = entry["branches"][other]["preview"]
    k = int(round((j.s_m + 50 - part["s0_m"]) / 10))
    if k < part["n"]:
        assert math.hypot(part["x"][k] - pv["x"][5], part["z"][k] - pv["z"][5]) < 1.5
    # À 20 m du carrefour suivant : verrouillé.
    j2 = min((x for x in s.junctions.values() if x.s_m > j.s_m + 100), key=lambda x: x.s_m)
    s.handle({"type": "progress", "s_m": j2.s_m - 20, "v_mps": 8})
    s.handle({"type": "choose", "junction_id": j2.id, "branch": 0})
    assert rec.msgs[-1]["type"] == "error" and rec.msgs[-1]["code"] == "branch_locked"
    s.handle({"type": "choose", "junction_id": "j0-0", "branch": 0})
    assert rec.msgs[-1]["code"] == "unknown_junction"


def test_offline_stays_in_cached_zone_and_turns_back(tmp_path) -> None:
    db = line_db(tmp_path / "ligne.sqlite")
    limit = E_REF + 4500
    s, rec = session(tmp_path, db, Relief(limit_e=limit), network=False)
    s.handle(open_msg(E_REF + 100, N_REF, 90.0, network=False))
    for k in range(1, 40):
        s.handle({"type": "progress", "s_m": 250.0 * k, "v_mps": 8})
    assert all(float(np.max(leg.profile.x)) < limit for leg in s.legs)
    keys = [leg.key for leg in s.legs]
    turns = [i for i in range(1, len(keys)) if keys[i][0] == keys[i - 1][0] and keys[i][1] != keys[i - 1][1]]
    assert turns and s.legs[turns[0] - 1].profile.x[-1] == pytest.approx(E_REF + 4000, abs=1)
    assert any(m["type"] == "status" and m["data"] == "offline" for m in rec.msgs)
    assert json.loads((tmp_path / "seance.world" / "live.json").read_text())["status"] == "offline"


def test_unavailable_world(tmp_path) -> None:
    cache = WorldCache(tmp_path / "cache", 10**9, log=lambda _m: None)
    rec = Recorder()
    s = WorldSession(cache, Relief(), rec, {}, tmp_path / "x.world", log=lambda _m: None)
    s.handle(open_msg())
    assert rec.msgs[-1] == {"type": "error", "code": "world_unavailable", "message": rec.msgs[-1]["message"]}
    s2, rec2 = session(tmp_path / "b", line_db(tmp_path / "l.sqlite"))
    s2.handle(open_msg(E_REF, N_REF + 900))                    # route à 900 m
    assert rec2.msgs[-1]["code"] == "world_unavailable"


def _run_process(tmp_path: Path, cache_dir: Path, messages: list) -> tuple[list[dict], str]:
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[open_world]\ncache_dir = "{cache_dir}"\n', encoding="utf-8")
    lat, lon = latlon(E_REF, N_REF)
    proc = subprocess.Popen(
        [sys.executable, "-m", "openride_compiler.worldgen.process", "--config", str(cfg), "--no-network",
         "--fake-clock", "--synthetic-relief", f"{lat},{lon}"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        cwd=Path(__file__).resolve().parents[1], env={**__import__("os").environ,
                                                      "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
    lines = [m if isinstance(m, str) else json.dumps(m) for m in messages]
    out, err = proc.communicate("".join(line + "\n" for line in lines), timeout=120)
    assert proc.returncode == 0, err
    return [json.loads(line) for line in out.splitlines()], err


def test_process_end_to_end_and_second_session_reuses_cache(grid, tmp_path) -> None:
    cache_dir = tmp_path / "cache"
    (cache_dir / "brut" / "osm").mkdir(parents=True)
    (cache_dir / "brut" / "osm" / "grille.sqlite").write_bytes(grid.read_bytes())
    msgs = [open_msg(network=False), {"type": "progress", "s_m": 50.0, "v_mps": 8.0}, "pas du json",
            {"type": "close"}]
    out, err = _run_process(tmp_path, cache_dir, msgs)
    kinds = [m["type"] for m in out]
    ready_at = next(i for i, m in enumerate(out) if m["type"] == "status" and m["phase"] == "ready")
    assert kinds[-1] == "closed" and kinds.index("revision") == ready_at + 1
    ready = next(m for m in out if m["type"] == "status" and m["phase"] == "ready")
    assert ready["squares_ready"] == ready["squares_needed"] > 10
    assert "lignes illisibles 1" in err and "carrés générés 0" not in err
    sessions = sorted((cache_dir / "seances").glob("ow-*.world"))
    assert len(sessions) == 1 and (sessions[0] / "route" / "part_0.json").is_file()
    out2, err2 = _run_process(tmp_path, cache_dir, msgs)
    assert out2[-1]["type"] == "closed"
    assert "carrés générés 0," in err2 and "tuiles lointaines générées 0," in err2 and "téléchargements 0," in err2
