"""Banc des effets de rendu sur un tronçon de biomes (`engine/tests/cout_rendu.py --troncon`, 6 novembre).

Sonde fabriquée (une ligne par seconde à 60 km/h) sur le tronçon cultures → forêt → alpin : chaque seconde
est rangée dans le biome du plan `make_biome_world`, frontières de 300 m à part, et `cout.md` donne le GPU
médian de chaque variante dans chaque biome avec son gain par rapport à `base`.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"
sys.path.insert(0, str(TESTS))
spec = importlib.util.spec_from_file_location("cout_rendu", TESTS / "cout_rendu.py")
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)

TRONCON = ("farmland", "temperate_forest", "alpine")
HEAD = ["t_s", "unix_s", "fps", "frame_p99_ms", "gpu_ms", "primitives"]


def _fake_run(rdir: Path, gpu_of_m) -> None:
    """Dossier `<rdir>/demo/` de sim_bench : moteur.csv et journal de séance, 60 km/h pendant 260 s."""
    sdir = rdir / "demo"
    sdir.mkdir(parents=True)
    t0, speed = 1_800_000_000.0, 60.0 / 3.6
    rows, records = [";".join(HEAD)], []
    for k in range(260):
        d = k * speed
        rows.append(";".join(str(v) for v in (k, t0 + k, 60.0, 16.67, gpu_of_m(d), 1_000_000)))
        records.append(json.dumps({"kind": "record", "ts": t0 + k, "distance": d}))
    (sdir / "moteur.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (sdir / "seance.jsonl").write_text("\n".join(records) + "\n", encoding="utf-8")


def _gpu(extra_forest: float):
    return lambda d: 5.0 if d < 2000.0 else 5.0 + extra_forest


def test_duree_par_defaut_couvre_tous_les_blocs_sauf_le_dernier():
    assert cr.troncon_duration(TRONCON) == 2 * 2000.0 / (60.0 / 3.6) + 45.0


def test_variantes_de_densite_relatives_au_preset():
    variants = {v[0]: v for v in cr.VARIANTS}
    assert variants["vegetation_50"][1] == "vegetation_x=0.5"
    assert variants["sans_arbres"][1] == "vegetation_x=0"
    assert variants["sans_imposteurs"][2] == ("--forest", "off")


def test_analyse_par_biome(tmp_path):
    (tmp_path / "troncon.txt").write_text(",".join(TRONCON) + "\n", encoding="utf-8")
    for rep in ("r1", "r2"):
        _fake_run(tmp_path / "low" / "base" / rep, _gpu(2.0))
        _fake_run(tmp_path / "low" / "sans_arbres" / rep, _gpu(0.5))
    assert cr.analyse(tmp_path) == 0
    res = json.loads((tmp_path / "cout.json").read_text(encoding="utf-8"))
    base = res["low"]["base"]["par_biome"]
    assert base["farmland"]["gpu_ms"] == 5.0
    assert base["temperate_forest"]["gpu_ms"] == 7.0
    assert base["farmland"]["secondes"] > 0 and base["frontières"]["secondes"] > 0
    assert res["low"]["sans_arbres"]["par_biome"]["temperate_forest"]["gpu_ms"] == 5.5
    md = (tmp_path / "cout.md").read_text(encoding="utf-8")
    assert "## Par biome du tronçon" in md
    assert "| sans_arbres | 5.00 (+0.00) | 5.50 (+1.50) |" in md
    assert "**7.00**" in md   # base au-dessus du budget low (6 ms) en gras
