"""Doublure de `openride-compiler` pour l'import de traces depuis le menu (lot O23).

`build <trace> --out <dossier> [--force]` : écrit un parcours synthétique (demo_world) au nom normalisé de
la trace, avec la source et son SHA-256 dans le manifeste ; une trace sans point (`trkpt`) est refusée
comme le ferait le vrai compilateur (message sur la sortie, code 2). `build-all` (lancement) : rien à faire.
Choisie par `OPENRIDE_COMPILER` (banc des menus, scénario `parcours_import`) ou `route_compiler_cmd` (pytest).
"""

import hashlib
import json
import sys
from pathlib import Path

from openride_core.catalog import _normalize_name, track_stem
from openride_core.demo_world import write_world

args = sys.argv[1:]
if args[0] == "build-all":
    sys.exit(0)
assert args[0] == "build", args
track = Path(args[1])
out = Path(args[args.index("--out") + 1])
data = track.read_bytes()
if b"trkpt" not in data:
    print("Lecture de la trace…")
    print(f"openride-compiler : erreur : {track.name} : aucun point de trace exploitable")
    sys.exit(2)
name = _normalize_name(track_stem(track.name)[0])
if (out / f"{name}.world").exists() and "--force" not in args:
    print(f"openride-compiler : erreur : {name}.world existe déjà (--force pour le remplacer)")
    sys.exit(2)
world = write_world(out, name, 3000.0)
manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
manifest["source"] = {"gpx": track.name, "gpx_sha256": hashlib.sha256(data).hexdigest()}
(world / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"{name}.world écrit")
