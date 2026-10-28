extends Node3D

## Chargement par tronçons du ruban de route et des tuiles de terrain (lots E1 et E3).
##
## Fenêtre active, recalculée par update_window(s, v, caméra) à chaque image :
## - ruban : tronçons k dont l'intervalle [k × 1 000, (k + 1) × 1 000] touche (au sens strict)
##   [s − chunks_behind × 1 000 ; s + chunks_ahead × 1 000 + v × 10 s] ;
## - tuiles proches dont le carré passe à moins de 1 500 m de la caméra ou du point visé v × 10 s
##   plus loin ; tuiles lointaines présentes à moins de far_radius_m (fin du brouillard du préréglage
##   plus une tuile lointaine, au plus FAR_RADIUS_M = 12 km, lot Y1) ;
## - tuile proche manquante : rien si une tuile lointaine couvre l'endroit (elle est dessinée dessous),
##   sinon tuile plate à l'altitude de la route la plus proche (format §10) ;
## - lot S1 (`culling`, faux par défaut faute de gain mesuré, `--culling=on` pour l'essayer) : une tuile proche n'est voulue
##   que si elle est à moins de `culling_keep_m` de la caméra (distance des ombres plus une case d'arbres)
##   ou dans le champ de la caméra active, maintenant ou le long des prochains mètres de route
##   (view_culling.gd) ; les tuiles proches derrière la caméra ne sont ni construites, ni garnies d'arbres,
##   ni dessinées. Les tuiles lointaines restent toutes chargées : elles servent de fond si la vue change.
## Les tableaux de sommets se calculent dans WorkerThreadPool ; les ArrayMesh et MeshInstance3D se
## créent sur le fil principal, au plus MAX_NEW_PER_FRAME par image. Ce qui sort de la fenêtre est
## libéré tout de suite (free) ; un changement de parcours vide tout (set_world).
## Sans couche terrain : sol plat de 2 × far_radius_m de côté, 5 m sous l'altitude minimale de la route,
## qui suit la caméra.
## Pas de class_name (charger par preload).

const RoadBuilder := preload("res://scripts/road_builder.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const OsmLayers := preload("res://scripts/osm_layers.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const BiomeTextures := preload("res://scripts/biome_textures.gd")
const ViewCulling := preload("res://scripts/view_culling.gd")

const LOOKAHEAD_S := 10.0
const NEAR_RADIUS_M := 1500.0
const FAR_RADIUS_M := 12000.0
const MAX_NEW_PER_FRAME := 2
const MAX_RUNNING_TASKS := 4
const FLAT_GROUND_BELOW_M := 5.0
const FLAT_GROUND_COLOR := Color(0.33, 0.42, 0.28)

var route = null
var world_dir := ""
var has_terrain := false
var chunks_ahead: int = 3
var chunks_behind: int = 1
var vegetation_density_factor: float = 0.3
var visual_grade_scale: float = 1.0
## Rayon des tuiles lointaines et demi-côté du sol plat, réglé par render_quality.gd (far_radius_for).
var far_radius_m: float = FAR_RADIUS_M:
	set(value):
		far_radius_m = value
		if _ground != null and _ground.mesh is PlaneMesh:
			(_ground.mesh as PlaneMesh).size = Vector2(2.0 * far_radius_m, 2.0 * far_radius_m)
var tree_renderer: Node3D = null
## Lot S1 : tri des tuiles proches selon le champ de la caméra active ; rayon gardé tout autour réglé par
## render_quality.gd (ViewCulling.keep_radius_for, distance des ombres du préréglage).
var culling := false
var culling_keep_m: float = ViewCulling.keep_radius_for(150.0)
## Tuiles proches écartées par le dernier update_window (sonde X13, tests).
var culled_near := 0
## Contrôles du mode test (lot S1, `--test-mode`) : à chaque tuile proche instanciée, journal
## « [test] pop … » si elle apparaît dans le champ à moins de TEST_POP_DIST_M (apparition soudaine), et
## « [test] seam … » si son bord s'écarte de plus de TEST_SEAM_TOL_M de celui d'une tuile proche voisine.
var test_log := false
const TEST_POP_DIST_M := 1000.0
const TEST_SEAM_TOL_M := 0.05
var _view_now: Dictionary = {}
var _s_now := 0.0
var osm_streamer: Node3D = null
## Série U (lot U17, première partie) : biome forcé (`--biome=`, "auto" = données du parcours) et modèle de
## biome du parcours courant, créé par set_world et transmis aux arbres (U7) et aux animaux (U12). Sol
## multi-biome (U6) : chaque tuile de terrain reçoit un matériau de `biome_textures` (terrain_biomes.gdshader) ;
## le sol plat sans terrain prend la couleur du biome sous le départ (start_biome).
## Modèle inactif (ni couche biome ni forçage) : rendu d'avant la série U.
var forced_biome := "auto"
var biome_model = null
var biome_textures = null
## Préréglage de qualité (render_quality.gd) : 3 ou 4 biomes par tuile et côté des textures de sol (U-Q4).
var quality_preset := "":
	set(value):
		if value == quality_preset:
			return
		quality_preset = value
		if biome_textures != null:
			_make_biome_textures()

var _near_index: Dictionary = {}     # Vector2i -> true
var _far_index: Dictionary = {}
var _wanted: Dictionary = {}         # clé -> description du travail {kind, ...}
var _instances: Dictionary = {}      # clé -> MeshInstance3D
var _jobs: Dictionary = {}           # clé -> {task, arrays, origin, gen}
var _ready: Array = []               # travaux terminés, à instancier : {key, arrays, origin}
var _generation := 0
var _road_material: Material
## Lot P17 : marquages de P14 (`set_road_markings`), un matériau par tronçon qui porte des chiffres
## peints (`set_road_marks`), chaussée mouillée (`set_road_wetness`).
var road_markings := false
var _road_color: Color = RoadBuilder.ROAD_COLOR
var _road_texture: Texture2D = null
var _marks_by_chunk: Dictionary = {}    # k -> [{s, digit}]
var _chunk_road_materials: Dictionary = {}   # k -> ShaderMaterial (tronçons à chiffres)
var _road_wetness := 0.0
var _terrain_material: Material
var _road_width_m: float = RoadBuilder.ROAD_WIDTH_M
var _ground_color: Color = FLAT_GROUND_COLOR
var _ground: MeshInstance3D = null
var _theme_dict: Dictionary = {}
var _theme_dir := ""
var _manifest: Variant = null
## Monde vivant (lot W10) : amorces des branches non suivies des carrefours, clé "<carrefour>:<branche>" -> MeshInstance3D.
const PREVIEW_FADE_M := 100.0
var _previews: Dictionary = {}
var _preview_material: Material = null

## Mesures pour le rapport de performance : clé de type -> [nombre, µs cumulées].
var build_stats: Dictionary = {}
var _stats_mutex := Mutex.new()


func _init() -> void:
	_road_material = RoadBuilder.make_material()
	_terrain_material = TerrainMaterial.create_material()


func _process(_delta: float) -> void:
	integrate(MAX_NEW_PER_FRAME)
	if biome_textures != null:
		biome_textures.sync_from(_terrain_material)   # ombre des nuages réglée par living_world.gd
	# Bâtiments et eau (lot E4) : sans cet appel, les tronçons OSM préparés n'entraient jamais
	# dans la scène (seuls les tests appelaient flush()).
	if osm_streamer != null:
		osm_streamer.integrate(MAX_NEW_PER_FRAME)


func _exit_tree() -> void:
	_wait_all_jobs()


## Nouveau parcours (ou parcours rechargé) : tout est vidé puis reconstruit au fil des images.
func set_world(new_route, new_world_dir: String) -> void:
	clear()
	route = new_route
	world_dir = new_world_dir
	has_terrain = false
	_manifest = JSON.parse_string(FileAccess.get_file_as_string(world_dir.path_join("manifest.json"))) \
		if FileAccess.file_exists(world_dir.path_join("manifest.json")) else null
	if typeof(_manifest) == TYPE_DICTIONARY:
		var layers = _manifest.get("layers", {})
		if typeof(layers) == TYPE_DICTIONARY and typeof(layers.get("terrain")) == TYPE_DICTIONARY:
			has_terrain = bool(layers["terrain"].get("present", false))
	if has_terrain:
		_near_index = TerrainTiles.scan_index(world_dir, "near")
		_far_index = TerrainTiles.scan_index(world_dir, "far")
		if _near_index.is_empty() and _far_index.is_empty():
			push_warning("Couche terrain déclarée mais aucune tuile trouvée : sol plat")
			has_terrain = false
	if not has_terrain:
		_make_ground()
	_set_biome_model()
	if osm_streamer != null:
		osm_streamer.visual_grade_scale = visual_grade_scale
		osm_streamer.set_world(route, world_dir)


## Modèle de biome du parcours (couche `biome` du manifeste, forçage `forced_biome`), passé aux arbres et aux
## animaux ; sol aux couleurs du biome du départ quand le modèle est actif.
func _set_biome_model() -> void:
	biome_model = BiomeModel.new(_theme_dict, BiomeLayer.new(world_dir, _manifest if typeof(_manifest) == TYPE_DICTIONARY else {}))
	biome_model.set_forced(forced_biome)
	var active = biome_model if biome_model.active() else null
	if tree_renderer != null:
		tree_renderer.biome_model = active
	if osm_streamer != null:
		osm_streamer.biome_model = active
	biome_textures = null
	if active == null:
		return
	_make_biome_textures()
	var ground: Dictionary = biome_model.terrain_theme(start_biome())
	_ground_color = ThemeRenderParams.terrain_uniforms(ground)["grass_color"]
	if _ground != null and _ground.mesh != null and _ground.mesh.material is StandardMaterial3D:
		(_ground.mesh.material as StandardMaterial3D).albedo_color = _ground_color


## Sols des biomes (lot U6) pour le préréglage courant ; les tuiles déjà affichées changent de matériau.
func _make_biome_textures() -> void:
	biome_textures = BiomeTextures.new(biome_model, _theme_dir, quality_preset)
	biome_textures.sync_from(_terrain_material)
	for key in _instances:
		if not (key as String).begins_with("road:"):
			(_instances[key] as MeshInstance3D).mesh.surface_set_material(0, _terrain_material_for(key))


## Matériau d'une tuile de terrain ("near:ix:iz", "far:ix:iz" ou "flat:ix:iz") : celui du thème, ou celui
## de ses biomes quand le modèle de biome est actif.
func _terrain_material_for(key: String) -> Material:
	if biome_textures == null:
		return _terrain_material
	var parts := key.split(":")
	return biome_textures.tile_material("far" if parts[0] == "far" else "near", int(parts[1]), int(parts[2]))


## Biome le plus présent au départ du parcours (biome par défaut sans parcours ni modèle).
func start_biome() -> String:
	if biome_model == null:
		return BiomeModel.BiomeIds.DEFAULT_BIOME
	var p: Vector3 = route.sample_point(0.0) if route != null and route.n > 0 else Vector3.ZERO
	var weights: Dictionary = biome_model.weights_at(p.x, p.z)
	var best := ""
	for b in weights:
		if best == "" or float(weights[b]) > float(weights[best]):
			best = b
	return best


func _has_layer(layer_name: String) -> bool:
	if typeof(_manifest) == TYPE_DICTIONARY:
		var layers = _manifest.get("layers", {})
		if typeof(layers) == TYPE_DICTIONARY and typeof(layers.get(layer_name)) == TYPE_DICTIONARY:
			return bool(layers[layer_name].get("present", false))
	return false


func _get_vegetation_areas(t: Vector2i) -> Array:
	return _get_osm_items(t, "vegetation")


## Bâtiments OSM des tronçons proches d'une tuile proche (arbres exclus de leur emprise).
func _get_buildings(t: Vector2i) -> Array:
	return _get_osm_items(t, "buildings")


func _get_osm_items(t: Vector2i, layer: String) -> Array:
	if not _has_layer(layer) or world_dir == "":
		return []
	var areas := []
	var tile_rect := Rect2(t.x * 1000.0, t.y * 1000.0, 1000.0, 1000.0)
	var count := RoadBuilder.chunk_count(route) if route != null else 0
	for k in range(count):
		var s0 := k * RoadBuilder.CHUNK_LENGTH_M
		var s1 := (k + 1) * RoadBuilder.CHUNK_LENGTH_M
		var p0: Vector3 = route.sample_point(s0)
		var p1: Vector3 = route.sample_point(s1)
		var r_bounds := Rect2(Vector2(p0.x, p0.z), Vector2.ZERO).expand(Vector2(p1.x, p1.z)).grow(100.0)
		if r_bounds.intersects(tile_rect):
			var res := OsmLayers.load_chunk(world_dir, layer, k, route)
			if res.get("ok", false):
				areas.append_array(res.get("items", []))
	return areas


## Monde vivant (lot W10) : nouvelle route (prolongée ou réécrite depuis la partie `from_part`) et tuiles
## de terrain nouvellement écrites. Les tronçons de ruban touchés sont reconstruits, les autres gardés ;
## les travaux en cours gardent l'ancienne route, qui n'est plus modifiée.
func swap_route(new_route, from_part: int) -> void:
	for key in _jobs.keys():
		if (key as String).begins_with("road:") and int((key as String).get_slice(":", 1)) >= from_part:
			WorkerThreadPool.wait_for_task_completion(_jobs[key]["task"])
			_jobs.erase(key)
	_ready = _ready.filter(func(r): return not ((r["key"] as String).begins_with("road:")
			and int((r["key"] as String).get_slice(":", 1)) >= from_part))
	for key in _instances.keys():
		if (key as String).begins_with("road:") and int((key as String).get_slice(":", 1)) >= from_part:
			_free_instance(key)
	route = new_route
	if has_terrain or _has_layer("terrain"):
		var near_new := TerrainTiles.scan_index(world_dir, "near")
		var far_new := TerrainTiles.scan_index(world_dir, "far")
		for t in near_new:
			if not _near_index.has(t):
				_near_index[t] = true
				_free_flat_tile(t)
		for t in far_new:
			_far_index[t] = true
		has_terrain = not (_near_index.is_empty() and _far_index.is_empty())
	if osm_streamer != null:
		osm_streamer.swap_route(new_route, from_part)


## Amorces voulues, telles que `live_world.previews(s)` les décrit : crée celles qui manquent, libère
## les autres. Chaque amorce est un ruban de la largeur de la route dont les 100 derniers mètres se fondent.
func set_previews(items: Array) -> void:
	var wanted := {}
	for it in items:
		wanted[it["key"]] = it
	for key in _previews.keys():
		if not wanted.has(key):
			_free_preview(key)
	if route == null:
		return
	var alt_orig: float = route.alt_m[0] if route.n > 0 else 0.0
	for key in wanted:
		if _previews.has(key):
			continue
		var it: Dictionary = wanted[key]
		var ys: Array = it["ys"]
		if visual_grade_scale != 1.0:
			ys = ys.map(func(y): return alt_orig + (float(y) - alt_orig) * visual_grade_scale)
		var arrays := RoadBuilder.build_polyline_arrays(it["xs"], ys, it["zs"], _road_width_m, PREVIEW_FADE_M)
		if arrays.is_empty():
			continue
		if _preview_material == null:
			_preview_material = RoadBuilder.make_preview_material(_road_color)
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		mesh.surface_set_material(0, _preview_material)
		var mi := MeshInstance3D.new()
		mi.name = "preview_" + (key as String).replace(":", "_")
		mi.mesh = mesh
		add_child(mi)
		_previews[key] = mi


func preview_count() -> int:
	return _previews.size()


func _free_preview(key: String) -> void:
	var mi: MeshInstance3D = _previews[key]
	_previews.erase(key)
	remove_child(mi)
	mi.mesh = null
	mi.free()


## Une tuile « flat » provisoire est remplacée par la vraie tuile dès qu'elle existe.
func _free_flat_tile(t: Vector2i) -> void:
	var key := "flat:%d:%d" % [t.x, t.y]
	if _instances.has(key):
		_free_instance(key)


## Retire tout : objets de scène, travaux en cours (attendus puis ignorés), sol plat.
func clear() -> void:
	_generation += 1
	_wait_all_jobs()
	_jobs.clear()
	_ready.clear()
	_wanted.clear()
	for key in _instances.keys():
		_free_instance(key)
	for key in _previews.keys():
		_free_preview(key)
	if tree_renderer != null:
		tree_renderer.clear()
	if osm_streamer != null:
		osm_streamer.clear()
	if _ground != null:
		remove_child(_ground)
		_ground.mesh = null
		_ground.free()
		_ground = null
	_near_index = {}
	_far_index = {}
	route = null


# --- fenêtre -----------------------------------------------------------------------------

## Tronçons de route voulus pour la position s et la vitesse v.
func road_window(s_pos: float, v: float) -> Array:
	var out := []
	if route == null:
		return out
	var count := RoadBuilder.chunk_count(route)
	if count == 0:
		return out
	var lo := s_pos - float(chunks_behind) * RoadBuilder.CHUNK_LENGTH_M
	var hi := s_pos + float(chunks_ahead) * RoadBuilder.CHUNK_LENGTH_M + maxf(v, 0.0) * LOOKAHEAD_S
	var k_lo := floori(lo / RoadBuilder.CHUNK_LENGTH_M)
	var k_hi := ceili(hi / RoadBuilder.CHUNK_LENGTH_M) - 1
	for k in range(k_lo, k_hi + 1):
		var kk := k
		if route.is_loop():
			kk = posmod(k, count)
		elif k < 0 or k >= count:
			continue
		if not out.has(kk):
			out.append(kk)
	if route.is_loop() and k_hi - k_lo + 1 >= count:
		out = range(count)
	return out


static func _rect_distance(level: String, t: Vector2i, x: float, z: float) -> float:
	var size: float = TerrainTiles.LEVELS[level]["size"]
	var dx := maxf(maxf(t.x * size - x, 0.0), x - (t.x + 1) * size)
	var dz := maxf(maxf(t.y * size - z, 0.0), z - (t.y + 1) * size)
	return Vector2(dx, dz).length()


## Tuiles proches voulues autour des points donnés (positions x, z), avec leur nature :
## "near" (fichier présent) ou "flat" (ni proche ni lointaine) ; les tuiles couvertes par le
## lointain seul ne sont pas listées.
func near_window(points: Array) -> Dictionary:
	var out := {}
	if route == null or not has_terrain:
		return out
	for p in points:
		var lo := TerrainTiles.tile_of("near", p.x - NEAR_RADIUS_M, p.y - NEAR_RADIUS_M)
		var hi := TerrainTiles.tile_of("near", p.x + NEAR_RADIUS_M, p.y + NEAR_RADIUS_M)
		for ix in range(lo.x, hi.x + 1):
			for iz in range(lo.y, hi.y + 1):
				var t := Vector2i(ix, iz)
				if out.has(t) or _rect_distance("near", t, p.x, p.y) > NEAR_RADIUS_M:
					continue
				if _near_index.has(t):
					out[t] = "near"
				elif not _far_covers(t):
					out[t] = "flat"
	return out


## Vues de la caméra active (lot S1) : maintenant puis le long de la route ; vide hors de l'arbre de
## scène, sans caméra, ou caméra pas encore placée à `cam_pos` (chargement d'un parcours), et tout est
## alors voulu. Calculées même sans tri, pour les contrôles du mode test.
func _views(s_pos: float, v: float, cam_pos: Vector3) -> Array:
	if not is_inside_tree() or route == null:
		return []
	var cam := get_viewport().get_camera_3d()
	if cam == null or cam.global_position.distance_to(cam_pos) > ViewCulling.CAMERA_MATCH_M:
		return []
	return ViewCulling.route_views(ViewCulling.view_of(cam), route, s_pos, v)


## Tuile proche voulue pour ces vues (lot S1) ; `loaded` : déjà chargée ou en construction, gardée avec
## la marge d'hystérésis.
func near_tile_wanted(t: Vector2i, views: Array, loaded: bool = false) -> bool:
	var size: float = TerrainTiles.LEVELS["near"]["size"]
	var extra := deg_to_rad(ViewCulling.KEEP_MARGIN_DEG) if loaded else 0.0
	return ViewCulling.rect_wanted(Rect2(t.x * size, t.y * size, size, size), views, NEAR_RADIUS_M,
		culling_keep_m, extra)


## Une tuile proche (1 000 m) est toujours entièrement dans une seule tuile lointaine (5 000 m).
func _far_covers(near_tile: Vector2i) -> bool:
	var c := TerrainTiles.tile_origin("near", near_tile.x, near_tile.y) + Vector3(1.0, 0.0, 1.0)
	return _far_index.has(TerrainTiles.tile_of("far", c.x, c.z))


## Rayon des tuiles lointaines pour une fin de brouillard donnée : une tuile lointaine de marge, pour
## qu'aucune tuile n'apparaisse au bord du brouillard pendant sa construction ; plafond FAR_RADIUS_M.
static func far_radius_for(fog_end_m: float) -> float:
	return minf(fog_end_m + float(TerrainTiles.LEVELS["far"]["size"]), FAR_RADIUS_M)


## Tuiles lointaines présentes à moins de far_radius_m de la caméra.
func far_window(cam_x: float, cam_z: float) -> Array:
	var out := []
	for t in _far_index:
		if _rect_distance("far", t, cam_x, cam_z) <= far_radius_m:
			out.append(t)
	return out


## Met à jour la fenêtre active : libère ce qui en sort, lance la génération de ce qui y entre.
func update_window(s_pos: float, v: float, cam_pos: Vector3) -> void:
	if route == null:
		return
	var wanted := {}
	var views := _views(s_pos, v, cam_pos)
	_view_now = views[0] if not views.is_empty() else {}
	_s_now = s_pos
	if not culling:
		views = []
	for k in road_window(s_pos, v):
		wanted["road:%d" % k] = {"kind": "road", "k": k, "dist": 0.0}
	if has_terrain:
		var ahead: Vector3 = route.sample_point(route.wrap_s(s_pos + maxf(v, 0.0) * LOOKAHEAD_S))
		var near := near_window([Vector2(cam_pos.x, cam_pos.z), Vector2(ahead.x, ahead.z)])
		culled_near = 0
		for t in near:
			var key := "%s:%d:%d" % [near[t], t.x, t.y]
			if not near_tile_wanted(t, views, _instances.has(key) or _jobs.has(key)):
				culled_near += 1
				continue
			wanted[key] = {"kind": near[t], "tile": t, "dist": _rect_distance("near", t, cam_pos.x, cam_pos.z)}
		for t in far_window(cam_pos.x, cam_pos.z):
			wanted["far:%d:%d" % [t.x, t.y]] = {"kind": "far", "tile": t,
				"dist": 10000.0 + _rect_distance("far", t, cam_pos.x, cam_pos.z)}
	_wanted = wanted
	for key in _instances.keys():
		if not _wanted.has(key):
			_free_instance(key)
	_ready = _ready.filter(func(r): return _wanted.has(r["key"]))
	_start_jobs()
	if _ground != null:
		_ground.position = Vector3(cam_pos.x, _ground.position.y, cam_pos.z)
	if tree_renderer != null:
		tree_renderer.enforce_budget(cam_pos, views[0] if not views.is_empty() else {})
	if osm_streamer != null and route != null:
		osm_streamer.update_window(s_pos - float(chunks_behind) * 1000.0, s_pos + float(chunks_ahead) * 1000.0 + v * LOOKAHEAD_S)


func _start_jobs() -> void:
	var queued := {}
	for r in _ready:
		queued[r["key"]] = true
	var todo := []
	for key in _wanted:
		if not _instances.has(key) and not _jobs.has(key) and not queued.has(key):
			todo.append(key)
	todo.sort_custom(func(a, b): return float(_wanted[a]["dist"]) < float(_wanted[b]["dist"]))
	for key in todo:
		if _jobs.size() >= MAX_RUNNING_TASKS:
			break
		var alt_orig: float = route.alt_m[0] if route != null and route.n > 0 else 0.0
		var job := {"key": key, "spec": _wanted[key], "arrays": [], "origin": Vector3.ZERO, "gen": _generation,
			"route": route, "world_dir": world_dir, "road_width_m": _road_width_m,
			"visual_grade_scale": visual_grade_scale, "alt_orig": alt_orig}
		job["task"] = WorkerThreadPool.add_task(_build_job.bind(job), false, "maillage " + key)
		_jobs[key] = job


## Exécuté dans un fil de WorkerThreadPool : calcule seulement les tableaux de sommets.
func _build_job(job: Dictionary) -> void:
	var t0 := Time.get_ticks_usec()
	var spec: Dictionary = job["spec"]
	var r = job["route"]
	var v_scale: float = float(job.get("visual_grade_scale", 1.0))
	var alt_orig: float = float(job.get("alt_orig", 0.0))
	match spec["kind"]:
		"road":
			job["arrays"] = RoadBuilder.build_chunk_arrays(r, spec["k"], float(job.get("road_width_m", RoadBuilder.ROAD_WIDTH_M)), v_scale)
		"near", "far":
			var t: Vector2i = spec["tile"]
			var heights := TerrainTiles.load_filled(job["world_dir"], spec["kind"], t.x, t.y, r)
			if heights.is_empty():
				return
			if spec["kind"] == "far":
				heights = TerrainTiles.carve_under_route(heights, "far", t.x, t.y, r, TerrainTiles.FAR_CARVE_MARGIN_M, v_scale, alt_orig)
			var edges := TerrainTiles.load_neighbour_edges(job["world_dir"], spec["kind"], t.x, t.y)
			job["arrays"] = TerrainTiles.build_arrays(heights, spec["kind"], edges, v_scale, alt_orig)
			job["origin"] = TerrainTiles.tile_origin(spec["kind"], t.x, t.y)
			if spec["kind"] == "near" and tree_renderer != null:
				var h_scaled := TerrainTiles.scale_heights(heights, alt_orig, v_scale) if v_scale != 1.0 else heights
				job["trees_data"] = tree_renderer.prepare_tile(t.x, t.y, h_scaled, r, _theme_dict,
					vegetation_density_factor, _get_vegetation_areas(t), _get_buildings(t))
		"flat":
			var t: Vector2i = spec["tile"]
			var c := TerrainTiles.tile_origin("near", t.x, t.y) + Vector3(500.0, 0.0, 500.0)
			var alt := TerrainTiles.nearest_route_alt(r, c.x, c.z)
			var flat_h := TerrainTiles.flat_heights(alt)
			job["arrays"] = TerrainTiles.build_arrays(flat_h, "near", {}, v_scale, alt_orig)
			job["origin"] = TerrainTiles.tile_origin("near", t.x, t.y)
			if tree_renderer != null:
				var flat_scaled := TerrainTiles.scale_heights(flat_h, alt_orig, v_scale) if v_scale != 1.0 else flat_h
				job["trees_data"] = tree_renderer.prepare_tile(t.x, t.y, flat_scaled, r, _theme_dict,
					vegetation_density_factor, [])
	var dt := Time.get_ticks_usec() - t0
	_stats_mutex.lock()
	var st: Array = build_stats.get(spec["kind"], [0, 0])
	build_stats[spec["kind"]] = [st[0] + 1, st[1] + dt]
	_stats_mutex.unlock()


func _poll_jobs(wait: bool) -> void:
	for key in _jobs.keys():
		var job: Dictionary = _jobs[key]
		if not wait and not WorkerThreadPool.is_task_completed(job["task"]):
			continue
		WorkerThreadPool.wait_for_task_completion(job["task"])
		_jobs.erase(key)
		if job["gen"] == _generation and _wanted.has(key) and not (job["arrays"] as Array).is_empty():
			var ready_item := {"key": key, "arrays": job["arrays"], "origin": job["origin"], "kind": job["spec"]["kind"]}
			if job.has("trees_data"):
				ready_item["trees_data"] = job["trees_data"]
			_ready.append(ready_item)


func _wait_all_jobs() -> void:
	for key in _jobs.keys():
		WorkerThreadPool.wait_for_task_completion(_jobs[key]["task"])


## Relève les travaux terminés et crée au plus `max_new` objets de scène (fil principal).
func integrate(max_new: int) -> int:
	_poll_jobs(false)
	var created := 0
	while created < max_new and not _ready.is_empty():
		var r: Dictionary = _ready.pop_front()
		if not _wanted.has(r["key"]) or _instances.has(r["key"]):
			continue
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, r["arrays"])
		mesh.surface_set_material(0, road_material_for(int((r["key"] as String).get_slice(":", 1))) if r["kind"] == "road" else _terrain_material_for(r["key"]))
		var mi := MeshInstance3D.new()
		mi.name = (r["key"] as String).replace(":", "_")
		mi.mesh = mesh
		mi.position = r["origin"]
		add_child(mi)
		_instances[r["key"]] = mi
		if r.has("trees_data") and tree_renderer != null and not (r["trees_data"] as Dictionary).is_empty():
			tree_renderer.add_tile(r["trees_data"])
		if test_log and r["kind"] == "near":
			_test_check_tile(r["key"], r["arrays"][Mesh.ARRAY_VERTEX])
		created += 1
	_start_jobs()
	return created


## Mode test (lot S1) : apparition soudaine dans le champ et jointure avec les tuiles proches voisines.
func _test_check_tile(key: String, verts: PackedVector3Array) -> void:
	var parts := key.split(":")
	var t := Vector2i(int(parts[1]), int(parts[2]))
	var size: float = TerrainTiles.LEVELS["near"]["size"]
	if not _view_now.is_empty():
		var rect := Rect2(t.x * size, t.y * size, size, size)
		var d := ViewCulling.rect_distance(rect, _view_now["pos"])
		if d < TEST_POP_DIST_M and ViewCulling.rect_in_view(rect, _view_now):
			print("[test] pop key=%s dist=%.0f s=%.1f" % [key, d, _s_now])
	for dt in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		var nkey := "near:%d:%d" % [t.x + dt.x, t.y + dt.y]
		if not _instances.has(nkey) or nkey == key:
			continue
		var other: PackedVector3Array = (_instances[nkey] as MeshInstance3D).mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
		var gap := seam_gap(verts, other, dt.x, dt.y)
		if gap > TEST_SEAM_TOL_M:
			print("[test] seam key=%s voisine=%s ecart=%.2f s=%.1f" % [key, nkey, gap, _s_now])


## Plus grand écart de hauteur (m) entre le bord d'une tuile proche (`a`, sommets de build_arrays) et
## le bord commun de sa voisine `b` placée en (dx, dz) = (±1, 0) ou (0, ±1).
static func seam_gap(a: PackedVector3Array, b: PackedVector3Array, dx: int, dz: int) -> float:
	var n := TerrainTiles.SAMPLES
	var last := TerrainTiles.CELLS
	var gap := 0.0
	for k in range(n):
		var ia: int
		var ib: int
		if dx == 1:
			ia = k * n + last
			ib = k * n
		elif dx == -1:
			ia = k * n
			ib = k * n + last
		elif dz == 1:
			ia = last * n + k
			ib = k
		else:
			ia = k
			ib = last * n + k
		gap = maxf(gap, absf(a[ia].y - b[ib].y))
	return gap


## Attend et instancie tout ce que demande la fenêtre courante (tests, chargement initial).
func flush() -> void:
	while true:
		_poll_jobs(true)
		integrate(1 << 30)
		if _jobs.is_empty() and _ready.is_empty():
			break
	if osm_streamer != null:
		osm_streamer.flush()


## Morceaux de décor instanciés par nature (sonde de performance, lot X13) : {road, near, far},
## les tuiles « flat » comptant comme proches.
func loaded_tile_counts() -> Dictionary:
	var out := {"road": 0, "near": 0, "far": 0}
	for key in _instances:
		var kind: String = String(key).get_slice(":", 0)
		if kind == "flat":
			kind = "near"
		out[kind] = int(out.get(kind, 0)) + 1
	return out


## Tuiles voulues autour de la caméra pas encore affichées (en calcul ou en attente) : 0 quand la vue est
## complète (tour visuel, lot X21).
func pending_count() -> int:
	var n := 0
	for key in _wanted:
		if not _instances.has(key):
			n += 1
	return n


## Attend les travaux en cours sans dépasser le budget d'objets par image (tests en temps simulé).
func wait_jobs() -> void:
	_poll_jobs(true)


func _free_instance(key: String) -> void:
	var mi: MeshInstance3D = _instances[key]
	_instances.erase(key)
	remove_child(mi)
	if biome_textures != null and not key.begins_with("road:"):
		biome_textures.release(mi.mesh.surface_get_material(0))
	mi.mesh = null   # maillage libéré avant le nœud (évite une erreur du rendu factice sans écran)
	mi.free()
	if key.begins_with("near:") and tree_renderer != null:
		var parts := key.split(":")
		tree_renderer.remove_tile(Vector2i(int(parts[1]), int(parts[2])))


## Configure les matériaux de route et de terrain selon le thème (Lot E2).
func set_theme(theme_dict: Dictionary, theme_dir: String = "") -> void:
	_theme_dict = theme_dict
	_theme_dir = theme_dir
	var r_params := ThemeRenderParams.road_params(theme_dict)
	_road_width_m = float(r_params["width_m"])
	var road_tex: Texture2D = ThemeLoader.texture_for(theme_dict, theme_dir, "road.texture") if theme_dir != "" else null
	_road_color = r_params["color"]
	_preview_material = null
	_road_texture = road_tex
	_rebuild_road_material()

	if _terrain_material is ShaderMaterial:
		TerrainMaterial.apply_to_material(_terrain_material, theme_dict, theme_dir)

	var tu := ThemeRenderParams.terrain_uniforms(theme_dict)
	_ground_color = tu["grass_color"]
	if _ground != null and _ground.mesh != null and _ground.mesh.material is StandardMaterial3D:
		(_ground.mesh.material as StandardMaterial3D).albedo_color = _ground_color


func _rebuild_road_material() -> void:
	_chunk_road_materials.clear()
	if road_markings:
		var mm := RoadBuilder.make_markings_material(_road_color, _road_width_m)
		mm.set_shader_parameter("wetness", _road_wetness)
		_road_material = mm
	else:
		_road_material = RoadBuilder.make_material(_road_color, _road_texture)
	for key in _instances:
		if (key as String).begins_with("road:"):
			var mi: MeshInstance3D = _instances[key]
			mi.mesh.surface_set_material(0, road_material_for(int((key as String).get_slice(":", 1))))


## Marquages de la route (Lot P17) : à appeler avant le chargement des tronçons (sinon ceux déjà
## affichés changent de matériau).
func set_road_markings(on: bool) -> void:
	if on == road_markings:
		return
	road_markings = on
	_rebuild_road_material()


## Chiffres peints par tronçon (roadside_model.paint_marks réparti par tronçon de 1 000 m).
func set_road_marks(marks_by_chunk: Dictionary) -> void:
	_marks_by_chunk = marks_by_chunk
	_rebuild_road_material()


func road_material_for(k: int) -> Material:
	if not road_markings or not _marks_by_chunk.has(k):
		return _road_material
	if not _chunk_road_materials.has(k):
		var m := _road_material.duplicate() as ShaderMaterial
		RoadBuilder.set_marks(m, _marks_by_chunk[k])
		_chunk_road_materials[k] = m
	return _chunk_road_materials[k]


## Chaussée mouillée sous la pluie (P8 `wetness`, 0 à 1), avec les marquages seulement.
func set_road_wetness(w: float) -> void:
	w = clampf(w, 0.0, 1.0)
	if absf(w - _road_wetness) < 0.005:
		return
	_road_wetness = w
	if _road_material is ShaderMaterial:
		(_road_material as ShaderMaterial).set_shader_parameter("wetness", w)
	for k in _chunk_road_materials:
		(_chunk_road_materials[k] as ShaderMaterial).set_shader_parameter("wetness", w)


func road_wetness() -> float:
	return _road_wetness


func _make_ground() -> void:
	if _ground != null:
		return
	var min_alt := INF
	if route:
		for a in route.alt_m:
			min_alt = minf(min_alt, a)
	if is_inf(min_alt):
		min_alt = 0.0
	var alt_orig: float = route.alt_m[0] if route != null and route.n > 0 else 0.0
	if visual_grade_scale != 1.0:
		min_alt = alt_orig + (min_alt - alt_orig) * visual_grade_scale
	var plane := PlaneMesh.new()
	plane.size = Vector2(2.0 * far_radius_m, 2.0 * far_radius_m)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = _ground_color
	mat.roughness = 1.0
	plane.material = mat
	_ground = MeshInstance3D.new()
	_ground.name = "FlatGround"
	_ground.mesh = plane
	_ground.position = Vector3(0.0, min_alt - FLAT_GROUND_BELOW_M, 0.0)
	add_child(_ground)


# --- état, pour les tests et le journal ------------------------------------------------------

func loaded_keys() -> Array:
	var keys := _instances.keys()
	keys.sort()
	return keys


func wanted_keys() -> Array:
	var keys := _wanted.keys()
	keys.sort()
	return keys


func instance(key: String) -> MeshInstance3D:
	return _instances.get(key)


func has_ground() -> bool:
	return _ground != null


func ground_height() -> float:
	return _ground.position.y if _ground != null else NAN
