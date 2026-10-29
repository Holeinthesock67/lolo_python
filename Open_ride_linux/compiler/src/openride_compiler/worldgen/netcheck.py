"""`openride-worldgen-netcheck` (lot X28) : le vrai générateur sur un réseau dégradé simulé.

Lance `fake_tile_server` (tuiles vectorielles et relief synthétiques, au large de la Camargue comme
W15 : aucun lieu réel), puis le vrai `openride-worldgen` en sous-processus (`--tiles-url`,
`--dem-url`, `--fake-clock`, cache temporaire au plafond réduit), sans extrait régional : tout
passe par le réseau. Un cycliste simulé roule en temps accéléré (`acceleration` × le temps réel :
une demi-seconde simulée par `progress`) et s'arrête, comme le core, quand il reste moins de
`WAIT_BELOW_M` de route connue devant lui. Puis une seconde séance repart du même endroit.

Vérifications (une ligne chacune, `[OK]` / `[ÉCHEC]`) :

1. départ : première route publiée ;
2. aucune exception ni erreur interne (journal du générateur, messages `error`) ;
3. aucune pause d'attente (W16 : aucune ; plus courte route connue devant le cycliste) ;
4. tuiles demandées pendant le trajet (le trajet sort des cellules chargées au départ) ;
5. tuiles redemandées après chaque panne servie ;
6. recul entre deux demandes d'un même chemin (aucune rafale) ;
7. cache plafonné : les vieilles entrées de remplissage sont évincées, jamais au-dessus du plafond ;
8. retour au même endroit : aucun téléchargement (serveur et bilan du générateur) ;
9. scénario en moins d'une minute.

Scénarios intégrés (`reseau/<nom>.json`) : `lent`, `coupure`, `erreurs`, `tronque` ; ou un
fichier JSON de même forme (`{"serveur": {...}, "trajet": {...}}`).
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import mvt
from .fake_tile_server import FakeTileServer, ScenarioError, validate_server
from .store import GB, WorldCache
from .synthetic import ORIGIN_LAT, ORIGIN_LON

SCENARIOS_DIR = Path(__file__).with_name("reseau")
SCENARIOS = ("lent", "coupure", "erreurs", "tronque")
WAIT_BELOW_M = 200.0            # même seuil que `PAUSE_BELOW_M` du core (pause `world_data`)
SIM_TICK_S = 0.5                # temps simulé par `progress` (celui de `--fake-clock`)
OPEN_TIMEOUT_S = 40.0
CLOSE_TIMEOUT_S = 20.0
MIN_RETRY_GAP_S = 1.5           # plus court recul admis entre deux demandes d'un même chemin
MAX_SCENARIO_S = 60.0           # critère 1 du cahier X28
TRIP_DEFAULTS: dict[str, Any] = {
    "duree_s": 25.0,            # trajet de la première séance, en secondes réelles
    "retour_s": 5.0,            # seconde séance au même départ
    "vitesse_mps": 12.0,        # vitesse simulée du cycliste
    "acceleration": 40.0,       # temps simulé / temps réel
    "cache_max_mo": 20.0,       # plafond du cache de la séance
    "remplissage_mo": 18.0,     # vieilles entrées d'une séance passée, évincées en premier
    "seed": 3,
}
FILL_ENTRY_BYTES = 1_000_000
OLD_USE_S = 1_700_000_000.0     # dernière utilisation des entrées de remplissage (2023)


Check = tuple[bool | None, str, str]


@dataclass
class Session:
    """Ce qu'une séance a produit, vu de l'extérieur du générateur."""

    open_s: float | None = None
    ready: bool = False
    errors: list[dict[str, Any]] = field(default_factory=list)
    stderr: str = ""
    returncode: int | None = None
    pause_s: float = 0.0
    min_ahead_m: float = float("inf")
    ridden_m: float = 0.0
    revisions: int = 0
    end_t: float = 0.0


@dataclass
class Report:
    scenario: str
    checks: list[Check] = field(default_factory=list)
    elapsed_s: float = 0.0
    requests: list[dict[str, Any]] = field(default_factory=list)
    first: Session | None = None
    second: Session | None = None

    @property
    def ok(self) -> bool:
        return all(c[0] is not False for c in self.checks)

    def as_dict(self) -> dict[str, Any]:
        return {"scenario": self.scenario, "ok": self.ok, "elapsed_s": round(self.elapsed_s, 1),
                "checks": [{"ok": ok, "label": label, "measure": m} for ok, label, m in self.checks],
                "requests": self.requests}


# --- scénarios -------------------------------------------------------------------------------------

def load_scenario(name: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """(nom, serveur, trajet) d'un scénario intégré ou d'un fichier JSON."""
    path = SCENARIOS_DIR / f"{name}.json" if name in SCENARIOS else Path(name)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ScenarioError(f"scénario {name} illisible : {exc}") from exc
    unknown = set(doc) - {"description", "serveur", "trajet"}
    if unknown:
        raise ScenarioError(f"{path.name} : clé(s) inconnue(s) {sorted(unknown)}")
    trip = dict(TRIP_DEFAULTS)
    extra = set(doc.get("trajet", {})) - set(TRIP_DEFAULTS)
    if extra:
        raise ScenarioError(f"{path.name}, trajet : clé(s) inconnue(s) {sorted(extra)} "
                            f"(connues : {sorted(TRIP_DEFAULTS)})")
    trip.update(doc.get("trajet", {}))
    for k, v in trip.items():
        if not isinstance(v, (int, float)) or v < 0:
            raise ScenarioError(f"{path.name}, trajet.{k} : nombre positif attendu")
    if trip["remplissage_mo"] >= trip["cache_max_mo"]:
        raise ScenarioError(f"{path.name}, trajet : remplissage_mo doit rester sous cache_max_mo")
    return path.stem, validate_server(doc.get("serveur", {})), trip


def start_point() -> tuple[float, float]:
    """Sur la route est-ouest de la tuile synthétique qui contient l'origine de W15."""
    tx, ty = mvt.lonlat_to_tile(14, ORIGIN_LON, ORIGIN_LAT)
    lon, lat = mvt.tile_to_lonlat(14, tx, ty, 4096, 1500, 2048)
    return lat, lon


# --- cache ---------------------------------------------------------------------------------------

def fill_cache(root: Path, cap_bytes: int, fill_bytes: int) -> list[str]:
    """Entrées « carré » d'une séance passée, vieilles de trois ans : les premières à évincer."""
    cache = WorldCache(root, cap_bytes, clock=lambda: OLD_USE_S, log=lambda _m: None)
    keys = []
    for k in range(int(fill_bytes // FILL_ENTRY_BYTES)):
        d = cache.square_dir("99Z", 900 + k, 900)
        d.mkdir(parents=True, exist_ok=True)
        (d / "near.f32").write_bytes(b"\0" * FILL_ENTRY_BYTES)
        cache.add(cache.square_key("99Z", 900 + k, 900), "square", d / "near.f32")
        keys.append(cache.square_key("99Z", 900 + k, 900))
    return keys


# --- générateur ----------------------------------------------------------------------------------

def default_generator() -> list[str]:
    return [sys.executable, "-m", "openride_compiler.worldgen.process"]


def _env(work: Path) -> dict[str, str]:
    src = str(Path(__file__).resolve().parents[2])
    path = os.environ.get("PYTHONPATH", "")
    return {**os.environ, "PYTHONPATH": src + (os.pathsep + path if path else ""),
            "OPENRIDE_DEM_CACHE": str(work / "dem")}


def ride(cmd: list[str], work: Path, server: FakeTileServer, trip: dict[str, Any], duration_s: float,
         log: Callable[[str], None], arm: bool = False) -> Session:
    """Une séance : ouverture, trajet accéléré de `duration_s` secondes réelles, fermeture.

    `arm` : le trajet donne l'origine des instants du serveur (`coupure_s` tombe pendant le trajet).
    """
    out = Session()
    lat, lon = start_point()
    proc = subprocess.Popen(
        cmd + ["--config", str(work / "config.toml"), "--fake-clock", "--tiles-url", f"{server.url}/planet",
               "--dem-url", f"{server.url}/dem"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=_env(work))
    msgs: queue.Queue[dict[str, Any] | None] = queue.Queue()
    err_lines: list[str] = []

    def read_out() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                msgs.put(json.loads(line))
            except ValueError:
                err_lines.append(f"ligne de sortie illisible : {line.strip()[:80]}")
        msgs.put(None)

    def read_err() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            err_lines.append(line.rstrip("\n"))

    threading.Thread(target=read_out, daemon=True).start()
    threading.Thread(target=read_err, daemon=True).start()

    def send(msg: dict[str, Any]) -> bool:
        try:
            assert proc.stdin is not None
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            return True
        except (BrokenPipeError, OSError):
            return False

    length = 0.0
    closed = False

    def drain(block_s: float = 0.0) -> None:
        nonlocal length, closed
        deadline = time.monotonic() + block_s
        while True:
            try:
                m = msgs.get(timeout=max(0.0, deadline - time.monotonic())) if block_s else msgs.get_nowait()
            except queue.Empty:
                return
            if m is None:
                closed = True
                return
            if m.get("type") == "revision":
                length = float(m["length_m"])
                out.revisions += 1
            elif m.get("type") == "error":
                out.errors.append(m)
            elif m.get("type") == "closed":
                closed = True
            if block_s and (out.revisions or closed or out.errors):
                return

    t0 = time.monotonic()
    send({"type": "open", "lat": lat, "lon": lon, "heading_deg": 90.0, "nav": "ride", "target": None,
          "loop_km": None, "seed": int(trip["seed"]), "network": True})
    while not out.revisions and not closed and not out.errors and time.monotonic() - t0 < OPEN_TIMEOUT_S:
        drain(0.5)
    if out.revisions:
        out.open_s = time.monotonic() - t0
        out.ready = True
        log(f"  départ en {out.open_s:.1f} s, {length:.0f} m de route")
        tick = SIM_TICK_S / float(trip["acceleration"])
        v = float(trip["vitesse_mps"])
        s = 0.0
        if arm:
            server.arm()
        start = time.monotonic()
        nxt = start
        while time.monotonic() - start < duration_s and not closed:
            nxt += tick
            time.sleep(max(0.0, nxt - time.monotonic()))
            drain()
            ahead = length - s
            out.min_ahead_m = min(out.min_ahead_m, ahead)
            if ahead < WAIT_BELOW_M:
                out.pause_s += tick                          # le core serait en pause `world_data`
            else:
                s += v * SIM_TICK_S
            if not send({"type": "progress", "s_m": round(s, 2), "v_mps": v}):
                break
        out.ridden_m = s
    out.end_t = server.now()
    send({"type": "close"})
    deadline = time.monotonic() + CLOSE_TIMEOUT_S
    while not closed and time.monotonic() < deadline:
        drain(0.5)
    try:
        assert proc.stdin is not None
        proc.stdin.close()
    except OSError:
        pass
    try:
        out.returncode = proc.wait(timeout=CLOSE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        out.returncode = proc.wait()
    time.sleep(0.1)
    out.stderr = "\n".join(err_lines)
    return out


# --- vérifications -------------------------------------------------------------------------------

def request_checks(requests: list[dict[str, Any]], end_t: float, max_backoff_s: float) -> list[Check]:
    """Reprise après panne et recul, d'après le journal du serveur (première séance)."""
    by_path: dict[str, list[dict[str, Any]]] = {}
    for r in requests:
        by_path.setdefault(r["path"], []).append(r)
    faulted, retried, late = 0, 0, []
    min_gap, worst = float("inf"), ""
    for path, rs in by_path.items():
        rs.sort(key=lambda r: r["t"])
        for a, b in zip(rs, rs[1:]):
            if a["outcome"] != 200 and b["t"] - a["t"] < min_gap:
                min_gap, worst = b["t"] - a["t"], path
        for i, r in enumerate(rs):
            if r["outcome"] in (200, 404):
                continue
            if any(x["outcome"] == 200 for x in rs[i + 1:]):
                faulted += 1
                retried += 1
                break
            if r["t"] > end_t - max_backoff_s:
                continue                                   # panne trop proche de la fin : recul pas écoulé
            faulted += 1
            late.append(path)
            break
    if faulted == 0:
        retry: Check = (None, "tuiles redemandées après chaque panne servie", "aucune panne servie")
    else:
        retry = (retried == faulted, "tuiles redemandées après chaque panne servie",
                 f"{retried}/{faulted} chemin(s) repris" + (f" ; jamais repris : {late[:3]}" if late else ""))
    gap = (min_gap >= MIN_RETRY_GAP_S, f"recul d'au moins {MIN_RETRY_GAP_S:g} s avant de redemander un chemin",
           "aucune demande répétée après une panne" if min_gap == float("inf")
           else f"plus court : {min_gap:.2f} s ({worst})")
    return [retry, gap]


def session_checks(label: str, sess: Session) -> list[Check]:
    bad = [line for line in sess.stderr.splitlines() if "Traceback" in line or "erreur interne" in line]
    errors = [e for e in sess.errors if e.get("code") in ("internal", "world_unavailable")]
    return [(not bad and not errors and sess.returncode == 0, f"{label} : aucune exception ni erreur interne",
             f"code {sess.returncode}, {len(errors)} message(s) error" + (f" ; {bad[0][:120]}" if bad else ""))]


def downloads_in_bilan(stderr: str) -> int | None:
    for line in stderr.splitlines():
        if line.startswith("bilan :") and "téléchargements " in line:
            return int(line.split("téléchargements ")[1].split(",")[0])
    return None


def run_scenario(name: str, generator: list[str] | None = None, work: Path | None = None,
                 log: Callable[[str], None] = print) -> Report:
    sname, server_spec, trip = load_scenario(name)
    report = Report(sname)
    t_start = time.monotonic()
    cmd = generator or default_generator()
    with tempfile.TemporaryDirectory(prefix="openride-netcheck-") as tmp:
        work = Path(work or tmp)
        work.mkdir(parents=True, exist_ok=True)
        cap = int(trip["cache_max_mo"] * 1_000_000)
        cache_dir = work / "cache"
        (work / "config.toml").write_text(
            f'[open_world]\ncache_dir = "{cache_dir}"\ncache_max_gb = {cap / GB:.6f}\n', encoding="utf-8")
        filler = fill_cache(cache_dir, cap, int(trip["remplissage_mo"] * 1_000_000))
        with FakeTileServer(server_spec, seed=int(trip["seed"])) as server:
            log(f"{sname} : faux serveur {server.url}, séance de {trip['duree_s']:g} s (×{trip['acceleration']:g})")
            first = ride(cmd, work, server, trip, float(trip["duree_s"]), log, arm=True)
            n_first = len(server.log)
            log(f"  retour au même départ ({trip['retour_s']:g} s)")
            second = ride(cmd, work, server, trip, float(trip["retour_s"]), log)
            report.requests = list(server.log)
        report.first, report.second = first, second
        first_requests = report.requests[:n_first]
        again = report.requests[n_first:]
        left = {e.key for e in WorldCache(cache_dir, cap, log=lambda _m: None).entries()}
        total = WorldCache(cache_dir, cap, log=lambda _m: None).total_bytes()
    report.elapsed_s = time.monotonic() - t_start

    from .vector_tiles import TILE_RETRY_S
    max_backoff = max(TILE_RETRY_S, default=0.0) + 2.0
    c = report.checks
    c.append((first.ready, "départ : première route publiée",
              f"{first.open_s:.1f} s" if first.open_s is not None else
              f"aucune route ({[e.get('code') for e in first.errors]})"))
    c += session_checks("première séance", first)
    c.append((first.ready and first.pause_s == 0.0, "aucune pause d'attente (W16 : aucune)",
              f"pause {first.pause_s:.1f} s, route connue devant au plus court {first.min_ahead_m:.0f} m, "
              f"{first.ridden_m / 1000:.1f} km roulés"))
    during = [q for q in first_requests if q["t"] >= 0]
    c.append((len(during) > 0, "tuiles demandées pendant le trajet (pas seulement au départ)",
              f"{len(during)} demande(s) après le départ"))
    c += request_checks(first_requests, first.end_t, max_backoff)
    evicted = len([k for k in filler if k not in left])
    above = "au-dessus du plafond" in first.stderr + second.stderr
    c.append((evicted > 0 and not above, "cache plafonné : vieilles entrées évincées, jamais au-dessus du plafond",
              f"{evicted}/{len(filler)} entrée(s) évincée(s), {total / 1e6:.1f} Mo pour {cap / 1e6:.0f} Mo"
              + (" ; au-dessus du plafond" if above else "")))
    c += session_checks("seconde séance", second)
    dl = downloads_in_bilan(second.stderr)
    c.append((second.ready and not again and dl == 0, "retour au même endroit : aucun téléchargement",
              f"{len(again)} demande(s) au serveur, bilan : {dl} téléchargement(s), départ "
              + (f"{second.open_s:.1f} s" if second.open_s is not None else "manqué")))
    c.append((report.elapsed_s < MAX_SCENARIO_S, f"scénario en moins de {MAX_SCENARIO_S:g} s",
              f"{report.elapsed_s:.0f} s"))
    return report


def print_report(r: Report, log: Callable[[str], None] = print) -> None:
    for ok, label, measure in r.checks:
        tag = "[INFO]" if ok is None else "[OK]" if ok else "[ÉCHEC]"
        log(f"  {tag} {label} : {measure}")
    outcomes: dict[str, int] = {}
    for q in r.requests:
        outcomes[str(q["outcome"])] = outcomes.get(str(q["outcome"]), 0) + 1
    log(f"  demandes servies : {len(r.requests)} {dict(sorted(outcomes.items()))}")
    log(f"{r.scenario} : {'OK' if r.ok else 'ÉCHEC'} ({r.elapsed_s:.0f} s)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="openride-worldgen-netcheck",
                                 description="Générateur du monde ouvert sur réseau dégradé simulé (lot X28)")
    ap.add_argument("--scenario", action="append",
                    help=f"{'|'.join(SCENARIOS)} ou fichier JSON ; répétable (par défaut : les quatre)")
    ap.add_argument("--sortie", type=Path, help="rapport JSON (vérifications et demandes servies)")
    ap.add_argument("--garder", type=Path, help="dossier de travail gardé (cache, séances) au lieu d'un dossier temporaire")
    args = ap.parse_args(argv)
    reports = []
    for name in args.scenario or list(SCENARIOS):
        try:
            r = run_scenario(name, work=args.garder / Path(name).stem if args.garder else None)
        except ScenarioError as exc:
            print(f"scénario refusé : {exc}", file=sys.stderr)
            return 2
        print_report(r)
        reports.append(r)
    if args.sortie:
        args.sortie.write_text(json.dumps([r.as_dict() for r in reports], ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(r.ok for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
