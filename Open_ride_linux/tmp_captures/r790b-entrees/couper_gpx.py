"""Coupe une trace GPX à une longueur donnée (lot U3, essai PC de la côte). Python seul, sans paquet.

    python3 couper_gpx.py trace_d940.gpx cote_opale_essai.gpx --km 8
    python3 couper_gpx.py trace_d940.gpx cote_opale_essai.gpx --km 8 --depuis-la-fin

Garde le début de la trace (ou sa fin avec --depuis-la-fin, remise dans le sens d'origine) jusqu'à la
longueur demandée ; le dernier point est interpolé pour tomber pile. Les altitudes (<ele>) suivent.
"""
import argparse
import math
import re
import sys
from pathlib import Path

R = 6371008.8
PT = re.compile(r'<trkpt\b[^>]*?lat="([-\d.]+)"[^>]*?lon="([-\d.]+)"[^>]*?(?:/>|>(.*?)</trkpt>)', re.S)
PT2 = re.compile(r'<trkpt\b[^>]*?lon="([-\d.]+)"[^>]*?lat="([-\d.]+)"[^>]*?(?:/>|>(.*?)</trkpt>)', re.S)
ELE = re.compile(r"<ele>([-\d.]+)</ele>")


def read(path):
    text = Path(path).read_text(encoding="utf-8")
    pts = [(float(a), float(o), body or "") for a, o, body in PT.findall(text)]
    if not pts:
        pts = [(float(a), float(o), body or "") for o, a, body in PT2.findall(text)]
    out = []
    for lat, lon, body in pts:
        m = ELE.search(body)
        out.append((lat, lon, float(m.group(1)) if m else None))
    return out


def dist(p, q):
    la1, la2 = math.radians(p[0]), math.radians(q[0])
    dla, dlo = la2 - la1, math.radians(q[1] - p[1])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def cut(pts, length_m):
    out = [pts[0]]
    done = 0.0
    for p, q in zip(pts, pts[1:]):
        d = dist(p, q)
        if done + d >= length_m:
            t = (length_m - done) / d if d > 0 else 0.0
            ele = None if p[2] is None or q[2] is None else p[2] + t * (q[2] - p[2])
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]), ele))
            return out, length_m
        out.append(q)
        done += d
    return out, done


def write(path, pts, name):
    rows = []
    for lat, lon, ele in pts:
        e = "" if ele is None else f"<ele>{ele:.1f}</ele>"
        rows.append(f'<trkpt lat="{lat:.7f}" lon="{lon:.7f}">{e}</trkpt>')
    Path(path).write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                          '<gpx version="1.1" creator="OpenRide U3" xmlns="http://www.topografix.com/GPX/1/1">'
                          f"<trk><name>{name}</name><trkseg>\n" + "\n".join(rows) + "\n</trkseg></trk></gpx>\n",
                          encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source")
    ap.add_argument("sortie")
    ap.add_argument("--km", type=float, default=8.0)
    ap.add_argument("--depuis-la-fin", action="store_true", help="garder la fin de la trace")
    ap.add_argument("--nom", default="Côte d'Opale essai U3")
    a = ap.parse_args(argv)
    pts = read(a.source)
    if len(pts) < 2:
        sys.exit(f"{a.source} : moins de deux points")
    total = sum(dist(p, q) for p, q in zip(pts, pts[1:]))
    src = pts[::-1] if a.depuis_la_fin else pts
    out, got = cut(src, a.km * 1000.0)
    if a.depuis_la_fin:
        out = out[::-1]
    write(a.sortie, out, a.nom)
    print(f"trace source : {total / 1000:.2f} km, {len(pts)} points ; coupée : {got / 1000:.2f} km, {len(out)} points")
    if got < a.km * 1000.0 - 1.0:
        sys.exit(f"trace trop courte pour {a.km} km")


if __name__ == "__main__":
    main()
