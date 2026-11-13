extends RefCounted

## Jour, nuit et saisons de la séance selon les deux réglages du menu (lot P19, décision du propriétaire du
## 8 novembre : coupables séparément, coupés par défaut), sans nœud. Pas de class_name : charger par
## preload("res://scripts/sky_cycle.gd"). Appliqué à la scène par main.gd (atmosphere_view, paramètres globaux
## des saisons, arbres, sons, feuilles qui tombent).
##
## - `daylight_params(mode, theme)` -> paramètres de `DaylightModel.evaluate` pour `render.day_night` :
##   `off` (et thème sans heure en `theme`) : `present` faux, soleil fixe d'aujourd'hui ; `theme` : heure du
##   thème (`sky.time_of_day`) ; `real` : heure du PC ; `accelerated` : une journée en une heure (×24) depuis
##   ACCEL_START_HOUR, la nuit ne durant que le quart du jour (ACCEL_NIGHT_SHARE du cycle) ;
## - `season_state(mode, theme, month, day, lat)` -> `{active, season, progress, params}` pour `render.seasons` :
##   `off` : inactive (paramètres de l'été, rendu d'aujourd'hui) ; `theme` : saison du thème, l'été sans ;
##   `date` : saison de la date et de l'hémisphère, selon le calendrier de chaque biome (lot U13) : `weights`
##   (biome -> poids au point, biome_model.weights_at) mélange les saisons des biomes présents ; sans poids,
##   biome par défaut du thème (thème 1.x ou `temperate_grassland` : saisons de P18) ; `spring` à `winter` :
##   la saison, au milieu, pour tous les biomes ; enneigement partout l'hiver quand la météo du thème est la neige ;
## - `effective_day_mode(mode, indoor)` : coupé dans le vélodrome ;
## - `evaluate(day_mode, season_mode, theme, lat, lon, date, elapsed_s, now, hour, weights)` : les deux ensemble.

const DaylightModel := preload("res://scripts/daylight_model.gd")
const SeasonModel := preload("res://scripts/season_model.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const BiomeIds := preload("res://scripts/biome_ids.gd")

const DAY_MODES := ["off", "theme", "real", "accelerated"]
const SEASON_MODES := ["off", "theme", "date", "spring", "summer", "autumn", "winter"]
const ACCEL_START_HOUR := 6.0    # journée accélérée : départ à l'aube
const ACCEL_FACTOR := 24.0       # une journée en une heure de séance
const ACCEL_NIGHT_SHARE := 0.2   # la nuit dure le quart du jour (12 min de nuit, 48 min de jour ; 13/11)


## Réglage `render.day_night` appliqué à la scène : coupé en salle (vélodrome, demande du 13 novembre : pas de
## nuit dans une salle éclairée), le réglage sinon.
static func effective_day_mode(mode: String, indoor: bool) -> String:
	return "off" if indoor else mode


static func daylight_params(mode: String, theme: Dictionary) -> Dictionary:
	var tod := ThemeRenderParams.time_of_day_params(theme)
	match mode:
		"theme":
			return tod
		"real":
			tod["present"] = true
			tod["mode"] = "real"
		"accelerated":
			tod["present"] = true
			tod["mode"] = "accelerated"
			tod["hour"] = ACCEL_START_HOUR
			tod["factor"] = ACCEL_FACTOR
			tod["night_share"] = ACCEL_NIGHT_SHARE
		_:
			tod["present"] = false
	return tod


static func season_state(mode: String, theme: Dictionary, month: int, day: int, lat_deg: float,
		weights: Dictionary = {}) -> Dictionary:
	var snowy := typeof(theme.get("weather", null)) == TYPE_DICTIONARY and str(theme["weather"].get("kind", "")) == "snow"
	var s := {"season": "summer", "progress": 0.5}
	match mode:
		"off":
			return {"active": false, "season": "summer", "progress": 0.5, "params": SeasonModel.NEUTRAL.duplicate()}
		"theme":
			var t: Variant = theme.get("season", null)
			if typeof(t) == TYPE_STRING and t in SeasonModel.SEASONS:
				s = {"season": t, "progress": 0.5}
		"date":
			return _date_state(theme, month, day, lat_deg, weights, snowy)
		_:
			if mode in SeasonModel.SEASONS:
				s = {"season": mode, "progress": 0.5}
	return {"active": true, "season": s["season"], "progress": s["progress"],
		"params": SeasonModel.params(s["season"], s["progress"], snowy)}


## Mode `date` (lot U13) : saison de chaque biome selon son calendrier, paramètres mélangés par les poids.
static func _date_state(theme: Dictionary, month: int, day: int, lat_deg: float, weights: Dictionary, snowy: bool) -> Dictionary:
	var w := weights
	if w.is_empty():
		var d: Variant = theme.get("default_biome", null)
		w = {d if BiomeIds.is_biome(d) else BiomeIds.DEFAULT_BIOME: 1.0}
	var biomes: Dictionary = theme["biomes"] if typeof(theme.get("biomes", null)) == TYPE_DICTIONARY else {}
	var lat := 45.0 if is_nan(lat_deg) else lat_deg
	var by_biome := {}
	var best := ""
	var best_w := -1.0
	var keys := w.keys()
	keys.sort()
	for b in keys:
		var s := SeasonModel.biome_state(biomes.get(b, {}), month, day, lat, snowy)
		by_biome[b] = s["params"]
		by_biome[b]["progress"] = s["progress"]
		if float(w[b]) > best_w:
			best_w = float(w[b])
			best = b
	return {"active": true, "season": by_biome[best]["season"], "progress": by_biome[best]["progress"],
		"params": SeasonModel.blend(w, by_biome)}


## `date` : `{year, month, day}` (date du PC) ; `now` : heure locale et fuseau (`bias`), pour `real`.
## `hour` (essais seulement) : heure solaire fixe à la place de celle du réglage, s'il n'est pas coupé.
static func evaluate(day_mode: String, season_mode: String, theme: Dictionary, lat_deg: float, lon_deg: float,
		date: Dictionary, elapsed_s: float, now: Dictionary = {}, hour: float = NAN, weights: Dictionary = {}) -> Dictionary:
	var y := int(date.get("year", 2026))
	var m := int(date.get("month", 7))
	var d := int(date.get("day", 1))
	var doy := DaylightModel.day_of_year(y, m, d)
	var unix_days := Time.get_unix_time_from_datetime_dict({"year": y, "month": m, "day": d, "hour": 12}) / 86400.0
	var tod := daylight_params(day_mode, theme)
	if not is_nan(hour) and bool(tod["present"]):
		tod["mode"] = "fixed"
		tod["hour"] = fposmod(hour, 24.0)
	var light := DaylightModel.evaluate(tod, lat_deg, lon_deg, doy, elapsed_s, now, unix_days)
	return {"daylight": light, "season": season_state(season_mode, theme, m, d, lat_deg, weights)}
