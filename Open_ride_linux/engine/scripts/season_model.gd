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
## (facteur de l'altitude des nuages : ciel plus bas l'hiver), `ground_wet` (sol détrempé : plus sombre et
## plus brillant, saison des pluies).
##
## Calendriers par biome (lot U13, version 3.0) : `season_for_biome(biome_def, month, day, lat_deg, theme)`
## -> `{season, progress, calendar}` selon `seasons.calendar` du thème 2.0 (U1 §4.5) :
## - `four` : printemps, été, automne, hiver de durées `durations_months`, l'été centré sur le 16 juillet
##   (SUMMER_CENTER_M) puis décalé de `offset_months` ; durées 3, 3, 3, 3 : exactement les saisons de P18 ;
## - `wet_dry` : `dry` puis `wet` (durées dans cet ordre), la saison des pluies centrée sur le 16 août
##   (WET_CENTER_M : les pluies suivent le soleil avec un mois de retard) ;
## - `polar` : `polar_night`, `polar_rise`, `polar_day`, `polar_set` d'après le soleil de P7 (daylight_model)
##   à la latitude, ramenée au moins à POLAR_MIN_LAT_DEG ; neige partout toute l'année ;
## - `none` : saison `none` toute l'année, paramètres neutres (rendu d'aujourd'hui) ;
## au sud de l'équateur, la date six mois plus tard (comme P18) ; `season` du thème l'emporte toujours.
## `params` accepte toutes ces saisons ; `blend(weights, params_by_biome)` mélange les paramètres de
## plusieurs biomes (chacun dans sa saison) en un point.

const DaylightModel := preload("res://scripts/daylight_model.gd")
const BiomeIds := preload("res://scripts/biome_ids.gd")

const SEASONS := ["spring", "summer", "autumn", "winter"]
const WET_DRY := ["dry", "wet"]
const POLAR := ["polar_night", "polar_rise", "polar_day", "polar_set"]
const CALENDARS := BiomeIds.CALENDARS
const DEFAULT_SEASONS := {"calendar": "four", "offset_months": 0, "durations_months": [3, 3, 3, 3]}
const SUMMER_CENTER_M := 6.5       # milieu de l'été, en mois depuis le 1er janvier : 16 juillet
const WET_CENTER_M := 7.5          # milieu de la saison des pluies : 16 août
const POLAR_MIN_LAT_DEG := 75.0    # biome polaire plus au sud (biome forcé) : soleil de 75°
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
## Saison sèche puis saison des pluies (lot U13) : `y` = 0 à 1 sèche, 1 à 2 pluies, bouclé. Herbe jaunie et
## feuillus en partie dénudés au cœur de la saison sèche ; feuillage dense et sombre, herbe verte et sol
## détrempé pendant les pluies. Pas de neige.
const WET_DRY_KEYS := [
	{"y": 0.0, "leaf": Color(0.95, 0.99, 0.90), "autumn": 0.0, "bare": 0.0, "blossom": 0.0,
		"grass": Color(0.98, 1.02, 0.94), "dry": 0.3, "snow": 0.0, "fall": 0.0, "insects": 0.9, "birds": 1.0, "cloud": 1.0, "wet": 0.2},
	{"y": 0.5, "leaf": Color(0.96, 0.92, 0.74), "autumn": 0.0, "bare": 0.3, "blossom": 0.0,
		"grass": Color(1.04, 0.98, 0.82), "dry": 0.85, "snow": 0.0, "fall": 0.25, "insects": 0.5, "birds": 0.7, "cloud": 1.1, "wet": 0.0},
	{"y": 0.9, "leaf": Color(0.96, 0.93, 0.78), "autumn": 0.0, "bare": 0.2, "blossom": 0.0,
		"grass": Color(1.03, 0.98, 0.85), "dry": 0.7, "snow": 0.0, "fall": 0.1, "insects": 0.6, "birds": 0.8, "cloud": 1.05, "wet": 0.0},
	{"y": 1.2, "leaf": Color(0.82, 0.94, 0.78), "autumn": 0.0, "bare": 0.0, "blossom": 0.0,
		"grass": Color(0.92, 1.06, 0.88), "dry": 0.0, "snow": 0.0, "fall": 0.0, "insects": 1.0, "birds": 1.0, "cloud": 0.85, "wet": 1.0},
	{"y": 1.85, "leaf": Color(0.84, 0.95, 0.80), "autumn": 0.0, "bare": 0.0, "blossom": 0.0,
		"grass": Color(0.94, 1.05, 0.90), "dry": 0.05, "snow": 0.0, "fall": 0.0, "insects": 1.0, "birds": 1.0, "cloud": 0.9, "wet": 0.6},
]
## Polaire (lot U13) : nuit polaire, retour du soleil, jour polaire, départ du soleil ; neige partout toute
## l'année (`snow` 1 et enneigement forcé), herbe rase et pâle, oiseaux et insectes l'été seulement.
const POLAR_KEYS := [
	{"y": 0.5, "leaf": Color.WHITE, "autumn": 0.0, "bare": 0.0, "blossom": 0.0,
		"grass": Color(0.95, 0.97, 1.0), "dry": 0.6, "snow": 1.0, "fall": 0.0, "insects": 0.0, "birds": 0.1, "cloud": 0.75, "wet": 0.0},
	{"y": 2.5, "leaf": Color.WHITE, "autumn": 0.0, "bare": 0.0, "blossom": 0.0,
		"grass": Color(0.98, 1.0, 0.98), "dry": 0.4, "snow": 1.0, "fall": 0.0, "insects": 0.3, "birds": 1.0, "cloud": 0.9, "wet": 0.0},
]
## Table de chaque calendrier : saisons dans l'ordre de l'année et paliers.
const CALENDAR_KEYS := {"four": [SEASONS, KEYS], "wet_dry": [WET_DRY, WET_DRY_KEYS], "polar": [POLAR, POLAR_KEYS]}
const NEUTRAL := {
	"leaf_tint": Color.WHITE, "autumn": 0.0, "bare": 0.0, "blossom": 0.0, "grass_tint": Color.WHITE,
	"grass_dry": 0.0, "snow_drop_m": 0.0, "falling_leaves": 0.0, "insects": 1.0, "birds": 1.0, "cloud_altitude": 1.0, "ground_wet": 0.0,
}
## Paramètres globaux des shaders (project.godot `[shader_globals]`, valeurs par défaut = été) : nom -> clé.
const GLOBALS := {
	"season_leaf_tint": "leaf_tint", "season_autumn": "autumn", "season_bare": "bare",
	"season_blossom": "blossom", "season_grass_tint": "grass_tint", "season_grass_dry": "grass_dry",
	"season_snow_drop_m": "snow_drop_m", "season_ground_wet": "ground_wet",
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


## Calendrier d'une saison (`four`, `wet_dry`, `polar` ; `none` pour `none` et toute saison inconnue).
static func calendar_of(season: String) -> String:
	for c in CALENDAR_KEYS.keys():
		if season in CALENDAR_KEYS[c][0]:
			return c
	return "none"


static func year_position(season: String, progress: float) -> float:
	var names: Array = CALENDAR_KEYS[calendar_of(season)][0] if calendar_of(season) != "none" else SEASONS
	var i := names.find(season)
	if i < 0:
		i = 1
	return float(i) + clampf(progress, 0.0, 1.0)


## Paramètres d'une saison de n'importe quel calendrier ; `none` et saison inconnue : neutres (été).
static func params(season: String, progress: float = 0.5, snowy: bool = false) -> Dictionary:
	var cal := calendar_of(season)
	if season == "none":
		var n := NEUTRAL.duplicate()
		n["season"] = "none"
		return n
	if cal == "none":
		return params("summer", progress, snowy)
	var table: Array = CALENDAR_KEYS[cal][1]
	var n_seasons := float((CALENDAR_KEYS[cal][0] as Array).size())
	var y := fposmod(year_position(season, progress), n_seasons)
	var a: Dictionary = table[table.size() - 1]
	var b: Dictionary = table[0]
	var span := n_seasons - float(a["y"]) + float(b["y"])
	var t := (y - float(a["y"])) / span if y >= float(a["y"]) else (y + n_seasons - float(a["y"])) / span
	for i in range(table.size() - 1):
		if y >= float(table[i]["y"]) and y < float(table[i + 1]["y"]):
			a = table[i]
			b = table[i + 1]
			t = (y - float(a["y"])) / (float(b["y"]) - float(a["y"]))
			break
	t = clampf(t, 0.0, 1.0)
	var snow := lerpf(float(a["snow"]), float(b["snow"]), t)
	var everywhere := snowy or cal == "polar"
	return {
		"leaf_tint": (a["leaf"] as Color).lerp(b["leaf"], t),
		"autumn": lerpf(float(a["autumn"]), float(b["autumn"]), t),
		"bare": lerpf(float(a["bare"]), float(b["bare"]), t),
		"blossom": lerpf(float(a["blossom"]), float(b["blossom"]), t),
		"grass_tint": (a["grass"] as Color).lerp(b["grass"], t),
		"grass_dry": lerpf(float(a["dry"]), float(b["dry"]), t),
		"snow_drop_m": snow * (SNOW_EVERYWHERE_M if everywhere else SNOW_DROP_M),
		"falling_leaves": lerpf(float(a["fall"]), float(b["fall"]), t),
		"insects": lerpf(float(a["insects"]), float(b["insects"]), t),
		"birds": lerpf(float(a["birds"]), float(b["birds"]), t),
		"cloud_altitude": lerpf(float(a["cloud"]), float(b["cloud"]), t),
		"ground_wet": lerpf(float(a.get("wet", 0.0)), float(b.get("wet", 0.0)), t),
		"season": season,
	}


## Section `seasons` d'un biome du thème 2.0 (l'entrée du biome ou directement sa section), complétée par
## défaut : calendrier `four` de P18.
static func seasons_def(biome_def: Variant) -> Dictionary:
	var d: Variant = biome_def
	if typeof(d) == TYPE_DICTIONARY and typeof(d.get("seasons", null)) == TYPE_DICTIONARY:
		d = d["seasons"]
	var out := DEFAULT_SEASONS.duplicate(true)
	if typeof(d) != TYPE_DICTIONARY:
		return out
	if str(d.get("calendar", "")) in CALENDARS:
		out["calendar"] = d["calendar"]
		if out["calendar"] == "wet_dry":
			out["durations_months"] = [6, 6]
		elif out["calendar"] == "polar":
			out["durations_months"] = [6, 6]
		elif out["calendar"] == "none":
			out["durations_months"] = [12]
	var off: Variant = d.get("offset_months", 0)
	if (typeof(off) == TYPE_INT or typeof(off) == TYPE_FLOAT) and is_finite(float(off)):
		out["offset_months"] = clampf(float(off), -6.0, 6.0)
	var dur: Variant = d.get("durations_months", null)
	var want := 4 if out["calendar"] == "four" else (2 if out["calendar"] != "none" else 1)
	if typeof(dur) == TYPE_ARRAY and (dur as Array).size() == want:
		var ok := true
		var total := 0.0
		for v in dur:
			ok = ok and (typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT) and float(v) > 0.0
			total += float(v) if ok else 0.0
		if ok and total > 0.0:
			# Somme ramenée à 12 mois (le schéma l'exige, une erreur de thème ne casse pas l'année)
			out["durations_months"] = (dur as Array).map(func(v): return float(v) * 12.0 / total)
	return out


## Position dans l'année, en jours depuis le 1er janvier (milieu du jour), année de 365 jours ; au sud, la
## date six mois plus tard (mois décalé, jour borné à la longueur du mois d'arrivée, comme P18).
static func _year_day(month: int, day: int, lat_deg: float) -> float:
	var m := clampi(month, 1, 12)
	var mm := m if is_nan(lat_deg) or lat_deg >= 0.0 else (m + 5) % 12 + 1
	var d := clampi(day, 1, MONTH_LENGTHS[m - 1])
	d = mini(d, MONTH_LENGTHS[mm - 1])
	var n := 0
	for k in range(mm - 1):
		n += MONTH_LENGTHS[k]
	return float(n + d - 1) + 0.5


## Mois (0 à 12, fractionnaire) -> jours depuis le 1er janvier, suivant les longueurs des mois ; bouclé.
static func _month_to_day(month_pos: float) -> float:
	var p := fposmod(month_pos, 12.0)
	var k := mini(int(floor(p)), 11)
	var n := 0
	for i in range(k):
		n += MONTH_LENGTHS[i]
	return float(n) + (p - float(k)) * float(MONTH_LENGTHS[k])


## Saison d'une suite de saisons de durées `durations` (mois), la première commençant au mois `start_m`.
static func _cycle_season(names: Array, durations: Array, start_m: float, year_day: float) -> Dictionary:
	var acc := start_m
	for i in range(names.size()):
		var a := _month_to_day(acc)
		var b := _month_to_day(acc + float(durations[i]))
		var length := fposmod(b - a, 365.0)
		if length <= 0.0:
			length = 365.0
		var into := fposmod(year_day - a, 365.0)
		if into < length:
			return {"season": names[i], "progress": clampf(into / length, 0.0, 1.0)}
		acc += float(durations[i])
	return {"season": names[0], "progress": 0.0}


## État du soleil un jour donné : 2 jour polaire (soleil levé à minuit), 0 nuit polaire (couché à midi), 1 sinon.
static func _polar_state(lat_deg: float, doy: float) -> int:
	var dec := DaylightModel.declination_deg(doy)
	var noon := 90.0 - absf(lat_deg - dec)
	var midnight := absf(lat_deg + dec) - 90.0
	if midnight > 0.0:
		return 2
	if noon < 0.0:
		return 0
	return 1


## Polaire : nuit, retour du soleil, jour, départ du soleil, d'après le soleil de P7 (dates du nord au sud aussi :
## la latitude garde son signe). Avancement : place du jour dans sa période (jours consécutifs de même état).
static func _polar_season(year_day: float, lat_deg: float) -> Dictionary:
	var lat := POLAR_MIN_LAT_DEG if is_nan(lat_deg) else signf(lat_deg if lat_deg != 0.0 else 1.0) * maxf(absf(lat_deg), POLAR_MIN_LAT_DEG)
	var today := int(floor(year_day))
	var st := _polar_state(lat, today + 1)
	var lo := 0
	while lo < 365 and _polar_state(lat, posmod(today - lo - 1, 365) + 1) == st:
		lo += 1
	var hi := 0
	while hi < 365 and _polar_state(lat, posmod(today + hi + 1, 365) + 1) == st:
		hi += 1
	var length := float(mini(lo + hi + 1, 365))
	var progress := clampf((float(lo) + year_day - float(today)) / length, 0.0, 1.0)
	var name := "polar_day" if st == 2 else ("polar_night" if st == 0 else "")
	if st == 1:
		# Transition : le soleil revient si la déclinaison va vers l'hémisphère de la latitude
		var rising := (DaylightModel.declination_deg(today + 2) - DaylightModel.declination_deg(today + 1)) * signf(lat) > 0.0
		name = "polar_rise" if rising else "polar_set"
	return {"season": name, "progress": progress}


## Saison d'un biome à une date (lot U13) : `biome_def` = entrée du biome du thème 2.0 ou sa section
## `seasons` ; `theme` : `season` du thème, qui l'emporte comme en P18. `lat_deg` NAN : hémisphère nord.
static func season_for_biome(biome_def: Variant, month: int, day: int, lat_deg: float = 45.0, theme: Dictionary = {}) -> Dictionary:
	var def := seasons_def(biome_def)
	var cal: String = def["calendar"]
	var forced: Variant = theme.get("season", null)
	if typeof(forced) == TYPE_STRING and forced in SEASONS:
		return {"season": forced, "progress": 0.5, "calendar": "four"}
	var dur: Array = def["durations_months"]
	var off := float(def["offset_months"])
	var yd := _year_day(month, day, lat_deg)
	var out := {}
	match cal:
		"four":
			# Été, automne, hiver, printemps à partir du début de l'été
			var s := _cycle_season(["summer", "autumn", "winter", "spring"], [dur[1], dur[2], dur[3], dur[0]],
				SUMMER_CENTER_M - float(dur[1]) / 2.0 + off, yd)
			out = s
		"wet_dry":
			out = _cycle_season(["wet", "dry"], [dur[1], dur[0]], WET_CENTER_M - float(dur[1]) / 2.0 + off, yd)
		"polar":
			# Le soleil décide : la date réelle (pas de décalage de six mois), la latitude avec son signe
			out = _polar_season(_year_day(month, day, 45.0), lat_deg)
		_:
			out = {"season": "none", "progress": 0.5}
	out["calendar"] = cal
	return out


## Mélange des paramètres de saison de plusieurs biomes en un point : `weights` (somme 1) et
## `params_by_biome` (biome -> `params(...)`) ; couleurs et nombres pondérés, `season` du biome de plus grand poids.
static func blend(weights: Dictionary, params_by_biome: Dictionary) -> Dictionary:
	var out := {}
	var total := 0.0
	var best := -1.0
	for k in NEUTRAL.keys():
		out[k] = Color(0, 0, 0, 0) if typeof(NEUTRAL[k]) == TYPE_COLOR else 0.0
	out["season"] = "summer"
	var keys := weights.keys()
	keys.sort()
	for b in keys:
		var w := float(weights[b])
		if w <= 0.0 or not params_by_biome.has(b):
			continue
		var p: Dictionary = params_by_biome[b]
		total += w
		for k in NEUTRAL.keys():
			out[k] += p.get(k, NEUTRAL[k]) * w
		if w > best:
			best = w
			out["season"] = p.get("season", "summer")
	if total <= 0.0:
		var n := NEUTRAL.duplicate()
		n["season"] = "summer"
		return n
	for k in NEUTRAL.keys():
		out[k] = out[k] / total
		if typeof(out[k]) == TYPE_COLOR:
			out[k].a = 1.0
	return out


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
