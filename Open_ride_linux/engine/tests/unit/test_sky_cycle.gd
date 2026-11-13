extends SceneTree

## Tests unitaires sans écran du jour, de la nuit et des saisons de la séance (lot P19) : `sky_cycle.gd` (deux
## réglages du menu, coupables séparément) et leur application au soleil, à la lumière ambiante et au ciel par
## `atmosphere_view.gd`.
## Lancement : godot --headless --path engine --script res://tests/unit/test_sky_cycle.gd

const DaylightModel := preload("res://scripts/daylight_model.gd")
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
	var acc := SkyCycle.evaluate("accelerated", "off", _theme, 45.0, NAN, JUNE_21, _accel_s(0.0))
	_check(is_equal_approx(fposmod(acc["daylight"]["solar_hour"] + 12.0, 24.0), 12.0), "journée accélérée : minuit (%.2f h)" % acc["daylight"]["solar_hour"])
	# 13 novembre : la nuit (soleil sous −6°) ne dure que le quart du jour, et le cycle reste d'une heure
	var nov := {"year": 2026, "month": 11, "day": 13}
	var night_s := 0.0
	var day_s := 0.0
	for i in range(3600):
		var e: Dictionary = SkyCycle.evaluate("accelerated", "off", _theme, 48.9, NAN, nov, float(i))["daylight"]
		if float(e["sun_elevation_deg"]) < DaylightModel.NIGHT_DEG:
			night_s += 1.0
		else:
			day_s += 1.0
	_check(absf(night_s - 720.0) < 20.0 and absf(day_s - 2880.0) < 20.0,
		"journée accélérée de novembre : 12 min de nuit, 48 min de jour (%d s / %d s)" % [night_s, day_s])
	var back: Dictionary = SkyCycle.evaluate("accelerated", "off", _theme, 48.9, NAN, nov, 3600.0)["daylight"]
	_check(is_equal_approx(back["solar_hour"], SkyCycle.ACCEL_START_HOUR) and int(back["day_of_year"]) == DaylightModel.day_of_year(2026, 11, 13) + 1,
		"journée accélérée : 6 h du lendemain après une heure (%.2f h)" % back["solar_hour"])
	var polar: Dictionary = SkyCycle.evaluate("accelerated", "off", _theme, 80.0, NAN, JUNE_21, 900.0)["daylight"]
	_check(is_equal_approx(polar["solar_hour"], 12.0), "jour polaire : allure constante (%.2f h)" % polar["solar_hour"])
	var th := SkyCycle.evaluate("theme", "theme", _theme, 45.0, NAN, JUNE_21, 600.0)
	_check(th["daylight"]["active"] and is_equal_approx(th["daylight"]["solar_hour"], 14.0), "heure du thème : 14 h fixe")
	_check(th["season"]["season"] == "summer", "saison du thème par défaut : été")
	var no_tod := SkyCycle.evaluate("theme", "theme", {"sky": {}}, 45.0, NAN, JUNE_21, 0.0)
	_check(not no_tod["daylight"]["active"] and no_tod["season"]["season"] == "summer", "thème sans heure ni saison : soleil fixe, été")
	var date := SkyCycle.evaluate("off", "date", _theme, 45.0, NAN, OCT_15, 0.0)
	_check(date["season"]["season"] == "autumn", "selon la date : 15 octobre, automne")
	var south := SkyCycle.evaluate("off", "date", _theme, -35.0, NAN, OCT_15, 0.0)
	_check(south["season"]["season"] == "spring", "selon la date au sud : printemps")
	# Lot U13 : sans poids, biome par défaut du thème (prairie) = P18, chaque jour ; avec poids, saisons des biomes
	var diffs := 0
	for m in range(1, 13):
		for d in [1, 10, 20, 28]:
			var a := SkyCycle.season_state("date", _theme, m, d, 45.0)
			var b := SeasonModel.params(SeasonModel.season_for({}, m, d, 45.0)["season"], SeasonModel.season_for({}, m, d, 45.0)["progress"])
			for k in SeasonModel.NEUTRAL.keys():
				if str(a["params"][k]) != str(b[k]):
					diffs += 1
	_check(diffs == 0, "selon la date, sans poids : paramètres de P18 (%d écarts)" % diffs)
	var sav := SkyCycle.season_state("date", _theme, 7, 15, 12.0, {"savanna": 1.0})
	_check(sav["season"] == "wet" and float(sav["params"]["ground_wet"]) > 0.5, "savane, 15 juillet, 12° : saison des pluies")
	var mix := SkyCycle.season_state("date", _theme, 7, 15, 12.0, {"savanna": 0.25, "sand_desert": 0.75})
	_check(mix["season"] == "none" and is_equal_approx(float(mix["params"]["ground_wet"]), float(sav["params"]["ground_wet"]) * 0.25),
		"savane 25 %, désert 75 % : saison du désert, sol détrempé au quart")
	var forced := SkyCycle.season_state("winter", _theme, 7, 15, 12.0, {"savanna": 1.0})
	_check(forced["season"] == "winter", "saison imposée par le réglage : tous les biomes")
	var snowy := SkyCycle.season_state("winter", {"weather": {"kind": "snow"}}, 1, 10, 45.0)
	_check(float(snowy["params"]["snow_drop_m"]) > 10000.0, "hiver d'un thème neigeux : neige partout")
	var real := SkyCycle.evaluate("real", "off", _theme, 45.0, 15.0, JUNE_21, 0.0, {"hour": 22, "minute": 0, "second": 0, "bias": 60})
	_check(is_equal_approx(real["daylight"]["solar_hour"], 22.0) and real["daylight"]["sun_elevation_deg"] < 0.0,
			"heure du PC : 22 h, soleil couché")


## Secondes de journée accélérée (départ à 6 h, 45°, 21 juin) pour arriver à l'heure solaire `h`.
func _accel_s(h: float) -> float:
	var half := DaylightModel.half_day_hours(45.0, DaylightModel.day_of_year(2026, 6, 21))
	var share := SkyCycle.ACCEL_NIGHT_SHARE
	var u := fposmod(DaylightModel.accel_phase(h, half, share) - DaylightModel.accel_phase(SkyCycle.ACCEL_START_HOUR, half, share), 1.0)
	return u * 3600.0


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
	var night: Dictionary = SkyCycle.evaluate("accelerated", "off", _theme, 45.0, NAN, JUNE_21, _accel_s(1.0))["daylight"]
	view.set_cycle(night)
	_check(sun.light_energy < day_energy * 0.25, "nuit : soleil remplacé par la lune, faible (%.3f)" % sun.light_energy)
	_check(env.ambient_light_sky_contribution < 0.2 and env.ambient_light_color.get_luminance() > 0.0,
			"nuit : lumière ambiante de la nuit, route lisible")
	_check((env.sky.sky_material as PhysicalSkyMaterial).night_sky != null, "nuit : ciel étoilé")
	var noon: Dictionary = SkyCycle.evaluate("accelerated", "off", _theme, 45.0, NAN, JUNE_21, _accel_s(12.0))["daylight"]
	view.set_cycle(noon)
	_check(is_equal_approx(sun.light_energy, day_energy) and env.ambient_light_sky_contribution > 0.95
			and (env.sky.sky_material as PhysicalSkyMaterial).night_sky == null, "midi : lumière du thème, pas d'étoiles")
	_check(not sun.basis.is_equal_approx(day_basis), "midi du 21 juin : soleil plus haut que celui du thème")
	view.set_cycle({})
	_check(is_equal_approx(sun.light_energy, day_energy) and sun.basis.is_equal_approx(day_basis)
			and is_equal_approx(env.ambient_light_sky_contribution, 1.0), "réglage coupé : soleil et lumière d'aujourd'hui")
	var dusk: Dictionary = SkyCycle.evaluate("accelerated", "off", _theme, 45.0, NAN, JUNE_21, _accel_s(19.6))["daylight"]
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
