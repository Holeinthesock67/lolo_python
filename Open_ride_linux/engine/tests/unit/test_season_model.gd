extends SceneTree

## Tests unitaires sans écran des saisons `season_model.gd` (lot P18, critères 2, 3 et 5 du cahier §7 ;
## calendriers par biome du lot U13, critères 2 à 6).
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


## Lot U13 : calendriers par biome, avec les sections `seasons` du thème par défaut.
func _theme() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string("res://themes/default/theme.json"))


func _test_u13_calendars() -> void:
	var biomes: Dictionary = _theme()["biomes"]
	# Critère 2 : savane, 15 juillet, 12° nord (pluies) et 12° sud (saison sèche)
	var n := SeasonModel.season_for_biome(biomes["savanna"], 7, 15, 12.0)
	var s := SeasonModel.season_for_biome(biomes["savanna"], 7, 15, -12.0)
	_check(n["season"] == "wet" and s["season"] == "dry", "savane, 15 juillet : 12° %s, −12° %s" % [n["season"], s["season"]])
	_check(SeasonModel.season_for_biome(biomes["jungle"], 3, 1, 5.0)["season"] == "dry", "jungle, 1er mars au nord : saison sèche")
	# Critère 3 : taïga à 62°, hiver le 15 février ; le 15 mai encore en hiver si l'hiver dure 6 mois
	_check(SeasonModel.season_for_biome(biomes["boreal_forest"], 2, 15, 62.0)["season"] == "winter", "taïga, 15 février : hiver")
	# Hiver de 6 mois, l'été centré sur le 16 juillet : du 1er novembre au 30 avril (écart au cahier §7.3 :
	# le 15 mai est au printemps, débourrement de la taïga) ; hiver de 6 mois et demi : encore l'hiver le 15 mai.
	var six := {"calendar": "four", "offset_months": 0, "durations_months": [1, 3, 2, 6]}
	_check(SeasonModel.season_for_biome(six, 11, 1, 62.0)["season"] == "winter" and SeasonModel.season_for_biome(six, 4, 30, 62.0)["season"] == "winter"
		and SeasonModel.season_for_biome(six, 10, 31, 62.0)["season"] == "autumn" and SeasonModel.season_for_biome(six, 5, 1, 62.0)["season"] == "spring",
		"hiver de 6 mois : du 1er novembre au 30 avril")
	var longer := {"calendar": "four", "offset_months": 0, "durations_months": [0.5, 3, 2, 6.5]}
	_check(SeasonModel.season_for_biome(longer, 5, 15, 62.0)["season"] == "winter", "hiver de 6 mois et demi : 15 mai, encore l'hiver")
	var taiga_may := SeasonModel.season_for_biome(biomes["boreal_forest"], 5, 15, 62.0)
	_check(taiga_may["season"] == "spring", "taïga du thème (hiver de 5 mois), 15 mai : printemps court (%s)" % taiga_may["season"])
	_check(SeasonModel.season_for_biome(biomes["tundra"], 9, 25, 68.0)["season"] == "winter", "toundra, 25 septembre : déjà l'hiver")
	_check(SeasonModel.season_for_biome(biomes["mediterranean"], 5, 15, 43.0)["season"] == "summer", "méditerranéen, 15 mai : déjà l'été (5 mois)")
	var med := SeasonModel.biome_state(biomes["mediterranean"], 7, 16, 43.0)
	var tg := SeasonModel.biome_state(biomes["temperate_grassland"], 7, 16, 45.0)
	_check(med["season"] == "summer" and float(med["params"]["grass_dry"]) > 0.7 and float(tg["params"]["grass_dry"]) == 0.0,
		"16 juillet : été sec et jaune en méditerranéen (%.2f), prairie neutre" % med["params"]["grass_dry"])
	_check(float(SeasonModel.biome_state(biomes["steppe"], 7, 16, 48.0)["params"]["grass_dry"]) > 0.6, "steppe : été sec")
	var edge_gap := 0.0
	for pr in [[ "spring", 0.995, "summer", 0.005], ["summer", 0.995, "autumn", 0.005]]:
		var a := SeasonModel.params(pr[0], pr[1], false, 0.8)
		var b := SeasonModel.params(pr[2], pr[3], false, 0.8)
		edge_gap = maxf(edge_gap, absf(float(a["grass_dry"]) - float(b["grass_dry"])))
	_check(edge_gap <= 0.05, "été sec : aucune marche avec le printemps et l'automne (%.3f)" % edge_gap)
	# Critère 4 : désert de sable, même saison toute l'année, paramètres neutres
	var seen := {}
	for m in range(1, 13):
		for lat in [25.0, -25.0]:
			seen[SeasonModel.season_for_biome(biomes["sand_desert"], m, 15, lat)["season"]] = true
	_check(seen.keys() == ["none"], "désert de sable : %s toute l'année" % str(seen.keys()))
	var none := SeasonModel.params("none")
	var same := true
	for k in SeasonModel.NEUTRAL.keys():
		same = same and str(none[k]) == str(SeasonModel.NEUTRAL[k])
	_check(same, "saison « none » : paramètres neutres (rendu d'aujourd'hui)")
	# Critère 5 : prairie tempérée = P18, chaque jour de l'année, aux deux hémisphères
	var diff := 0
	var worst := 0.0
	for lat in [45.0, -35.0]:
		for m in range(1, 13):
			for d in range(1, SeasonModel.MONTH_LENGTHS[m - 1] + 1):
				var a := SeasonModel.season_for({}, m, d, lat)
				var b := SeasonModel.season_for_biome(biomes["temperate_grassland"], m, d, lat)
				if a["season"] != b["season"]:
					diff += 1
				worst = maxf(worst, absf(float(a["progress"]) - float(b["progress"])))
	_check(diff == 0 and worst < 0.02, "prairie tempérée : saisons de P18 toute l'année (%d écarts, avancement à %.4f près)" % [diff, worst])
	var nd := 0
	for m in range(1, 13):
		for d in range(1, SeasonModel.MONTH_LENGTHS[m - 1] + 1):
			if not is_equal_approx(float(SeasonModel.season_for({}, m, d, 45.0)["progress"]),
					float(SeasonModel.season_for_biome({}, m, d, 45.0)["progress"])):
				nd += 1
	_check(nd == 0, "hémisphère nord : avancement identique à P18 chaque jour (%d écarts)" % nd)
	# Saison du thème : l'emporte sur tous les calendriers
	_check(SeasonModel.season_for_biome(biomes["savanna"], 7, 15, 12.0, {"season": "winter"})["season"] == "winter",
		"saison du thème : l'emporte sur le calendrier du biome")
	_check(SeasonModel.season_for_biome({"seasons": {"calendar": "four", "offset_months": 1}}, 6, 15, 45.0)["season"] == "spring",
		"décalage d'un mois : 15 juin encore au printemps")


func _test_u13_polar() -> void:
	var biomes: Dictionary = _theme()["biomes"]
	var seq := []
	for m in range(1, 13):
		var s: String = SeasonModel.season_for_biome(biomes["polar"], m, 15, 78.0)["season"]
		if seq.is_empty() or seq[seq.size() - 1] != s:
			seq.append(s)
	_check(seq == ["polar_night", "polar_rise", "polar_day", "polar_set", "polar_night"], "polaire, 78° : %s" % str(seq))
	_check(SeasonModel.season_for_biome(biomes["polar"], 1, 15, -78.0)["season"] == "polar_day", "polaire, 15 janvier, −78° : jour polaire")
	_check(SeasonModel.season_for_biome(biomes["polar"], 6, 21, 48.0)["season"] == "polar_day", "polaire forcé à 48° : soleil de 75°, jour polaire en juin")
	var ok := true
	for y in range(0, 40):
		var name: String = SeasonModel.POLAR[y / 10]
		ok = ok and float(SeasonModel.params(name, (y % 10) / 10.0)["snow_drop_m"]) >= SeasonModel.SNOW_EVERYWHERE_M - 1.0
	_check(ok, "polaire : neige partout toute l'année")
	var day := SeasonModel.params("polar_day", 0.5)
	var night := SeasonModel.params("polar_night", 0.5)
	_check(float(day["birds"]) > float(night["birds"]) and float(night["insects"]) == 0.0, "polaire : oiseaux l'été, aucun insecte la nuit polaire")
	var prog := []
	for d in [1, 10, 20]:
		prog.append(float(SeasonModel.season_for_biome(biomes["polar"], 12, d, 78.0)["progress"]))
	_check(prog[0] < prog[1] and prog[1] < prog[2], "polaire : l'avancement croît dans la nuit polaire (%s)" % str(prog))


func _test_u13_params() -> void:
	var dry := SeasonModel.params("dry", 0.5)
	var wet := SeasonModel.params("wet", 0.5)
	_check(float(dry["grass_dry"]) > 0.7 and (dry["grass_tint"] as Color).r > (dry["grass_tint"] as Color).b, "saison sèche : herbe jaunie")
	var lw: Color = wet["leaf_tint"]
	_check(lw.v < 0.95 and lw.g > lw.r, "saison des pluies : feuillage dense et sombre")
	_check(float(wet["ground_wet"]) > 0.75 and float(dry["ground_wet"]) == 0.0, "saison des pluies : sol détrempé")
	_check(float(dry["snow_drop_m"]) == 0.0 and float(wet["snow_drop_m"]) == 0.0, "saisons sèche et des pluies : pas de neige")
	# Critère 6 : continuité de chaque calendrier sur un cycle complet au pas de 0,01
	for cal in ["wet_dry", "polar"]:
		var names: Array = SeasonModel.CALENDAR_KEYS[cal][0]
		var n := names.size()
		var max_step := 0.0
		var worst := ""
		var prev := SeasonModel.params(names[0], 0.0)
		for i in range(1, n * 100 + 1):
			var idx := mini(i / 100, n - 1) if i < n * 100 else 0
			var progress := (i % 100) / 100.0 if i < n * 100 else 0.0
			if i < n * 100 and i % 100 == 0:
				progress = 0.0
			var cur := SeasonModel.params(names[idx], progress)
			for k in SeasonModel.NEUTRAL.keys():
				var step := 0.0
				if typeof(cur[k]) == TYPE_COLOR:
					var a: Color = cur[k]
					var b: Color = prev[k]
					step = maxf(absf(a.r - b.r), maxf(absf(a.g - b.g), absf(a.b - b.b)))
				elif k == "snow_drop_m":
					step = absf(float(cur[k]) - float(prev[k])) / SeasonModel.SNOW_EVERYWHERE_M
				else:
					step = absf(float(cur[k]) - float(prev[k]))
				if step > max_step:
					max_step = step
					worst = "%s à %s %.2f" % [k, names[idx], progress]
			prev = cur
		_check(max_step <= 0.05, "%s au pas de 0,01 : plus grand pas %.4f (%s), ≤ 5 %%" % [cal, max_step, worst])
	# Mélange : moitié savane en pluies, moitié prairie en été
	var mix := SeasonModel.blend({"savanna": 0.5, "temperate_grassland": 0.5},
		{"savanna": wet, "temperate_grassland": SeasonModel.params("summer")})
	_check(is_equal_approx(float(mix["ground_wet"]), float(wet["ground_wet"]) * 0.5)
		and is_equal_approx((mix["leaf_tint"] as Color).r, (lw.r + 1.0) / 2.0), "mélange : moitié des paramètres de chaque saison")
	_check(SeasonModel.blend({}, {})["season"] == "summer", "mélange vide : neutre")
	var g := SeasonModel.globals(wet)
	_check(is_equal_approx(float(g["season_ground_wet"]), float(wet["ground_wet"])), "paramètre global du sol détrempé")


func _init() -> void:
	_test_season_for()
	_test_summer_neutral()
	_test_seasons()
	_test_continuity()
	_test_hooks()
	_test_u13_calendars()
	_test_u13_polar()
	_test_u13_params()
	print("test_season_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
