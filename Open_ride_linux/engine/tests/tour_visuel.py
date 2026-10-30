#!/usr/bin/env python3
"""Tour visuel guidé (lot X21) : la caméra va seule aux endroits à regarder d'un vrai parcours compilé.

Usage :
    tour_visuel.py [--godot CHEMIN] (--world demo|village|osm|DOSSIER.world) [--auto] [--tour FICHIER.json]
                   [--quality low|medium|high] [--size 1280x720] [--native] [--out DOSSIER] [--keep]

Les recettes visuelles (E3/E4, P16, P17, U18, Y11/Y12) demandent de rouler jusqu'au bon endroit pour regarder.
Ici, la vraie scène de l'engine (`main.tscn`, `--test-mode`, préréglage `--quality`) charge le parcours face au
faux core des tests graphiques (`visual_check.VisualCore`, aucun vrai core) ; pour chaque point, le faux core
place le cycliste à la distance voulue, l'engine prend la vue de caméra et la météo demandées, le tour attend que
les tuiles voulues soient toutes affichées (`streaming_pending` de la capture à 0) puis capture.

Points :
- `--tour engine/tests/tours/NOM.json` : `{"description", "world", "points": [{"id", "s", "label", "camera",
  "weather"}]}` ; `camera` : subjective (défaut), follow_near, follow_far ou side ; `weather` : objet du
  message de test `weather` (ex. `{"kind": "rain", "intensity": 0.8}`), temps clair sinon ;
- `--auto` : tirés du parcours (`auto_points`) : départ et arrivée, plat et montées à 5 et 10 % (pente lissée
  sur 200 m), village le plus dense (bâtiments à moins de 150 m de la route), forêt et eau les plus proches de la
  route, frontières de biome (couche `biome`). Les deux se cumulent.

L'heure du jour n'est pas réglable : l'engine n'a pas de cycle jour et nuit.

Sortie dans `--out` (défaut `~/OpenRide/tour_visuel/<date>_<heure>/`) : une capture PNG par point,
`points.json` (points joués et mesures), `mesures.csv` et `planche.html` : une carte par point, la capture, les
mesures (triangles, appels de dessin, maillages, images par seconde, tuiles encore en attente), trois cases
« OK / à revoir / défaut » et une note, gardées dans la page (localStorage) et exportables en JSON. Le
propriétaire juge, l'outil fait le trajet. Code 0 si chaque point a sa capture, 1 sinon, 2 si Godot ou
xvfb-run manque.
"""

from __future__ import annotations

import argparse
import copy
import html
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
ENGINE_DIR = TESTS_DIR.parent
TOURS_DIR = TESTS_DIR / "tours"
sys.path.insert(0, str(TESTS_DIR))

CAMERAS = ("subjective", "follow_near", "follow_far", "side")
POINT_KEYS = {"id", "s", "label", "camera", "weather"}
GRADE_WINDOW_M = 200.0
GRADE_TARGETS = ((0.0, "plat", "Plat (pente lissée vers 0 %)"), (5.0, "montee_5", "Montée vers 5 %"),
                 (10.0, "montee_10", "Montée vers 10 %"))
GRADE_TOLERANCE = 1.5          # % : une montée « à 10 % » qui n'existe pas n'est pas inventée
MIN_GAP_M = 150.0              # deux points automatiques plus proches sont fusionnés
NEAR_ROUTE_M = 150.0           # bâtiments comptés autour de la route
FEATURE_MAX_M = 300.0          # forêt ou eau plus loin : pas de point
WOOD_KINDS = {"wood", "forest"}
BIOME_STEP_M = 50.0
MAX_BIOME_POINTS = 3
SETTLE_S = 2.5
PENDING_RETRIES = 12


class TourError(ValueError):
    """Fichier de tour ou parcours illisible."""


# --- parcours ------------------------------------------------------------------------------------

def load_world(world_dir: Path) -> dict[str, Any]:
    """Route et couches utiles d'un dossier .world : {"route", "manifest", "buildings", "vegetation", "water", "dir"}."""
    try:
        manifest = json.loads((world_dir / "manifest.json").read_text(encoding="utf-8"))
        route = json.loads((world_dir / "route.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TourError(f"parcours illisible : {world_dir} ({exc})") from None

    def chunks(layer: str, key: str) -> list[dict]:
        out: list[dict] = []
        for p in sorted((world_dir / layer).glob("chunk_*.json")):
            try:
                out += json.loads(p.read_text(encoding="utf-8")).get(key, [])
            except (OSError, ValueError):
                continue
        return out

    water = [{"points": [(p[0], p[1]) for p in w.get("points", [])]} for w in chunks("water", "lines")]
    water += [{"points": [tuple(p[:2]) for p in a.get("outer", [])]} for a in chunks("water", "areas")]
    return {"dir": world_dir, "manifest": manifest, "route": route, "buildings": chunks("buildings", "buildings"),
            "vegetation": chunks("vegetation", "areas"), "water": water}


def _centroid(points: list) -> tuple[float, float]:
    xs = [float(p[0]) for p in points]
    zs = [float(p[1]) for p in points]
    return sum(xs) / len(xs), sum(zs) / len(zs)


def _samples(route: dict[str, Any], step_m: float) -> list[tuple[float, float, float, int]]:
    """(s, x, z, indice) tous les `step_m` mètres."""
    ds = float(route["ds_m"])
    every = max(1, int(round(step_m / ds)))
    return [(i * ds, float(route["x"][i]), float(route["z"][i]), i) for i in range(0, int(route["n"]), every)]


def smoothed_grades(route: dict[str, Any], window_m: float = GRADE_WINDOW_M) -> list[float]:
    """Pente moyenne (%) sur `window_m` centrés sur chaque point, à partir des altitudes."""
    ds = float(route["ds_m"])
    alt = [float(a) for a in route["alt_m"]]
    n = len(alt)
    half = max(1, int(round(window_m / ds / 2)))
    out = []
    for i in range(n):
        a, b = max(0, i - half), min(n - 1, i + half)
        out.append(100.0 * (alt[b] - alt[a]) / ((b - a) * ds) if b > a else 0.0)
    return out


def _dominant_biome(world_dir: Path, x: float, z: float, cache: dict) -> str | None:
    """Biome de plus grand poids au point (couche `biome`, tuiles proches de 1 000 m, grille 17 × 17)."""
    ix, iz = math.floor(x / 1000.0), math.floor(z / 1000.0)
    if (ix, iz) not in cache:
        p = world_dir / "biome" / "near" / f"tile_{ix}_{iz}.json"
        try:
            cache[(ix, iz)] = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache[(ix, iz)] = None
    tile = cache[(ix, iz)]
    if not tile:
        return None
    i = min(16, max(0, round((x - ix * 1000.0) / 1000.0 * 16)))
    j = min(16, max(0, round((z - iz * 1000.0) / 1000.0 * 16)))
    weights = [g[j * 17 + i] for g in tile["weights"]]
    return tile["biomes"][weights.index(max(weights))]


def auto_points(world: dict[str, Any]) -> list[dict[str, Any]]:
    """Points à regarder tirés du parcours, triés par distance ; chacun dit pourquoi il est là (`label`)."""
    route = world["route"]
    length = float(route["length_m"])
    found: list[dict[str, Any]] = [
        {"id": "depart", "s": min(30.0, length * 0.02), "label": "Départ"},
        {"id": "arrivee", "s": max(0.0, length - 60.0), "label": "Arrivée"},
    ]
    grades = smoothed_grades(route)
    ds = float(route["ds_m"])
    margin = int(GRADE_WINDOW_M / ds / 2)
    usable = range(margin, max(margin + 1, len(grades) - margin))
    for target, pid, label in GRADE_TARGETS:
        best = min(usable, key=lambda i: abs(grades[i] - target))
        if abs(grades[best] - target) <= GRADE_TOLERANCE:
            found.append({"id": pid, "s": best * ds, "label": f"{label} : {grades[best]:.1f} %"})
    samples = _samples(route, 25.0)
    houses = [_centroid(b["outer"]) for b in world["buildings"] if b.get("outer")]
    if houses:
        # Le plus de bâtiments à portée, puis, à égalité, au plus près d'eux (le cœur du village).
        def around(x: float, z: float) -> tuple[int, float]:
            d = [math.hypot(hx - x, hz - z) for hx, hz in houses]
            near = [v for v in d if v <= NEAR_ROUTE_M]
            return len(near), -sum(near)
        (n, _), s = max((around(x, z), s) for s, x, z, _ in samples)
        if n:
            found.append({"id": "village", "s": s, "label": f"Village le plus dense : {n} bâtiment(s) à moins de "
                                                          f"{NEAR_ROUTE_M:.0f} m"})
    woods = [_centroid(a["outer"]) for a in world["vegetation"] if a.get("kind") in WOOD_KINDS and a.get("outer")]
    for pid, label, spots in (("foret", "Forêt", woods),
                              ("eau", "Eau", [p for w in world["water"] for p in w["points"]])):
        if not spots:
            continue
        d, s = min((min(math.hypot(px - x, pz - z) for px, pz in spots), s) for s, x, z, _ in samples)
        if d <= FEATURE_MAX_M:
            found.append({"id": pid, "s": s, "label": f"{label} la plus proche : à {d:.0f} m de la route"})
    if (world["manifest"].get("layers", {}).get("biome") or {}).get("present"):
        cache: dict = {}
        prev = None
        k = 0
        for s, x, z, _ in _samples(route, BIOME_STEP_M):
            b = _dominant_biome(world["dir"], x, z, cache)
            if b is not None and prev is not None and b != prev and k < MAX_BIOME_POINTS:
                k += 1
                found.append({"id": f"biome_{k}", "s": s, "label": f"Frontière de biome : {prev} → {b}"})
            prev = b if b is not None else prev
    out: list[dict[str, Any]] = []
    for p in sorted(found, key=lambda p: p["s"]):
        near = [q for q in out if abs(q["s"] - p["s"]) < MIN_GAP_M]
        if near:
            near[0]["label"] += " ; " + p["label"]
            continue
        out.append({**p, "s": round(p["s"], 1), "camera": "subjective"})
    return out


def validate_tour(doc: Any, where: str = "tour") -> list[dict[str, Any]]:
    if not isinstance(doc, dict) or not isinstance(doc.get("points"), list):
        raise TourError(f"{where} : objet avec une liste `points` attendu")
    out = []
    for k, p in enumerate(doc["points"]):
        w = f"{where}.points[{k}]"
        if not isinstance(p, dict) or not isinstance(p.get("s"), (int, float)) or p["s"] < 0:
            raise TourError(f"{w} : distance `s` en mètres attendue")
        unknown = set(p) - POINT_KEYS
        if unknown:
            raise TourError(f"{w} : clé(s) inconnue(s) {sorted(unknown)}")
        if p.get("camera", "subjective") not in CAMERAS:
            raise TourError(f"{w}.camera : {', '.join(CAMERAS)}")
        if "weather" in p and not isinstance(p["weather"], dict):
            raise TourError(f"{w}.weather : objet attendu (message de test `weather`)")
        out.append({"id": str(p.get("id", f"p{k + 1}")), "s": float(p["s"]), "label": str(p.get("label", "")),
                    "camera": p.get("camera", "subjective"), **({"weather": p["weather"]} if "weather" in p else {})})
    return out


# --- planche -------------------------------------------------------------------------------------

def write_board(out: Path, title: str, points: list[dict[str, Any]]) -> Path:
    """planche.html : une carte par point, cases OK / à revoir / défaut et note gardées dans la page."""
    cards = []
    for p in points:
        m = p.get("mesures", {})
        measures = " · ".join(f"{label} {m[k]}" for k, label in (
            ("triangles", "triangles"), ("draw_calls", "appels de dessin"), ("meshes", "maillages"),
            ("fps", "images/s"), ("pending", "tuiles en attente"), ("particles", "particules de météo"),
            ("wetness", "chaussée mouillée")) if m.get(k))
        img = (f'<img src="{html.escape(p["file"])}" alt="{html.escape(p["id"])}" loading="lazy">'
               if p.get("file") else '<div class="missing">pas de capture</div>')
        radios = "".join(f'<label><input type="radio" name="{html.escape(p["id"])}" value="{v}"> {t}</label>'
                         for v, t in (("ok", "OK"), ("revoir", "à revoir"), ("defaut", "défaut")))
        extra = (f" · météo {html.escape(json.dumps(p['weather'], ensure_ascii=False))}" if p.get("weather") else "")
        cards.append(f'''<section class="card" data-id="{html.escape(p["id"])}">
  <h2>{html.escape(p["id"])} · {p["s"] / 1000:.2f} km · {html.escape(p["camera"])}{extra}</h2>
  <p class="why">{html.escape(p.get("label", ""))}</p>
  {img}
  <p class="m">{html.escape(measures)}</p>
  <div class="verdict">{radios}</div>
  <textarea placeholder="Note"></textarea>
</section>''')
    key = "tour_visuel:" + out.name
    page = f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tour visuel</title>
<style>
:root {{ --bg:#f6f7f9; --card:#fff; --ink:#1b1f24; --dim:#5b6470; --line:#d9dde3; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#14171b; --card:#1d2228; --ink:#e8ecf1; --dim:#9aa4b1; --line:#323a44; }} }}
body {{ margin:0; padding:16px; background:var(--bg); color:var(--ink); font:15px/1.45 system-ui, sans-serif; }}
header {{ display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; margin-bottom:16px; }}
h1 {{ font-size:20px; margin:0; }} h2 {{ font-size:15px; margin:0 0 4px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(min(100%, 420px), 1fr)); gap:16px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px; }}
.card img {{ width:100%; height:auto; border-radius:4px; display:block; }}
.why, .m {{ color:var(--dim); margin:4px 0; }} .missing {{ padding:40px; text-align:center; color:var(--dim); }}
.verdict {{ display:flex; gap:14px; margin:6px 0; }} textarea {{ width:100%; box-sizing:border-box; min-height:44px; }}
button {{ padding:6px 12px; }}
</style></head><body>
<header><h1>{html.escape(title)}</h1><span id="count"></span><button id="export">Exporter en JSON</button></header>
<div class="grid">
{chr(10).join(cards)}
</div>
<script>
const KEY = {json.dumps(key)};
let saved = {{}};
try {{ saved = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ saved = {{}}; }}
function save() {{ try {{ localStorage.setItem(KEY, JSON.stringify(saved)); }} catch (e) {{}} count(); }}
function count() {{
  const n = document.querySelectorAll(".card").length;
  const done = Object.values(saved).filter(v => v.verdict).length;
  document.getElementById("count").textContent = done + " / " + n + " points jugés";
}}
document.querySelectorAll(".card").forEach(card => {{
  const id = card.dataset.id, cur = saved[id] || {{}};
  card.querySelectorAll("input").forEach(r => {{
    r.checked = r.value === cur.verdict;
    r.addEventListener("change", () => {{ saved[id] = {{...(saved[id] || {{}}), verdict: r.value}}; save(); }});
  }});
  const t = card.querySelector("textarea");
  t.value = cur.note || "";
  t.addEventListener("input", () => {{ saved[id] = {{...(saved[id] || {{}}), note: t.value}}; save(); }});
}});
document.getElementById("export").addEventListener("click", () => {{
  const blob = new Blob([JSON.stringify(saved, null, 2)], {{type: "application/json"}});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "verdicts_tour_visuel.json"; a.click();
}});
count();
</script>
</body></html>
'''
    path = out / "planche.html"
    path.write_text(page, encoding="utf-8")
    return path


# --- tour ----------------------------------------------------------------------------------------

def run_tour(args: argparse.Namespace, world_dir: Path, route_id: str, routes: Path, points: list[dict[str, Any]],
             out: Path) -> list[dict[str, Any]]:
    from e2e_check import free_udp_ports
    from fake_core import EngineLog, now
    from visual_check import AVATAR_PROGRESSION, CONTRACT_VERSION, VisualCore

    width, height = (int(v) for v in args.size.lower().split("x"))
    state_port, cmd_port = free_udp_ports(2)
    log_path = out / "engine.log"
    log_path.write_text("")
    core = VisualCore(state_port, cmd_port, EngineLog(log_path))
    core.route_id = route_id
    core.progression = copy.deepcopy(AVATAR_PROGRESSION)   # avatar présent : les quatre vues de caméra
    core.start()
    cmd = [str(args.godot), "--path", str(ENGINE_DIR), "--resolution", f"{width}x{height}", "--audio-driver", "Dummy"]
    if not args.native:
        cmd = ["xvfb-run", "-a", "-s", f"-screen 0 {width}x{height}x24"] + cmd + [
            "--rendering-driver", "opengl3", "--rendering-method", "gl_compatibility"]
    cmd += ["--", f"--ipc-state-port={state_port}", f"--ipc-cmd-port={cmd_port}", f"--routes-dir={routes}",
            "--test-mode", f"--quality={args.quality}", "--camera=subjective"]
    with log_path.open("w") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    done: list[dict[str, Any]] = []
    try:
        t0 = now()
        while now() - t0 < 30.0 and "IpcClient attaché" not in log_path.read_text(errors="replace"):
            time.sleep(0.2)
        core.set_scene(speed=0.0, s=points[0]["s"] if points else 0.0, session_state="RUNNING", power=200.0,
                       power_3s=200.0, cadence=85.0, mode="SIM", erg=None, pause_reason=None,
                       trainer_status="CONNECTED", input_status="CONNECTED")
        core.auto_hello_ack = True
        core.streaming = True
        loaded = core.log.wait_for(rf"^route_loaded id={route_id}", 60.0)
        if loaded is None:
            print(f"[ÉCHEC] parcours {route_id} non chargé par l'engine en 60 s")
            return [{**p, "file": "", "mesures": {}} for p in points]
        for k, p in enumerate(points):
            mark = core.log.mark()
            core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "weather",
                           "weather": p.get("weather") or {"kind": "clear"}})
            core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "camera_view", "view": p["camera"]})
            core.log.wait_for(r"^camera_view done=", 5.0, mark)
            core.set_scene(speed=0.0, s=p["s"])
            time.sleep(SETTLE_S)
            info: dict[str, Any] | None = None
            png = out / f"{k + 1:02d}_{p['id']}.png"
            for _ in range(PENDING_RETRIES):
                mark = core.log.mark()
                core.send_raw({"type": "_test", "v": CONTRACT_VERSION, "action": "screenshot", "path": str(png),
                               "tag": p["id"]})
                hit = core.log.wait_for(r"^screenshot (\{.*\})$", 15.0, mark)
                info = json.loads(hit[1].group(1)) if hit else None
                if info is None or int(info.get("streaming_pending", 0)) == 0:
                    break
                time.sleep(1.0)
            ok = bool(info and info.get("ok")) and png.is_file()
            m = {} if info is None else {"triangles": int(info.get("triangles", 0)),
                                         "draw_calls": int(info.get("draw_calls", 0)),
                                         "meshes": int(info.get("meshes", 0)), "fps": round(float(info.get("fps", 0))),
                                         "pending": int(info.get("streaming_pending", 0)),
                                         "camera": info.get("camera_view"),
                                         "particles": int(info.get("decor", {}).get("particles", 0)),
                                         "wetness": round(float(info.get("decor", {}).get("wetness", 0.0)), 2)}
            print(f"[{'OK' if ok else 'ÉCHEC'}] {p['id']} à {p['s']:.0f} m ({p['camera']}) : "
                  + (f"{m['triangles']} triangles, {m['draw_calls']} appels, {m['pending']} tuile(s) en attente"
                     if ok else "pas de capture"), flush=True)
            done.append({**p, "file": png.name if ok else "", "mesures": m})
    finally:
        core.stop()
        try:
            os.killpg(proc.pid, 15)
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(proc.pid, 9)
            except ProcessLookupError:
                pass
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tour visuel guidé (lot X21).")
    ap.add_argument("--godot", type=Path, default=Path(os.environ.get(
        "GODOT", Path.home() / "Applications/godot/Godot_v4.7.2-stable_linux.x86_64")))
    ap.add_argument("--world", required=True, help="demo, village, osm, ou dossier .world compilé")
    ap.add_argument("--auto", action="store_true", help="points tirés du parcours")
    ap.add_argument("--tour", type=Path, help="liste de points (engine/tests/tours/*.json, ou un nom de ce dossier)")
    ap.add_argument("--quality", default="low", help="low, medium ou high (défaut low)")
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--native", action="store_true", help="fenêtre sur l'écran réel, sans Xvfb")
    ap.add_argument("--out", type=Path, default=Path.home() / "OpenRide" / "tour_visuel" / time.strftime("%Y-%m-%d_%H%M%S"))
    ap.add_argument("--keep", action="store_true", help="garder le dossier temporaire du parcours")
    args = ap.parse_args(argv)
    if not args.auto and args.tour is None:
        ap.error("--auto ou --tour (ou les deux)")
    if not os.access(args.godot, os.X_OK):
        print(f"Godot introuvable : {args.godot} (option --godot ou variable GODOT)")
        return 2
    if not args.native and shutil.which("xvfb-run") is None:
        print("xvfb-run introuvable : installer xvfb, xauth et libgl1-mesa-dri (ou lancer avec --native)")
        return 2
    from sim_bench import prepare_world

    tmp = Path(tempfile.mkdtemp(prefix="openride-tour-"))
    try:
        routes = tmp / "routes"
        route_id = prepare_world(args.world, routes, tmp)
        world_dir = next(p for p in routes.iterdir() if p.is_dir() and p.name.split(".")[0] == route_id)
        world = load_world(world_dir)
        points: list[dict[str, Any]] = []
        if args.tour is not None:
            path = args.tour if args.tour.is_file() else TOURS_DIR / f"{args.tour}.json"
            points += validate_tour(json.loads(path.read_text(encoding="utf-8")), path.name)
        if args.auto:
            points += auto_points(world)
        length = float(world["route"]["length_m"])
        points = sorted((p for p in points if p["s"] <= length), key=lambda p: p["s"])   # dans le sens de la route
        if not points:
            print("Aucun point à regarder sur ce parcours.")
            return 1
        args.out.mkdir(parents=True, exist_ok=True)
        print(f"== Tour visuel : {route_id}, {len(points)} point(s), préréglage {args.quality} ==", flush=True)
        done = run_tour(args, world_dir, route_id, routes, points, args.out)
    finally:
        if args.keep:
            print(f"Dossier temporaire gardé : {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    (args.out / "points.json").write_text(json.dumps(done, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "mesures.csv").write_text("point;s_m;camera;triangles;appels_de_dessin;maillages;images_s;tuiles_en_attente;capture\n" + "".join(
        f"{p['id']};{p['s']:.0f};{p['camera']};{p['mesures'].get('triangles', '')};{p['mesures'].get('draw_calls', '')};"
        f"{p['mesures'].get('meshes', '')};{p['mesures'].get('fps', '')};{p['mesures'].get('pending', '')};{p['file']}\n"
        for p in done), encoding="utf-8")
    board = write_board(args.out, f"Tour visuel : {route_id} ({args.quality})", done)
    missing = [p["id"] for p in done if not p["file"]]
    print(f"Planche : {board}")
    print("RÉSULTAT : " + ("tour complet" if not missing else f"ÉCHEC, sans capture : {', '.join(missing)}"))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.path.insert(0, str(ENGINE_DIR.parent / "scripts"))
    from isolation_tests import verrou_suite   # une seule suite de tests ou banc à la fois

    with verrou_suite("tour_visuel"):
        code = main()
    sys.exit(code)
