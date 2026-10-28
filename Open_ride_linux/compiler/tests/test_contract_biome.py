"""Lot U1 (format) : couche `biome`, mer et côte, surface de la route, thème 2.0 (Format .world v1, 1.6)."""

from __future__ import annotations

import json

import jsonschema
import pytest

from conftest import REPO, WORLD_CONTRACTS

EXAMPLES = WORLD_CONTRACTS / "examples"
BIOME_TILE = EXAMPLES / "biome_tile_near_3_biomes.json"
THEME_2_0 = EXAMPLES / "theme_2_0_two_biomes.json"
DEFAULT_THEME = REPO / "engine" / "themes" / "default" / "theme.json"

# Identifiants du lot U0, dans l'ordre de la liste définitive.
BIOMES = [
    "temperate_grassland", "temperate_forest", "farmland", "boreal_forest", "alpine", "tundra",
    "polar", "mediterranean", "steppe", "savanna", "sand_desert", "rock_desert", "jungle",
    "wetland", "coast", "volcanic",
]


def schema(name: str) -> dict:
    return json.loads((WORLD_CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8"))


def load(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def biome_tile_issues(tile: dict) -> list[str]:
    """Règles de la couche biome que le schéma ne peut pas exprimer (§8 quater)."""
    issues = []
    if len(tile["weights"]) != len(tile["biomes"]):
        issues.append("une grille de poids par biome")
    for p in range(tile["grid"] * tile["grid"]):
        total = sum(grid[p] for grid in tile["weights"])
        if total != 255:
            issues.append(f"point {p} : somme {total} au lieu de 255")
    return issues


def test_biome_tile_example_is_valid_and_small() -> None:
    tile = load(BIOME_TILE)
    jsonschema.validate(tile, schema("biome"))
    assert biome_tile_issues(tile) == []
    assert len(tile["biomes"]) == 3
    assert BIOME_TILE.stat().st_size < 8 * 1024


def test_biome_tile_with_wrong_sum_is_refused() -> None:
    tile = load(BIOME_TILE)
    tile["weights"][0][100] += 1
    jsonschema.validate(tile, schema("biome"))
    assert biome_tile_issues(tile) == ["point 100 : somme 256 au lieu de 255"]


@pytest.mark.parametrize("change", [
    lambda t: t["biomes"].append("savanna") or t["biomes"].append("jungle"),
    lambda t: t.__setitem__("biomes", ["prairie"]),
    lambda t: t.__setitem__("grid", 16),
    lambda t: t["weights"][0].__setitem__(0, 256),
    lambda t: t["weights"][1].pop(),
    lambda t: t.__setitem__("variant", "calcaire_blanc"),
    lambda t: t["variant"].__setitem__("ground", "tuile_ronde"),
])
def test_biome_tile_schema_refuses(change) -> None:
    tile = load(BIOME_TILE)
    change(tile)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(tile, schema("biome"))


def test_biome_ids_match_lot_u0() -> None:
    assert schema("biome")["$defs"]["biomeId"]["enum"] == BIOMES
    assert schema("theme")["$defs"]["biomeId"]["enum"] == BIOMES
    layer = schema("manifest")["properties"]["layers"]["properties"]["biome"]
    assert layer["properties"]["default_biome"]["enum"] == BIOMES


def test_theme_2_0_example_and_default_theme_are_valid() -> None:
    theme_schema = schema("theme")
    jsonschema.validate(load(THEME_2_0), theme_schema)
    default = load(DEFAULT_THEME)
    jsonschema.validate(default, theme_schema)
    one_x = {k: v for k, v in default.items() if k not in ("default_biome", "biomes", "variants", "surfaces")}
    one_x["version"] = "1.2"
    jsonschema.validate(one_x, theme_schema)


def test_default_theme_2_0_has_sixteen_biomes_and_keeps_1_x_grassland() -> None:
    """Lot U15 : thème par défaut 2.0 en couleurs unies ; la prairie reprend exactement le 1.x."""
    default = load(DEFAULT_THEME)
    assert default["version"] == "2.0" and list(default["biomes"]) == BIOMES
    terrain = default["terrain"]
    grass = default["biomes"]["temperate_grassland"]["ground"]
    by_role = {layer["role"]: layer for layer in grass["layers"]}
    for role, key in (("flat", "grass"), ("steep", "rock"), ("high", "snow")):
        assert {k: by_role[role][k] for k in ("color", "texture", "scale_m")} == terrain[key]
    assert grass["high_line_m"] == terrain["snow_line_m"]
    assert grass["slope_threshold_deg"] == terrain["slope_threshold_deg"]
    veg = default["biomes"]["temperate_grassland"]["vegetation"]
    assert veg["max_density_per_ha"] == default["vegetation"]["max_density_per_ha"]
    assert veg["treeline_m"] == default["vegetation"]["treeline_m"]
    flats = {b["ground"]["layers"][0]["color"] for b in default["biomes"].values()}
    assert len(flats) == 16
    for biome in default["biomes"].values():
        assert sum(biome["seasons"]["durations_months"]) == 12
        for layer in biome["ground"]["layers"]:
            assert layer["texture"] is None


def test_theme_2_0_ground_roles_are_unique() -> None:
    for biome in load(THEME_2_0)["biomes"].values():
        roles = [layer["role"] for layer in biome["ground"]["layers"]]
        assert len(roles) == len(set(roles))
        assert roles[0] == "flat"
        assert sum(biome["seasons"]["durations_months"]) == 12


@pytest.mark.parametrize("change", [
    lambda t: t.__setitem__("version", "3.0"),
    lambda t: t["biomes"].__setitem__("desert", {}),
    lambda t: t["biomes"]["mediterranean"]["vegetation"]["species"].append({"kind": "banana", "weight": 1}),
    lambda t: t["biomes"]["mediterranean"]["seasons"].__setitem__("calendar", "monsoon"),
    lambda t: t["variants"].__setitem__("brique", {}),
    lambda t: t["surfaces"].__setitem__("asphalt", {}),
])
def test_theme_2_0_schema_refuses(change) -> None:
    theme = load(THEME_2_0)
    change(theme)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(theme, schema("theme"))


def minimal_manifest() -> dict:
    return {
        "format": "openride-world", "format_version": "1.6", "name": "essai",
        "origin": {"lat": 45.0, "lon": 6.0, "alt_m": 1000.0}, "projection": "utm",
        "route": {"present": True, "file": "route.json", "length_m": 20.0, "ds_m": 10, "n": 3, "type": "open"},
    }


def test_manifest_without_new_layers_stays_valid() -> None:
    jsonschema.validate(minimal_manifest(), schema("manifest"))


def test_manifest_with_biome_and_coast_layers() -> None:
    manifest = minimal_manifest()
    manifest["route"]["surface_source"] = "osm"
    manifest["layers"] = {
        "biome": {
            "present": True, "version": "1.0", "default_biome": "temperate_grassland", "forced": None,
            "sources": ["esa_worldcover_2021", "osm", "dem", "latitude"],
            "shares": {"temperate_grassland": 60.0, "mediterranean": 30.0, "coast": 10.0},
            "tiles": {"near": [[0, 0], [0, -1]], "far": [[0, 0]]},
        },
        "coast": {"present": True, "version": "1.0", "lines_count": 2, "beaches_count": 1, "osm_date": None},
    }
    manifest["stats"] = {"version": 1, "surface_pct": {"paved": 80.0, "gravel": 20.0}}
    jsonschema.validate(manifest, schema("manifest"))
    manifest["layers"]["biome"]["forced"] = "desert"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(manifest, schema("manifest"))


def minimal_route() -> dict:
    return {
        "version": "1.0", "ds_m": 10, "n": 3, "length_m": 20.0, "type": "open",
        "lat": [45.0, 45.0001, 45.0002], "lon": [6.0, 6.0, 6.0], "alt_m": [1000.0, 1000.0, 1000.0],
        "x": [0.0, 0.0, 0.0], "z": [0.0, -10.0, -20.0], "grade_pct": [0.0, 0.0, 0.0],
        "heading_deg": [0.0, 0.0, 0.0],
    }


def test_route_surface_column_is_optional() -> None:
    route = minimal_route()
    jsonschema.validate(route, schema("route"))
    route["surface"] = ["paved", "gravel", "dirt"]
    jsonschema.validate(route, schema("route"))
    route["surface"][1] = "sand"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(route, schema("route"))


def test_water_sea_and_coast_chunk() -> None:
    water = {"version": "1.0", "lines": [], "areas": [
        {"id": "s1", "kind": "sea", "level_y": 0.0, "outer": [[0, 0], [500, 0], [500, 500]], "holes": []},
    ]}
    jsonschema.validate(water, schema("water"))
    coast = {"version": "1.0",
             "lines": [{"id": "c1", "shore": "cliff", "points": [[0.0, 0.0], [120.0, 40.0]]}],
             "beaches": [{"id": "b1", "kind": "sand", "outer": [[0, 0], [30, 0], [30, 10]], "holes": []}]}
    jsonschema.validate(coast, schema("coast"))
    coast["lines"][0]["shore"] = "mud"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(coast, schema("coast"))
