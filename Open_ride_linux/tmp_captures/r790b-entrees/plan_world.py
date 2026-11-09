"""Vue de dessus d'un .world compilé (lot U3) : mer par tronçon, rivage, plages, route. Python seul (SVG),
sans Pillow : le venv du PC ne l'a pas (r790).

    python3 plan_world.py ~/.local/share/openride/routes/cote-opale-essai.world plan_u3.svg

Le SVG s'ouvre dans Firefox ; `rsvg-convert plan_u3.svg -o plan_u3.png` en fait une image si besoin.
"""
import json
import sys
from pathlib import Path

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
W, H = int((x1 - x0) * S) + 1, int((z1 - z0) * S) + 41


def P(seq):
    return " ".join(f"{(p[0] - x0) * S:.1f},{(p[1] - z0) * S + 40:.1f}" for p in seq)


def ring_path(outer, holes):
    return " ".join("M" + P(r) + "Z" for r in [outer] + list(holes))


svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
       f'<rect width="{W}" height="{H}" fill="rgb(215,205,170)"/>']
for k, a in seas:
    fill = "rgb(40,110,190)" if k % 2 else "rgb(60,135,215)"
    svg.append(f'<path d="{ring_path(a["outer"], a["holes"])}" fill="{fill}" fill-rule="evenodd" '
               'stroke="rgb(20,60,120)" stroke-width="0.5"/>')
for b in beaches:
    fill = "rgb(245,225,140)" if b["kind"] == "sand" else "rgb(170,170,190)"
    svg.append(f'<path d="{ring_path(b["outer"], b["holes"])}" fill="{fill}" fill-rule="evenodd"/>')
col = {"sand": "rgb(230,190,40)", "rock": "rgb(80,80,80)", "cliff": "rgb(210,40,40)", "shingle": "rgb(120,120,170)"}
for ln in lines:
    svg.append(f'<polyline points="{P(ln["points"])}" fill="none" stroke="{col[ln["shore"]]}" stroke-width="3"/>')
svg.append(f'<polyline points="{P(list(zip(route["x"], route["z"])))}" fill="none" stroke="black" stroke-width="4"/>')
svg.append(f'<rect width="{W}" height="36" fill="white"/><text x="10" y="24" font-family="sans-serif" font-size="16">'
           f'{world.name} : {route["length_m"] / 1000:.2f} km, {len(seas)} aires de mer, {len(lines)} lignes de côte, '
           f'{len(beaches)} plages (rouge falaise, jaune sable, gris roche, bleu-gris galets ; route en noir)</text>')
svg.append("</svg>")
out.write_text("\n".join(svg), encoding="utf-8")
print(out)
