extends SceneTree

## Tests unitaires sans écran de l'atmosphère par biome `atmosphere_model.gd` (lot U10).
## Lancement : godot --headless --path engine --script res://tests/unit/test_atmosphere_model.gd

const AtmosphereModel := preload("res://scripts/atmosphere_model.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const CLEAR := {"rain": 0.0, "snow": 0.0, "fog_boost": 0.0}
const RAMP_M := 1000.0


## Prairie pour x < 0, désert de sable pour x > 1 km, passage linéaire entre les deux.
class RampModel extends "res://scripts/biome_model.gd":
	var from_biome := "temperate_grassland"
	var to_biome := "sand_desert"

	func weights_at(x: float, _z: float) -> Dictionary:
		var t := clampf(x / 1000.0, 0.0, 1.0)
		if t <= 0.0:
			return {from_biome: 1.0}
		if t >= 1.0:
			return {to_biome: 1.0}
		return {from_biome: 1.0 - t, to_biome: t}


var _failures := 0
var _checked := 0
var _theme: Dictionary


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _ramp() -> AtmosphereModel:
	var m := RampModel.new(_theme, null)
	return AtmosphereModel.new(m, func(s: float) -> Vector2: return Vector2(s, 0.0))


func _forced(biome: String) -> Dictionary:
	var m = BiomeModel.new(_theme, null)
	m.set_forced(biome)
	return m.weights_at(0.0, 0.0)


func _params(biome: String, daylight: Dictionary, weather: Dictionary, quality: String) -> Dictionary:
	var m = BiomeModel.new(_theme, null)
	return AtmosphereModel.params_at(m, {biome: 1.0}, daylight, weather, quality)


# Critère 5 : la prairie garde le ciel, le brouillard et le soleil d'aujourd'hui.
func _test_grassland_unchanged() -> void:
	var day := AtmosphereModel.daylight_from_theme(_theme, 48.9)
	var p := _params("temperate_grassland", day, CLEAR, "high")
	var m = BiomeModel.new(_theme, null)
	var sky: Dictionary = m.params("temperate_grassland")["sky"]
	var today: Color = RenderQuality.FOG_COLOR.lerp(RenderQuality.HAZE_COLOR, float(sky["haze"]) * 0.6) * (sky["light_tint"] as Color)
	_check(is_equal_approx(p["fog_density"], ThemeRenderParams.sky_params(_theme)["fog_density"]),
		"prairie : densité du brouillard du thème (%.4f)" % p["fog_density"])
	_check(p["horizon_color"].is_equal_approx(today), "prairie : horizon de main._apply_sky_params")
	_check(p["light_tint"].is_equal_approx(Color.WHITE) and p["light_energy_factor"] == 1.0 and p["fog_end_factor"] == 1.0,
		"prairie : lumière blanche, soleil et brouillard de profondeur inchangés")
	_check(p["heat_haze"] == 0.0 and p["humidity"] == 0.0, "prairie : ni brume de chaleur ni humidité")
	_check(p["sun_direction"].is_equal_approx(ThemeRenderParams.sky_params(_theme)["sun_direction"]),
		"prairie : soleil du thème (%.0f°)" % p["sun_elevation_deg"])


# Critère 2 : prairie vers désert sur 1 km, brouillard continu (moins de 2 % par 10 m).
func _test_transition() -> void:
	var atmo := _ramp()
	var day := AtmosphereModel.daylight_from_theme(_theme, 30.0)
	var worst := 0.0
	var worst_heat := 0.0
	var prev := {}
	var s := -600.0
	while s <= RAMP_M + 600.0:
		var p := atmo.at(s, day, CLEAR, "medium")
		if not prev.is_empty():
			worst = maxf(worst, absf(p["fog_density"] - prev["fog_density"]) / minf(p["fog_density"], prev["fog_density"]))
			worst_heat = maxf(worst_heat, absf(p["heat_haze"] - prev["heat_haze"]))
		prev = p
		s += 10.0
	_check(worst <= 0.02, "prairie -> désert : densité du brouillard au plus %.2f %% d'écart par 10 m" % (worst * 100.0))
	_check(worst_heat <= 0.02, "prairie -> désert : brume de chaleur au plus %.3f par 10 m" % worst_heat)
	var start := atmo.at(-600.0, day, CLEAR, "medium")
	var end := atmo.at(RAMP_M + 600.0, day, CLEAR, "medium")
	_check(is_equal_approx(start["fog_density"], 0.0008) and is_equal_approx(end["fog_density"], 0.0004),
		"avant et après le passage : densités de la prairie et du désert")
	var w := atmo.smoothed_weights(437.0)
	var total := 0.0
	for b in w.keys():
		total += float(w[b])
	_check(absf(total - 1.0) < 1e-5, "poids moyennés de somme 1 (%.6f)" % total)
	_check(not atmo.smoothed_weights(-260.0).has("sand_desert") and atmo.smoothed_weights(-240.0).has("sand_desert"),
		"fenêtre de 500 m : le désert entre dans la moyenne 250 m avant le début du passage")


# Critère 3 et 4 : la pluie l'emporte sur la brume de chaleur ; low la coupe.
func _test_heat_haze() -> void:
	var day := AtmosphereModel.daylight_from_theme(_theme, 25.0)
	_check(is_equal_approx(day["solar_hour"], 14.0), "heure fixe du thème : 14 h")
	var clear := _params("sand_desert", day, CLEAR, "medium")
	_check(clear["heat_haze"] > 0.9, "désert à 14 h, temps clair : brume de chaleur %.2f" % clear["heat_haze"])
	var rain := _params("sand_desert", day, {"rain": 0.6, "snow": 0.0, "fog_boost": 0.0}, "medium")
	_check(rain["heat_haze"] == 0.0, "désert sous la pluie : la pluie l'emporte (brume %.2f)" % rain["heat_haze"])
	var mist := _params("savanna", day, {"rain": 0.0, "snow": 0.0, "fog_boost": 0.5}, "high")
	_check(mist["heat_haze"] == 0.0, "savane dans la brume : pas de brume de chaleur")
	_check(_params("sand_desert", day, CLEAR, "low")["heat_haze"] == 0.0, "préréglage low : brume de chaleur coupée")
	_check(_params("rock_desert", day, CLEAR, "high")["heat_haze"] > 0.9 and _params("savanna", day, CLEAR, "high")["heat_haze"] > 0.9,
		"désert de roche et savane : brume de chaleur")
	for b in ["temperate_grassland", "jungle", "polar", "steppe", "mediterranean"]:
		_check(_params(b, day, CLEAR, "high")["heat_haze"] == 0.0, "%s : pas de brume de chaleur" % b)
	_check(AtmosphereModel.heat_hour_factor(10.0) == 0.0 and AtmosphereModel.heat_hour_factor(15.0) == 1.0
		and AtmosphereModel.heat_hour_factor(21.0) == 0.0, "brume de chaleur l'après-midi seulement (10 h, 15 h, 21 h)")
	_check(AtmosphereModel.heat_hour_factor(NAN) == 1.0, "heure inconnue : brume pleine")


func _test_humidity_and_polar() -> void:
	var day := AtmosphereModel.daylight_from_theme(_theme, 2.0)
	var jungle := _params("jungle", day, CLEAR, "high")
	_check(jungle["humidity"] == 1.0 and is_equal_approx(jungle["fog_end_factor"], 0.6)
		and is_equal_approx(jungle["light_energy_factor"], 0.75),
		"jungle : air lourd (brouillard à 60 %, soleil à 75 %)")
	var wet := _params("wetland", day, CLEAR, "high")
	_check(wet["humidity"] > 0.0 and wet["humidity"] < 1.0, "zone humide : humidité %.2f" % wet["humidity"])
	_check(_params("alpine", day, CLEAR, "high")["fog_end_factor"] == 1.0, "montagne : ciel net, brouillard non rapproché")

	var north := AtmosphereModel.daylight_from_theme(_theme, 75.0)
	var polar := _params("polar", north, CLEAR, "high")
	_check(polar["sun_elevation_deg"] <= AtmosphereModel.POLAR_MAX_SUN_DEG,
		"75° N : soleil rasant (%.0f°)" % polar["sun_elevation_deg"])
	var mid := _params("polar", AtmosphereModel.daylight_from_theme(_theme, 48.0), CLEAR, "high")
	_check(is_equal_approx(mid["sun_elevation_deg"], 40.0), "48° N : soleil du thème, même en biome polaire")
	_check(polar["light_tint"].b > polar["light_tint"].r and polar["light_tint"].r < mid["light_tint"].r,
		"75° N : lumière plus froide")
	_check(polar["sun_direction"].y < mid["sun_direction"].y, "75° N : direction du soleil plus basse")
	var unknown := _params("polar", AtmosphereModel.daylight_from_theme(_theme), CLEAR, "high")
	_check(is_equal_approx(unknown["sun_elevation_deg"], 40.0), "latitude inconnue : soleil du thème")


func _test_cost() -> void:
	var atmo := _ramp()
	var day := AtmosphereModel.daylight_from_theme(_theme, 30.0)
	atmo.at(500.0, day, CLEAR, "high")
	var t0 := Time.get_ticks_usec()
	for i in range(1000):
		atmo.at(500.0 + i * 0.1, day, CLEAR, "high")
	var ms := (Time.get_ticks_usec() - t0) / 1000.0 / 1000.0
	_check(PerfBudget.check("atmosphere_at", ms), "coût de at (cache chaud) : %.4f ms" % ms)


func _init() -> void:
	_theme = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	_test_grassland_unchanged()
	_test_transition()
	_test_heat_haze()
	_test_humidity_and_polar()
	_test_cost()
	print("test_atmosphere_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
