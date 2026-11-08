extends SceneTree

## Tests unitaires sans écran des saisons `season_model.gd` (lot P18, critères 2, 3 et 5 du cahier §7).
## Lancement : godot --headless --path engine --script res://tests/unit/test_season_model.gd

const SeasonModel := preload("res://scripts/season_model.gd")
const WeatherParticles := preload("res://scripts/weather_particles.gd")
const AmbienceModel := preload("res://scripts/ambience_model.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _test_season_for() -> void:
	var s := SeasonModel.season_for({}, 10, 15, 45.0)
	_check(s["season"] == "autumn", "15 octobre, 45° : automne (%s)" % s["season"])
	_check(absf(float(s["progress"]) - 0.49) < 0.03, "15 octobre : milieu de l'automne (%.3f)" % s["progress"])
	s = SeasonModel.season_for({}, 10, 15, -35.0)
	_check(s["season"] == "spring", "15 octobre, −35° : printemps (%s)" % s["season"])
	_check(SeasonModel.season_for({}, 1, 10, 45.0)["season"] == "winter", "10 janvier : hiver")
	_check(SeasonModel.season_for({}, 7, 1, 45.0)["season"] == "summer", "1er juillet : été")
	_check(SeasonModel.season_for({}, 7, 1, -12.0)["season"] == "winter", "1er juillet au sud : hiver")
	var dec1 := SeasonModel.season_for({}, 12, 1, 45.0)
	var feb28 := SeasonModel.season_for({}, 2, 28, 45.0)
	_check(dec1["season"] == "winter" and float(dec1["progress"]) < 0.02 and float(feb28["progress"]) > 0.98,
			"hiver : du 1er décembre (%.3f) au 28 février (%.3f)" % [dec1["progress"], feb28["progress"]])
	_check(SeasonModel.season_for({"season": "winter"}, 7, 1, 45.0)["season"] == "winter", "saison du thème : l'emporte")
	_check(SeasonModel.season_for({"season": "monsoon"}, 7, 1, 45.0)["season"] == "summer", "saison inconnue du thème : la date")


func _test_summer_neutral() -> void:
	var neutral := true
	for i in range(0, 101):
		var p := SeasonModel.params("summer", i / 100.0)
		for k in SeasonModel.NEUTRAL.keys():
			var v: Variant = p[k]
			var n: Variant = SeasonModel.NEUTRAL[k]
			if typeof(n) == TYPE_COLOR:
				if not (v as Color).is_equal_approx(n):
					neutral = false
			elif not is_equal_approx(float(v), float(n)):
				neutral = false
	_check(neutral, "été : tous les paramètres neutres (rendu d'aujourd'hui)")
	var g := SeasonModel.globals(SeasonModel.params("summer"))
	var defaults := {}
	for name in SeasonModel.GLOBALS.keys():
		defaults[name] = ProjectSettings.get_setting("shader_globals/" + name, {}).get("value", null)
	var same := true
	for name in g.keys():
		if defaults[name] == null or not is_equal_approx(float(g[name].x if g[name] is Vector3 else g[name]),
				float(defaults[name].x if defaults[name] is Vector3 else defaults[name])):
			same = false
	_check(same, "paramètres globaux de project.godot = été")


func _test_seasons() -> void:
	var au := SeasonModel.params("autumn", 0.5)
	_check(au["autumn"] > 0.9 and au["falling_leaves"] > 0.9 and au["bare"] < 0.3, "milieu de l'automne : feuillage d'automne, feuilles qui tombent")
	var wi := SeasonModel.params("winter", 0.5)
	_check(wi["bare"] > 0.99 and wi["autumn"] < 0.5 and wi["falling_leaves"] == 0.0, "hiver : feuillus dénudés, plus de feuilles qui tombent")
	_check(wi["snow_drop_m"] > 600.0 and wi["grass_dry"] > 0.5, "hiver : neige plus bas, herbe jaunie")
	_check(SeasonModel.params("winter", 0.5, true)["snow_drop_m"] > 10000.0, "hiver enneigé : neige partout")
	_check(wi["insects"] == 0.0 and wi["birds"] < 0.5 and wi["cloud_altitude"] < 1.0, "hiver : sans insectes, oiseaux rares, ciel plus bas")
	var sp := SeasonModel.params("spring", 0.5)
	_check(sp["blossom"] > 0.9 and sp["bare"] == 0.0 and (sp["leaf_tint"] as Color).g > 1.05, "printemps : vergers en fleurs, vert tendre")
	_check(SeasonModel.params("autumn", 0.5)["falling_leaves"] > 0.0 and SeasonModel.params("spring", 0.5)["falling_leaves"] == 0.0,
			"feuilles qui tombent : seulement en automne")


## Critère 5 : aucune variation de plus de 5 % entre deux avancements distants de 0,01, sur toute l'année.
func _test_continuity() -> void:
	var max_step := 0.0
	var worst := ""
	var prev := SeasonModel.params("spring", 0.0)
	for i in range(1, 401):
		var y := i / 100.0
		var season: String = SeasonModel.SEASONS[mini(int(floor(y)), 3)] if i < 400 else "spring"
		var progress: float = y - floor(y) if i < 400 else 0.0
		var cur := SeasonModel.params(season, progress)
		for k in SeasonModel.NEUTRAL.keys():
			var step := 0.0
			if typeof(cur[k]) == TYPE_COLOR:
				var a: Color = cur[k]
				var b: Color = prev[k]
				step = maxf(absf(a.r - b.r), maxf(absf(a.g - b.g), absf(a.b - b.b)))
			elif k == "snow_drop_m":
				step = absf(float(cur[k]) - float(prev[k])) / SeasonModel.SNOW_DROP_M
			else:
				step = absf(float(cur[k]) - float(prev[k]))
			if step > max_step:
				max_step = step
				worst = "%s à %.2f" % [k, y]
		prev = cur
	_check(max_step <= 0.05, "année entière au pas de 0,01 : plus grand pas %.4f (%s), ≤ 5 %%" % [max_step, worst])


## Branchements de P18 : feuilles qui tombent, sons, neige du terrain (fonction de référence du shader).
func _test_hooks() -> void:
	var fall := float(SeasonModel.params("autumn", 0.5)["falling_leaves"])
	_check(WeatherParticles.leaves_intensity(fall, 5.0) > 0.9, "feuilles : pleines à 5 m d'une forêt en automne")
	_check(WeatherParticles.leaves_intensity(fall, 31.0) == 0.0, "feuilles : aucune au-delà de 30 m d'une forêt")
	_check(WeatherParticles.leaves_intensity(float(SeasonModel.params("summer")["falling_leaves"]), 0.0) == 0.0, "feuilles : aucune l'été")
	for budget in [16, 100, 400, 1200]:
		var used := WeatherParticles.dust_amount(budget) + WeatherParticles.leaves_amount(budget) \
				+ maxi(budget - WeatherParticles.dust_amount(budget) - WeatherParticles.leaves_amount(budget), 1)
		_check(used <= budget, "budget %d : pluie ou neige, poussière et feuilles dessous (%d)" % [budget, used])
	var amb = AmbienceModel.new()
	var neigh := {"forest_share": 0.5, "built_share": 0.0, "solar_hour": 12.0}
	var summer: Dictionary = amb.targets(neigh)
	amb.set_season(SeasonModel.params("winter"))
	var winter: Dictionary = amb.targets(neigh)
	_check(float(winter["field_insects"]) == AmbienceModel.SILENCE_DB and float(winter["forest_birds"]) < float(summer["forest_birds"]) - 6.0,
			"sons : pas d'insectes l'hiver, oiseaux plus rares (%.1f dB contre %.1f)" % [winter["forest_birds"], summer["forest_birds"]])
	amb.set_season(SeasonModel.params("summer"))
	_check(is_equal_approx(float(amb.targets(neigh)["field_insects"]), float(summer["field_insects"])), "sons : été inchangé")
	var flat := Vector3.UP
	var w_summer := ThemeRenderParams.blend_weights(flat, 1500.0, {})
	var w_winter := ThemeRenderParams.blend_weights(flat, 1500.0, {"season_snow_drop_m": SeasonModel.params("winter")["snow_drop_m"]})
	_check(w_summer.z < 0.01 and w_winter.z > 0.99, "neige à 1 500 m seulement l'hiver (référence du shader)")


func _init() -> void:
	_test_season_for()
	_test_summer_neutral()
	_test_seasons()
	_test_continuity()
	_test_hooks()
	print("test_season_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
