"""Contrôle de la phase du vent sur une longue séance (lot EC10, revue E12-51) : engine/tests/wind_phase_check.py."""

import importlib.util
import math
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "engine" / "tests" / "wind_phase_check.py"
spec = importlib.util.spec_from_file_location("wind_phase_check", SCRIPT)
wpc = importlib.util.module_from_spec(spec)
sys.modules["wind_phase_check"] = wpc
spec.loader.exec_module(wpc)


def _probe(path: Path, seconds: int, drift: float = 0.0) -> Path:
    """moteur.csv en rafales ; `drift` ajoute une avance qui grandit avec la durée (le défaut à attraper)."""
    lines = ["t_s;wind_phase;wind_strength;wind_gust;preset"]
    phase = 0.0
    for t in range(seconds + 1):
        g = 0.5 + 0.5 * math.sin(t / 7.0)
        s = 0.4 + 0.1 * g
        lines.append(f"{t:.2f};{phase:.2f};{s:.2f};{g:.2f};low")
        phase += wpc.phase_rate(s, g) * (1.0 + drift * t)
    lines.append("999;1")   # ligne en cours d'écriture : ignorée
    path.mkdir(parents=True, exist_ok=True)
    (path / "moteur.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_phase_sans_derive_acceptee(tmp_path):
    assert wpc.main([str(_probe(tmp_path / "banc" / "vent_duree", 900))]) == 0


def test_phase_qui_derive_refusee(tmp_path):
    assert wpc.main([str(_probe(tmp_path / "banc", 900, drift=0.002))]) == 1


def test_seance_trop_courte_refusee(tmp_path):
    assert wpc.main([str(_probe(tmp_path / "banc", 300))]) == 1


def test_sonde_sans_colonnes_du_vent(tmp_path):
    (tmp_path / "moteur.csv").write_text("t_s;fps;preset\n1.00;60.00;low\n", encoding="utf-8")
    assert wpc.main([str(tmp_path)]) == 2
