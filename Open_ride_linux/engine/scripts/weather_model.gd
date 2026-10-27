extends RefCounted

## Météo légère de l'engine, sans aucun nœud (Lot P8, thème 1.2 `weather`, world_format_v1.md §9).
## Pas de class_name : charger par preload("res://scripts/weather_model.gd"). Branché par P17.
##
## - `from_theme(theme)` lit `weather` (`kind`, `intensity`, `morning_mist`) et `terrain.snow_line_m` ;
##   thème sans `weather` : météo claire, aucun effet.
## - `evaluate(weather, rider_alt_m, valley_alt_m, wind_eval, solar_hour = NAN)` rend
##   `{fog_boost, fog_height_m, rain, snow, wetness, wind_dir, wind_strength}` :
##   - `fog_boost` (0 à 1) : brume de vallée (`morning_mist`), plus dense sous `valley_alt_m`
##     (altitude moyenne du terrain proche, fournie par l'appelant), et brume générale (`kind` = `mist`).
##     Constante dans le temps en 1.x ; avec `solar_hour` (P7, version 2.0), la brume du matin est
##     pleine jusqu'à 6 h et disparaît vers 10 h ;
##   - `fog_height_m` : sommet de la nappe de brume, pour le brouillard en hauteur de P17 ;
##   - `rain` et `snow` (0 à 1) : jamais les deux à la fois ; la pluie devient neige au-dessus de
##     `snow_line_m` ;
##   - `wetness` (0 à 1) : assombrissement de la route sous la pluie (paramètre pour P17).

const KINDS := ["clear", "mist", "rain", "snow"]
const MORNING_MIST := 0.6         # intensité de la brume de vallée quand le thème la demande
const VALLEY_BAND_M := 400.0      # de pleine brume (200 m sous la vallée) à rien (200 m au-dessus)
const MIST_LAYER_M := 80.0        # épaisseur de la nappe au-dessus de l'altitude de la vallée
const MIST_FULL_HOUR := 6.0
const MIST_GONE_HOUR := 10.0
const WETNESS_GAIN := 1.5
const DEFAULT_SNOW_LINE_M := 2200.0


static func _is_number(v: Variant) -> bool:
	return typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT


static func clear() -> Dictionary:
	return {"kind": "clear", "intensity": 0.0, "morning_mist": false, "snow_line_m": DEFAULT_SNOW_LINE_M}


static func from_theme(theme: Dictionary) -> Dictionary:
	var out := clear()
	if typeof(theme) != TYPE_DICTIONARY:
		return out
	var terrain: Variant = theme.get("terrain", null)
	if typeof(terrain) == TYPE_DICTIONARY and _is_number(terrain.get("snow_line_m", null)):
		out["snow_line_m"] = float(terrain["snow_line_m"])
	var w: Variant = theme.get("weather", null)
	if typeof(w) != TYPE_DICTIONARY:
		return out
	var kind := str(w.get("kind", "clear"))
	out["kind"] = kind if kind in KINDS else "clear"
	if _is_number(w.get("intensity", null)):
		out["intensity"] = clampf(float(w["intensity"]), 0.0, 1.0)
	out["morning_mist"] = w.get("morning_mist", false) == true
	return out


## Facteur de la brume du matin selon l'heure solaire : 1 jusqu'à 6 h, 0 à partir de 10 h.
static func mist_time_factor(solar_hour: float) -> float:
	if is_nan(solar_hour):
		return 1.0
	var h := fposmod(solar_hour, 24.0)
	if h <= MIST_FULL_HOUR:
		return 1.0
	if h >= MIST_GONE_HOUR:
		return 0.0
	return 1.0 - smoothstep(MIST_FULL_HOUR, MIST_GONE_HOUR, h)


static func evaluate(weather: Dictionary, rider_alt_m: float, valley_alt_m: float, wind_eval: Dictionary,
		solar_hour: float = NAN) -> Dictionary:
	var kind := str(weather.get("kind", "clear"))
	var intensity := clampf(float(weather.get("intensity", 0.0)), 0.0, 1.0)
	var valley := clampf(0.5 + (valley_alt_m - rider_alt_m) / VALLEY_BAND_M, 0.0, 1.0)
	var fog := 0.0
	if weather.get("morning_mist", false) == true:
		fog = MORNING_MIST * valley * mist_time_factor(solar_hour)
	if kind == "mist":
		fog = maxf(fog, intensity * (0.5 + 0.5 * valley))
	var rain := 0.0
	var snow := 0.0
	if kind == "snow":
		snow = intensity
	elif kind == "rain":
		if rider_alt_m > float(weather.get("snow_line_m", DEFAULT_SNOW_LINE_M)):
			snow = intensity
		else:
			rain = intensity
	return {
		"fog_boost": clampf(fog, 0.0, 1.0),
		"fog_height_m": valley_alt_m + MIST_LAYER_M,
		"rain": rain,
		"snow": snow,
		"wetness": clampf(rain * WETNESS_GAIN, 0.0, 1.0),
		"wind_dir": wind_eval.get("dir", Vector3.ZERO),
		"wind_strength": float(wind_eval.get("strength", 0.0)),
	}
