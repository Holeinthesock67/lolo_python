extends SceneTree

## Sols multi-biomes (lot U6, `biome_textures.gd`) : budget de mémoire vidéo et niveau retenu, couches de
## sol des 16 biomes, biomes en usage, poids d'une tuile (3 biomes en low, 4 sinon, forçage, tuile absente).

const BiomeTextures := preload("res://scripts/biome_textures.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const BiomeIds := preload("res://scripts/biome_ids.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_biome_textures : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Tuile de 4 biomes à parts fixes (somme 255 en chaque point).
func _tile4(biomes: Array, parts: Array) -> Dictionary:
	var grids: Array[PackedFloat32Array] = []
	for p in parts:
		var g := PackedFloat32Array()
		g.resize(BiomeLayer.POINTS)
		g.fill(float(p) / 255.0)
		grids.append(g)
	var names: Array[String] = []
	for b in biomes:
		names.append(b)
	return {"biomes": names, "weights": grids, "variant": null}


func _run() -> void:
	# 1. Budget (U-Q4 : 1 Go) et niveau retenu (règle de P20 : tailles décompressées, mipmaps comprises)
	_check(BiomeTextures.estimate_bytes(1, 1024) == int(1024 * 1024 * 4 * 4.0 / 3.0), "estimation : 1 carte de 1 024 px = 5,3 Mo")
	var six := 6 * 3 * 2
	var c6 := BiomeTextures.choose_size(six, 2048)
	_check(c6["px"] == 2048, "6 biomes texturés (36 cartes) en high : 2 048 px, %.0f Mo" % (c6["bytes"] / 1048576.0))
	var c9 := BiomeTextures.choose_size(9 * 3 * 2, 2048)
	_check(c9["px"] == 1024 and c9["reason"] == "budget de 1 Go", "9 biomes (54 cartes) en high : %.0f Mo à 2 048 px, niveau 1 024 retenu (%s)" % [BiomeTextures.estimate_bytes(54, 2048) / 1048576.0, c9["reason"]])
	_check(BiomeTextures.choose_size(six, 1024)["px"] == 1024, "low et medium : 1 024 px")
	var c_huge := BiomeTextures.choose_size(200, 2048)
	_check(c_huge["px"] == 0, "au-delà du budget même à 1 024 px : couleurs unies (%s)" % c_huge["reason"])
	_check(BiomeTextures.choose_size(0, 2048)["px"] == 0, "aucune texture : couleurs unies")

	# 2. Couches de sol du thème par défaut 2.0 : les 16 biomes, 3 couches chacun, sans doublon
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	var model := BiomeModel.new(theme, BiomeLayer.new())
	model.set_forced("savanna")
	var bt := BiomeTextures.new(model, "", "low")
	_check(bt.biome_layers.size() == 16, "16 biomes décrits")
	_check(bt.layers.size() <= BiomeTextures.MAX_LAYERS, "%d couches de sol distinctes (au plus %d)" % [bt.layers.size(), BiomeTextures.MAX_LAYERS])
	var sav: Array = bt.biome_layers["savanna"]["layers"]
	_check((bt.layers[sav[0]]["color"] as Color).is_equal_approx(Color.html("#a08848")), "savane : herbes hautes jaunes #a08848")
	_check((bt.layers[sav[1]]["color"] as Color).is_equal_approx(Color.html("#a5583a")), "savane : latérite rouge #a5583a")
	var rule: Vector4 = bt.biome_layers["savanna"]["rule"]
	_check(is_equal_approx(rule.x, 24.0) and rule.y >= BiomeModel.NO_HIGH_LINE_M, "savane : seuil de pente 24°, pas de neige")
	_check(bt.texture_px == 0 and bt.log_line.contains("couleurs unies"), "thème sans textures : couleurs unies, journal « %s »" % bt.log_line)
	_check(bt.material != null and bt.material.get_shader_parameter("biome_rule").size() == 16, "matériau de base : 16 règles de biome")
	_check(bt.material.get_shader_parameter("layer_color").size() == BiomeTextures.MAX_LAYERS, "matériau de base : 48 couleurs de couche")

	# 3. Biomes en usage : forçage, parts du manifeste, sinon tous
	_check(bt.biomes_in_use() == ["savanna"], "biome forcé : seul en usage")
	var manifest := {"layers": {"biome": {"present": true, "default_biome": "temperate_grassland",
		"shares": {"alpine": 30, "temperate_forest": 70}}}}
	var model2 := BiomeModel.new(theme, BiomeLayer.new("res://", manifest))
	var bt2 := BiomeTextures.new(model2, "", "medium")
	_check(bt2.biomes_in_use() == ["temperate_grassland", "temperate_forest", "alpine"], "parts du manifeste : %s" % str(bt2.biomes_in_use()))
	var model3 := BiomeModel.new(theme, BiomeLayer.new("res://", {"layers": {"biome": {"present": true}}}))
	_check(BiomeTextures.new(model3, "", "low").biomes_in_use().size() == 16, "sans parts : les 16 biomes")

	# 4. Poids d'une tuile : 4 biomes, triés par part ; le plus faible écarté en low
	var layer := BiomeLayer.new()
	layer.put_tile("near", 0, 0, _tile4(["volcanic", "alpine", "temperate_forest", "polar"], [35, 100, 70, 50]))
	var m4 := BiomeModel.new(theme, layer)
	var w_med := BiomeTextures.tile_weights(m4, "near", 0, 0, 4)
	_check(w_med["biomes"] == ["alpine", "temperate_forest", "polar", "volcanic"], "medium : 4 biomes par part décroissante %s" % str(w_med["biomes"]))
	var idx: Vector4 = w_med["index"]
	_check(int(idx.x) == BiomeIds.BIOMES.find("alpine") and int(idx.w) == BiomeIds.BIOMES.find("volcanic"), "indices dans BiomeIds.BIOMES")
	var px: Color = (w_med["image"] as Image).get_pixel(8, 8)
	_check(absf(px.r - 100.0 / 255.0) < 0.01 and absf(px.a - 35.0 / 255.0) < 0.01, "image 17 × 17 : RGBA = parts (%.3f, %.3f)" % [px.r, px.a])
	var w_low := BiomeTextures.tile_weights(m4, "near", 0, 0, 3)
	_check(w_low["biomes"].size() == 3 and not (w_low["biomes"] as Array).has("volcanic") and (w_low["index"] as Vector4).w < 0.0,
		"low : 3 biomes, le plus faible (volcanique) écarté")
	_check((w_low["image"] as Image).get_pixel(3, 5).a == 0.0, "low : canal alpha vide")
	var w_none := BiomeTextures.tile_weights(m4, "near", 5, 5, 4)
	_check(w_none["biomes"] == ["temperate_grassland"] and (w_none["image"] as Image).get_pixel(0, 0).r == 1.0, "tuile sans fichier : biome par défaut à 100 %")
	m4.set_forced("jungle")
	var w_forced := BiomeTextures.tile_weights(m4, "near", 0, 0, 4)
	_check(w_forced["biomes"] == ["jungle"] and int((w_forced["index"] as Vector4).x) == BiomeIds.BIOMES.find("jungle"), "biome forcé : une seule couche à 100 %")

	# 5. Matériau de tuile : rectangle de la tuile, paramètres partagés recopiés (ombre des nuages)
	m4.set_forced("")
	var bt4 := BiomeTextures.new(m4, "", "high")
	var tm := bt4.tile_material("far", 1, -2)
	_check(tm.get_shader_parameter("tile_rect") == Vector4(5000.0, -10000.0, 5000.0, 5000.0), "tuile lointaine (1, -2) : rectangle %s" % str(tm.get_shader_parameter("tile_rect")))
	var src := ShaderMaterial.new()
	src.shader = preload("res://shaders/terrain.gdshader")
	src.set_shader_parameter("cloud_shadow_enabled", true)
	src.set_shader_parameter("cloud_shadow_offset", Vector2(12.0, 3.0))
	bt4.sync_from(src)
	_check(tm.get_shader_parameter("cloud_shadow_offset") == Vector2(12.0, 3.0), "ombre des nuages recopiée sur la tuile")
	var tm2 := bt4.tile_material("near", 0, 0)
	_check(tm2.get_shader_parameter("cloud_shadow_enabled") == true, "nouvelle tuile : paramètres partagés déjà appliqués")
	bt4.release(tm)
	_check(not bt4._tile_materials.has(tm), "tuile retirée : matériau oublié")
