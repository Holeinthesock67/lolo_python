extends RefCounted

## Paramètres de rendu tirés du thème et fonction de référence du mélange triplanaire
## herbe / roche / neige (Lot L3, SRS §8, §8.1 et §10, Format .world v1 §9), sans nœud ni shader.
## Pas de class_name : charger par preload("res://scripts/theme_render_params.gd").
##
## Noms des clés de `terrain_uniforms(theme)` (futurs `uniform` du shader triplanaire d'E2) :
## - `grass_color` (Color), `grass_inv_scale` (float, 1 / scale_m), `grass_texture` (String ou null)
## - `rock_color` (Color), `rock_inv_scale` (float, 1 / scale_m), `rock_texture` (String ou null)
## - `snow_color` (Color), `snow_inv_scale` (float, 1 / scale_m), `snow_texture` (String ou null)
## - `cos_slope` (float, cos(slope_threshold_deg)), `slope_threshold_deg` (float)
## - `snow_line_m` (float), `blend_sharpness` (float)
## - sous-dictionnaires `grass`, `rock`, `snow` (`{color, inv_scale, texture}`) également exposés.
##
## Azimut du soleil : constante `SUN_AZIMUTH_DEG = 150.0` (sud-sud-est, sens horaire depuis le nord −z),
## non présente dans le format .world v1 §9 (candidate pour une version ultérieure du schéma de thème).

const DEFAULT_GRASS_HEX := "#6f9a4a"
const DEFAULT_GRASS_SCALE_M := 6.0
const DEFAULT_ROCK_HEX := "#9a9488"
const DEFAULT_ROCK_SCALE_M := 12.0
const DEFAULT_SNOW_HEX := "#f2f5f8"
const DEFAULT_SNOW_SCALE_M := 8.0
const DEFAULT_SLOPE_THRESHOLD_DEG := 22.0
const DEFAULT_SNOW_LINE_M := 2200.0
const DEFAULT_BLEND_SHARPNESS := 4.0

const DEFAULT_ROAD_HEX := "#4a4a4d"
const DEFAULT_ROAD_WIDTH_M := 6.0

const DEFAULT_SUN_ELEVATION_DEG := 40.0
const DEFAULT_FOG_DENSITY := 0.0008
const SUN_AZIMUTH_DEG := 150.0

const SNOW_MELT_BAND_M := 50.0
const STEEP_SNOW_START_DEG := 44.0
const STEEP_SNOW_MAX_DEG := 50.0
const MAX_SLOPE_HALF_BAND_DEG := 3.0
const MIN_SLOPE_HALF_BAND_DEG := 1.5


static func _is_number(v: Variant) -> bool:
	return (typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT) and is_finite(float(v))


static func _color_or_default(raw: Variant, fallback_hex: String) -> Color:
	if typeof(raw) == TYPE_COLOR:
		return raw
	if typeof(raw) == TYPE_STRING and Color.html_is_valid(raw):
		return Color.html(raw)
	return Color.html(fallback_hex)


static func _tex_or_null(raw: Variant) -> Variant:
	if typeof(raw) == TYPE_STRING and not (raw as String).strip_edges().is_empty():
		return raw
	return null


static func _layer_params(t_dict: Dictionary, key: String, def_hex: String, def_scale: float) -> Dictionary:
	var sub: Dictionary = {}
	if typeof(t_dict.get(key, null)) == TYPE_DICTIONARY:
		sub = t_dict[key]
	var col := _color_or_default(sub.get("color", null), def_hex)
	var scale_m := def_scale
	if _is_number(sub.get("scale_m", null)) and float(sub["scale_m"]) > 0.0:
		scale_m = float(sub["scale_m"])
	var tex = _tex_or_null(sub.get("texture", null))
	return {
		"color": col,
		"inv_scale": 1.0 / scale_m,
		"scale_m": scale_m,
		"texture": tex,
	}


## Convertit la section `terrain` d'un thème en paramètres/uniforms pour le shader triplanaire.
static func terrain_uniforms(theme: Dictionary) -> Dictionary:
	var t_dict: Dictionary = {}
	if typeof(theme) == TYPE_DICTIONARY and typeof(theme.get("terrain", null)) == TYPE_DICTIONARY:
		t_dict = theme["terrain"]

	var grass := _layer_params(t_dict, "grass", DEFAULT_GRASS_HEX, DEFAULT_GRASS_SCALE_M)
	var rock := _layer_params(t_dict, "rock", DEFAULT_ROCK_HEX, DEFAULT_ROCK_SCALE_M)
	var snow := _layer_params(t_dict, "snow", DEFAULT_SNOW_HEX, DEFAULT_SNOW_SCALE_M)

	var slope_deg := DEFAULT_SLOPE_THRESHOLD_DEG
	if _is_number(t_dict.get("slope_threshold_deg", null)):
		var s := float(t_dict["slope_threshold_deg"])
		if s >= 0.0 and s <= 90.0:
			slope_deg = s

	var snow_line := DEFAULT_SNOW_LINE_M
	if _is_number(t_dict.get("snow_line_m", null)):
		snow_line = float(t_dict["snow_line_m"])

	var sharpness := DEFAULT_BLEND_SHARPNESS
	if _is_number(t_dict.get("blend_sharpness", null)) and float(t_dict["blend_sharpness"]) > 0.0:
		sharpness = float(t_dict["blend_sharpness"])

	var cos_slope := cos(deg_to_rad(slope_deg))

	return {
		"grass_color": grass["color"],
		"grass_inv_scale": grass["inv_scale"],
		"grass_texture": grass["texture"],
		"rock_color": rock["color"],
		"rock_inv_scale": rock["inv_scale"],
		"rock_texture": rock["texture"],
		"snow_color": snow["color"],
		"snow_inv_scale": snow["inv_scale"],
		"snow_texture": snow["texture"],
		"cos_slope": cos_slope,
		"slope_threshold_deg": slope_deg,
		"snow_line_m": snow_line,
		"blend_sharpness": sharpness,
		"grass": grass,
		"rock": rock,
		"snow": snow,
	}


## Fonction de référence du mélange (herbe, roche, neige) dans [0, 1]^3, de somme 1 (SRS §8.1).
static func blend_weights(normal: Vector3, altitude_m: float, params: Dictionary) -> Vector3:
	var n := normal.normalized() if normal.length_squared() > 1e-12 else Vector3.UP
	var cos_n := clampf(n.y, -1.0, 1.0)
	var slope_deg := rad_to_deg(acos(cos_n))

	var thresh_deg := DEFAULT_SLOPE_THRESHOLD_DEG
	if _is_number(params.get("slope_threshold_deg", null)):
		thresh_deg = float(params["slope_threshold_deg"])
	elif _is_number(params.get("cos_slope", null)):
		thresh_deg = rad_to_deg(acos(clampf(float(params["cos_slope"]), -1.0, 1.0)))

	var sharpness := DEFAULT_BLEND_SHARPNESS
	if _is_number(params.get("blend_sharpness", null)) and float(params["blend_sharpness"]) > 0.0:
		sharpness = float(params["blend_sharpness"])

	var snow_line := DEFAULT_SNOW_LINE_M
	if _is_number(params.get("snow_line_m", null)):
		snow_line = float(params["snow_line_m"])

	# Demi-largeur de transition bornée à ± 3° autour du seuil, plus étroite quand blend_sharpness augmente
	var half_band := clampf(12.0 / maxf(sharpness, 1.0), MIN_SLOPE_HALF_BAND_DEG, MAX_SLOPE_HALF_BAND_DEG)
	var t_rock := smoothstep(thresh_deg - half_band, thresh_deg + half_band, slope_deg)

	# Neige au-dessus de snow_line_m, fondue sur 50 m, absente sur la roche raide (> 50°)
	var snow_alt := smoothstep(snow_line, snow_line + SNOW_MELT_BAND_M, altitude_m)
	var snow_slope := 1.0 - smoothstep(STEEP_SNOW_START_DEG, STEEP_SNOW_MAX_DEG, slope_deg)
	var w_snow := clampf(snow_alt * snow_slope, 0.0, 1.0)

	var rem := 1.0 - w_snow
	var w_rock := rem * t_rock
	var w_grass := rem * (1.0 - t_rock)
	return Vector3(w_grass, w_rock, w_snow)


## Poids des trois projections triplanaires (YZ, XZ, XY), positifs et de somme 1.
static func triplanar_weights(normal: Vector3, sharpness: float) -> Vector3:
	var n := normal.normalized() if normal.length_squared() > 1e-12 else Vector3.UP
	var s := maxf(sharpness if is_finite(sharpness) else DEFAULT_BLEND_SHARPNESS, 0.01)
	var wx := pow(maxf(absf(n.x), 1e-8), s)
	var wy := pow(maxf(absf(n.y), 1e-8), s)
	var wz := pow(maxf(absf(n.z), 1e-8), s)
	var total := wx + wy + wz
	if total <= 1e-12:
		return Vector3(0.0, 1.0, 0.0)
	return Vector3(wx / total, wy / total, wz / total)


## Paramètres de rendu de la route (`color`, `texture`, `width_m`).
static func road_params(theme: Dictionary) -> Dictionary:
	var r_dict: Dictionary = {}
	if typeof(theme) == TYPE_DICTIONARY and typeof(theme.get("road", null)) == TYPE_DICTIONARY:
		r_dict = theme["road"]
	var col := _color_or_default(r_dict.get("color", null), DEFAULT_ROAD_HEX)
	var tex = _tex_or_null(r_dict.get("texture", null))
	var width_m := DEFAULT_ROAD_WIDTH_M
	if _is_number(r_dict.get("width_m", null)) and float(r_dict["width_m"]) > 0.0:
		width_m = float(r_dict["width_m"])
	return {
		"color": col,
		"texture": tex,
		"width_m": width_m,
	}


## Paramètres du ciel et du brouillard (`sun_direction`, `sun_elevation_deg`, `sun_azimuth_deg`, `fog_density`).
static func sky_params(theme: Dictionary) -> Dictionary:
	var s_dict: Dictionary = {}
	if typeof(theme) == TYPE_DICTIONARY and typeof(theme.get("sky", null)) == TYPE_DICTIONARY:
		s_dict = theme["sky"]
	var elev_deg := DEFAULT_SUN_ELEVATION_DEG
	if _is_number(s_dict.get("sun_elevation_deg", null)):
		var e := float(s_dict["sun_elevation_deg"])
		if e >= -90.0 and e <= 90.0:
			elev_deg = e
	var fog := DEFAULT_FOG_DENSITY
	if _is_number(s_dict.get("fog_density", null)) and float(s_dict["fog_density"]) >= 0.0:
		fog = float(s_dict["fog_density"])

	var el_rad := deg_to_rad(elev_deg)
	var az_rad := deg_to_rad(SUN_AZIMUTH_DEG)
	var horiz := cos(el_rad)
	var sun_dir := Vector3(horiz * sin(az_rad), sin(el_rad), -horiz * cos(az_rad)).normalized()

	return {
		"sun_direction": sun_dir,
		"sun_elevation_deg": elev_deg,
		"sun_azimuth_deg": SUN_AZIMUTH_DEG,
		"fog_density": fog,
	}
