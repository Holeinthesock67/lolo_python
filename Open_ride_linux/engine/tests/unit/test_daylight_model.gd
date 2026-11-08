extends SceneTree

## Tests unitaires sans écran du jour et de la nuit `daylight_model.gd` (lot P7, critères du cahier §7).
## Lancement : godot --headless --path engine --script res://tests/unit/test_daylight_model.gd
## Latitudes de test rondes (45°, 60°, 0°, −35°) : aucune coordonnée réelle.

const DaylightModel := preload("res://scripts/daylight_model.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const JUNE_21 := 172
const DEC_21 := 355
const MARCH_21 := 80

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _near(a: float, b: float, tol: float) -> bool:
	return absf(a - b) <= tol


## Critère 2 : position du soleil.
func _test_sun_position() -> void:
	_check(DaylightModel.day_of_year(2026, 6, 21) == JUNE_21, "21 juin = jour 172")
	_check(DaylightModel.day_of_year(2028, 3, 1) == 61, "année bissextile : 1er mars = jour 61")
	var p := DaylightModel.sun_position(45.0, JUNE_21, 12.0)
	_check(_near(p["elevation_deg"], 68.4, 1.0), "45°, 21 juin, midi : élévation %.2f° (68,4 ± 1)" % p["elevation_deg"])
	_check(_near(p["azimuth_deg"], 180.0, 2.0), "45°, 21 juin, midi : azimut %.2f° (180 ± 2)" % p["azimuth_deg"])
	p = DaylightModel.sun_position(45.0, DEC_21, 12.0)
	_check(_near(p["elevation_deg"], 21.6, 1.0), "45°, 21 décembre, midi : élévation %.2f° (21,6 ± 1)" % p["elevation_deg"])
	p = DaylightModel.sun_position(45.0, MARCH_21, 6.0)
	_check(_near(p["elevation_deg"], 0.0, 1.5), "équinoxe, 6 h : élévation %.2f° (0 ± 1,5)" % p["elevation_deg"])
	_check(_near(p["azimuth_deg"], 90.0, 3.0), "équinoxe, 6 h : azimut %.2f° (90 ± 3)" % p["azimuth_deg"])
	p = DaylightModel.sun_position(45.0, MARCH_21, 18.0)
	_check(_near(p["azimuth_deg"], 270.0, 3.0), "équinoxe, 18 h : soleil à l'ouest (%.1f°)" % p["azimuth_deg"])
	p = DaylightModel.sun_position(-35.0, JUNE_21, 12.0)
	_check(p["azimuth_deg"] < 5.0 or p["azimuth_deg"] > 355.0, "hémisphère sud, midi : soleil au nord (%.1f°)" % p["azimuth_deg"])
	p = DaylightModel.sun_position(0.0, MARCH_21, 12.0)
	_check(p["elevation_deg"] > 88.0, "équateur, équinoxe, midi : soleil presque au zénith (%.1f°)" % p["elevation_deg"])
	p = DaylightModel.sun_position(60.0, JUNE_21, 0.0)
	_check(p["elevation_deg"] < 0.0 and p["elevation_deg"] > -8.0, "60°, 21 juin, minuit : nuit claire, soleil juste sous l'horizon (%.1f°)" % p["elevation_deg"])
	var d := DaylightModel.direction(40.0, ThemeRenderParams.SUN_AZIMUTH_DEG)
	var ref: Vector3 = ThemeRenderParams.sky_params({})["sun_direction"]
	_check(d.distance_to(ref) < 1e-5, "direction : même convention que sky_params")


## Critère 3 : coucher orangé, aucune marche entre paliers.
func _test_light() -> void:
	var prev_blue := INF
	var decreasing := true
	for i in range(0, 201):
		var e := 20.0 - i * 0.1
		var c: Color = DaylightModel.light(e)["sun_color"]
		if c.b > prev_blue + 1e-6:
			decreasing = false
		prev_blue = c.b
	_check(decreasing, "de 20° à 0°, soleil de plus en plus orangé (composante bleue décroissante)")
	_check(DaylightModel.light(0.5)["sun_color"].b < 0.4, "soleil à l'horizon franchement orangé")
	var keys := ["sun_energy", "ambient_energy"]
	var colors := ["sun_color", "ambient_color", "sky_top", "sky_horizon", "fog_color"]
	var max_step := 0.0
	var prev := DaylightModel.light(-25.0, 1.0)
	for i in range(1, 701):
		var cur := DaylightModel.light(-25.0 + i * 0.1, 1.0)
		for k in keys:
			max_step = maxf(max_step, absf(float(cur[k]) - float(prev[k])))
		for k in colors:
			var a: Color = cur[k]
			var b: Color = prev[k]
			max_step = maxf(max_step, maxf(absf(a.r - b.r), maxf(absf(a.g - b.g), absf(a.b - b.b))))
		prev = cur
	_check(max_step <= 0.05, "balayage de −25° à 45° au pas de 0,1° : plus grand pas %.4f (≤ 5 %%)" % max_step)
	var day := DaylightModel.light(40.0)
	_check(day["sun_color"] == Color.WHITE and is_equal_approx(day["sun_energy"], 1.0)
			and day["sky_top"] == Color.WHITE and is_equal_approx(day["ambient_energy"], 1.0),
			"plein jour : multiplicateurs neutres, lumière du thème inchangée")


## Critère 7 : étoiles, lune, lumière minimale.
func _test_night() -> void:
	_check(DaylightModel.stars(0.0) == 0.0 and DaylightModel.stars(10.0) == 0.0, "étoiles : 0 au-dessus de 0°")
	_check(is_equal_approx(DaylightModel.stars(-18.0), 1.0) and is_equal_approx(DaylightModel.stars(-30.0), 1.0),
			"étoiles : 1 sous −18°")
	var growing := true
	var prev := 0.0
	for i in range(1, 181):
		var s := DaylightModel.stars(-i * 0.1)
		if s < prev:
			growing = false
		prev = s
	_check(growing and DaylightModel.stars(-9.0) > 0.0 and DaylightModel.stars(-9.0) < 1.0, "étoiles : croissantes de 0° à −18°")
	var full := DaylightModel.light(-25.0, 1.0, 0.12)
	var new_moon := DaylightModel.light(-25.0, 0.0, 0.12)
	_check(full["ambient_energy"] > new_moon["ambient_energy"] and full["moon_energy"] > new_moon["moon_energy"],
			"pleine lune plus claire que nouvelle lune")
	_check(new_moon["ambient_energy"] >= 0.12 - 1e-6, "nuit noire : lumière ambiante au moins au minimum (%.3f)" % new_moon["ambient_energy"])
	_check(DaylightModel.light(20.0, 1.0)["moon_energy"] == 0.0, "pas de lune de jour")
	# Phases : pleine lune le 21 janvier 2000 (≈ 14,8 jours après la nouvelle lune de référence).
	var ref := DaylightModel.NEW_MOON_UNIX_DAYS
	_check(DaylightModel.moon_illumination(ref) < 0.01, "nouvelle lune de référence : 0")
	_check(DaylightModel.moon_illumination(ref + DaylightModel.SYNODIC_DAYS / 2.0) > 0.99, "demi-lunaison : pleine lune")
	_check(DaylightModel.moon_illumination(ref + 10.0 * DaylightModel.SYNODIC_DAYS) < 0.01, "dix lunaisons plus tard : nouvelle lune")


## Critère 4 : horloge.
func _test_clock() -> void:
	var h := DaylightModel.clock("accelerated", 7.0, 24.0, 1800.0)
	_check(_near(h, 19.0, 1e-4), "accéléré ×24 depuis 7 h : 19 h après 30 min (%.3f)" % h)
	_check(DaylightModel.days_elapsed("accelerated", 7.0, 24.0, 1800.0) == 0, "même jour à 19 h")
	_check(DaylightModel.days_elapsed("accelerated", 7.0, 24.0, 3600.0) == 1, "lendemain 7 h après 1 h à ×24")
	_check(_near(DaylightModel.clock("fixed", 14.0, 24.0, 5000.0), 14.0, 1e-6), "heure fixe : inchangée")
	var now := {"hour": 15, "minute": 30, "second": 0, "bias": 60}
	_check(_near(DaylightModel.clock("real", 0.0, 1.0, 0.0, now), 15.5, 1e-6), "heure du PC sans longitude : heure locale")
	_check(_near(DaylightModel.clock("real", 0.0, 1.0, 0.0, now, 15.0), 15.5, 1e-6),
			"heure du PC : UTC+1 à 15° est = heure solaire égale à l'heure locale")
	_check(_near(DaylightModel.clock("real", 0.0, 1.0, 0.0, now, 0.0), 14.5, 1e-6), "heure du PC : UTC+1 à 0° = une heure de moins")
	_check(DaylightModel.days_elapsed("real", 0.0, 1.0, 1e6) == 0, "jours passés : seulement en accéléré")


## Critère 5 : thème sans `time_of_day`, paramètres du thème.
func _test_theme() -> void:
	var theme := {"sky": {"sun_elevation_deg": 33.0}}
	var tod := ThemeRenderParams.time_of_day_params(theme)
	_check(not tod["present"], "thème sans time_of_day : absent")
	var out := DaylightModel.evaluate(tod, 45.0, 0.0, JUNE_21, 3600.0)
	var sky := ThemeRenderParams.sky_params(theme)
	_check(not out["active"] and is_equal_approx(out["sun_elevation_deg"], 33.0)
			and (out["sun_direction"] as Vector3).is_equal_approx(sky["sun_direction"])
			and out["sun_color"] == Color.WHITE and is_equal_approx(out["sun_energy"], 1.0),
			"thème sans time_of_day : élévation, direction et lumière d'aujourd'hui")
	var default_theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	tod = ThemeRenderParams.time_of_day_params(default_theme)
	_check(tod["present"] and tod["mode"] == "fixed" and is_equal_approx(tod["hour"], 14.0), "thème par défaut : 14 h fixe")
	tod = ThemeRenderParams.time_of_day_params({"sky": {"time_of_day": {"mode": "warp", "hour": 25.0, "factor": 1e6, "min_ambient": 3.0}}})
	_check(tod["mode"] == "fixed" and is_equal_approx(tod["hour"], 1.0)
			and is_equal_approx(tod["factor"], ThemeRenderParams.MAX_TIME_OF_DAY_FACTOR) and is_equal_approx(tod["min_ambient"], 1.0),
			"valeurs hors bornes ramenées (mode inconnu, 25 h, facteur, lumière minimale)")
	tod = ThemeRenderParams.time_of_day_params({"sky": {"time_of_day": {"mode": "accelerated", "hour": 5.0, "factor": 24.0}}})
	var night := DaylightModel.evaluate(tod, 45.0, NAN, JUNE_21, 3600.0 * 20.0 / 24.0, {}, DaylightModel.NEW_MOON_UNIX_DAYS + 14.8)
	_check(night["active"] and night["sun_elevation_deg"] < -6.0 and night["stars"] > 0.3 and night["moon_energy"] > 0.0,
			"accéléré : 1 h du matin, nuit étoilée sous la pleine lune (soleil %.1f°)" % night["sun_elevation_deg"])
	_check((night["moon_direction"] as Vector3).y > sin(deg_to_rad(DaylightModel.MOON_MIN_ELEVATION_DEG)) - 1e-4, "lune assez haute pour éclairer")
	var dusk := DaylightModel.evaluate(tod, 45.0, NAN, JUNE_21, 3600.0 * 14.5 / 24.0)
	_check(dusk["sun_color"].b < 0.7 and dusk["sun_elevation_deg"] > -1.0 and dusk["sun_elevation_deg"] < 10.0,
			"accéléré : 19 h 30 le 21 juin, coucher orangé (soleil %.1f°)" % dusk["sun_elevation_deg"])
	var later := DaylightModel.evaluate(tod, 45.0, NAN, JUNE_21, 3600.0 * 30.0 / 24.0)
	_check(int(later["day_of_year"]) == JUNE_21 + 1, "accéléré : le jour avance après minuit")


## Critère 6 : coût.
func _test_cost() -> void:
	var tod := ThemeRenderParams.time_of_day_params({"sky": {"time_of_day": {"mode": "accelerated", "hour": 5.0, "factor": 24.0}}})
	var n := 2000
	var t0 := Time.get_ticks_usec()
	for i in range(n):
		DaylightModel.evaluate(tod, 45.0, 7.0, JUNE_21, i * 10.0, {}, 20000.0)
	var ms := (Time.get_ticks_usec() - t0) / 1000.0 / n
	_check(PerfBudget.check("daylight_evaluate", ms), "coût de evaluate : %.4f ms" % ms)


func _init() -> void:
	_test_sun_position()
	_test_light()
	_test_night()
	_test_clock()
	_test_theme()
	_test_cost()
	print("test_daylight_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
