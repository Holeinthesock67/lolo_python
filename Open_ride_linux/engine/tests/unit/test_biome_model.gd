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
	_check(same, "thème 1.x : les 16 biomes ont les paramètres de theme_render_params.gd")

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

	# Thème par défaut 2.0 (U15) : prairie = valeurs 1.x exactes, 16 biomes distincts
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
	_check(flats.size() == 15, "défaut 2.0 : 15 couleurs de sol différentes hors alpine (%d)" % flats.size())
	_check(md.params("sand_desert")["vegetation"]["species"][0]["kind"] == "palm" and md.params("polar")["vegetation"]["species"].is_empty(), "défaut 2.0 : espèces par biome")

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

	print("test_biome_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
