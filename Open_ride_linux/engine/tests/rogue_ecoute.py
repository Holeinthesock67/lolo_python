#!/usr/bin/env python3
"""Page d'écoute des sons du Cyber-Rogue (lot X51), pour l'écoute de la recette R18 en quelques minutes.

    engine/tests/rogue_ecoute.py --godot GODOT [--out DOSSIER]

Godot exporte sans écran (tests/rogue_sound_export.gd) chaque bruitage et la musique au niveau où le mode les
joue avec les réglages par défaut, le vent de référence à 30 et 60 km/h, et une scène de salle de 20 s. La page
`ecoute.html` les met dans l'ordre : scène de salle, vent, musique, puis chaque son avec son événement et sa
description (tableau §4.1 du cahier R18). Les sons sont inclus dans la page : elle s'ouvre seule, sur le PC ou
le téléphone. Les mesures de niveau et d'aigus sont faites par tests/unit/test_rogue_sound_levels.gd ; la page
sert au jugement de l'oreille (douceur, rien de strident). Code 0, 2 si Godot manque ou si l'export échoue.
Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import base64
import html
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
CAHIER = ENGINE.parent / "docs" / "lots" / "LOT_R18_bruitages_rogue.md"
ROW = re.compile(r"^\| `(rogue_\w+)` \| (.+?) \| (.+?) \| (.+?) \|$")
REFERENCES = (
    ("scene_salle", "Scène de salle (20 s)", "vent à 35 km/h, deux couches de musique et les bruitages d'une salle"),
    ("vent_30", "Vent à 30 km/h", "référence : le vent du vélo, inchangé dans le mode"),
    ("vent_60", "Vent à 60 km/h", "référence : aucun son du mode ne doit être plus fort"),
    ("musique_boss", "Musique du boss (20 s)", "les trois couches ensemble, au volume par défaut (40 %)"),
)


def sound_table(path: Path = CAHIER) -> list[tuple[str, str, str, str]]:
    """(son, événement, description, durée) du tableau §4.1 du cahier R18, dans l'ordre."""
    out = []
    for line in path.read_text("utf-8").splitlines():
        m = ROW.match(line.strip())
        if m:
            out.append(tuple(g.replace("`", "") for g in m.groups()))
    return out


def export(godot: str, out: Path) -> None:
    cmd = [godot, "--headless", "--path", str(ENGINE), "--script", "res://tests/rogue_sound_export.gd", "--", str(out)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)


def _audio(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<audio controls preload="none" src="data:audio/wav;base64,{data}"></audio>'


def write_page(wav_dir: Path, dest: Path) -> Path:
    rows = []
    for name, title, note in REFERENCES:
        f = wav_dir / f"{name}.wav"
        if f.exists():
            rows.append(f"<tr class='ref'><td><b>{html.escape(title)}</b><br><small>{html.escape(note)}</small></td>"
                        f"<td>{_audio(f)}</td></tr>")
    table = sound_table()
    listed = {r[0] for r in table}
    extra = [(f.stem, f.stem.removeprefix("rogue_").replace("_", " "), "hors du tableau du cahier", "")
             for f in sorted(wav_dir.glob("rogue_*.wav")) if f.stem not in listed]
    for name, event, desc, dur in table + extra:
        f = wav_dir / f"{name}.wav"
        if f.exists():
            rows.append(f"<tr><td><b>{html.escape(event)}</b> <code>{name}</code><br><small>{html.escape(desc)}"
                        f"{f' ({html.escape(dur)})' if dur else ''}</small></td><td>{_audio(f)}</td></tr>")
    page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Écoute Cyber-Rogue</title>
<style>
:root {{ --bg:#fff; --fg:#1d1d1f; --muted:#666; --line:#ddd; --ref:#f3f6fb; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#16171a; --fg:#eee; --muted:#aaa; --line:#333; --ref:#1f2430; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.45 system-ui, sans-serif; margin:0 auto; max-width:820px; padding:16px; }}
table {{ border-collapse:collapse; width:100%; }} td {{ border-bottom:1px solid var(--line); padding:8px 4px; vertical-align:middle; }}
tr.ref td {{ background:var(--ref); }} small {{ color:var(--muted); }} audio {{ width:260px; max-width:100%; }}
code {{ font-size:12px; color:var(--muted); }}
</style></head><body>
<h1>Écoute des sons du Cyber-Rogue</h1>
<p>Chaque son est au niveau où le mode le joue avec les réglages par défaut (bruitages 70 %, musique 40 %).
Mets le volume du PC comme pendant une séance, écoute d'abord la scène de salle et le vent, puis les sons un par un.
À noter : un son trop fort, strident, désagréable ou qu'on n'entend pas sur le vent.</p>
<table>{''.join(rows)}</table>
</body></html>
"""
    dest.write_text(page, encoding="utf-8")
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Page d'écoute des sons du Cyber-Rogue (lot X51).")
    ap.add_argument("--godot", required=True)
    ap.add_argument("--out", type=Path, default=None, help="dossier des WAV et de ecoute.html")
    args = ap.parse_args(argv)
    if not (Path(args.godot).is_file() and os.access(args.godot, os.X_OK)):
        print(f"Godot introuvable : {args.godot}", file=sys.stderr)
        return 2
    out = args.out or Path(tempfile.mkdtemp(prefix="openride-rogue-ecoute-"))
    out.mkdir(parents=True, exist_ok=True)
    try:
        export(args.godot, out)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"export des sons impossible : {exc}", file=sys.stderr)
        return 2
    print(f"Page d'écoute : {write_page(out, out / 'ecoute.html')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
