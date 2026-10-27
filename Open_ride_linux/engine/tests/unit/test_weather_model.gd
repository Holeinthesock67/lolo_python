extends SceneTree

## Tests unitaires sans écran du modèle de météo `weather_model.gd` (Lot P8).
## Lancement : godot --headless --path engine --script res://tests/unit/test_weather_model.gd

const WeatherModel := preload("res://scripts/weather_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const CALM := {"dir": Vector3.ZERO, "strength": 0.0}

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _theme(weather: Dictionary) -> Dictionary:
	return {"version": "1.2", "terrain": {"snow_line_m": 1800}, "weather": weather}


# Critère 2 : brume de vallée
func _test_valley_mist() -> void:
	var w := WeatherModel.from_theme(_theme({"kind": "clear", "intensity": 0.0, "morning_mist": true}))
	var below := WeatherModel.evaluate(w, 300.0, 500.0, CALM)
	var above := WeatherModel.evaluate(w, 700.0, 500.0, CALM)
	_check(below["fog_boost"] > above["fog_boost"],
		"brume plus forte 200 m sous la vallée (%.2f) que 200 m au-dessus (%.2f)" % [below["fog_boost"], above["fog_boost"]])
	_check(is_equal_approx(below["fog_height_m"], 500.0 + WeatherModel.MIST_LAYER_M), "sommet de la nappe au-dessus de la vallée")
	var same := true
	for i in range(10):
		same = same and is_equal_approx(WeatherModel.evaluate(w, 300.0, 500.0, CALM)["fog_boost"], below["fog_boost"])
	_check(same, "sans heure solaire : brume constante dans le temps")
	var at6: float = WeatherModel.evaluate(w, 300.0, 500.0, CALM, 6.0)["fog_boost"]
	var at8: float = WeatherModel.evaluate(w, 300.0, 500.0, CALM, 8.0)["fog_boost"]
	var at11: float = WeatherModel.evaluate(w, 300.0, 500.0, CALM, 11.0)["fog_boost"]
	var best := 0.0
	for h in range(0, 24):
		best = maxf(best, WeatherModel.evaluate(w, 300.0, 500.0, CALM, float(h))["fog_boost"])
	_check(is_equal_approx(at6, best) and at6 > at8 and at8 > 0.0 and at11 == 0.0,
		"avec l'heure solaire : maximale à 6 h (%.2f), %.2f à 8 h, nulle à 11 h" % [at6, at8])
	var no_mist := WeatherModel.from_theme(_theme({"kind": "clear", "morning_mist": false}))
	_check(WeatherModel.evaluate(no_mist, 300.0, 500.0, CALM)["fog_boost"] == 0.0, "sans brume du matin : rien")
	var mist := WeatherModel.from_theme(_theme({"kind": "mist", "intensity": 0.8}))
	_check(WeatherModel.evaluate(mist, 900.0, 500.0, CALM)["fog_boost"] > 0.3, "brume générale aussi au-dessus de la vallée")


# Critère 3 : pluie et neige jamais ensemble, neige au-dessus de la limite
func _test_rain_snow() -> void:
	var rain := WeatherModel.from_theme(_theme({"kind": "rain", "intensity": 0.5}))
	var low := WeatherModel.evaluate(rain, 600.0, 600.0, CALM)
	var high := WeatherModel.evaluate(rain, 1900.0, 1900.0, CALM)
	_check(is_equal_approx(low["rain"], 0.5) and low["snow"] == 0.0, "pluie sous la limite de la neige")
	_check(is_equal_approx(high["snow"], 0.5) and high["rain"] == 0.0, "neige au-dessus de snow_line_m (1 800 m)")
	_check(low["wetness"] > 0.5 and high["wetness"] == 0.0, "route mouillée sous la pluie seulement")
	var snow := WeatherModel.from_theme(_theme({"kind": "snow", "intensity": 1.0}))
	var ok := true
	for alt in [0.0, 500.0, 1799.0, 1801.0, 4000.0]:
		for w in [rain, snow]:
			var e := WeatherModel.evaluate(w, alt, alt, CALM)
			ok = ok and not (e["rain"] > 0.0 and e["snow"] > 0.0)
	_check(ok, "pluie et neige jamais ensemble")
	var odd := WeatherModel.from_theme(_theme({"kind": "orage", "intensity": 7}))
	_check(odd["kind"] == "clear" and is_equal_approx(odd["intensity"], 1.0), "type inconnu : clair ; intensité bornée")


# Critère 6 : thème sans `weather`
func _test_no_weather() -> void:
	var w := WeatherModel.from_theme({"version": "1.0"})
	var e := WeatherModel.evaluate(w, 200.0, 800.0, CALM, 6.0)
	_check(e["fog_boost"] == 0.0 and e["rain"] == 0.0 and e["snow"] == 0.0 and e["wetness"] == 0.0,
		"thème sans weather : aucun effet")
	var tl = ThemeLoader.new()
	var dflt := WeatherModel.from_theme(tl.load_named("default")["theme"])
	var ed := WeatherModel.evaluate(dflt, 200.0, 800.0, CALM)
	_check(dflt["kind"] == "clear" and ed["rain"] == 0.0 and ed["fog_boost"] == 0.0, "thème par défaut : temps clair")


func _test_cost() -> void:
	var w := WeatherModel.from_theme(_theme({"kind": "rain", "intensity": 0.5, "morning_mist": true}))
	var t0 := Time.get_ticks_usec()
	for i in range(10000):
		WeatherModel.evaluate(w, 400.0 + i * 0.01, 500.0, CALM)
	var ms := (Time.get_ticks_usec() - t0) / 1000.0 / 10000.0
	_check(PerfBudget.check("weather_evaluate", ms), "coût de evaluate : %.4f ms par image" % ms)


func _init() -> void:
	_test_valley_mist()
	_test_rain_snow()
	_test_no_weather()
	_test_cost()
	print("test_weather_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
