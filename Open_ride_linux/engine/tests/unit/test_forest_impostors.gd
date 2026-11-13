extends SceneTree

## Tests unitaires sans écran de forest_impostors.gd (forêts lointaines en imposteurs, lot Y5).
## Vérifie :
## - Houppiers vus de loin (TreeSpecies.CROWNS) : cône des résineux, rond des feuillus, plantes basses écartées.
## - Placement d'une tuile lointaine : déterministe, dans la tuile, pied sous le sol dessiné, couloir de la
##   route libre, limite des arbres et pente respectées, même bruit de densité que les arbres proches.
## - Biomes : forêt tempérée plus dense que la prairie, polaire sans arbre.
## - Affichage : une instance de MultiMesh par case, part du préréglage, boîte et distances, retrait.
## - Temps de préparation d'une tuile (budget `forest_far_tile` de tests/perf_budgets.json).

const ForestImpostors := preload("res://scripts/forest_impostors.gd")
const TreeSpecies := preload("res://scripts/tree_species.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const BiomeIds := preload("res://scripts/biome_ids.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const N := ForestImpostors.FLOATS_PER_INSTANCE

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite nord-sud au milieu de la tuile lointaine (0, 0), x = 2 500 m.
func _route() -> Variant:
	var ds := 10.0
	var n := 501
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(300.0)
		d["x"].append(2500.0)
		d["z"].append(i * ds)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(180.0)
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


## Toutes les instances d'une tuile préparée : [x, y, z, largeur, hauteur, graine, forme, ordre de case].
func _instances(data: Dictionary) -> Array:
	var out := []
	for cell_idx in data["cells"]:
		var buf: PackedFloat32Array = data["cells"][cell_idx]["buffer"]
		for k in range(buf.size() / N):
			out.append([buf[k * N + 3], buf[k * N + 7], buf[k * N + 11], buf[k * N], buf[k * N + 5],
				buf[k * N + 16], buf[k * N + 17], cell_idx])
	return out


func _test_crowns() -> void:
	for kind in BiomeIds.SPECIES:
		_check(TreeSpecies.CROWNS.has(kind), "houppier de « %s » décrit dans TreeSpecies.CROWNS" % kind)
	var spruce := ForestImpostors.crown_look("spruce")
	var oak := ForestImpostors.crown_look("oak")
	_check(spruce["shape"] == 1.0 and oak["shape"] == 0.0, "épicéa en cône, chêne en houppier rond")
	_check(oak["deciduous"] and not spruce["deciduous"] and not ForestImpostors.crown_look("")["deciduous"],
			"saisons (P18) : chêne caduc, épicéa et arbre d'avant la série U persistants")
	_check(oak["base"] > 0.3 and oak["base"] < 0.5 and spruce["base"] < 0.2, "pied de couronne : chêne %.2f, épicéa %.2f" % [oak["base"], spruce["base"]])
	var low := ["cactus", "reed", "dwarf_shrub", "vine_row", "heather", "gorse", "bracken", "bunchgrass"]
	_check(low.all(func(k): return ForestImpostors.crown_look(k).is_empty()), "plantes basses écartées des forêts lointaines")
	_check(ForestImpostors.crown_look("")["height"] == ForestImpostors.GENERIC_HEIGHT_M, "arbre d'avant la série U (5,4 m)")
	var q := ForestImpostors.build_quad()
	_check(q.get_aabb().position.is_equal_approx(Vector3(-0.5, 0.0, 0.0)) and is_equal_approx(q.get_aabb().size.x, 1.0) and is_equal_approx(q.get_aabb().size.y, 1.0), "quadrilatère de base 1 × 1, pied à y = 0 (%s)" % str(q.get_aabb()))


func _test_placement() -> void:
	var theme := {"vegetation": {"max_density_per_ha": 400.0, "treeline_m": 2000.0},
		"road": {"width_m": 6.0}, "terrain": {"slope_threshold_deg": 22.0}}
	var route = _route()
	var forest = ForestImpostors.new()
	var flat := TerrainTiles.flat_heights(300.0)
	var a: Dictionary = forest.prepare_tile(0, 0, flat, route, theme)
	var b: Dictionary = forest.prepare_tile(0, 0, flat, route, theme)
	print("Préparation d'une tuile lointaine : ", JSON.stringify(forest.last_profile))
	_check(int(a["count"]) > 1000, "tuile lointaine boisée (%d bouquets)" % int(a["count"]))
	_check(var_to_str(a) == var_to_str(b), "placement déterministe (même tuile, mêmes octets)")
	var inst := _instances(a)
	_check(inst.size() == int(a["count"]), "tampons : %d flottants par bouquet" % N)
	var inside := true
	var foot := true
	var road_free := true
	var corridor := 6.0 * 0.5 + VegetationPlacer.ROAD_MARGIN_M + ForestImpostors.CLUMP_WIDTH_M * 0.5
	for it in inst:
		inside = inside and it[0] >= 0.0 and it[0] <= 5000.0 and it[2] >= 0.0 and it[2] <= 5000.0
		foot = foot and is_equal_approx(it[1], 300.0 - TerrainTiles.FAR_DROP_M - ForestImpostors.SINK_M)
		road_free = road_free and (absf(it[0] - 2500.0) >= corridor or it[2] > 5000.0)
	_check(inside, "bouquets dans la tuile")
	_check(foot, "pied des bouquets FAR_DROP_M + SINK_M sous le sol")
	_check(road_free, "couloir de la route libre (%.0f m de part et d'autre)" % corridor)
	# Même bruit de densité que les arbres proches : bruit moyen plus fort sous les bouquets gardés
	var mean_kept := 0.0
	for it in inst:
		mean_kept += VegetationPlacer.density_noise(it[0], it[2])
	mean_kept /= maxf(inst.size(), 1.0)
	var mean_all := 0.0
	for k in range(400):
		mean_all += VegetationPlacer.density_noise(12.5 * (k % 20) * 20.0, 12.5 * (k / 20) * 20.0)
	mean_all /= 400.0
	_check(mean_kept > mean_all + 0.05, "forêts là où le bruit de densité est fort (%.2f contre %.2f)" % [mean_kept, mean_all])
	# Case par case : boîte qui contient tous les bouquets
	var aabb_ok := true
	for cell_idx in a["cells"]:
		var c: Dictionary = a["cells"][cell_idx]
		var box: AABB = c["aabb"]
		var buf: PackedFloat32Array = c["buffer"]
		for k in range(int(c["count"])):
			var p := Vector3(buf[k * N + 3], buf[k * N + 7], buf[k * N + 11])
			aabb_ok = aabb_ok and box.grow(0.01).has_point(p) and box.grow(0.01).has_point(p + Vector3(0, buf[k * N + 5], 0))
	_check(a["cells"].size() <= 25 and aabb_ok, "25 cases au plus, boîtes qui contiennent leurs bouquets")
	# Limite des arbres et pente
	var high := TerrainTiles.flat_heights(2500.0)
	_check(int(forest.prepare_tile(0, 0, high, null, theme)["count"]) == 0, "au-dessus de la limite des arbres : aucun bouquet")
	var steep := PackedFloat32Array()
	steep.resize(TerrainTiles.SAMPLES * TerrainTiles.SAMPLES)
	for j in range(TerrainTiles.SAMPLES):
		for i in range(TerrainTiles.SAMPLES):
			steep[j * TerrainTiles.SAMPLES + i] = 300.0 + i * 50.0 * 0.6   # pente de 31°
	_check(int(forest.prepare_tile(0, 0, steep, null, theme)["count"]) == 0, "pente au-delà du seuil : aucun bouquet")
	# Coupé ou sans hauteurs
	forest.enabled = false
	_check(forest.prepare_tile(0, 0, flat, route, theme).is_empty(), "--forest=off : aucune préparation")
	forest.enabled = true
	_check(forest.prepare_tile(0, 0, PackedFloat32Array(), route, theme).is_empty(), "tuile sans hauteurs : rien")
	# Temps de préparation (tâche de fond, lot X2)
	var ms := PerfBudget.measure_ms(func(): forest.prepare_tile(1, 0, flat, null, theme), 3, 1)
	_check(PerfBudget.check("forest_far_tile", ms), "préparation d'une tuile lointaine dans le budget (%.1f ms)" % ms)
	forest.free()


func _test_biomes() -> void:
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	var flat := TerrainTiles.flat_heights(300.0)
	var counts := {}
	for b in ["temperate_forest", "farmland", "polar", "boreal_forest"]:
		var forest = ForestImpostors.new()
		forest.biome_model = BiomeModel.new(theme, null)
		forest.biome_model.set_forced(b)
		var data: Dictionary = forest.prepare_tile(0, 0, flat, null, theme)
		counts[b] = int(data.get("count", 0))
		if b == "boreal_forest":
			var cones := 0
			for it in _instances(data):
				cones += 1 if it[6] > 0.5 else 0
			_check(cones * 2 > int(data["count"]), "forêt boréale surtout en résineux (%d cônes sur %d)" % [cones, int(data["count"])])
		forest.free()
	print("Bouquets par biome : ", counts)
	_check(counts["temperate_forest"] > 3 * counts["farmland"], "forêt tempérée plus dense que les cultures")
	_check(counts["polar"] == 0, "polaire : aucun arbre")


func _test_display() -> void:
	var theme := {"vegetation": {"max_density_per_ha": 400.0, "treeline_m": 2000.0}}
	var forest = ForestImpostors.new()
	root.add_child(forest)
	forest.set_preset("low")
	var data: Dictionary = forest.prepare_tile(0, 0, TerrainTiles.flat_heights(300.0), null, theme)
	forest.add_tile(data)
	_check(forest.get_child_count() == data["cells"].size(), "une instance de MultiMesh par case (%d)" % forest.get_child_count())
	var mmi := forest.get_child(0) as MultiMeshInstance3D
	var mm := mmi.multimesh
	var frac := QualityPresets.forest_fraction("low")
	_check(mm.use_colors and mm.use_custom_data and mm.visible_instance_count == ForestImpostors.visible_count(mm.instance_count, frac),
		"low : %d bouquets affichés sur %d (part %.1f)" % [mm.visible_instance_count, mm.instance_count, frac])
	_check(mmi.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF and mmi.material_override == forest.get_material(),
		"sans ombre, matériau partagé")
	_check(mmi.visibility_range_begin < ForestImpostors.BEGIN_M and mmi.visibility_range_end > QualityPresets.fog_end_m("low"),
		"case dessinée de %.0f à %.0f m (centre de la case)" % [mmi.visibility_range_begin, mmi.visibility_range_end])
	_check(is_equal_approx(float(forest.get_material().get_shader_parameter("end_m")), QualityPresets.fog_end_m("low")),
		"fin des forêts = fin du brouillard en low")
	var low_count: int = forest.get_count()
	forest.set_preset("high")
	_check(forest.get_count() > low_count and is_equal_approx(float(forest.get_material().get_shader_parameter("end_m")), QualityPresets.fog_end_m("high")),
		"high : plus de bouquets (%d contre %d), fin à %.0f m" % [forest.get_count(), low_count, QualityPresets.fog_end_m("high")])
	_check(ForestImpostors.visible_count(10, 0.0) == 0 and ForestImpostors.visible_count(10, 0.55) == 6 and ForestImpostors.visible_count(10, 1.0) == 10,
		"part affichée arrondie au-dessus")
	forest.add_tile(data)
	_check(forest.tile_count() == 1, "tuile remplacée, pas doublée")
	forest.remove_tile(data["tile_key"])
	_check(forest.get_child_count() == 0 and forest.get_count() == 0, "tuile retirée : plus aucune instance")
	forest.add_tile({})
	_check(forest.tile_count() == 0, "tuile vide ignorée")
	# File de préparation (hors de l'attente du départ) : une tâche à la fois, demande remplacée, retrait
	var flat2 := TerrainTiles.flat_heights(300.0)
	forest.request_tile(2, 0, flat2, null, theme)
	forest.request_tile(3, 0, flat2, null, theme)
	forest.request_tile(2, 0, flat2, null, theme)
	_check(forest.pending_tiles() == 3, "file : tâche en cours annulée et redemandée, une seule fois en file (%d)" % forest.pending_tiles())
	forest.wait_all()
	_check(forest.pending_tiles() == 0 and forest.tile_count() == 2, "file : les deux tuiles posées (%d)" % forest.tile_count())
	forest.request_tile(4, 0, flat2, null, theme)
	forest.remove_tile(Vector2i(4, 0))
	forest.wait_all()
	_check(forest.tile_count() == 2, "file : tuile retirée avant d'être prête, jamais posée")
	forest.clear()
	_check(forest.tile_count() == 0 and forest.pending_tiles() == 0, "clear : file et tuiles vidées")
	# Préchauffage du pipeline au chargement (banc PC du 6 novembre : à-coup à la première forêt dessinée)
	var cam := Camera3D.new()
	root.add_child(cam)
	_check(not forest.warm_up(null), "préchauffage sans caméra : rien")
	_check(forest.warm_up(cam) and forest.is_warming() and cam.get_child_count() == 1,
		"préchauffage : un bouquet collé devant la caméra")
	var warm := cam.get_child(0) as MultiMeshInstance3D
	_check(warm.multimesh.use_colors and warm.multimesh.use_custom_data and warm.multimesh.transform_format == MultiMesh.TRANSFORM_3D,
		"préchauffage : même format de MultiMesh que les forêts")
	_check((warm.material_override as ShaderMaterial).shader == forest.get_material().shader, "préchauffage : même shader")
	for i in range(ForestImpostors.WARM_FRAMES):
		forest._process(0.016)
	_check(not forest.is_warming(), "préchauffage retiré après %d images" % ForestImpostors.WARM_FRAMES)
	forest.enabled = false
	_check(not forest.warm_up(cam), "forêts coupées : pas de préchauffage")
	cam.free()
	forest.free()


func _init() -> void:
	_test_crowns()
	_test_placement()
	_test_biomes()
	_test_display()
	print("test_forest_impostors : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
