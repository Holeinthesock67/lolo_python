extends RefCounted

## Saisons, sans nœud ni affichage (lot P18, version 2.0) : saison du thème ou de la date, paramètres du
## paysage (feuillage, arbres dénudés, herbe, neige, floraison, feuilles qui tombent, sons, ciel) et
## paramètres globaux des shaders. Appliqué à la scène par P19 (réglage « Saisons » du menu, coupé par défaut).
## Pas de class_name : charger par preload("res://scripts/season_model.gd").
##
## - `season_for(theme, month, day, lat_deg)` -> `{season, progress}` : `season` du thème 1.2, sinon d'après
##   la date (saisons météorologiques : printemps de mars à mai dans l'hémisphère nord, inversées au sud) ;
##   `progress` de 0 à 1 dans la saison ;
## - `params(season, progress, snowy)` : paramètres continus sur l'année (paliers interpolés, aucune marche) ;
##   été : neutres (rendu d'aujourd'hui) ; `snowy` (météo `snow` du thème) : neige partout l'hiver ;
## - `NEUTRAL` : paramètres de l'été, ceux des valeurs par défaut des paramètres globaux de `project.godot` ;
## - `globals(p)` -> paramètres globaux des shaders (`season_*`), posés par `apply_globals`.
##
## Paramètres rendus : `leaf_tint` (Color, multiplie le feuillage des feuillus), `autumn` (0 à 1 : palette
## d'automne variée par arbre), `bare` (part des feuillus sans feuilles), `blossom` (floraison des vergers),
## `grass_tint`, `grass_dry` (herbe jaunie), `snow_drop_m` (abaissement de la limite de neige), `falling_leaves`
## (densité des feuilles qui tombent), `insects`, `birds` (facteurs des sons d'ambiance), `cloud_altitude`
## (facteur de l'altitude des nuages : ciel plus bas l'hiver).

const SEASONS := ["spring", "summer", "autumn", "winter"]
const SNOW_DROP_M := 1200.0        # hiver : limite de neige 1 200 m plus bas (2 200 -> 1 000 m)
const SNOW_EVERYWHERE_M := 20000.0 # hiver enneigé : neige partout
## Paliers de l'année : `y` = indice de la saison (printemps 0) + avancement. Linéaire entre deux paliers,
## bouclé de l'hiver au printemps. L'été (de 1,0 à 2,0) est neutre.
const KEYS := [
	{"y": 0.0, "leaf": Color(0.90, 0.95, 0.80), "autumn": 0.0, "bare": 0.85, "blossom": 0.2,
		"grass": Color(1.0, 1.0, 0.96), "dry": 0.35, "snow": 0.35, "fall": 0.0, "insects": 0.2, "birds": 0.8, "cloud": 0.9},
	{"y": 0.5, "leaf": Color(1.06, 1.12, 0.78), "autumn": 0.0, "bare": 0.0, "blossom": 1.0,
		"grass": Color(1.02, 1.08, 0.90), "dry": 0.0, "snow": 0.0, "fall": 0.0, "insects": 0.6, "birds": 1.0, "cloud": 1.0},
	{"y": 0.9, "leaf": Color(1.02, 1.04, 0.94), "autumn": 0.0, "bare": 0.0, "blossom": 0.0,
		"grass": Color(1.0, 1.02, 0.98), "dry": 0.0, "snow": 0.0, "fall": 0.0, "insects": 0.9, "birds": 1.0, "cloud": 1.0},
	{"y": 1.0, "leaf": Color.WHITE, "autumn": 0.0, "bare": 0.0, "blossom": 0.0,
		"grass": Color.WHITE, "dry": 0.0, "snow": 0.0, "fall": 0.0, "insects": 1.0, "birds": 1.0, "cloud": 1.0},
	{"y": 2.0, "leaf": Color.WHITE, "autumn": 0.0, "bare": 0.0, "blossom": 0.0,
		"grass": Color.WHITE, "dry": 0.0, "snow": 0.0, "fall": 0.0, "insects": 1.0, "birds": 1.0, "cloud": 1.0},
	{"y": 2.5, "leaf": Color.WHITE, "autumn": 1.0, "bare": 0.1, "blossom": 0.0,
		"grass": Color(1.02, 0.98, 0.88), "dry": 0.3, "snow": 0.0, "fall": 1.0, "insects": 0.3, "birds": 0.7, "cloud": 0.9},
	{"y": 2.9, "leaf": Color(0.85, 0.80, 0.72), "autumn": 1.0, "bare": 0.6, "blossom": 0.0,
		"grass": Color(1.0, 0.95, 0.85), "dry": 0.5, "snow": 0.5, "fall": 0.6, "insects": 0.05, "birds": 0.5, "cloud": 0.8},
	{"y": 3.1, "leaf": Color(0.80, 0.76, 0.70), "autumn": 0.6, "bare": 1.0, "blossom": 0.0,
		"grass": Color(1.0, 0.96, 0.88), "dry": 0.7, "snow": 1.0, "fall": 0.0, "insects": 0.0, "birds": 0.35, "cloud": 0.7},
	{"y": 3.9, "leaf": Color(0.85, 0.85, 0.78), "autumn": 0.0, "bare": 1.0, "blossom": 0.0,
		"grass": Color(1.0, 0.98, 0.92), "dry": 0.6, "snow": 0.8, "fall": 0.0, "insects": 0.0, "birds": 0.4, "cloud": 0.75},
]
const NEUTRAL := {
	"leaf_tint": Color.WHITE, "autumn": 0.0, "bare": 0.0, "blossom": 0.0, "grass_tint": Color.WHITE,
	"grass_dry": 0.0, "snow_drop_m": 0.0, "falling_leaves": 0.0, "insects": 1.0, "birds": 1.0, "cloud_altitude": 1.0,
}
## Paramètres globaux des shaders (project.godot `[shader_globals]`, valeurs par défaut = été) : nom -> clé.
const GLOBALS := {
	"season_leaf_tint": "leaf_tint", "season_autumn": "autumn", "season_bare": "bare",
	"season_blossom": "blossom", "season_grass_tint": "grass_tint", "season_grass_dry": "grass_dry",
	"season_snow_drop_m": "snow_drop_m",
}
const MONTH_LENGTHS := [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


static func season_for(theme: Dictionary, month: int, day: int, lat_deg: float = 45.0) -> Dictionary:
	var forced: Variant = theme.get("season", null) if typeof(theme) == TYPE_DICTIONARY else null
	if typeof(forced) == TYPE_STRING and forced in SEASONS:
		return {"season": forced, "progress": 0.5}
	# Au sud, la date de l'hémisphère nord six mois plus tard (longueurs des mois de cette date-là).
	var m := clampi(month, 1, 12)
	var mm := m if lat_deg >= 0.0 else (m + 5) % 12 + 1
	var idx := posmod(mm - 3, 12) / 3
	var days := clampi(day, 1, MONTH_LENGTHS[m - 1]) - 1
	var length := 0
	for k in range(3):
		var mk := posmod(2 + idx * 3 + k, 12)   # indice 0..11 des trois mois de la saison
		if k < posmod(mm - 3, 3):
			days += MONTH_LENGTHS[mk]
		length += MONTH_LENGTHS[mk]
	return {"season": SEASONS[idx], "progress": clampf((days + 0.5) / float(length), 0.0, 1.0)}


static func year_position(season: String, progress: float) -> float:
	var i := SEASONS.find(season)
	if i < 0:
		i = 1
	return float(i) + clampf(progress, 0.0, 1.0)


static func params(season: String, progress: float = 0.5, snowy: bool = false) -> Dictionary:
	var y := fposmod(year_position(season, progress), 4.0)
	var a: Dictionary = KEYS[KEYS.size() - 1]
	var b: Dictionary = KEYS[0]
	var span := 4.0 - float(a["y"]) + float(b["y"])
	var t := (y - float(a["y"])) / span if y >= float(a["y"]) else (y + 4.0 - float(a["y"])) / span
	for i in range(KEYS.size() - 1):
		if y >= float(KEYS[i]["y"]) and y < float(KEYS[i + 1]["y"]):
			a = KEYS[i]
			b = KEYS[i + 1]
			t = (y - float(a["y"])) / (float(b["y"]) - float(a["y"]))
			break
	t = clampf(t, 0.0, 1.0)
	var snow := lerpf(float(a["snow"]), float(b["snow"]), t)
	return {
		"leaf_tint": (a["leaf"] as Color).lerp(b["leaf"], t),
		"autumn": lerpf(float(a["autumn"]), float(b["autumn"]), t),
		"bare": lerpf(float(a["bare"]), float(b["bare"]), t),
		"blossom": lerpf(float(a["blossom"]), float(b["blossom"]), t),
		"grass_tint": (a["grass"] as Color).lerp(b["grass"], t),
		"grass_dry": lerpf(float(a["dry"]), float(b["dry"]), t),
		"snow_drop_m": snow * (SNOW_EVERYWHERE_M if snowy else SNOW_DROP_M),
		"falling_leaves": lerpf(float(a["fall"]), float(b["fall"]), t),
		"insects": lerpf(float(a["insects"]), float(b["insects"]), t),
		"birds": lerpf(float(a["birds"]), float(b["birds"]), t),
		"cloud_altitude": lerpf(float(a["cloud"]), float(b["cloud"]), t),
		"season": season if season in SEASONS else "summer",
	}


static func globals(p: Dictionary) -> Dictionary:
	var out := {}
	for name in GLOBALS.keys():
		var v: Variant = p.get(GLOBALS[name], NEUTRAL[GLOBALS[name]])
		out[name] = Vector3(v.r, v.g, v.b) if typeof(v) == TYPE_COLOR else float(v)
	return out


## Pose les paramètres globaux des shaders (un appel au chargement de la séance, puis à chaque changement).
static func apply_globals(p: Dictionary) -> void:
	var g := globals(p)
	for name in g.keys():
		RenderingServer.global_shader_parameter_set(name, g[name])
