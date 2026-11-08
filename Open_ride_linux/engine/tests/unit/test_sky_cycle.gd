extends SceneTree

## Tests unitaires sans écran du jour, de la nuit et des saisons de la séance (lot P19) : `sky_cycle.gd` (deux
## réglages du menu, coupables séparément) et leur application au soleil, à la lumière ambiante et au ciel par
## `atmosphere_view.gd`.
## Lancement : godot --headless --path engine --script res://tests/unit/test_sky_cycle.gd

const SkyCycle := preload("res://scripts/sky_cycle.gd")
const SeasonModel := preload("res://scripts/season_model.gd")
const AtmosphereView := preload("res://scripts/atmosphere_view.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")

const JUNE_21 := {"year": 2026, "month": 6, "day": 21}
const OCT_15 := {"year": 2026, "month": 10, "day": 15}

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


func _test_modes() -> void:
	var off := SkyCycle.evaluate("off", "off", _theme, 45.0, 7.0, JUNE_21, 0.0)
	_check(not off["daylight"]["active"] and not off["season"]["active"], "réglages coupés : rien d'actif")
	var sky := ThemeRenderParams.sky_params(_theme)
	_check(is_equal_approx(off["daylight"]["sun_elevation_deg"], sky["sun_elevation_deg"]), "jour et nuit coupé : soleil du thème")
	var day_only := SkyCycle.evaluate("accelerated", "off", _theme, 45.0, 7.0, JUNE_21, 0.0)
	_check(day_only["daylight"]["active"] and not day_only["season"]["active"], "jour et nuit seul : saisons coupées")
	var season_only := SkyCycle.evaluate("off", "winter", _theme, 45.0, 7.0, JUNE_21, 0.0)
	_check(not season_only["daylight"]["active"] and season_only["season"]["active"]
			and season_only["season"]["season"] == "winter", "saisons seules : jour et nuit coupé")
	var acc0 := SkyCycle.evaluate("accelerated", "off", _theme, 45.0, NAN, JUNE_21, 0.0)
	_check(is_equal_approx(acc0["daylight"]["solar_hour"], SkyCycle.ACCEL_START_HOUR), "journée accélérée : départ à 6 h")
	var acc := SkyCycle.evaluate("accelerated", "off", _theme, 45.0, NAN, JUNE_21, 45.0 * 60.0)
	_check(is_equal_approx(fposmod(acc["daylight"]["solar_hour"] + 12.0, 24.0), 12.0), "journée accélérée : minuit après 18 h de journée, 45 min (%.2f h)" % acc["daylight"]["solar_hour"])
	var th := SkyCycle.evaluate("theme", "theme", _theme, 45.0, NAN, JUNE_21, 600.0)
	_check(th["daylight"]["active"] and is_equal_approx(th["daylight"]["solar_hour"], 14.0), "heure du thème : 14 h fixe")
	_check(th["season"]["season"] == "summer", "saison du thème par défaut : été")
	var no_tod := SkyCycle.evaluate("theme", "theme", {"sky": {}}, 45.0, NAN, JUNE_21, 0.0)
	_check(not no_tod["daylight"]["active"] and no_tod["season"]["season"] == "summer", "thème sans heure ni saison : soleil fixe, été")
	var date := SkyCycle.evaluate("off", "date", _theme, 45.0, NAN, OCT_15, 0.0)
	_check(date["season"]["season"] == "autumn", "selon la date : 15 octobre, automne")
	var south := SkyCycle.evaluate("off", "date", _theme, -35.0, NAN, OCT_15, 0.0)
	_check(south["season"]["season"] == "spring", "selon la date au sud : printemps")
	var snowy := SkyCycle.season_state("winter", {"weather": {"kind": "snow"}}, 1, 10, 45.0)
	_check(float(snowy["params"]["snow_drop_m"]) > 10000.0, "hiver d'un thème neigeux : neige partout")
	var real := SkyCycle.evaluate("real", "off", _theme, 45.0, 15.0, JUNE_21, 0.0, {"hour": 22, "minute": 0, "second": 0, "bias": 60})
	_check(is_equal_approx(real["daylight"]["solar_hour"], 22.0) and real["daylight"]["sun_elevation_deg"] < 0.0,
			"heure du PC : 22 h, soleil couché")


func _test_view() -> void:
	var env := Environment.new()
	env.ambient_light_sky_contribution = 1.0
	env.sky = Sky.new()
	env.sky.sky_material = PhysicalSkyMaterial.new()
	var sun := DirectionalLight3D.new()
	root.add_child(sun)
	var view = AtmosphereView.new()
	root.add_child(view)
	view.setup(env, sun)
	view.set_world(_theme, null, null, false)
	var day_energy: float = sun.light_energy
	var day_basis: Basis = sun.basis
	var night: Dictionary = SkyCycle.evaluate("accelerated", "off", _theme, 45.0, NAN, JUNE_21, 3600.0 * 19.0 / 24.0)["daylight"]
	view.set_cycle(night)
	_check(sun.light_energy < day_energy * 0.25, "nuit : soleil remplacé par la lune, faible (%.3f)" % sun.light_energy)
	_check(env.ambient_light_sky_contribution < 0.2 and env.ambient_light_color.get_luminance() > 0.0,
			"nuit : lumière ambiante de la nuit, route lisible")
	_check((env.sky.sky_material as PhysicalSkyMaterial).night_sky != null, "nuit : ciel étoilé")
	var noon: Dictionary = SkyCycle.evaluate("accelerated", "off", _theme, 45.0, NAN, JUNE_21, 3600.0 * 6.0 / 24.0)["daylight"]
	view.set_cycle(noon)
	_check(is_equal_approx(sun.light_energy, day_energy) and env.ambient_light_sky_contribution > 0.95
			and (env.sky.sky_material as PhysicalSkyMaterial).night_sky == null, "midi : lumière du thème, pas d'étoiles")
	_check(not sun.basis.is_equal_approx(day_basis), "midi du 21 juin : soleil plus haut que celui du thème")
	view.set_cycle({})
	_check(is_equal_approx(sun.light_energy, day_energy) and sun.basis.is_equal_approx(day_basis)
			and is_equal_approx(env.ambient_light_sky_contribution, 1.0), "réglage coupé : soleil et lumière d'aujourd'hui")
	var dusk: Dictionary = SkyCycle.evaluate("accelerated", "off", _theme, 45.0, NAN, JUNE_21, 3600.0 * 13.6 / 24.0)["daylight"]
	view.set_cycle(dusk)
	_check(sun.light_color.b < sun.light_color.r * 0.8, "crépuscule : soleil orangé (%s)" % sun.light_color)
	view.queue_free()
	sun.queue_free()


func _init() -> void:
	_theme = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	_test_modes()
	_test_view()
	print("test_sky_cycle : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
