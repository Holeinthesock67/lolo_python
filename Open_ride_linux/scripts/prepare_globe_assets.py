#!/usr/bin/env python3
"""Prépare les données embarquées du menu globe (lot W11). Non exécuté à l'installation : les fichiers
produits sont dans le dépôt (`engine/assets/globe/`, `core/src/openride_core/data/places.json`).

    python3 scripts/prepare_globe_assets.py [--src DOSSIER] [--texture bluemarble.jpg]

Entrées (Natural Earth, domaine public ; téléchargées depuis le dépôt `nvkelso/natural-earth-vector` si
`--src` ne les contient pas) : `ne_110m_coastline.geojson`, `ne_110m_admin_0_boundary_lines_land.geojson`,
`ne_110m_land.geojson`, `ne_10m_populated_places_simple.geojson`. Les cols viennent du pack O16
(`compiler/src/openride_compiler/route_packs/cols_celebres/*.toml`, dernier point de passage = sommet).

Sorties :
- `globe.jpg` : 2 048 × 1 024, projection équirectangulaire. Avec `--texture` (image NASA Blue Marble,
  domaine public, à télécharger soi-même), l'image est réduite à cette taille ; sans, la texture est dessinée
  depuis les terres de Natural Earth (océan bleu, terres teintées selon la latitude).
- `coast.json` : côtes et frontières, polylignes `[lon, lat, lon, lat, …]` au centième de degré.
- `places.json` : villes de plus de 50 000 habitants (`city`) et cols célèbres (`pass`, ou `peak` pour un sommet), `[nom, genre, lat, lon, pays, population]`.
"""

from __future__ import annotations

import argparse
import json
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson"
FILES = ["ne_110m_coastline", "ne_110m_admin_0_boundary_lines_land", "ne_110m_land", "ne_10m_populated_places_simple"]
MIN_POP = 50_000
TEX_W, TEX_H = 2048, 1024


def load(name: str, src: Path | None) -> dict:
    if src and (src / f"{name}.geojson").exists():
        return json.loads((src / f"{name}.geojson").read_text(encoding="utf-8"))
    with urllib.request.urlopen(NE_URL.format(name), timeout=120) as r:   # noqa: S310 (adresse fixe)
        return json.loads(r.read())


def lines_of(geo: dict) -> list[list[list[float]]]:
    out = []
    for f in geo["features"]:
        g = f["geometry"]
        parts = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"] if g["type"] == "MultiLineString" else []
        out.extend(parts)
    return out


def flat(line: list[list[float]]) -> list[float]:
    pts: list[float] = []
    for lon, lat, *_ in line:
        pts += [round(lon, 2), round(lat, 2)]
    return pts


def polygons_of(geo: dict) -> list[list[list[list[float]]]]:
    out = []
    for f in geo["features"]:
        g = f["geometry"]
        if g["type"] == "Polygon":
            out.append(g["coordinates"])
        elif g["type"] == "MultiPolygon":
            out.extend(g["coordinates"])
    return out


def draw_texture(land: dict, path: Path) -> None:
    from PIL import Image, ImageDraw   # noqa: PLC0415

    img = Image.new("RGB", (TEX_W, TEX_H), (18, 52, 96))
    d = ImageDraw.Draw(img)

    def px(lon: float, lat: float) -> tuple[float, float]:
        return (lon + 180.0) / 360.0 * TEX_W, (90.0 - lat) / 180.0 * TEX_H

    for poly in polygons_of(land):
        outer = [px(lon, lat) for lon, lat, *_ in poly[0]]
        lat_mid = sum(p[1] for p in poly[0]) / len(poly[0])
        t = abs(lat_mid) / 90.0
        colour = (round(70 + 150 * t * t), round(120 + 80 * t * t), round(60 + 150 * t * t))   # vert vers blanc aux pôles
        d.polygon(outer, fill=colour)
        for hole in poly[1:]:
            d.polygon([px(lon, lat) for lon, lat, *_ in hole], fill=(18, 52, 96))
    d.rectangle([0, TEX_H - 40, TEX_W, TEX_H], fill=(235, 240, 245))  # Antarctique (les polygones s'arrêtent à 85° S)
    img.save(path, "JPEG", quality=85, optimize=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, help="dossier des fichiers Natural Earth déjà téléchargés")
    ap.add_argument("--texture", type=Path, help="image NASA Blue Marble à réduire à 2 048 × 1 024")
    ap.add_argument("--out", type=Path, default=ROOT / "engine" / "assets" / "globe")
    ap.add_argument("--places", type=Path, default=ROOT / "core" / "src" / "openride_core" / "data" / "places.json")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    geo = {name: load(name, args.src) for name in FILES}
    coast = [flat(line) for line in lines_of(geo["ne_110m_coastline"])]
    borders = [flat(line) for line in lines_of(geo["ne_110m_admin_0_boundary_lines_land"])]
    (args.out / "coast.json").write_text(json.dumps({"coast": coast, "borders": borders}, separators=(",", ":")),
                                         encoding="utf-8")

    if args.texture:
        from PIL import Image   # noqa: PLC0415

        Image.open(args.texture).convert("RGB").resize((TEX_W, TEX_H), Image.LANCZOS).save(
            args.out / "globe.jpg", "JPEG", quality=85, optimize=True)
    else:
        draw_texture(geo["ne_110m_land"], args.out / "globe.jpg")

    places = []
    for f in geo["ne_10m_populated_places_simple"]["features"]:
        p = f["properties"]
        if (p.get("pop_max") or 0) >= MIN_POP:
            places.append([p.get("name") or p.get("nameascii"), "city", round(float(p["latitude"]), 3),
                           round(float(p["longitude"]), 3), p.get("adm0name") or "", int(p["pop_max"])])
    places.sort(key=lambda r: -r[5])
    for toml_path in sorted((ROOT / "compiler" / "src" / "openride_compiler" / "route_packs" / "cols_celebres").glob("*.toml")):
        if toml_path.name == "pack.toml":
            continue
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        lat, lon = data["waypoints"][-1]
        kind = "pass" if data["name"].split()[0].lower() in ("col", "passo", "port", "puerto") else "peak"
        places.append([data["name"], kind, round(lat, 4), round(lon, 4), data.get("country", ""), 0])
    args.places.parent.mkdir(parents=True, exist_ok=True)
    args.places.write_text(json.dumps({"version": "1.0", "fields": ["name", "kind", "lat", "lon", "country", "pop"],
                                       "places": places}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for p in (args.out / "globe.jpg", args.out / "coast.json", args.places):
        print(f"{p.relative_to(ROOT)} : {p.stat().st_size / 1024:.0f} Ko")


if __name__ == "__main__":
    main()
