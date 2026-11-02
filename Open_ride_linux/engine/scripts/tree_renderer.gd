extends Node3D

## Gestionnaire et affichage de la végétation par tuiles (Lot E3 §4.3, Lot E4 §4.3, SRS §8).
## Pas de class_name (charger par preload).
##
## Découpe chaque tuile proche de 1 000 m en 16 cases de 250 m × 250 m.
## Chaque case avec arbres possède deux MultiMeshInstance3D :
## - LOD 0 (0 à 450 m) : modèle polygonal bas (tronc + cônes, <= 120 triangles), ombres actives.
## - LOD 1 (450 à 1 500 m) : quadrilatères croisés (4 triangles), sans ombre.
## Le budget global d'instances (QualityPresets.tree_budget) est respecté en éliminant les cases
## les plus éloignées en cas de dépassement.
## Vent (Lot P5) : quand `QualityPresets.living(preset).tree_sway` est vrai, les deux LOD utilisent le
## shader `tree_sway.gdshader` ; sinon les StandardMaterial3D d'origine (rendu inchangé).
## `apply_wind(eval)` met à jour une fois par image les paramètres globaux du vent du shader.
## Biomes (lot U7) : avec `biome_model` actif (couche biome ou forçage), la densité et la limite des
## arbres suivent les biomes de la tuile et chaque arbre reçoit une espèce (tree_species.gd) ; une case
## a alors une paire de MultiMeshInstance3D par espèce présente (`parts`). Sans biome : rendu inchangé.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const ViewCulling := preload("res://scripts/view_culling.gd")
const TreeSwayShader := preload("res://shaders/tree_sway.gdshader")
const TreeSpecies := preload("res://scripts/tree_species.gd")
const LOD1_SWAY_FACTOR := 0.6   # amplitude réduite des panneaux croisés du LOD 1

const CELL_SIZE_M := 250.0
const CELLS_PER_TILE := 4   # 4 x 4 = 16 cases par tuile de 1000 m
## Bascule LOD 0 → LOD 1 éloignée de 300 à 450 m (demande user 01/11 : simplification trop proche).
const LOD0_MAX_DIST_M := 450.0
const LOD1_MAX_DIST_M := 1500.0
## Lot S1 : distance ajoutée au rang d'une case hors du champ, pour qu'elle passe avant toute case visible.
const OUT_OF_VIEW_RANK_M := 1.0e6
## Distance minimale entre un tronc et le mur d'un bâtiment OSM (houppier compris).
const BUILDING_CLEARANCE_M := 3.0

# Constantes de région pour le semis hors polygones OSM (Lot E4 §4.3)
const REGION_OSM_COVERAGE_FACTOR := 0.8
const REGION_OSM_THRESHOLD := 0.4
const REGION_BUILDINGS_THRESHOLD := 0.1
const REGION_TREELINE_MARGIN_M := 300.0

var placer := VegetationPlacer.new()
var _lod0_mesh: ArrayMesh
var _lod1_mesh: ArrayMesh
var _lod0_material: Material
var _lod1_material: Material
var _tree_sway := false
## Modèle de biome (biome_model.gd) ; null ou inactif : végétation d'avant la série U.
var biome_model = null
## (x, z) -> vrai près de l'eau (oasis des déserts) ; invalide : aucun palmier au désert.
var near_water := Callable()
## Maillages et matériaux par espèce, construits à la première rencontre : { index: {lod0, lod1, m0, m1} }.
var _species := {}

## { tile_key: { cell_idx: { lod0: MultiMeshInstance3D, lod1: MultiMeshInstance3D, count: int, center: Vector3 } } }
var _tiles: Dictionary = {}
var _active_tree_count := 0
var _budget := 20000
## Temps des étapes du dernier `prepare_tile`, en ms (lot O1) : placement (détail de
## `placer.last_profile`), semis hors zones OSM, bâtiments, répartition en cases.
var last_profile := {}


func _init() -> void:
	_init_materials()
	_lod0_mesh = build_lod0_mesh()
	_lod1_mesh = build_lod1_mesh()


func _init_materials() -> void:
	if _tree_sway:
		_lod0_material = sway_material(false)
		_lod1_material = sway_material(true)
		return
	_lod0_material = StandardMaterial3D.new()
	_lod0_material.vertex_color_use_as_albedo = true
	_lod0_material.roughness = 0.85

	_lod1_material = StandardMaterial3D.new()
	_lod1_material.vertex_color_use_as_albedo = true
	_lod1_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	_lod1_material.roughness = 0.85


func set_preset(preset_name: String, living_enabled: bool = true) -> void:
	_budget = QualityPresets.tree_budget(preset_name)
	var sway: bool = QualityPresets.living(preset_name, living_enabled)["tree_sway"]
	if sway != _tree_sway:
		_tree_sway = sway
		_init_materials()
		_species.clear()
		for tile_cells in _tiles.values():
			for cell_info in tile_cells.values():
				for part in cell_info["parts"]:
					var look := _look(int(part["species"]))
					(part["lod0"] as MultiMeshInstance3D).material_override = look["m0"]
					(part["lod1"] as MultiMeshInstance3D).material_override = look["m1"]


func is_tree_sway() -> bool:
	return _tree_sway


## Shader des panneaux croisés (copie cull_disabled de tree_sway.gdshader), un seul pour tous les
## matériaux : un Shader par matériau ferait compiler autant de fois les mêmes pipelines (lot Y8 étape 2).
static var _lod1_shader: Shader


## Matériau de balancement (Lot P5) ; `lod1` : panneaux croisés vus des deux côtés, amplitude réduite.
static func sway_material(lod1: bool) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	if lod1:
		if _lod1_shader == null:
			_lod1_shader = Shader.new()
			_lod1_shader.code = TreeSwayShader.code.replace("render_mode cull_back;", "render_mode cull_disabled;")
		mat.shader = _lod1_shader
		mat.set_shader_parameter("sway_amplitude_m", 0.45 * LOD1_SWAY_FACTOR)
	else:
		mat.shader = TreeSwayShader
	return mat


## Maillages et matériaux d'une espèce (GENERIC : arbre d'avant la série U).
func _look(index: int) -> Dictionary:
	if index == TreeSpecies.GENERIC:
		return {"lod0": _lod0_mesh, "lod1": _lod1_mesh, "m0": _lod0_material, "m1": _lod1_material}
	if not _species.has(index):
		var built := TreeSpecies.build(TreeSpecies.kind_of(index))
		var m0: Material = _lod0_material
		var m1: Material = _lod1_material
		if _tree_sway:
			m0 = sway_material(false)
			m1 = sway_material(true)
			for m in [m0, m1]:
				(m as ShaderMaterial).set_shader_parameter("sway_height_m", float(built["height"]))
		_species[index] = {"lod0": built["lod0"], "lod1": built["lod1"], "m0": m0, "m1": m1}
	return _species[index]


## Met à jour en un appel par image le vent de tous les arbres et touffes (sortie de wind_model.evaluate).
## Les quatre paramètres globaux (`wind_dir`, `wind_strength`, `wind_gust`, `wind_phase`) sont déclarés
## dans `project.godot` ([shader_globals]).
static func apply_wind(wind_eval: Dictionary) -> void:
	RenderingServer.global_shader_parameter_set("wind_dir", wind_eval.get("dir", Vector3.ZERO))
	RenderingServer.global_shader_parameter_set("wind_strength", float(wind_eval.get("strength", 0.0)))
	RenderingServer.global_shader_parameter_set("wind_gust", float(wind_eval.get("gust", 0.0)))
	RenderingServer.global_shader_parameter_set("wind_phase", float(wind_eval.get("phase", 0.0)))


func get_active_tree_count() -> int:
	return _active_tree_count


## Génère les données de placement des arbres d'une tuile (exécutable en thread secondaire).
## `heights` : hauteurs réelles (pente, limite des arbres et biomes jugés sur le vrai relief) ; les arbres gardés sont
## posés à la hauteur affichée de la route (`route.display_y`, relief exagéré des lots Q2 et Y15).
## Renvoie un dictionnaire avec la clé de tuile et les listes d'arbres par case [0..15].
func prepare_tile(tile_x: int, tile_z: int, heights: PackedFloat32Array, route, theme: Dictionary,
		density_factor: float, areas: Array = [], buildings: Array = []) -> Dictionary:
	var t_start := Time.get_ticks_usec()
	# Seule la section `vegetation` change : copie superficielle du thème, copie de cette section.
	var tile_theme := theme.duplicate()
	var veg = tile_theme.get("vegetation", {})
	veg = veg.duplicate(true) if typeof(veg) == TYPE_DICTIONARY else {}
	var base_dens = veg.get("max_density_per_ha", VegetationPlacer.DEFAULT_MAX_DENSITY)
	veg["max_density_per_ha"] = float(base_dens) * clampf(density_factor, 0.0, 1.0)
	var biomes_on: bool = biome_model != null and biome_model.active()
	if biomes_on:
		# Placement à la densité du biome le plus dense de la tuile, puis éclaircie par biome (assign_species).
		var dens := 0.0
		var treeline := -INF
		for b in biome_model.top_biomes(tile_x, tile_z, 4).keys():
			var bv: Dictionary = biome_model.params(b)["vegetation"]
			dens = maxf(dens, float(bv["max_density_per_ha"]))
			treeline = maxf(treeline, 1.0e6 if bv["treeline_m"] == null else float(bv["treeline_m"]))
		veg["max_density_per_ha"] = dens * clampf(density_factor, 0.0, 1.0)
		veg["treeline_m"] = treeline
	tile_theme["vegetation"] = veg

	var height_fn: Callable
	if heights.is_empty():
		var flat_alt := 0.0
		if route != null and route.n > 0:
			flat_alt = route.alt_m[0]
		height_fn = func(_x: float, _z: float) -> float: return flat_alt
	else:
		var h0 := heights[0]
		# Optimisation terrain plat (évite interpolation bilinéaire inutile pour sol uniforme)
		if heights[heights.size() - 1] == h0 and heights[heights.size() / 2] == h0 and heights[101] == h0 and heights[1020] == h0:
			height_fn = func(_x: float, _z: float) -> float: return h0
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
	var t_place := Time.get_ticks_usec()
	var trees: PackedVector4Array = placer.place_tile(tile_x, tile_z, 1000.0, height_fn, route, tile_theme, areas)
	var place_profile: Dictionary = placer.last_profile

	# 2. Si des zones OSM existent, semer également au hasard hors des zones (Lot E4 §4.3)
	var t_region := Time.get_ticks_usec()
	if not areas.is_empty():
		var noise_trees: PackedVector4Array = placer.place_tile(tile_x, tile_z, 1000.0, height_fn, route, tile_theme, [])
		var treeline: float = float(veg.get("treeline_m", VegetationPlacer.DEFAULT_TREELINE_M))
		# Anneaux extérieurs des zones convertis une fois par tuile, avec leur boîte englobante
		# (un point hors de la boîte est hors de l'anneau).
		var rings: Array[PackedVector2Array] = []
		var boxes := PackedFloat64Array()   # (x min, z min, x max, z max) par anneau
		for area in areas:
			if typeof(area) == TYPE_DICTIONARY:
				var outer = area.get("outer", [])
				if typeof(outer) == TYPE_ARRAY and outer.size() >= 3:
					var ring := VegetationPlacer._packed_ring(outer)
					var lo := Vector2(INF, INF)
					var hi := Vector2(-INF, -INF)
					for q in ring:
						lo = lo.min(q)
						hi = hi.max(q)
					rings.append(ring)
					boxes.append_array([lo.x, lo.y, hi.x, hi.y])
		for tree in noise_trees:
			var px := tree.x
			var pz := tree.z
			var y := tree.y
			# Vérifier que l'arbre n'est pas dans une zone OSM
			var inside_osm := false
			for r in range(rings.size()):
				if px < boxes[4 * r] or pz < boxes[4 * r + 1] or px > boxes[4 * r + 2] or pz > boxes[4 * r + 3]:
					continue
				if VegetationPlacer._in_ring(px, pz, rings[r]):
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

	# 3. Aucun arbre dans un bâtiment OSM ni à moins de BUILDING_CLEARANCE_M de ses murs
	#    (défaut vu au banc simulé le 25 octobre : sapins plantés dans les maisons des villages).
	var t_buildings := Time.get_ticks_usec()
	if not buildings.is_empty():
		trees = exclude_buildings(trees, buildings)
	var tree_species := PackedByteArray()
	if biomes_on:
		var assigned := VegetationPlacer.assign_species(trees, biome_model, float(veg["max_density_per_ha"]) / maxf(clampf(density_factor, 0.0, 1.0), 1e-6), near_water)
		trees = assigned["trees"]
		tree_species = assigned["species"]
	if route != null and route.relief_k != 1.0:
		for k in range(trees.size()):
			var tr := trees[k]
			trees[k] = Vector4(tr.x, route.display_y(tr.y), tr.z, tr.w)
	var t_cells := Time.get_ticks_usec()

	# Répartition des arbres dans les 16 cases de 250 m x 250 m
	var tile_origin_x := float(tile_x * 1000)
	var tile_origin_z := float(tile_z * 1000)
	var cells: Array[PackedVector4Array] = []
	var cell_species: Array[PackedByteArray] = []
	for i in range(16):
		cells.append(PackedVector4Array())
		cell_species.append(PackedByteArray())

	for k in range(trees.size()):
		var tree := trees[k]
		var cx := clampi(int(floor((tree.x - tile_origin_x) / CELL_SIZE_M)), 0, CELLS_PER_TILE - 1)
		var cz := clampi(int(floor((tree.z - tile_origin_z) / CELL_SIZE_M)), 0, CELLS_PER_TILE - 1)
		var cell_idx := cz * CELLS_PER_TILE + cx
		cells[cell_idx].append(tree)
		cell_species[cell_idx].append(tree_species[k] if biomes_on else TreeSpecies.GENERIC)

	var t_end := Time.get_ticks_usec()
	last_profile = {
		"total_ms": (t_end - t_start) / 1000.0,
		"placement_ms": (t_region - t_place) / 1000.0,
		"placement": place_profile,
		"hors_zones_ms": (t_buildings - t_region) / 1000.0,
		"batiments_ms": (t_cells - t_buildings) / 1000.0,
		"cases_ms": (t_end - t_cells) / 1000.0,
		"arbres": trees.size(),
	}
	return {
		"tile_x": tile_x,
		"tile_z": tile_z,
		"tile_key": Vector2i(tile_x, tile_z),
		"cells": cells,
		"species": cell_species,
		"tile_origin": Vector3(tile_origin_x, 0.0, tile_origin_z),
	}


## Retire les arbres situés dans l'emprise d'un bâtiment (anneau `outer`) ou à moins de
## BUILDING_CLEARANCE_M de ses murs. Exécutable en thread secondaire.
static func exclude_buildings(trees: PackedVector4Array, buildings: Array) -> PackedVector4Array:
	var rings: Array[PackedVector2Array] = []
	var boxes: Array[Rect2] = []
	for b in buildings:
		if typeof(b) != TYPE_DICTIONARY:
			continue
		var outer = b.get("outer", [])
		if typeof(outer) != TYPE_ARRAY or outer.size() < 3:
			continue
		rings.append(VegetationPlacer._packed_ring(outer))
		boxes.append(VegetationPlacer._ring_bounds(outer).grow(BUILDING_CLEARANCE_M))
	if rings.is_empty():
		return trees
	var out := PackedVector4Array()
	for tree in trees:
		var p := Vector2(tree.x, tree.z)
		var blocked := false
		for i in range(rings.size()):
			if not boxes[i].has_point(p):
				continue
			if VegetationPlacer._in_ring(p.x, p.y, rings[i]) or _ring_distance(p, rings[i]) < BUILDING_CLEARANCE_M:
				blocked = true
				break
		if not blocked:
			out.append(tree)
	return out


static func _ring_distance(p: Vector2, ring: PackedVector2Array) -> float:
	var best := INF
	var n := ring.size()
	for i in range(n):
		var q := Geometry2D.get_closest_point_to_segment(p, ring[i], ring[(i + 1) % n])
		best = minf(best, p.distance_to(q))
	return best


## Instancie les MultiMesh pour une tuile préparée (doit être appelé sur le fil principal).
func add_tile(data: Dictionary) -> void:
	var tile_key: Vector2i = data["tile_key"]
	if _tiles.has(tile_key):
		remove_tile(tile_key)

	var tile_cells := {}
	var cells_data: Array = data["cells"]
	var species_data: Array = data.get("species", [])
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

		# Arbres de la case groupés par espèce (une seule espèce, GENERIC, sans biome).
		var groups := {}
		var sp: PackedByteArray = species_data[cell_idx] if cell_idx < species_data.size() else PackedByteArray()
		for i in range(tree_list.size()):
			var key := int(sp[i]) if i < sp.size() else TreeSpecies.GENERIC
			if not groups.has(key):
				groups[key] = []   # Array (référence) : un tableau compact serait copié par groups[key]
			(groups[key] as Array).append(tree_list[i])

		var parts := []
		var keys := groups.keys()
		keys.sort()
		for key in keys:
			parts.append(_make_part(int(key), PackedVector4Array(groups[key])))

		tile_cells[cell_idx] = {
			"parts": parts,
			"count": tree_list.size(),
			"center": cell_center,
		}
		_active_tree_count += tree_list.size()

	_tiles[tile_key] = tile_cells


## Paire de MultiMeshInstance3D (LOD 0 et LOD 1) des arbres d'une espèce dans une case.
func _make_part(species: int, tree_list: PackedVector4Array) -> Dictionary:
	var look := _look(species)
	var count := tree_list.size()
	var mm0 := MultiMesh.new()
	mm0.transform_format = MultiMesh.TRANSFORM_3D
	mm0.use_colors = true
	mm0.mesh = look["lod0"]
	mm0.instance_count = count
	var mm1 := MultiMesh.new()
	mm1.transform_format = MultiMesh.TRANSFORM_3D
	mm1.use_colors = true
	mm1.mesh = look["lod1"]
	mm1.instance_count = count
	var vine := species == TreeSpecies.index_of("vine_row")

	for i in range(count):
		var t := tree_list[i]
		var px := t.x
		var py := t.y
		var pz := t.z
		var scale_f := t.w

		var h_rot := VegetationPlacer.hash3(0x5EED, int(px), int(pz))
		var angle := float(h_rot & 0xFFFF) / 65536.0 * TAU
		if vine:
			# Rangs de vigne parallèles dans toute la case (orientation tirée par case de 250 m).
			angle = float(VegetationPlacer.hash3(0x7111, int(floor(px / CELL_SIZE_M)), int(floor(pz / CELL_SIZE_M))) & 0x3) * 0.25 * PI
			scale_f = 1.0
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
	mmi0.material_override = look["m0"]
	mmi0.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	mmi0.visibility_range_begin = 0.0
	mmi0.visibility_range_end = LOD0_MAX_DIST_M
	add_child(mmi0)

	var mmi1 := MultiMeshInstance3D.new()
	mmi1.multimesh = mm1
	mmi1.material_override = look["m1"]
	mmi1.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mmi1.visibility_range_begin = LOD0_MAX_DIST_M
	mmi1.visibility_range_end = LOD1_MAX_DIST_M
	add_child(mmi1)
	return {"lod0": mmi0, "lod1": mmi1, "species": species, "count": count}


func _free_cell(cell_info: Dictionary) -> void:
	for part in cell_info["parts"]:
		for key in ["lod0", "lod1"]:
			var mmi: MultiMeshInstance3D = part[key]
			if mmi != null:
				if mmi.get_parent() == self:
					remove_child(mmi)
				mmi.free()


func remove_tile(tile_key: Vector2i) -> void:
	if not _tiles.has(tile_key):
		return
	var tile_cells: Dictionary = _tiles[tile_key]
	for cell_idx in tile_cells.keys():
		var cell_info: Dictionary = tile_cells[cell_idx]
		_active_tree_count -= int(cell_info["count"])
		_free_cell(cell_info)
	_tiles.erase(tile_key)


func clear() -> void:
	for tile_key in _tiles.keys():
		var tile_cells: Dictionary = _tiles[tile_key]
		for cell_idx in tile_cells.keys():
			_free_cell(tile_cells[cell_idx])
	_tiles.clear()
	_active_tree_count = 0


## Vérifie et applique le budget d'instances en retirant les cases les plus lointaines. Lot S1 : avec la
## vue de la caméra active (view_culling.gd), les cases hors du champ partent avant celles du champ.
func enforce_budget(cam_pos: Vector3, view: Dictionary = {}) -> void:
	if _active_tree_count <= _budget:
		return

	# Collecter toutes les cases actives avec leur distance au point de vue
	var all_cells := []
	for tile_key in _tiles.keys():
		var tile_cells: Dictionary = _tiles[tile_key]
		for cell_idx in tile_cells.keys():
			var cell_info: Dictionary = tile_cells[cell_idx]
			var center: Vector3 = cell_info["center"]
			var dist: float = center.distance_to(cam_pos)
			if not view.is_empty() and not ViewCulling.rect_in_view(Rect2(center.x - CELL_SIZE_M * 0.5,
					center.z - CELL_SIZE_M * 0.5, CELL_SIZE_M, CELL_SIZE_M), view):
				dist += OUT_OF_VIEW_RANK_M
			all_cells.append({"tile_key": tile_key, "cell_idx": cell_idx, "dist": dist, "cell": cell_info})

	all_cells.sort_custom(func(a, b) -> bool: return a["dist"] > b["dist"])

	for item in all_cells:
		if _active_tree_count <= _budget:
			break
		var cell_info: Dictionary = item["cell"]
		_active_tree_count -= int(cell_info["count"])
		_free_cell(cell_info)
		_tiles[item["tile_key"]].erase(item["cell_idx"])


# --- Génération des maillages LOD 0 et LOD 1 ---

static func build_lod0_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var trunk_col := TreeSpecies.mat(Color(0.35, 0.22, 0.12), TreeSpecies.MAT_BARK)
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
	var foliage_col := TreeSpecies.mat(Color(0.18, 0.40, 0.18), TreeSpecies.MAT_NEEDLES)
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
			st.set_color(TreeSpecies.shade(foliage_col, 0.8))
			st.set_normal(n_down)
			st.add_vertex(Vector3(0.0, y0, 0.0))
			st.set_color(TreeSpecies.shade(foliage_col, 0.8))
			st.set_normal(n_down)
			st.add_vertex(p1)
			st.set_color(TreeSpecies.shade(foliage_col, 0.8))
			st.set_normal(n_down)
			st.add_vertex(p0)

	return st.commit()


static func build_lod1_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var col := TreeSpecies.mat(Color(0.20, 0.38, 0.18), TreeSpecies.MAT_NEEDLES)
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
