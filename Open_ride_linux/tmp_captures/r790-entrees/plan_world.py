"""Vue de dessus d'un .world compilé (lot U3) : mer par tronçon, rivage, plages, route.

    python3 plan_world.py ~/.local/share/openride/routes/cote-opale-essai.world plan_u3.png

Demande Pillow (déjà installé avec le compilateur [dev]).
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

world, out = Path(sys.argv[1]).expanduser(), Path(sys.argv[2])
route = json.loads((world / "route.json").read_text())
seas, lines, beaches = [], [], []
for f in sorted((world / "water").glob("chunk_*.json")):
    k = int(f.stem.split("_")[1])
    seas += [(k, a) for a in json.loads(f.read_text())["areas"] if a["kind"] == "sea"]
for f in sorted((world / "coast").glob("chunk_*.json")):
    c = json.loads(f.read_text())
    lines += c["lines"]
    beaches += c["beaches"]
pts = [p for _, a in seas for p in a["outer"]] + list(zip(route["x"], route["z"]))
x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
z0, z1 = min(p[1] for p in pts), max(p[1] for p in pts)
S = 1600.0 / max(x1 - x0, z1 - z0)
img = Image.new("RGB", (int((x1 - x0) * S) + 1, int((z1 - z0) * S) + 1), (215, 205, 170))
d = ImageDraw.Draw(img)


def P(p):
    return ((p[0] - x0) * S, (p[1] - z0) * S)


for k, a in seas:
    d.polygon([P(p) for p in a["outer"]], fill=(40, 110, 190) if k % 2 else (60, 135, 215))
    for h in a["holes"]:
        d.polygon([P(p) for p in h], fill=(215, 205, 170))
for b in beaches:
    d.polygon([P(p) for p in b["outer"]], fill=(245, 225, 140) if b["kind"] == "sand" else (170, 170, 190))
col = {"sand": (230, 190, 40), "rock": (80, 80, 80), "cliff": (210, 40, 40), "shingle": (120, 120, 170)}
for ln in lines:
    d.line([P(p) for p in ln["points"]], fill=col[ln["shore"]], width=3)
d.line([P(p) for p in zip(route["x"], route["z"])], fill=(0, 0, 0), width=4)
d.text((10, 10), f"{world.name} : {len(seas)} aires de mer, {len(lines)} lignes de côte, {len(beaches)} plages "
       "(rouge falaise, jaune sable, gris roche, bleu-gris galets ; route en noir)", fill=(0, 0, 0))
img.save(out)
print(out)
