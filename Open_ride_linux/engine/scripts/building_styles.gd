extends RefCounted

## Styles d'architecture des bâtiments OSM (Lot Y8, habillage), sans nœud ni affichage.
## Pas de class_name : charger par preload("res://scripts/building_styles.gd").
##
## Un style par variante d'architecture du contrat U1 §4.3 (`tuile_ronde`, `ardoise`, `tuile_plate`,
## `pierre_seche`, `toit_plat_blanc`, `bois`) : matière et pente du toit, part de toits à croupes, poids des
## matières de mur des maisons. Avant la série U, tout le parcours prend STYLE_DEFAULT ; en 3.0, chaque bâtiment
## prend la variante régionale de sa tuile (U4, U14) ou, à défaut, le style de son biome dominant (BIOME_STYLES,
## biomes du lot U0) : `resolve()`, posé dans la clé `style` du bâtiment avant building_mesh.gd. Les teintes restent celles du thème (`buildings.walls` et
## `buildings.roofs`, puis `walls` et `roofs` de la variante en 3.0) pour l'enduit et les tuiles ; les matières
## qui ont leur propre couleur (brique, pierre, bois, tôle, béton, ardoise) prennent les palettes ci-dessous.
##
## `classify(osm_building)` range le type OSM (`hint.building`) dans une famille : maison, dépendance agricole,
## lieu de culte, immeuble ou bâtiment public, commerce, atelier ou industrie. La famille décide des fenêtres, de la
## matière des murs et de la forme du toit, le style décide du reste.

## Matières de mur (code lu par building.gdshader)
const WALL_PLASTER := 0
const WALL_BRICK := 1
const WALL_STONE := 2
const WALL_WOOD := 3
const WALL_TIMBER := 4      # colombage : poutres sombres sur enduit
const WALL_METAL := 5       # bardage de tôle nervurée
const WALL_CONCRETE := 6

## Ouvertures (code lu par building.gdshader)
const WINDOWS_NONE := 0
const WINDOWS_HOUSE := 1    # fenêtres à volets, une porte au rez-de-chaussée
const WINDOWS_BANDS := 2    # bandeaux vitrés par étage (immeubles, bureaux)
const WINDOWS_BARN := 3     # jours hauts et grand portail (granges, hangars, ateliers)
const WINDOWS_CHURCH := 4   # hautes baies cintrées
const WINDOWS_SHOP := 5     # vitrines au rez-de-chaussée, fenêtres aux étages

## Matières de toit (code lu par building.gdshader)
const ROOF_FLAT := 0        # gravillons sur étanchéité
const ROOF_TILE_FLAT := 1   # tuiles plates
const ROOF_TILE_ROUND := 2  # tuiles rondes (canal)
const ROOF_SLATE := 3       # ardoise ou lauze
const ROOF_METAL := 4       # bac acier nervuré
const ROOF_SHINGLE := 5     # bardeaux de bois

## Formes de toit
const SHAPE_FLAT := "flat"
const SHAPE_GABLED := "gabled"
const SHAPE_HIPPED := "hipped"

const FAMILY_HOUSE := "house"
const FAMILY_FARM := "farm"
const FAMILY_WORSHIP := "worship"
const FAMILY_BLOCK := "block"
const FAMILY_WORK := "work"
const FAMILY_SHOP := "shop"

const STYLE_DEFAULT := "tuile_plate"

## pitch_deg : pente des maisons ; hip_share : part des maisons à quatre pans ; walls : poids des matières de
## mur des maisons ; farm_wall : matière des dépendances agricoles ; worship_roof : toit des églises.
const STYLES := {
	"tuile_plate": {"roof": ROOF_TILE_FLAT, "pitch_deg": 45.0, "hip_share": 0.2,
		"walls": {WALL_PLASTER: 0.6, WALL_TIMBER: 0.25, WALL_BRICK: 0.05, WALL_STONE: 0.1},
		"farm_wall": WALL_WOOD, "worship_roof": ROOF_SLATE},
	"tuile_ronde": {"roof": ROOF_TILE_ROUND, "pitch_deg": 25.0, "hip_share": 0.35,
		"walls": {WALL_PLASTER: 0.7, WALL_STONE: 0.3},
		"farm_wall": WALL_STONE, "worship_roof": ROOF_TILE_ROUND},
	"ardoise": {"roof": ROOF_SLATE, "pitch_deg": 45.0, "hip_share": 0.3,
		"walls": {WALL_PLASTER: 0.45, WALL_STONE: 0.4, WALL_BRICK: 0.15},
		"farm_wall": WALL_STONE, "worship_roof": ROOF_SLATE},
	"pierre_seche": {"roof": ROOF_SLATE, "pitch_deg": 35.0, "hip_share": 0.15,
		"walls": {WALL_STONE: 0.8, WALL_PLASTER: 0.2},
		"farm_wall": WALL_STONE, "worship_roof": ROOF_SLATE},
	"toit_plat_blanc": {"roof": ROOF_FLAT, "pitch_deg": 0.0, "hip_share": 0.0,
		"walls": {WALL_PLASTER: 0.85, WALL_STONE: 0.15},
		"farm_wall": WALL_PLASTER, "worship_roof": ROOF_FLAT},
	"bois": {"roof": ROOF_SHINGLE, "pitch_deg": 35.0, "hip_share": 0.1,
		"walls": {WALL_WOOD: 0.85, WALL_PLASTER: 0.15},
		"farm_wall": WALL_WOOD, "worship_roof": ROOF_SHINGLE},
}

## Style par défaut de chaque biome du lot U0, quand la tuile n'a pas de variante régionale (U1 `variant` null) :
## la variante de la tuile (U4) l'emporte toujours, puis le biome dominant du bâtiment, puis STYLE_DEFAULT.
const BIOME_STYLES := {
	"temperate_grassland": "tuile_plate", "temperate_forest": "tuile_plate", "farmland": "tuile_plate",
	"boreal_forest": "bois", "alpine": "ardoise", "tundra": "bois", "polar": "bois",
	"mediterranean": "tuile_ronde", "steppe": "pierre_seche", "savanna": "toit_plat_blanc",
	"sand_desert": "toit_plat_blanc", "rock_desert": "toit_plat_blanc", "jungle": "bois", "wetland": "ardoise",
	"coast": "ardoise", "volcanic": "pierre_seche",
}

## Teintes propres aux matières (l'enduit et les tuiles prennent celles du thème)
const MATERIAL_COLORS := {
	"brick": ["#9c4a32", "#a85a3c", "#8a4430"],
	"stone": ["#b8ab94", "#a99c86", "#c4b8a2"],
	"wood": ["#8a6040", "#9a6c45", "#7a5236", "#9c4632"],
	"tile_round": ["#c27a45", "#b86a3e", "#cf8a52", "#a95f3a"],
	"metal": ["#8b9298", "#6f7f72", "#a7a9a6"],
	"concrete": ["#bdbab3", "#c9c5bc"],
	"slate": ["#4d535c", "#545a63", "#474c55"],
	"metal_roof": ["#6b6e72", "#7a4a3a", "#56605a"],
	"shingle": ["#6b5a48", "#5a4b3d"],
	"flat_roof": ["#6e6c68", "#7c7a75"],
	"white": ["#f2efe8", "#ebe6dc"],
}

## Familles par valeur OSM de `building=*` ; toute autre valeur (dont `yes`) est une maison.
const FAMILIES := {
	"barn": FAMILY_FARM, "farm_auxiliary": FAMILY_FARM, "shed": FAMILY_FARM, "stable": FAMILY_FARM,
	"cowshed": FAMILY_FARM, "sty": FAMILY_FARM, "hut": FAMILY_FARM, "garage": FAMILY_FARM,
	"garages": FAMILY_FARM, "carport": FAMILY_FARM, "greenhouse": FAMILY_FARM,
	"church": FAMILY_WORSHIP, "chapel": FAMILY_WORSHIP, "cathedral": FAMILY_WORSHIP,
	"religious": FAMILY_WORSHIP, "temple": FAMILY_WORSHIP, "mosque": FAMILY_WORSHIP,
	"apartments": FAMILY_BLOCK, "office": FAMILY_BLOCK, "school": FAMILY_BLOCK, "public": FAMILY_BLOCK,
	"civic": FAMILY_BLOCK, "government": FAMILY_BLOCK, "hospital": FAMILY_BLOCK, "university": FAMILY_BLOCK,
	"college": FAMILY_BLOCK, "kindergarten": FAMILY_BLOCK, "townhall": FAMILY_BLOCK, "hotel": FAMILY_BLOCK,
	"industrial": FAMILY_WORK, "warehouse": FAMILY_WORK, "commercial": FAMILY_SHOP, "retail": FAMILY_SHOP,
	"supermarket": FAMILY_SHOP, "kiosk": FAMILY_SHOP, "manufacture": FAMILY_WORK, "hangar": FAMILY_WORK, "service": FAMILY_WORK,
	"transportation": FAMILY_WORK, "sports_hall": FAMILY_WORK,
}

## Toit en pente seulement si le contour remplit au moins FILL_MIN de son rectangle orienté et si sa largeur
## reste sous MAX_PITCHED_WIDTH_M (au-delà, un toit à pans monterait trop haut : toit plat ou à faible pente).
const FILL_MIN := 0.8
const MAX_PITCHED_WIDTH_M := 22.0
const WORK_PITCH_DEG := 8.0
## Débord des toits en pente au-delà des murs (égout et rives)
const EAVE_OVERHANG_M := 0.4
const WORSHIP_PITCH_DEG := 50.0
const BLOCK_PITCH_FACTOR := 0.7


## Style d'un bâtiment : variante régionale de sa tuile si elle existe, sinon style du biome dominant.
static func resolve(variant_roofs: String, biome: String) -> String:
	if STYLES.has(variant_roofs):
		return variant_roofs
	return BIOME_STYLES.get(biome, STYLE_DEFAULT)


static func style(name: String) -> Dictionary:
	return STYLES.get(name, STYLES[STYLE_DEFAULT])


static func classify(osm_building: String) -> String:
	return FAMILIES.get(osm_building.strip_edges().to_lower(), FAMILY_HOUSE)


## Choix pondéré déterministe dans {clé: poids} avec u dans [0, 1[.
static func _weighted(weights: Dictionary, u: float) -> int:
	var total := 0.0
	for k in weights:
		total += float(weights[k])
	var acc := 0.0
	var last := -1
	for k in weights:
		acc += float(weights[k]) / total
		last = int(k)
		if u < acc:
			return last
	return last


## Habillage d'un bâtiment : matières, ouvertures, forme et pente du toit.
## `u1`, `u2`, `u3` : tirages déterministes dans [0, 1[ (hachage de l'identifiant).
## `fill` : aire du contour / aire du rectangle orienté ; `width_m` : petit côté du rectangle orienté.
static func dress(style_name: String, family: String, fill: float, width_m: float, height_m: float,
		u1: float, u2: float, u3: float) -> Dictionary:
	var st := style(style_name)
	var wall: int = _weighted(st["walls"], u1)
	var windows := WINDOWS_HOUSE
	var roof: int = st["roof"]
	var pitch: float = st["pitch_deg"]
	var hip: bool = u2 < float(st["hip_share"])
	match family:
		FAMILY_FARM:
			wall = st["farm_wall"]
			windows = WINDOWS_BARN if width_m > 6.0 else WINDOWS_NONE
			if roof != ROOF_FLAT and u3 < 0.35:
				roof = ROOF_METAL
			hip = false
		FAMILY_WORSHIP:
			wall = WALL_STONE if wall != WALL_WOOD else WALL_WOOD
			windows = WINDOWS_CHURCH
			roof = st["worship_roof"]
			if roof != ROOF_FLAT:
				pitch = WORSHIP_PITCH_DEG
			hip = false
		FAMILY_BLOCK:
			wall = WALL_CONCRETE if u1 < 0.3 else (WALL_BRICK if u1 > 0.85 else WALL_PLASTER)
			windows = WINDOWS_BANDS if wall == WALL_CONCRETE else WINDOWS_HOUSE
			pitch *= BLOCK_PITCH_FACTOR
			hip = hip or u3 < 0.3
		FAMILY_SHOP:
			wall = WALL_CONCRETE if u1 < 0.35 else WALL_PLASTER
			windows = WINDOWS_SHOP
			if width_m > 14.0:
				roof = ROOF_FLAT
			hip = false
		FAMILY_WORK:
			wall = WALL_METAL if u1 < 0.7 else WALL_CONCRETE
			windows = WINDOWS_BARN
			roof = ROOF_METAL
			pitch = WORK_PITCH_DEG if u3 < 0.5 else 0.0
			hip = false
	if roof == ROOF_FLAT:
		pitch = 0.0
	var shape := SHAPE_FLAT
	if pitch > 0.0 and fill >= FILL_MIN and width_m <= MAX_PITCHED_WIDTH_M:
		shape = SHAPE_HIPPED if hip else SHAPE_GABLED
	if shape == SHAPE_FLAT and roof != ROOF_METAL:
		roof = ROOF_FLAT
	return {"wall": wall, "windows": windows, "roof": roof, "shape": shape,
		"pitch_deg": pitch if shape != SHAPE_FLAT else 0.0}


## Deux pans imposés par la couche (`roof: gabled`) : pente du style, tôle si le style est à toits plats.
static func force_gabled(dress: Dictionary, style_name: String) -> Dictionary:
	var st := style(style_name)
	var out := dress.duplicate()
	out["shape"] = SHAPE_GABLED
	if float(out["pitch_deg"]) <= 0.0:
		out["pitch_deg"] = float(st["pitch_deg"]) if float(st["pitch_deg"]) > 0.0 else WORK_PITCH_DEG
	if int(out["roof"]) == ROOF_FLAT:
		out["roof"] = ROOF_METAL if int(st["roof"]) == ROOF_FLAT else int(st["roof"])
	return out


## Palette de teintes d'une matière de mur, ou null pour garder celle du thème (enduit, colombage).
static func wall_palette_key(wall: int, style_name: String) -> String:
	match wall:
		WALL_BRICK:
			return "brick"
		WALL_STONE:
			return "stone"
		WALL_WOOD:
			return "wood"
		WALL_METAL:
			return "metal"
		WALL_CONCRETE:
			return "concrete"
	return "white" if style_name == "toit_plat_blanc" else ""


static func roof_palette_key(roof: int, style_name: String) -> String:
	match roof:
		ROOF_TILE_ROUND:
			return "tile_round"
		ROOF_SLATE:
			return "slate"
		ROOF_METAL:
			return "metal_roof"
		ROOF_SHINGLE:
			return "shingle"
		ROOF_FLAT:
			return "white" if style_name == "toit_plat_blanc" else "flat_roof"
	return ""
