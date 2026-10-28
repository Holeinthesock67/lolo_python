extends RefCounted

## Identifiants fermés de la série U (Format .world v1 §8 quater et §9, thème 2.0, lots U0 et U1),
## partagés par le chargeur de thèmes, la couche biome et le modèle de biome.
## Pas de class_name : charger par preload("res://scripts/biome_ids.gd").

## Les seize biomes du lot U0, dans l'ordre de la liste définitive.
const BIOMES: Array[String] = [
	"temperate_grassland", "temperate_forest", "farmland", "boreal_forest", "alpine", "tundra",
	"polar", "mediterranean", "steppe", "savanna", "sand_desert", "rock_desert", "jungle",
	"wetland", "coast", "volcanic",
]

const DEFAULT_BIOME := "temperate_grassland"

## Variantes régionales : roches et terres, puis architecture (styles de building_styles.gd).
const GROUND_VARIANTS: Array[String] = [
	"gres_rose", "calcaire_blanc", "granite_gris", "schiste_sombre", "basalte", "laterite_rouge", "craie",
]
const ROOF_VARIANTS: Array[String] = [
	"tuile_ronde", "ardoise", "tuile_plate", "pierre_seche", "toit_plat_blanc", "bois",
]

## Espèces de `vegetation.species` (lot U7).
const SPECIES: Array[String] = [
	"oak", "beech", "spruce", "pine", "birch", "larch", "olive", "holm_oak", "cypress", "stone_pine",
	"palm", "acacia", "baobab", "cactus", "tree_fern", "reed", "dwarf_shrub", "vine_row",
]

const GROUND_ROLES: Array[String] = ["flat", "steep", "high"]
const CALENDARS: Array[String] = ["four", "wet_dry", "polar", "none"]
const SURFACES: Array[String] = ["compacted", "gravel", "dirt"]


static func is_biome(id: Variant) -> bool:
	return typeof(id) == TYPE_STRING and BIOMES.has(id)
