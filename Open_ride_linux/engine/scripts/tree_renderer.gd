extends Node3D

## Gestionnaire et affichage de la végétation par tuiles (Lot E3 §4.3, Lot E4 §4.3, SRS §8).
## Pas de class_name (charger par preload).
##
## Découpe chaque tuile proche de 1 000 m en 16 cases de 250 m × 250 m.
## Chaque case avec arbres possède deux MultiMeshInstance3D :
## - LOD 0 (0 à 300 m) : modèle polygonal bas (tronc + cônes, <= 120 triangles), ombres actives.
## - LOD 1 (300 à 1 500 m) : quadrilatères croisés (4 triangles), sans ombre.
## Le budget global d'instances (QualityPresets.tree_budget) est respecté en éliminant les cases
## les plus éloignées en cas de dépassement.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")

const CELL_SIZE_M := 250.0
const CELLS_PER_TILE := 4   # 4 x 4 = 16 cases par tuile de 1000 m
const LOD0_MAX_DIST_M := 300.0
const LOD1_MAX_DIST_M := 1500.0

# Constantes de région pour le semis hors polygones OSM (Lot E4 §4.3)
const REGION_OSM_COVERAGE_FACTOR := 0.8
const REGION_OSM_THRESHOLD := 0.4
const REGION_BUILDINGS_THRESHOLD := 0.1
const REGION_TREELINE_MARGIN_M := 300.0

var placer := VegetationPlacer.new()
var _lod0_mesh: ArrayMesh
var _lod1_mesh: ArrayMesh
var _lod0_material: StandardMaterial3D
var _lod1_material: StandardMaterial3D

## { tile_key: { cell_idx: { lod0: MultiMeshInstance3D, lod1: MultiMeshInstance3D, count: int, center: Vector3 } } }
var _tiles: Dictionary = {}
var _active_tree_count := 0
var _budget := 20000


func _init() -> void:
	_init_materials()
	_lod0_mesh = build_lod0_mesh()
	_lod1_mesh = build_lod1_mesh()


func _init_materials() -> void:
	_lod0_material = StandardMaterial3D.new()
	_lod0_material.vertex_color_use_as_albedo = true
	_lod0_material.roughness = 0.85

	_lod1_material = StandardMaterial3D.new()
	_lod1_material.vertex_color_use_as_albedo = true
	_lod1_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	_lod1_material.roughness = 0.85


func set_preset(preset_name: String) -> void:
	_budget = QualityPresets.tree_budget(preset_name)


func get_active_tree_count() -> int:
	return _active_tree_count


## Génère les données de placement des arbres d'une tuile (exécutable en thread secondaire).
## Renvoie un dictionnaire avec la clé de tuile et les listes d'arbres par case [0..15].
func prepare_tile(tile_x: int, tile_z: int, heights: PackedFloat32Array, route, theme: Dictionary,
		density_factor: float, areas: Array = []) -> Dictionary:
	var tile_theme := theme.duplicate(true)
	var veg = tile_theme.get("vegetation", {})
	if typeof(veg) != TYPE_DICTIONARY:
		veg = {}
	var base_dens = veg.get("max_density_per_ha", VegetationPlacer.DEFAULT_MAX_DENSITY)
	veg["max_density_per_ha"] = float(base_dens) * clampf(density_factor, 0.0, 1.0)
	tile_theme["vegetation"] = veg

	var height_fn: Callable
	if heights.is_empty():
		var flat_alt := 0.0
		if route != null and route.n > 0:
			flat_alt = route.alt_m[0]
		height_fn = func(_x: float, _z: float) -> float: return flat_alt
	else:
		var origin_x := float(tile_x * 1000)
		var origin_z := float(tile_z * 1000)
		height_fn = func(x: float, z: float) -> float:
			var fi := clampf((x - origin_x) / 10.0, 0.0, 100.0)
			var fj := clampf((z - origin_z) / 10.0, 0.0, 100.0)
			var i := mini(int(fi), 99)
			var j := mini(int(fj), 99)
			var u := fi - i
			var v := fj - j
			var a := heights[j * 101 + i]
			var b := heights[j * 101 + i + 1]
			var c := heights[(j + 1) * 101 + i]
			var d := heights[(j + 1) * 101 + i + 1]
			if u + v <= 1.0:
				return a + u * (b - a) + v * (c - a)
			return d + (1.0 - u) * (c - d) + (1.0 - v) * (b - d)

	# 1. Placement selon zones OSM ou bruit de base (Lots E3 & E4)
	var trees: PackedVector4Array = placer.place_tile(tile_x, tile_z, 1000.0, height_fn, route, tile_theme, areas)

	# 2. Si des zones OSM existent, semer également au hasard hors des zones (Lot E4 §4.3)
	if not areas.is_empty():
		var noise_trees: PackedVector4Array = placer.place_tile(tile_x, tile_z, 1000.0, height_fn, route, tile_theme, [])
		var treeline: float = float(veg.get("treeline_m", VegetationPlacer.DEFAULT_TREELINE_M))
		for tree in noise_trees:
			var px := tree.x
			var pz := tree.z
			var y := tree.y
			# Vérifier que l'arbre n'est pas dans une zone OSM
			var inside_osm := false
			for area in areas:
				if typeof(area) == TYPE_DICTIONARY:
					var outer = area.get("outer", [])
					if typeof(outer) == TYPE_ARRAY and outer.size() >= 3:
						if VegetationPlacer._in_ring(px, pz, VegetationPlacer._packed_ring(outer)):
							inside_osm = true
							break
			if inside_osm:
				continue
			# Facteur d'altitude : s'éclaircit sous la limite des arbres
			var alt_factor := smoothstep(treeline, treeline - REGION_TREELINE_MARGIN_M, y)
			var p_region := alt_factor
			var draw := float((VegetationPlacer.hash3(0x7EE5, int(px), int(pz)) & 0xFFFF)) / 65536.0
			if draw < p_region:
				trees.append(tree)

	# Répartition des arbres dans les 16 cases de 250 m x 250 m
	var tile_origin_x := float(tile_x * 1000)
	var tile_origin_z := float(tile_z * 1000)
	var cells: Array[PackedVector4Array] = []
	for i in range(16):
		cells.append(PackedVector4Array())

	for tree in trees:
		var cx := clampi(int(floor((tree.x - tile_origin_x) / CELL_SIZE_M)), 0, CELLS_PER_TILE - 1)
		var cz := clampi(int(floor((tree.z - tile_origin_z) / CELL_SIZE_M)), 0, CELLS_PER_TILE - 1)
		var cell_idx := cz * CELLS_PER_TILE + cx
		cells[cell_idx].append(tree)

	return {
		"tile_x": tile_x,
		"tile_z": tile_z,
		"tile_key": Vector2i(tile_x, tile_z),
		"cells": cells,
		"tile_origin": Vector3(tile_origin_x, 0.0, tile_origin_z),
	}


## Instancie les MultiMesh pour une tuile préparée (doit être appelé sur le fil principal).
func add_tile(data: Dictionary) -> void:
	var tile_key: Vector2i = data["tile_key"]
	if _tiles.has(tile_key):
		remove_tile(tile_key)

	var tile_cells := {}
	var cells_data: Array = data["cells"]
	var tile_x: int = data["tile_x"]
	var tile_z: int = data["tile_z"]

	for cell_idx in range(cells_data.size()):
		var tree_list: PackedVector4Array = cells_data[cell_idx]
		if tree_list.is_empty():
			continue

		var cx := cell_idx % CELLS_PER_TILE
		var cz := cell_idx / CELLS_PER_TILE
		var center_x := (tile_x * 1000.0) + (cx + 0.5) * CELL_SIZE_M
		var center_z := (tile_z * 1000.0) + (cz + 0.5) * CELL_SIZE_M
		var sum_y := 0.0
		for t in tree_list:
			sum_y += t.y
		var center_y := sum_y / float(tree_list.size())
		var cell_center := Vector3(center_x, center_y, center_z)

		var count := tree_list.size()

		# LOD 0 MultiMeshInstance3D
		var mm0 := MultiMesh.new()
		mm0.transform_format = MultiMesh.TRANSFORM_3D
		mm0.use_colors = true
		mm0.mesh = _lod0_mesh
		mm0.instance_count = count

		# LOD 1 MultiMeshInstance3D
		var mm1 := MultiMesh.new()
		mm1.transform_format = MultiMesh.TRANSFORM_3D
		mm1.use_colors = true
		mm1.mesh = _lod1_mesh
		mm1.instance_count = count

		for i in range(count):
			var t := tree_list[i]
			var px := t.x
			var py := t.y
			var pz := t.z
			var scale_f := t.w

			var h_rot := VegetationPlacer.hash3(0x5EED, int(px), int(pz))
			var angle := float(h_rot & 0xFFFF) / 65536.0 * TAU
			var basis := Basis(Vector3.UP, angle).scaled(Vector3.ONE * scale_f)
			var xform := Transform3D(basis, Vector3(px, py, pz))

			var h_col := VegetationPlacer.hash3(0xCAFE, int(px), int(pz))
			var tint := (float(h_col & 0xFF) / 255.0 - 0.5) * 0.16
			var col := Color(1.0 + tint, 1.0 + tint, 1.0 + tint, 1.0)

			mm0.set_instance_transform(i, xform)
			mm0.set_instance_color(i, col)

			mm1.set_instance_transform(i, xform)
			mm1.set_instance_color(i, col)

		var mmi0 := MultiMeshInstance3D.new()
		mmi0.multimesh = mm0
		mmi0.material_override = _lod0_material
		mmi0.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		mmi0.visibility_range_begin = 0.0
		mmi0.visibility_range_end = LOD0_MAX_DIST_M
		add_child(mmi0)

		var mmi1 := MultiMeshInstance3D.new()
		mmi1.multimesh = mm1
		mmi1.material_override = _lod1_material
		mmi1.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mmi1.visibility_range_begin = LOD0_MAX_DIST_M
		mmi1.visibility_range_end = LOD1_MAX_DIST_M
		add_child(mmi1)

		tile_cells[cell_idx] = {
			"lod0": mmi0,
			"lod1": mmi1,
			"count": count,
			"center": cell_center,
		}
		_active_tree_count += count

	_tiles[tile_key] = tile_cells


func remove_tile(tile_key: Vector2i) -> void:
	if not _tiles.has(tile_key):
		return
	var tile_cells: Dictionary = _tiles[tile_key]
	for cell_idx in tile_cells.keys():
		var cell_info: Dictionary = tile_cells[cell_idx]
		_active_tree_count -= int(cell_info["count"])
		var mmi0: MultiMeshInstance3D = cell_info["lod0"]
		var mmi1: MultiMeshInstance3D = cell_info["lod1"]
		if mmi0 != null:
			if mmi0.get_parent() == self:
				remove_child(mmi0)
			mmi0.free()
		if mmi1 != null:
			if mmi1.get_parent() == self:
				remove_child(mmi1)
			mmi1.free()
	_tiles.erase(tile_key)


func clear() -> void:
	for tile_key in _tiles.keys():
		var tile_cells: Dictionary = _tiles[tile_key]
		for cell_idx in tile_cells.keys():
			var cell_info: Dictionary = tile_cells[cell_idx]
			var mmi0: MultiMeshInstance3D = cell_info["lod0"]
			var mmi1: MultiMeshInstance3D = cell_info["lod1"]
			if mmi0 != null:
				if mmi0.get_parent() == self:
					remove_child(mmi0)
				mmi0.free()
			if mmi1 != null:
				if mmi1.get_parent() == self:
					remove_child(mmi1)
				mmi1.free()
	_tiles.clear()
	_active_tree_count = 0


## Vérifie et applique le budget d'instances en retirant les cases les plus lointaines.
func enforce_budget(cam_pos: Vector3) -> void:
	if _active_tree_count <= _budget:
		return

	# Collecter toutes les cases actives avec leur distance au point de vue
	var all_cells := []
	for tile_key in _tiles.keys():
		var tile_cells: Dictionary = _tiles[tile_key]
		for cell_idx in tile_cells.keys():
			var cell_info: Dictionary = tile_cells[cell_idx]
			var dist: float = (cell_info["center"] as Vector3).distance_to(cam_pos)
			all_cells.append({"tile_key": tile_key, "cell_idx": cell_idx, "dist": dist, "cell": cell_info})

	all_cells.sort_custom(func(a, b) -> bool: return a["dist"] > b["dist"])

	for item in all_cells:
		if _active_tree_count <= _budget:
			break
		var cell_info: Dictionary = item["cell"]
		_active_tree_count -= int(cell_info["count"])
		var mmi0: MultiMeshInstance3D = cell_info["lod0"]
		var mmi1: MultiMeshInstance3D = cell_info["lod1"]
		if mmi0 != null:
			if mmi0.get_parent() == self:
				remove_child(mmi0)
			mmi0.free()
		if mmi1 != null:
			if mmi1.get_parent() == self:
				remove_child(mmi1)
			mmi1.free()
		_tiles[item["tile_key"]].erase(item["cell_idx"])


# --- Génération des maillages LOD 0 et LOD 1 ---

static func build_lod0_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var trunk_col := Color(0.35, 0.22, 0.12)
	var sides := 6

	# Tronc (6 faces latérales = 12 triangles)
	for i in range(sides):
		var a0 := TAU * float(i) / sides
		var a1 := TAU * float(i + 1) / sides
		var cos0 := cos(a0)
		var sin0 := sin(a0)
		var cos1 := cos(a1)
		var sin1 := sin(a1)
		var p00 := Vector3(cos0 * 0.25, 0.0, sin0 * 0.25)
		var p10 := Vector3(cos1 * 0.25, 0.0, sin1 * 0.25)
		var p01 := Vector3(cos0 * 0.18, 1.8, sin0 * 0.18)
		var p11 := Vector3(cos1 * 0.18, 1.8, sin1 * 0.18)
		var n := Vector3((cos0 + cos1) * 0.5, 0.0, (sin0 + sin1) * 0.5).normalized()

		st.set_color(trunk_col)
		st.set_normal(n)
		st.add_vertex(p00)
		st.set_color(trunk_col)
		st.set_normal(n)
		st.add_vertex(p10)
		st.set_color(trunk_col)
		st.set_normal(n)
		st.add_vertex(p01)

		st.set_color(trunk_col)
		st.set_normal(n)
		st.add_vertex(p10)
		st.set_color(trunk_col)
		st.set_normal(n)
		st.add_vertex(p11)
		st.set_color(trunk_col)
		st.set_normal(n)
		st.add_vertex(p01)

	# Feuillage : 3 cônes empilés (3 x 6 x 2 = 36 triangles)
	# Total = 48 triangles (bien inférieur au plafond de 120 triangles)
	var cones := [
		{"y0": 1.2, "r": 1.5, "y1": 3.2},
		{"y0": 2.2, "r": 1.2, "y1": 4.2},
		{"y0": 3.2, "r": 0.8, "y1": 5.4},
	]
	var foliage_col := Color(0.18, 0.40, 0.18)
	for c in cones:
		var y0: float = c["y0"]
		var r: float = c["r"]
		var y1: float = c["y1"]
		var tip := Vector3(0.0, y1, 0.0)
		for i in range(sides):
			var a0 := TAU * float(i) / sides
			var a1 := TAU * float(i + 1) / sides
			var p0 := Vector3(cos(a0) * r, y0, sin(a0) * r)
			var p1 := Vector3(cos(a1) * r, y0, sin(a1) * r)
			var n := (p0 - tip).cross(p1 - tip).normalized()

			st.set_color(foliage_col)
			st.set_normal(n)
			st.add_vertex(p0)
			st.set_color(foliage_col)
			st.set_normal(n)
			st.add_vertex(p1)
			st.set_color(foliage_col)
			st.set_normal(n)
			st.add_vertex(tip)

			var n_down := Vector3.DOWN
			st.set_color(foliage_col * 0.8)
			st.set_normal(n_down)
			st.add_vertex(Vector3(0.0, y0, 0.0))
			st.set_color(foliage_col * 0.8)
			st.set_normal(n_down)
			st.add_vertex(p1)
			st.set_color(foliage_col * 0.8)
			st.set_normal(n_down)
			st.add_vertex(p0)

	return st.commit()


static func build_lod1_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var col := Color(0.20, 0.38, 0.18)
	var w := 1.4
	var h := 5.4

	# Quad 1 (dans le plan X-Y)
	var p0 := Vector3(-w, 0.0, 0.0)
	var p1 := Vector3(w, 0.0, 0.0)
	var p2 := Vector3(w, h, 0.0)
	var p3 := Vector3(-w, h, 0.0)
	var n1 := Vector3.FORWARD

	st.set_color(col); st.set_normal(n1); st.add_vertex(p0)
	st.set_color(col); st.set_normal(n1); st.add_vertex(p1)
	st.set_color(col); st.set_normal(n1); st.add_vertex(p2)
	st.set_color(col); st.set_normal(n1); st.add_vertex(p0)
	st.set_color(col); st.set_normal(n1); st.add_vertex(p2)
	st.set_color(col); st.set_normal(n1); st.add_vertex(p3)

	# Quad 2 (dans le plan Z-Y)
	var q0 := Vector3(0.0, 0.0, -w)
	var q1 := Vector3(0.0, 0.0, w)
	var q2 := Vector3(0.0, h, w)
	var q3 := Vector3(0.0, h, -w)
	var n2 := Vector3.RIGHT

	st.set_color(col); st.set_normal(n2); st.add_vertex(q0)
	st.set_color(col); st.set_normal(n2); st.add_vertex(q1)
	st.set_color(col); st.set_normal(n2); st.add_vertex(q2)
	st.set_color(col); st.set_normal(n2); st.add_vertex(q0)
	st.set_color(col); st.set_normal(n2); st.add_vertex(q2)
	st.set_color(col); st.set_normal(n2); st.add_vertex(q3)

	return st.commit()
