extends Node3D

## Forêts lointaines en imposteurs (lot Y5, cahier docs/lots/LOT_Y5_arbres_lointains_imposteurs.md).
## Pas de class_name (charger par preload).
##
## Les arbres de tree_renderer.gd s'arrêtent à 1 500 m (LOD 1) ; le brouillard ne se ferme qu'à 4, 6 ou 9 km.
## Ce nœud garnit les tuiles lointaines du terrain (5 km, maille 50 m) de bouquets d'arbres, chacun dessiné par
## un seul quadrilatère tourné vers la caméra (tree_impostor.gdshader), de 1 500 m à la fin du brouillard.
##
## Placement (prepare_tile, exécutable dans une tâche de fond) : grille à tirage décalé de STEP_M ; chaque
## bouquet couvre STEP_M × STEP_M et représente les arbres de cette surface. Il est gardé avec la probabilité
## de couverture du sol par les houppiers, 1 − exp(−densité × surface d'un houppier), où la densité est celle
## des arbres proches au même endroit : densité du biome (ou du thème 1.x) × moitié du maximum × même bruit
## de densité (VegetationPlacer.density_noise). Les forêts lointaines continuent donc les forêts proches.
## Espèce tirée comme pour les arbres proches (biome selon les poids du point, puis `weight` des espèces) ;
## plantes basses (houppier `box` de TreeSpecies.CROWNS) écartées. Exclusions : couloir de la route, pente
## du terrain au-dessus du seuil du thème, altitude au-dessus de la limite des arbres du biome.
## Hauteur : terrain lointain réel (avant l'enfoncement sous le proche), au relief affiché (route.display_y),
## FAR_DROP_M et SINK_M plus bas que le sol pour ne jamais flotter.
##
## Affichage (add_tile) : par case de CELL_M, un MultiMeshInstance3D (tampon rempli d'un bloc, boîte
## `custom_aabb` posée, sans ombre) ; instances rangées par tirage, `visible_instance_count` donne la part
## affichée du préréglage (QualityPresets.forest_fraction). Distances exactes par instance dans le shader.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const TreeSpecies := preload("res://scripts/tree_species.gd")
const BiomeIds := preload("res://scripts/biome_ids.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const ImpostorShader := preload("res://shaders/tree_impostor.gdshader")

## Début des imposteurs : fin du LOD 1 des arbres proches (tree_renderer.gd LOD1_MAX_DIST_M).
const BEGIN_M := 1500.0
## Entrée progressive des bouquets après BEGIN_M (un seuil par bouquet).
const FADE_M := 250.0
## Pas de la grille des bouquets et largeur d'un bouquet (recouvrement : forêt continue vue de loin).
const STEP_M := 32.0
const CLUMP_WIDTH_M := STEP_M * 1.3
## Cases d'affichage (alignées sur les tuiles proches : 25 par tuile lointaine).
const CELL_M := 1000.0
## Pied des bouquets sous le sol lointain dessiné (déjà FAR_DROP_M sous ses valeurs).
const SINK_M := 1.0
## Plus petit arbre gardé (m) : en dessous, invisible au-delà de 1,5 km.
const MIN_HEIGHT_M := 3.0
## Surface du plus grand houppier de TreeSpecies.CROWNS (10 m de large), borne du premier tri.
const MAX_CROWN_AREA_M2 := 80.0
## Arbre d'avant la série U (tree_renderer.build_lod0_mesh) : sapin de 5,4 m, couronne de 1,2 m à la cime.
const GENERIC_CROWN := {"w": 3.0, "col": Color(0.18, 0.40, 0.18), "shape": "cone", "cy": 1.2, "ry": 0.0}
const GENERIC_HEIGHT_M := 5.4
## Flottants par instance dans le tampon du MultiMesh : transformation 3 × 4, couleur, données propres.
const FLOATS_PER_INSTANCE := 20
## Préchauffage (banc PC du 6 novembre : 100 à 133 ms à la première forêt dessinée, juste après le départ) :
## un bouquet minuscule collé devant la caméra pendant WARM_FRAMES images au chargement du parcours, même
## MultiMesh et même shader, pour que le pipeline soit compilé avant la première vraie forêt.
const WARM_FRAMES := 5
const WARM_DIST_M := 2.0
const WARM_SIZE_M := 0.002

## Modèle de biome (biome_model.gd) ; null ou inactif : arbre d'avant la série U, densité du thème.
var biome_model = null
## (x, z) -> vrai près de l'eau (oasis des déserts) ; invalide : aucun palmier au désert (comme tree_renderer).
var near_water := Callable()
## Faux : aucune forêt lointaine (`--forest=off`, essai au banc).
var enabled := true
## Temps du dernier prepare_tile, en ms, et nombre de bouquets.
var last_profile := {}

var _fraction := 1.0
var _end_m := 6000.0
var _mesh: ArrayMesh
var _material: ShaderMaterial
## { Vector2i(tuile lointaine): [MultiMeshInstance3D, …] }
var _tiles := {}
var _count := 0
var _warm: MultiMeshInstance3D = null
var _warm_frames := 0


func _init() -> void:
	_mesh = build_quad()
	_material = ShaderMaterial.new()
	_material.shader = ImpostorShader
	_material.set_shader_parameter("begin_m", BEGIN_M)
	_material.set_shader_parameter("fade_m", FADE_M)
	_apply_end()


## Part affichée et fin du brouillard du préréglage ; s'applique aussi aux tuiles déjà construites.
func set_preset(preset_name: String) -> void:
	_fraction = clampf(QualityPresets.forest_fraction(preset_name), 0.0, 1.0)
	_end_m = QualityPresets.fog_end_m(preset_name)
	_apply_end()
	_count = 0
	for nodes in _tiles.values():
		for mmi in nodes:
			_apply_to(mmi)
			_count += (mmi as MultiMeshInstance3D).multimesh.visible_instance_count


func _apply_end() -> void:
	_material.set_shader_parameter("end_m", _end_m)


func _apply_to(mmi: MultiMeshInstance3D) -> void:
	var mm := mmi.multimesh
	mm.visible_instance_count = visible_count(mm.instance_count, _fraction)
	mmi.visible = _fraction > 0.0
	mmi.visibility_range_end = _end_m + CELL_M * 0.75


## Préchauffage au chargement du parcours (main.gd, comme segment_markers.warm_up) : un bouquet de
## WARM_SIZE_M à WARM_DIST_M devant `camera`, dessiné dès 0 m (matériau à part, même shader), retiré après
## WARM_FRAMES images. Sans caméra ou forêts coupées : rien. Retourne vrai si le bouquet est posé.
func warm_up(camera: Node3D) -> bool:
	_drop_warm()
	if camera == null or not enabled:
		return false
	var mat := ShaderMaterial.new()
	mat.shader = ImpostorShader
	mat.set_shader_parameter("begin_m", -1.0)
	mat.set_shader_parameter("fade_m", 0.0)
	mat.set_shader_parameter("end_m", 1.0e6)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.use_custom_data = true
	mm.mesh = _mesh
	mm.instance_count = 1
	mm.set_instance_transform(0, Transform3D(Basis().scaled(Vector3.ONE * WARM_SIZE_M), Vector3.ZERO))
	mm.set_instance_color(0, Color(0.2, 0.4, 0.2))
	mm.set_instance_custom_data(0, Color(0.5, 0.0, 0.3, 0.2))
	_warm = MultiMeshInstance3D.new()
	_warm.name = "ForestImpostorsWarm"
	_warm.multimesh = mm
	_warm.material_override = mat
	_warm.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_warm.position = Vector3(0.0, 0.0, -WARM_DIST_M)
	camera.add_child(_warm)
	_warm_frames = WARM_FRAMES
	return true


## Bouquet du préchauffage encore en scène (tests).
func is_warming() -> bool:
	return _warm != null


func _process(_delta: float) -> void:
	if _warm != null:
		_warm_frames -= 1
		if _warm_frames <= 0:
			_drop_warm()


func _drop_warm() -> void:
	if _warm != null:
		_warm.queue_free()
	_warm = null
	_warm_frames = 0


## Instances affichées pour une part donnée (les premières du tampon, rangées par tirage).
static func visible_count(count: int, fraction: float) -> int:
	return clampi(int(ceil(count * clampf(fraction, 0.0, 1.0))), 0, count)


func get_material() -> ShaderMaterial:
	return _material


## Bouquets affichés (part du préréglage comprise).
func get_count() -> int:
	return _count


func tile_count() -> int:
	return _tiles.size()


## Quadrilatère de base : x de −0,5 à 0,5, y de 0 à 1, face vers +z, UV (0, 0) en haut à gauche.
static func build_quad() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var corners := [Vector3(-0.5, 0.0, 0.0), Vector3(0.5, 0.0, 0.0), Vector3(0.5, 1.0, 0.0), Vector3(-0.5, 1.0, 0.0)]
	for k in [0, 1, 2, 0, 2, 3]:
		var c: Vector3 = corners[k]
		st.set_color(Color.WHITE)
		st.set_normal(Vector3.BACK)
		st.set_uv(Vector2(c.x + 0.5, 1.0 - c.y))
		st.add_vertex(c)
	return st.commit()


## Réglages d'un houppier vu de loin pour l'imposteur : forme (0 rond, 1 cône), pied de la couronne en part
## de la hauteur, demi-largeur d'un houppier en part de la largeur du bouquet, couleur sRGB, hauteur, surface
## du houppier. Vide pour une plante basse (à ne pas dessiner).
static func crown_look(kind: String) -> Dictionary:
	var crown: Dictionary
	var height: float
	if kind == "":
		crown = GENERIC_CROWN
		height = GENERIC_HEIGHT_M
	else:
		if not TreeSpecies.CROWNS.has(kind):
			return {}
		crown = TreeSpecies.CROWNS[kind]
		height = TreeSpecies.height_m(kind)
	var shape := str(crown["shape"])
	if shape == "box" or height < MIN_HEIGHT_M:
		return {}
	var w := float(crown["w"])
	var base := float(crown["cy"]) if shape == "cone" else float(crown["cy"]) - float(crown["ry"])
	var col: Color = crown["col"]
	return {
		"shape": 1.0 if shape == "cone" else 0.0,
		"base": clampf(base / height, 0.0, 0.9),
		"half": clampf(w * 0.5 / CLUMP_WIDTH_M * 1.15, 0.08, 0.4),
		"col": Color(col.r, col.g, col.b, 1.0),
		"height": height,
		"area": PI * w * w * 0.25,
	}


## Bouquets d'une tuile lointaine. `heights` : hauteurs de la tuile (101 × 101, maille 50 m) avant
## l'enfoncement sous le terrain proche. Renvoie {tile_key, cells: {index de case: {buffer, count, aabb}}, count},
## ou {} sans hauteurs ou coupé. Ne touche à aucun nœud : exécutable dans une tâche de fond.
func prepare_tile(tile_x: int, tile_z: int, heights: PackedFloat32Array, route, theme: Dictionary) -> Dictionary:
	if not enabled or heights.size() != TerrainTiles.SAMPLES * TerrainTiles.SAMPLES:
		return {}
	var t_start := Time.get_ticks_usec()
	var size: float = TerrainTiles.LEVELS["far"]["size"]
	var far_cell: float = TerrainTiles.LEVELS["far"]["cell"]
	var x0 := tile_x * size
	var z0 := tile_z * size
	var tile := Rect2(x0, z0, size, size)
	var theme_density := maxf(0.0, VegetationPlacer._theme_value(theme, "vegetation", "max_density_per_ha", VegetationPlacer.DEFAULT_MAX_DENSITY))
	var theme_treeline := VegetationPlacer._theme_value(theme, "vegetation", "treeline_m", VegetationPlacer.DEFAULT_TREELINE_M)
	var max_slope := tan(deg_to_rad(clampf(VegetationPlacer._theme_value(theme, "terrain", "slope_threshold_deg", VegetationPlacer.DEFAULT_SLOPE_DEG), 0.0, 89.9)))
	var corridor := VegetationPlacer._theme_value(theme, "road", "width_m", VegetationPlacer.DEFAULT_ROAD_WIDTH_M) * 0.5 \
		+ VegetationPlacer.ROAD_MARGIN_M + CLUMP_WIDTH_M * 0.5
	var biomes_on: bool = biome_model != null and biome_model.active()
	var model = biome_model
	# Borne haute de la densité (premier tri sur le seul bruit, avant tout calcul coûteux)
	var dens_cap := theme_density
	if biomes_on:
		dens_cap = 0.0
		for b in BiomeIds.BIOMES:
			dens_cap = maxf(dens_cap, float(model.params(b)["vegetation"]["max_density_per_ha"]))
	if dens_cap <= 0.0:
		return {}
	var k_cap := dens_cap * VegetationPlacer.NOISE_MAX_FRACTION / 10000.0 * MAX_CROWN_AREA_M2
	var roads := VegetationPlacer._road_buckets(route, tile, corridor)
	var generic := crown_look("")
	var looks := {}        # biome -> VegetationPlacer._species_look
	var crowns := {}       # indice d'espèce -> crown_look
	var forced: String = model.forced if biomes_on else ""
	# Grilles du bruit de densité (mêmes nœuds et mêmes opérations que VegetationPlacer._place_noise)
	var ns := VegetationPlacer.NOISE_SCALE_M
	var ns2 := VegetationPlacer.NOISE_SCALE2_M
	var ax0 := int(floor(x0 / ns)) - 1
	var az0 := int(floor(z0 / ns)) - 1
	var an := int(floor(tile.end.x / ns)) - ax0 + 3
	var anz := int(floor(tile.end.y / ns)) - az0 + 3
	var lat1 := VegetationPlacer._lattice(VegetationPlacer.NOISE_SEED, ax0, az0, an, anz)
	var bx0 := int(floor(x0 / ns2)) - 1
	var bz0 := int(floor(z0 / ns2)) - 1
	var bn := int(floor(tile.end.x / ns2)) - bx0 + 3
	var bnz := int(floor(tile.end.y / ns2)) - bz0 + 3
	var lat2 := VegetationPlacer._lattice(VegetationPlacer.NOISE_SEED + 1, bx0, bz0, bn, bnz)

	var per_side := int(round(size / STEP_M))
	var step := size / per_side
	var seed := VegetationPlacer.hash3(0xF0E5, tile_x, tile_z)
	var cells_per_side := int(round(size / CELL_M))
	var picked := {}   # index de case -> [[ordre, PackedFloat32Array de l'instance], …]
	var total := 0
	for j in range(per_side):
		var hj := VegetationPlacer._mix(seed ^ VegetationPlacer._mix(j ^ 0x9E3779B9))
		for i in range(per_side):
			var h := VegetationPlacer._mix(hj ^ i)
			var px := x0 + (i + VegetationPlacer._unit(h)) * step
			var pz := z0 + (j + VegetationPlacer._unit(VegetationPlacer._mix(h + 1))) * step
			var v := 0.65 * VegetationPlacer._lattice_noise(px / ns, pz / ns, lat1, ax0, az0, an)
			v += 0.35 * VegetationPlacer._lattice_noise(px / ns2, pz / ns2, lat2, bx0, bz0, bn)
			v = clampf(v, 0.0, 1.0)
			var draw := VegetationPlacer._unit(VegetationPlacer._mix(h + 3))
			if draw >= 1.0 - exp(-k_cap * v):
				continue
			# Pente lue sur la maille lointaine qui contient le bouquet
			var ci := clampi(int((px - x0) / far_cell), 0, TerrainTiles.CELLS - 1)
			var cj := clampi(int((pz - z0) / far_cell), 0, TerrainTiles.CELLS - 1)
			var h00 := heights[cj * TerrainTiles.SAMPLES + ci]
			var h10 := heights[cj * TerrainTiles.SAMPLES + ci + 1]
			var h01 := heights[(cj + 1) * TerrainTiles.SAMPLES + ci]
			var h11 := heights[(cj + 1) * TerrainTiles.SAMPLES + ci + 1]
			var gx := ((h10 + h11) - (h00 + h01)) / (2.0 * far_cell)
			var gz := ((h01 + h11) - (h00 + h10)) / (2.0 * far_cell)
			if not is_finite(gx) or not is_finite(gz) or sqrt(gx * gx + gz * gz) > max_slope:
				continue
			if not roads.is_empty() and VegetationPlacer._near_road(roads, px, pz, corridor):
				continue
			var y := TerrainTiles.mesh_height_at(heights, "far", tile_x, tile_z, px, pz)
			if not is_finite(y):
				continue
			# Espèce et densité du point (biome tiré selon les poids, comme VegetationPlacer.assign_species)
			var look_c: Dictionary = generic
			var density := theme_density
			var treeline := theme_treeline
			var hb := VegetationPlacer._mix(h + 7)
			if biomes_on:
				var weights: Dictionary = {forced: 1.0} if forced != "" else model.weights_at(px, pz)
				var bdraw := VegetationPlacer._unit(hb)
				var acc := 0.0
				var biome := ""
				for b in weights:
					acc += float(weights[b])
					biome = b
					if bdraw < acc:
						break
				if not looks.has(biome):
					looks[biome] = VegetationPlacer._species_look(model, biome)
				var look: Dictionary = looks[biome]
				density = float(look["density"])
				treeline = float(look["treeline"])
				if not look["generic"]:
					var cum: PackedFloat32Array = look["cum"]
					if cum.is_empty():
						continue
					var pick := VegetationPlacer._unit(VegetationPlacer._mix(hb + 23)) * cum[-1]
					var k := 0
					while k < cum.size() - 1 and pick >= cum[k]:
						k += 1
					var id: int = look["ids"][k]
					if id == look["palm"] and look["desert"] and not (near_water.is_valid() and bool(near_water.call(px, pz))):
						continue
					if not crowns.has(id):
						crowns[id] = crown_look(BiomeIds.SPECIES[id])
					look_c = crowns[id]
			if look_c.is_empty() or y > treeline:
				continue
			var cover := 1.0 - exp(-density * VegetationPlacer.NOISE_MAX_FRACTION / 10000.0 * float(look_c["area"]) * v)
			if draw >= cover:
				continue
			# Bouquet gardé : taille, teinte (même écart que les arbres proches) et graine
			var scale_f := 0.85 + 0.3 * VegetationPlacer._unit(VegetationPlacer._mix(h + 2))
			var tint := (VegetationPlacer._unit(VegetationPlacer._mix(h + 5)) - 0.5) * 0.16
			var col: Color = look_c["col"]
			var y_draw := y - TerrainTiles.FAR_DROP_M - SINK_M
			if route != null:
				y_draw = route.display_y(y) - TerrainTiles.FAR_DROP_M - SINK_M
			var inst := PackedFloat32Array([
				CLUMP_WIDTH_M, 0.0, 0.0, px,
				0.0, float(look_c["height"]) * scale_f, 0.0, y_draw,
				0.0, 0.0, 1.0, pz,
				col.r * (1.0 + tint), col.g * (1.0 + tint), col.b * (1.0 + tint), 1.0,
				VegetationPlacer._unit(VegetationPlacer._mix(h + 9)), float(look_c["shape"]), float(look_c["base"]), float(look_c["half"]),
			])
			var cx := clampi(int((px - x0) / CELL_M), 0, cells_per_side - 1)
			var cz := clampi(int((pz - z0) / CELL_M), 0, cells_per_side - 1)
			var cell_idx := cz * cells_per_side + cx
			if not picked.has(cell_idx):
				picked[cell_idx] = []
			(picked[cell_idx] as Array).append([VegetationPlacer._unit(VegetationPlacer._mix(h + 11)), inst])
			total += 1

	var cells := {}
	for cell_idx in picked:
		var items: Array = picked[cell_idx]
		# Rangés par tirage : les premières instances sont celles qu'une part réduite garde
		items.sort_custom(func(a, b) -> bool: return a[0] < b[0])
		var buf := PackedFloat32Array()
		var y_lo := INF
		var y_hi := -INF
		for it in items:
			var inst: PackedFloat32Array = it[1]
			buf.append_array(inst)
			y_lo = minf(y_lo, inst[7])
			y_hi = maxf(y_hi, inst[7] + inst[5])
		var cx := int(cell_idx) % cells_per_side
		var cz := int(cell_idx) / cells_per_side
		var lo := Vector3(x0 + cx * CELL_M - CLUMP_WIDTH_M, y_lo, z0 + cz * CELL_M - CLUMP_WIDTH_M)
		cells[cell_idx] = {"buffer": buf, "count": items.size(),
			"aabb": AABB(lo, Vector3(CELL_M + 2.0 * CLUMP_WIDTH_M, maxf(y_hi - y_lo, 1.0), CELL_M + 2.0 * CLUMP_WIDTH_M)),
			"center": Vector3(x0 + (cx + 0.5) * CELL_M, 0.5 * (y_lo + y_hi), z0 + (cz + 0.5) * CELL_M)}
	last_profile = {"total_ms": (Time.get_ticks_usec() - t_start) / 1000.0, "bouquets": total, "candidats": per_side * per_side}
	return {"tile_key": Vector2i(tile_x, tile_z), "cells": cells, "count": total}


## Crée les MultiMeshInstance3D d'une tuile préparée (fil principal).
func add_tile(data: Dictionary) -> void:
	if data.is_empty():
		return
	var key: Vector2i = data["tile_key"]
	remove_tile(key)
	var nodes := []
	var cells: Dictionary = data["cells"]
	var keys := cells.keys()
	keys.sort()
	for cell_idx in keys:
		var c: Dictionary = cells[cell_idx]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.use_custom_data = true
		mm.mesh = _mesh
		mm.instance_count = int(c["count"])
		mm.buffer = c["buffer"]
		mm.custom_aabb = c["aabb"]
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "foret_%d_%d_%d" % [key.x, key.y, int(cell_idx)]
		mmi.multimesh = mm
		mmi.material_override = _material
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mmi.custom_aabb = c["aabb"]
		# Case entière plus proche que le début ou plus loin que la fin : pas dessinée du tout
		mmi.visibility_range_begin = maxf(0.0, BEGIN_M - CELL_M * 0.75)
		_apply_to(mmi)
		add_child(mmi)
		nodes.append(mmi)
		_count += mm.visible_instance_count
	_tiles[key] = nodes


func remove_tile(key: Vector2i) -> void:
	if not _tiles.has(key):
		return
	for mmi in _tiles[key]:
		_count -= (mmi as MultiMeshInstance3D).multimesh.visible_instance_count
		remove_child(mmi)
		mmi.free()
	_tiles.erase(key)


func clear() -> void:
	for key in _tiles.keys():
		remove_tile(key)
	_tiles.clear()
	_count = 0
