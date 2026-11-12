extends SceneTree

## Tests sans écran de la couche biome et du modèle de biome (lot U5, série U).
## Lancement : godot --headless --path engine --script res://tests/unit/test_biome_model.gd

const BiomeIds := preload("res://scripts/biome_ids.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Tuile en dégradé ouest-est entre deux biomes : poids de `b` = 255 × (x_global / 2000) sur deux tuiles.
func _gradient_tile(a: String, b: String, ix: int) -> Dictionary:
	var ga := []
	var gb := []
	for j in range(17):
		for i in range(17):
			var x := ix * 1000.0 + i * 62.5
			var wb := int(round(255.0 * clampf(x / 2000.0, 0.0, 1.0)))
			ga.append(255 - wb)
			gb.append(wb)
	return {"version": "1.0", "biomes": [a, b], "grid": 17, "weights": [ga, gb], "variant": null}


func _flat_tile(ids: Array, values: Array) -> Dictionary:
	var grids := []
	for v in values:
		var g := []
		for p in range(289):
			g.append(v)
		grids.append(g)
	return {"version": "1.0", "biomes": ids, "grid": 17, "weights": grids, "variant": null}


func _layer_with(tiles: Dictionary) -> Object:
	var layer = BiomeLayer.new()
	for key in tiles.keys():
		var errors := PackedStringArray()
		var t := BiomeLayer.parse_tile(tiles[key], errors)
		_check(errors.is_empty(), "tuile %s acceptée" % str(key))
		layer.put_tile("near", key.x, key.y, t)
	return layer


func _init() -> void:
	var default_theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	var theme := ThemeLoader.without_biomes(default_theme)
	theme["version"] = "1.2"

	# Validation légère des tuiles
	var errors := PackedStringArray()
	var bad := _flat_tile(["savanna", "jungle"], [128, 128])
	_check(BiomeLayer.parse_tile(bad, errors).is_empty() and errors[0].contains("256"), "somme 256 refusée : " + errors[0])
	errors.clear()
	_check(BiomeLayer.parse_tile(_flat_tile(["desert"], [255]), errors).is_empty(), "biome inconnu refusé")
	errors.clear()
	var five := _flat_tile(["savanna", "jungle", "polar", "tundra", "coast"], [51, 51, 51, 51, 51])
	_check(BiomeLayer.parse_tile(five, errors).is_empty(), "5 biomes refusés")

	# Lecture sur disque de l'exemple du contrat (tuile proche 0, 0)
	var world := "user://biome_world_test.world"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(world.path_join("biome/near")))
	var example := FileAccess.get_file_as_string("res://../docs/contracts/world/examples/biome_tile_near_3_biomes.json")
	var f := FileAccess.open(world.path_join("biome/near/tile_0_0.json"), FileAccess.WRITE)
	f.store_string(example)
	f.close()
	var disk_layer = BiomeLayer.new(world, {"layers": {"biome": {"present": true, "default_biome": "farmland"}}})
	var disk_tile: Dictionary = disk_layer.tile("near", 0, 0)
	_check(example != "" and disk_tile.get("biomes", []) == ["temperate_grassland", "mediterranean", "coast"], "exemple du contrat lu sur disque")
	_check(disk_layer.tile("near", 5, 5).is_empty(), "tuile absente : {}")
	var disk_model = BiomeModel.new(theme, disk_layer)
	_check(disk_model.weights_at(5200.0, 5200.0) == {"farmland": 1.0}, "hors des tuiles : biome par défaut du manifeste")
	var w00: Dictionary = disk_model.weights_at(0.0, 0.0)
	_check(is_equal_approx(float(w00.get("temperate_grassland", 0.0)), 1.0), "coin ouest : prairie seule")

	# Critère 2 : dégradé 50/50 continu, y compris à travers le bord de tuile x = 1000
	var model = BiomeModel.new(theme, _layer_with({
		Vector2i(0, 0): _gradient_tile("temperate_grassland", "mediterranean", 0),
		Vector2i(1, 0): _gradient_tile("temperate_grassland", "mediterranean", 1),
	}))
	var max_step := 0.0
	var prev := -1.0
	for xi in range(0, 2000):
		var w: Dictionary = model.weights_at(float(xi), 500.0)
		var sum := 0.0
		for v in w.values():
			sum += float(v)
		if absf(sum - 1.0) > 1e-5:
			max_step = 1.0
		var m := float(w.get("mediterranean", 0.0))
		if prev >= 0.0:
			max_step = maxf(max_step, absf(m - prev))
		prev = m
	_check(max_step <= 0.02, "dégradé : marche max %.4f par mètre (≤ 2 %%), somme 1, bord de tuile compris" % max_step)
	var mid: Dictionary = model.weights_at(1000.0, 500.0)
	_check(absf(float(mid["mediterranean"]) - 0.5) < 0.01, "bord des deux tuiles : 50/50")

	# Critère 3 : top_biomes en low sur 4 biomes
	var four = BiomeModel.new(theme, _layer_with({Vector2i(0, 0): _flat_tile(["savanna", "jungle", "steppe", "coast"], [100, 80, 50, 25])}))
	var top3: Dictionary = four.top_biomes(0, 0, QualityPresets.max_biomes("low"))
	var s3 := 0.0
	for v in top3.values():
		s3 += float(v)
	_check(top3.size() == 3 and not top3.has("coast") and is_equal_approx(s3, 1.0), "low : 3 biomes, le plus faible écarté, somme 1")
	_check(four.top_biomes(0, 0, QualityPresets.max_biomes("medium")).size() == 4, "medium : 4 biomes")

	# Critère 4 : forçage
	_check(four.set_forced("savanna") and four.weights_at(123.0, -456.0) == {"savanna": 1.0}, "forçage savanna : poids 1 partout")
	_check(four.top_biomes(0, 0, 3) == {"savanna": 1.0}, "forçage : top_biomes = savanna")
	_check(not four.set_forced("desert") and four.forced == "savanna", "forçage inconnu refusé")
	_check(four.set_forced("auto") and four.weights_at(10.0, 10.0).size() == 4, "auto : retour aux données")
	var args := EngineArgs.parse(PackedStringArray(["--biome=sand_desert"]))
	_check(args["biome"] == "sand_desert", "--biome=sand_desert lu")
	_check(EngineArgs.parse(PackedStringArray(["--biome=lune"]))["biome"] == "auto", "--biome inconnu : auto")
	_check(EngineArgs.parse(PackedStringArray([]))["biome"] == "auto", "sans --biome : auto")

	# Critère 5 : thème 1.x seul -> paramètres d'aujourd'hui pour tous les biomes
	var ref := ThemeRenderParams.terrain_uniforms(theme)
	var same := true
	for id in BiomeIds.BIOMES:
		var p: Dictionary = model.params(id, "summer", 0.5)
		for k in ["grass_color", "rock_color", "snow_color", "cos_slope", "snow_line_m", "blend_sharpness", "grass_inv_scale"]:
			if p["terrain"][k] != ref[k]:
				same = false
		if p["sky"]["fog_density"] != ThemeRenderParams.sky_params(theme)["fog_density"]:
			same = false
		if p["vegetation"]["max_density_per_ha"] != float(theme["vegetation"]["max_density_per_ha"]):
			same = false
	_check(same, "thème 1.x : les 17 biomes ont les paramètres de theme_render_params.gd")

	# Thème 2.0 de l'exemple du contrat : clés du biome, repli 1.x pour le reste
	var v2_dir := "user://theme_v2_test"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(v2_dir))
	var tf := FileAccess.open(v2_dir.path_join("theme.json"), FileAccess.WRITE)
	tf.store_string(FileAccess.get_file_as_string("res://../docs/contracts/world/examples/theme_2_0_two_biomes.json"))
	tf.close()
	var v2_res := ThemeLoader.load_theme(v2_dir)
	_check(v2_res["errors"].is_empty() and v2_res["warnings"].is_empty(), "exemple de thème 2.0 accepté sans avertissement")
	var m2 = BiomeModel.new(v2_res["theme"], null)
	var med: Dictionary = m2.params("mediterranean")
	_check(med["terrain"]["grass_color"] == Color.html("#b39461"), "méditerranéen : sol plat ocre")
	_check(med["terrain"]["snow_line_m"] >= 100000.0, "méditerranéen : high_line_m null -> pas de neige")
	_check(med["terrain"]["snow_color"] == ref["snow_color"], "couche high absente : neige 1.x")
	_check(med["vegetation"]["species"].size() == 4 and med["vegetation"]["treeline_m"] == null, "méditerranéen : 4 espèces, pas de limite des arbres")
	_check(med["sky"]["light_tint"] == Color.html("#fff3e0") and is_equal_approx(med["sky"]["haze"], 0.25), "méditerranéen : ciel")
	var med_var: Dictionary = m2.params("mediterranean", "", 0.0, {"ground": "calcaire_blanc", "roofs": "tuile_ronde"})
	_check(med_var["variant"]["roofs"]["id"] == "tuile_ronde" and med_var["variant"]["ground"]["values"]["rock_color"] == "#e2ddd0", "variante : entrées du thème")
	var jungle: Dictionary = m2.params("jungle")
	_check(jungle["terrain"]["grass_color"] == ref["grass_color"] and jungle["vegetation"]["species"].is_empty(), "biome absent du thème 2.0 : valeurs 1.x")
	_check(m2.default_biome() == "temperate_grassland" and not m2.active(), "sans couche ni forçage : modèle muet")

	# Thème par défaut 2.0 (U15) : prairie = valeurs 1.x exactes, 17 biomes distincts
	var md = BiomeModel.new(default_theme, null)
	var gp: Dictionary = md.params("temperate_grassland")
	var same_grass := true
	for k in ref.keys():
		if typeof(ref[k]) != TYPE_DICTIONARY and gp["terrain"][k] != ref[k]:
			same_grass = false
	_check(same_grass, "défaut 2.0 : temperate_grassland = terrain 1.x au bit près")
	# Biome alpin au look du parcours de démonstration (choix du propriétaire, 30 octobre) : même terrain que la
	# prairie, sapins d'avant la série U ; les 15 autres biomes ont chacun leur couleur de sol.
	var ap: Dictionary = md.params("alpine")
	var same_alpine := true
	for k in ref.keys():
		if typeof(ref[k]) != TYPE_DICTIONARY and ap["terrain"][k] != ref[k]:
			same_alpine = false
	_check(same_alpine and not bool(ap["vegetation"].get("has_species", true)),
		"défaut 2.0 : alpine = terrain du parcours de démonstration, arbre d'avant la série U")
	var flats := {}
	for id in BiomeIds.BIOMES:
		if id != "alpine":
			flats[md.params(id)["terrain"]["grass_color"].to_html()] = true
	_check(flats.size() == BiomeIds.BIOMES.size() - 1, "défaut 2.0 : %d couleurs de sol différentes hors alpine (%d)" % [BiomeIds.BIOMES.size() - 1, flats.size()])
	_check(md.params("sand_desert")["vegetation"]["species"][0]["kind"] == "palm" and md.params("polar")["vegetation"]["species"].is_empty(), "défaut 2.0 : espèces par biome")

	# Paysages (lot U25) : bloc du biome dans le paysage de la variante, biomes de base seulement
	var fj_var := {"ground": "schiste_sombre", "roofs": "bois_peint", "landscape": "fjord"}
	var coast_fj: Dictionary = md.params("coast", "", 0.0, fj_var)
	var coast_plain: Dictionary = md.params("coast")
	var fj_kinds := []
	for sp in coast_fj["vegetation"]["species"]:
		fj_kinds.append(sp["kind"])
	_check(fj_kinds.has("birch") and not fj_kinds.has("palm") and float(coast_fj["vegetation"]["treeline_m"]) == 700.0,
		"paysage fjord : côte en bouleaux et épicéas, sans palmier, limite des arbres 700 m")
	_check(coast_fj["terrain"] == coast_plain["terrain"] and coast_fj["water"] == coast_plain["water"],
		"paysage fjord : sections non décrites (sol, eau) gardées du biome")
	_check(md.params("savanna", "", 0.0, fj_var)["vegetation"] == md.params("savanna")["vegetation"],
		"paysage fjord : biome qui n'est pas une base du paysage inchangé")
	_check(md.params("coast", "", 0.0, {"ground": "schiste_sombre", "roofs": null})["vegetation"] == coast_plain["vegetation"],
		"variante sans paysage (tuile d'avant le lot U25) : biome inchangé")
	_check(md.params("coast", "", 0.0, {"landscape": "lagon"})["vegetation"] == coast_plain["vegetation"],
		"paysage inconnu du thème : biome inchangé")
	var vol_iv: Dictionary = md.params("volcanic", "", 0.0, {"landscape": "ile_volcanique"})
	_check(vol_iv["vegetation"]["species"][0]["kind"] == "pine" and vol_iv["vegetation"]["max_density_per_ha"] > md.params("volcanic")["vegetation"]["max_density_per_ha"],
		"paysage île volcanique : pinède sur le volcan")
	var rice: Dictionary = md.params("farmland", "", 0.0, {"landscape": "rizieres"})
	var rice_kinds := []
	for sp in rice["vegetation"]["species"]:
		rice_kinds.append(sp["kind"])
	_check(rice_kinds.has("palm") and not rice_kinds.has("vine_row"), "paysage rizières : palmiers, pas de vignes")
	_check(md.params("rock_desert", "", 0.0, {"landscape": "canyon"})["vegetation"]["max_density_per_ha"] > md.params("rock_desert")["vegetation"]["max_density_per_ha"],
		"paysage canyon : genévriers et pins épars sur le désert de roche")
	for l in BiomeIds.LANDSCAPES:
		_check(typeof(default_theme.get("landscapes", {}).get(l, null)) == TYPE_DICTIONARY, "défaut 2.0 : paysage " + l + " décrit")

	# Variante d'un point : tuile proche, forçage --biome= qui l'ignore
	var tile_l := _flat_tile(["coast"], [255])
	tile_l["variant"] = fj_var
	var ml = BiomeModel.new(default_theme, _layer_with({Vector2i(0, 0): tile_l}))
	_check(ml.variant_at(500.0, 500.0)["landscape"] == "fjord" and ml.building_style_at(500.0, 500.0) == "bois_peint",
		"variant_at : paysage et toit bois_peint de la tuile")
	ml.set_forced("coast")
	_check(ml.variant_at(500.0, 500.0) == null and ml.building_style_at(500.0, 500.0) == "ardoise",
		"forçage --biome= : variante ignorée")

	# blend : 50/50
	var bl := BiomeModel.blend({"temperate_grassland": 0.5, "mediterranean": 0.5},
		{"temperate_grassland": m2.params("temperate_grassland"), "mediterranean": med})
	var expect: Color = (m2.params("temperate_grassland")["terrain"]["grass_color"] + med["terrain"]["grass_color"]) * 0.5
	_check(bl["grass_color"].is_equal_approx(expect), "blend : couleur moyenne")
	_check(is_equal_approx(bl["max_density_per_ha"], 275.0), "blend : densité 275 (400 et 150)")
	_check(is_equal_approx(bl["species"]["olive"], 0.5 * 0.4) and is_equal_approx(bl["species"]["oak"], 0.25), "blend : espèces pondérées")

	# Critère 7 : coût de weights_at
	var st := {"k": 0}
	var ms := PerfBudget.measure_ms(func():
		for i in range(1000):
			model.weights_at(float(st["k"] % 2000), float(st["k"] % 997))
			st["k"] += 1, 5, 1)
	_check(PerfBudget.check("biome_weights_at", ms / 1000.0), "weights_at : %.2f µs par appel (5 µs indicatif)" % ms)

	# Lot U13 : saison de chaque biome à la date posée, paramètres mélangés par les poids
	var sm := BiomeModel.new(default_theme)
	_check(str(sm.params("savanna")["season"]) == "" and float(sm.params("savanna")["season_params"]["ground_wet"]) == 0.0,
		"sans date : pas de saison, paramètres neutres")
	sm.set_season_date(7, 15, 12.0)
	var sav: Dictionary = sm.params("savanna")
	var tg: Dictionary = sm.params("temperate_grassland")
	_check(sav["season"] == "wet" and float(sav["season_params"]["ground_wet"]) > 0.5, "15 juillet, 12° : savane en saison des pluies")
	_check(tg["season"] == "summer" and sm.params("sand_desert")["season"] == "none", "même date : prairie en été, désert sans saison")
	var mixed: Dictionary = BiomeModel.blend({"savanna": 0.5, "temperate_grassland": 0.5}, {"savanna": sav, "temperate_grassland": tg})
	_check(is_equal_approx(float(mixed["season_params"]["ground_wet"]), float(sav["season_params"]["ground_wet"]) * 0.5),
		"mélange savane et prairie : moitié du sol détrempé")
	sm.set_season_date(7, 15, -12.0)
	_check(sm.params("savanna")["season"] == "dry", "même date, −12° : savane en saison sèche (cache vidé au changement de date)")
	_check(sm.params("savanna", "winter", 0.5)["season"] == "winter", "saison imposée à l'appel : l'emporte")
	sm.clear_season()
	_check(str(sm.params("savanna")["season"]) == "", "date retirée : plus de saison")
	_check(sm.params("boreal_forest")["seasons"]["durations_months"] == [2.0, 3.0, 2.0, 5.0], "section seasons du biome lue (taïga : hiver de 5 mois)")

	# Lot U16 : réglage « Biome du décor », chaque biome a son nom français au menu, tous différents
	var texts: Dictionary = SettingsViewModel.CHOICE_TEXTS["render.biome"]
	var names := {}
	for id in ["auto"] + BiomeIds.BIOMES:
		names[str(texts.get(id, ""))] = true
	var n_choices := BiomeIds.BIOMES.size() + 1
	_check(texts.size() == n_choices and names.size() == n_choices and not names.has(""), "render.biome : %d noms français distincts" % n_choices)
	_check(SettingsViewModel.format_value({"key": "render.biome"}, "savanna") == "savane", "render.biome : savanna = savane")

	print("test_biome_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
