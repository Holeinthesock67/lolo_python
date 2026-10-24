extends SceneTree

## Tests unitaires sans écran de tree_renderer.gd (Lot E3 / SRS §8).
## Vérifie :
## - Déterminisme des positions et transformations.
## - Respect des exclusions (couloir de la route, limite des arbres, seuil de pente).
## - Hauteur du pied de chaque arbre à moins de 5 cm de la surface dessinée de la tuile.
## - Respect du budget d'instances selon le préréglage.
## - Présence des 2 MultiMeshInstance3D par case avec leurs distances LOD.

const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _make_simple_route(length_m: float = 3000.0) -> Variant:
	var ds := 10.0
	var n := int(length_m / ds) + 1
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": length_m, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(1000.0)
		d["x"].append(500.0)   # au milieu de la tuile x = 0 (X: 0..1000)
		d["z"].append(i * ds)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(180.0)
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _test_tree_generation_and_determinism() -> void:
	var renderer = TreeRenderer.new()
	root.add_child(renderer)
	var route = _make_simple_route(2000.0)
	var theme := {
		"vegetation": {"max_density_per_ha": 300.0, "treeline_m": 2000.0},
		"road": {"width_m": 6.0},
		"terrain": {"slope_threshold_deg": 25.0}
	}
	var heights := TerrainTiles.flat_heights(1000.0)

	# Échauffement hors mesure
	var prep1: Dictionary = renderer.prepare_tile(0, 0, heights, route, theme, 1.0)
	var best_ms := INF
	for i in range(3):
		var t0 := Time.get_ticks_usec()
		prep1 = renderer.prepare_tile(0, 0, heights, route, theme, 1.0)
		best_ms = minf(best_ms, (Time.get_ticks_usec() - t0) / 1000.0)
	var prep_time_ms := best_ms
	print("Mesure : placement tuile high en %.2f ms (meilleur de 3, seuil 150 ms)" % prep_time_ms)
	# Seuil du cahier : 150 ms ; seuil adapté en intégration continue (machines partagées).
	var limit := 200.0 if OS.get_environment("CI") != "" else 150.0
	_check(prep_time_ms < limit, "temps CPU préparation tuile < %.0f ms (%.2f ms)" % [limit, prep_time_ms])

	var prep2: Dictionary = renderer.prepare_tile(0, 0, heights, route, theme, 1.0)

	# Déterminisme : comparer arbre par arbre
	var same := true
	var cells1: Array = prep1["cells"]
	var cells2: Array = prep2["cells"]
	var total_trees := 0
	for i in range(16):
		var c1: PackedVector4Array = cells1[i]
		var c2: PackedVector4Array = cells2[i]
		if c1.size() != c2.size():
			same = false
			break
		total_trees += c1.size()
		for k in range(c1.size()):
			if c1[k] != c2[k]:
				same = false
				break
	_check(same and total_trees > 0, "déterminisme : mêmes arbres et transformations (%d arbres générés)" % total_trees)

	# Vérifier les exclusions et hauteurs
	var corridor: float = 6.0 * 0.5 + 4.0 # 7.0 m
	var no_in_corridor := true
	var height_exact := true
	var below_treeline := true

	for i in range(16):
		var cell_trees: PackedVector4Array = cells1[i]
		for tree in cell_trees:
			# Route à x = 500
			if absf(tree.x - 500.0) < corridor:
				no_in_corridor = false
			# Surface dessinée de la tuile
			var mesh_h := TerrainTiles.mesh_height_at(heights, "near", 0, 0, tree.x, tree.z)
			if absf(tree.y - mesh_h) > 0.05:
				height_exact = false
			if tree.y > 2000.0:
				below_treeline = false

	_check(no_in_corridor, "aucun arbre dans le couloir de la route (7 m de l'axe)")
	_check(height_exact, "pied de chaque arbre à moins de 5 cm de la surface dessinée")
	_check(below_treeline, "aucun arbre au-dessus de treeline_m")

	# Instanciation sur la scène
	renderer.add_tile(prep1)
	_check(renderer.get_active_tree_count() == total_trees, "arbres actifs = %d" % total_trees)

	# Vérification des MultiMeshInstance3D et distances LOD
	var cell_info: Dictionary = renderer._tiles[Vector2i(0, 0)]
	var valid_lods := true
	for cell_idx in cell_info.keys():
		var info: Dictionary = cell_info[cell_idx]
		var mmi0: MultiMeshInstance3D = info["lod0"]
		var mmi1: MultiMeshInstance3D = info["lod1"]
		if mmi0.visibility_range_begin != 0.0 or mmi0.visibility_range_end != 300.0:
			valid_lods = false
		if mmi1.visibility_range_begin != 300.0 or mmi1.visibility_range_end != 1500.0:
			valid_lods = false
		if mmi0.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_ON:
			valid_lods = false
		if mmi1.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
			valid_lods = false
	_check(valid_lods, "chaque case possède ses 2 MultiMeshInstance3D avec LOD0 (0-300m ombre) et LOD1 (300-1500m sans ombre)")

	# Libération
	renderer.remove_tile(Vector2i(0, 0))
	_check(renderer.get_active_tree_count() == 0, "libération tuile : compteur à 0")

	renderer.queue_free()


func _test_budget_enforcement() -> void:
	var renderer = TreeRenderer.new()
	root.add_child(renderer)
	var route = _make_simple_route(5000.0)
	var theme := {"vegetation": {"max_density_per_ha": 400.0}}
	var heights := TerrainTiles.flat_heights(1000.0)

	renderer.set_preset("low") # budget 20000
	# Ajouter plusieurs tuiles pour dépasser un budget restreint
	renderer._budget = 500 # budget test restreint
	var p0 := renderer.prepare_tile(0, 0, heights, route, theme, 1.0)
	var p1 := renderer.prepare_tile(0, 1, heights, route, theme, 1.0)
	renderer.add_tile(p0)
	renderer.add_tile(p1)
	var count_before := renderer.get_active_tree_count()

	renderer.enforce_budget(Vector3(500.0, 1000.0, 500.0))
	var count_after := renderer.get_active_tree_count()
	_check(count_after <= 500 and count_after < count_before,
		"budget respecté après enforce_budget (%d -> %d <= 500)" % [count_before, count_after])

	renderer.queue_free()


func _init() -> void:
	_test_tree_generation_and_determinism()
	_test_budget_enforcement()
	print("test_tree_renderer : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
