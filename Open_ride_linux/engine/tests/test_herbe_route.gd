extends SceneTree

## Rien du paysage sur la chaussée (demande du 31 octobre) : sur chaque parcours donné, le décor posé le long de
## la route et le terrain sont comparés à la route RÉELLE (axe en Catmull-Rom tous les 2 m, comme le ruban de
## road_builder.gd), sur tout le parcours, pas seulement au point qui pose l'objet.
##
##   $GODOT --headless --path engine --script res://tests/test_herbe_route.gd -- DOSSIER.world [DOSSIER.world ...]
##
## Contrôles, au relief réel (k = 1,0) et au relief de séance (EngineArgs.DEFAULT_VISUAL_GRADE) :
## - touffes d'herbe (grass_tufts.gd) : toutes les places de tous les tronçons au budget `high`, à au moins
##   TUFT_CLEAR_M du bord de la chaussée ;
## - détails de sol (ground_details.gd : rochers, herbes hautes, termitières) au budget `high`, si le parcours a
##   une couche biome : le rayon de l'objet hors de la chaussée ;
## - arbres semés au bruit (vegetation_placer.gd) sur les tuiles que touche la route : à au moins TREE_CLEAR_M
##   du bord ;
## - sol affiché sous la chaussée (_ground_fn, même choix que world_streamer.gd : tuile proche, sinon lointaine,
##   sinon tuile plate ; sol plat sans couche terrain) : en travers de la chaussée tous les SECTION_STEP_M mètres,
##   jamais plus de TERRAIN_TOL_M au-dessus de la route (route enfoncée sous l'herbe ou le terrain) ; et la route
##   ne lévite pas (constat du 4 novembre 2026 sur la démonstration sans terrain) : là où le sol est à plus de
##   FLOAT_TOL_M sous la chaussée, les pieds des deux talus (road_builder.gd, SKIRT_DROP_M plus bas, SKIRT_OUT_M
##   plus loin que le bas-côté) doivent être enterrés, sinon on voit sous la route. Les remblais plus hauts que
##   FLOAT_TOL_M sont comptés et le plus haut est affiché.
##   Le sol sous la route ne dépend pas du préréglage (low, medium et high ont les mêmes tuiles proches) : un
##   passage par parcours et par relief suffit pour les trois.
## Code de sortie 1 si un contrôle échoue ; les pires points sont listés (s, x, z) pour aller les voir.

const RouteDataScript := preload("res://scripts/route_data.gd")
const GrassTufts := preload("res://scripts/grass_tufts.gd")
const GroundDetails := preload("res://scripts/ground_details.gd")
const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")

const ROAD_HALF_M := RoadBuilder.ROAD_WIDTH_M * 0.5
## Écart minimal au bord de la chaussée (m) : touffe (rayon et brins penchés), tronc d'arbre.
const TUFT_CLEAR_M := 0.5
const TREE_CLEAR_M := 1.0
## Terrain au plus 2 cm au-dessus de la chaussée (il est posé 5 cm dessous par le compilateur).
const TERRAIN_TOL_M := 0.02
## Route au plus 50 cm au-dessus du sol affiché, sur toute sa largeur.
const FLOAT_TOL_M := 0.5
const WorldStreamer := preload("res://scripts/world_streamer.gd")
const SECTION_STEP_M := 2.0
const ACROSS_STEP_M := 1.0
const WORST_SHOWN := 5

var _failures := 0
var _checked := 0


func _init() -> void:
	var dirs := OS.get_cmdline_user_args()
	if dirs.is_empty():
		printerr("Usage : -- DOSSIER.world [DOSSIER.world ...]")
		quit(2)
		return
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	for wd in dirs:
		for k in [1.0, EngineArgs.DEFAULT_VISUAL_GRADE]:
			_run(wd, k, theme)
	print("test_herbe_route : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Pires points d'une liste [écart, texte], triée du pire au moins grave.
static func _worst(items: Array) -> String:
	items.sort_custom(func(a, b): return a[0] > b[0])
	var out := []
	for i in range(mini(items.size(), WORST_SHOWN)):
		out.append(items[i][1])
	return "; ".join(out)


func _run(wd: String, k: float, theme: Dictionary) -> void:
	var name := wd.get_file()
	var route = RouteDataScript.new()
	if not route.load_world_dir(wd):
		_check(false, "%s : parcours lisible" % name)
		return
	route.relief_k = k
	var tag := "%s (relief ×%.1f)" % [name, k]
	var raw := OsmStreamer.terrain_height_fn(wd, route)
	var height_at := func(x: float, z: float) -> float: return route.display_y(float(raw.call(x, z)))
	var ground_at := _ground_fn(wd, route)
	# Axe réel de la route (Catmull-Rom tous les 2 m), sur tout le parcours.
	var bounds := _route_bounds(route)
	var corridor := ROAD_HALF_M + maxf(TUFT_CLEAR_M, TREE_CLEAR_M) + 2.0
	var road := VegetationPlacer._road_buckets(route, bounds, corridor)
	_check_terrain(tag, route, ground_at)
	if k != 1.0:
		return   # placement du décor : mêmes x et z au relief de séance, seule la pente change (contrôlé à ×k)
	_check_tufts(tag, route, height_at, road)
	_check_details(tag, wd, route, height_at, road, theme)
	_check_trees(tag, route, height_at, road, theme, bounds)


static func _route_bounds(route) -> Rect2:
	var r := Rect2(route.x[0], route.z[0], 0.0, 0.0)
	for i in range(route.n):
		r = r.expand(Vector2(route.x[i], route.z[i]))
	return r


## Distance à l'axe réel (INF au-delà du couloir des cases).
static func _axis_distance(road: Dictionary, x: float, z: float) -> float:
	var key := Vector2i(int(floor(x / VegetationPlacer.ROAD_BUCKET_M)), int(floor(z / VegetationPlacer.ROAD_BUCKET_M)))
	var best := INF
	var p := Vector2(x, z)
	for seg in road.get(key, PackedVector4Array()):
		best = minf(best, p.distance_to(Geometry2D.get_closest_point_to_segment(p, Vector2(seg.x, seg.y), Vector2(seg.z, seg.w))))
	return best


## Hauteur affichée du sol en (x, z), relief de la route compris, telle que world_streamer.gd la dessine :
## sans couche terrain, sol plat FLAT_GROUND_BELOW_M sous l'altitude la plus basse ; sinon tuile proche,
## sinon tuile lointaine (abaissée de FAR_DROP_M), sinon tuile plate à l'altitude de la route la plus proche
## de son centre.
static func _ground_fn(wd: String, route) -> Callable:
	var manifest: Variant = JSON.parse_string(FileAccess.get_file_as_string(wd.path_join("manifest.json")))
	var layers: Variant = manifest.get("layers", {}) if typeof(manifest) == TYPE_DICTIONARY else {}
	var terrain: Variant = layers.get("terrain", {}) if typeof(layers) == TYPE_DICTIONARY else {}
	if typeof(terrain) != TYPE_DICTIONARY or not bool(terrain.get("present", false)) \
			or (TerrainTiles.scan_index(wd, "near").is_empty() and TerrainTiles.scan_index(wd, "far").is_empty()):
		var min_alt := INF
		for a in route.alt_m:
			min_alt = minf(min_alt, a)
		var flat_y: float = route.display_y(min_alt) - WorldStreamer.FLAT_GROUND_BELOW_M
		return func(_x: float, _z: float) -> float: return flat_y
	var cache := {}
	return func(x: float, z: float) -> float:
		for level in ["near", "far"]:
			var t := TerrainTiles.tile_of(level, x, z)
			var key := "%s:%d:%d" % [level, t.x, t.y]
			if not cache.has(key):
				cache[key] = TerrainTiles.load_filled(wd, level, t.x, t.y, route)
			var h: PackedFloat32Array = cache[key]
			if not h.is_empty():
				return route.display_y(TerrainTiles.mesh_height_at(h, level, t.x, t.y, x, z)) \
					+ float(TerrainTiles.LEVELS[level]["y_offset"])
		var c := TerrainTiles.tile_origin("near", TerrainTiles.tile_of("near", x, z).x, TerrainTiles.tile_of("near", x, z).y) \
			+ Vector3(500.0, 0.0, 500.0)
		return route.display_y(TerrainTiles.nearest_route_alt(route, c.x, c.z))


## Sol affiché en travers de la chaussée : ni au-dessus de la route (route enfoncée), ni trop dessous sans que
## les talus touchent le sol (route qui lévite).
func _check_terrain(tag: String, route, ground_at: Callable) -> void:
	var above := []
	var floating := []
	var worst_up := -INF
	var worst_down := INF
	var banks := 0
	var n := 0
	var foot_off := ROAD_HALF_M + RoadBuilder.SHOULDER_WIDTH_M + RoadBuilder.SKIRT_OUT_M
	var foot_drop := RoadBuilder.SHOULDER_DROP_M + RoadBuilder.SKIRT_DROP_M
	var s := 0.0
	while s <= route.length_m:
		var smp: Dictionary = route.sample(s)
		var y: float = smp["y"]
		var h := deg_to_rad(float(smp["heading_deg"]))
		var right := Vector2(cos(h), sin(h))
		var low := INF
		var low_txt := ""
		var off := -ROAD_HALF_M
		while off <= ROAD_HALF_M + 1e-6:
			var x: float = smp["x"] + right.x * off
			var z: float = smp["z"] + right.y * off
			var d: float = float(ground_at.call(x, z)) - y
			n += 1
			worst_up = maxf(worst_up, d)
			worst_down = minf(worst_down, d)
			if d > TERRAIN_TOL_M:
				above.append([d, "s = %.0f m, x = %.1f, z = %.1f : +%.2f m" % [s, x, z, d]])
			if d < low:
				low = d
				low_txt = "s = %.0f m, x = %.1f, z = %.1f : %.2f m" % [s, x, z, d]
			off += ACROSS_STEP_M
		if low < -FLOAT_TOL_M:
			banks += 1
			var buried := true
			for side in [-1.0, 1.0]:
				var fx: float = smp["x"] + right.x * foot_off * side
				var fz: float = smp["z"] + right.y * foot_off * side
				buried = buried and float(ground_at.call(fx, fz)) >= y - foot_drop
			if not buried:
				floating.append([-low, low_txt])
		s += SECTION_STEP_M
	_check(above.is_empty(), "%s : sol jamais au-dessus de la chaussée (%d points, au plus %+.2f m, %d au-dessus)%s" % [
		tag, n, worst_up, above.size(), "" if above.is_empty() else " — " + _worst(above)])
	_check(floating.is_empty(), "%s : route posée sur le sol ou sur ses talus (sol au plus %.2f m sous la route ; %d coupes sur remblai de plus de %.1f m, %d sans appui)%s" % [
		tag, -worst_down, banks, FLOAT_TOL_M, floating.size(), "" if floating.is_empty() else " — " + _worst(floating)])


func _check_tufts(tag: String, route, height_at: Callable, road: Dictionary) -> void:
	var g = GrassTufts.new()
	root.add_child(g)
	g.configure(int(QualityPresets.living("high")["grass_tufts"]), route, RoadBuilder.ROAD_WIDTH_M)
	g.height_at = height_at
	var per_chunk: int = g._per_chunk
	var bad := []
	var placed := 0
	var nearest := INF
	for chunk in range(0, int(ceil(route.length_m / GrassTufts.CHUNK_M)) + 1):
		var stations: PackedVector4Array = g.chunk_stations(chunk)
		for slot in range(per_chunk):
			var xf: Variant = g.tuft_transform(chunk, slot, stations)
			if xf == null:
				continue
			placed += 1
			var p: Vector3 = (xf as Transform3D).origin
			var edge := _axis_distance(road, p.x, p.z) - ROAD_HALF_M
			nearest = minf(nearest, edge)
			if edge < TUFT_CLEAR_M:
				bad.append([-edge, "tronçon %d, x = %.1f, z = %.1f : %.2f m du bord" % [chunk, p.x, p.z, edge]])
	g.queue_free()
	_check(placed > 0 and bad.is_empty(), "%s : touffes d'herbe hors de la chaussée (%d posées, la plus proche à %.2f m du bord, %d trop près)%s" % [
		tag, placed, nearest, bad.size(), "" if bad.is_empty() else " — " + _worst(bad)])


func _check_details(tag: String, wd: String, route, height_at: Callable, road: Dictionary, theme: Dictionary) -> void:
	var manifest: Variant = JSON.parse_string(FileAccess.get_file_as_string(wd.path_join("manifest.json")))
	var model = BiomeModel.new(theme, BiomeLayer.new(wd, manifest if typeof(manifest) == TYPE_DICTIONARY else {}))
	if not model.active():
		print("[--] %s : pas de couche biome, détails de sol non posés" % tag)
		return
	var living := QualityPresets.living("high")
	var gd = GroundDetails.new()
	root.add_child(gd)
	gd.configure({"rock": int(living["ground_rocks"]), "grass": int(living["ground_grass"]),
		"termite": int(living["ground_termites"])}, route, model, RoadBuilder.ROAD_WIDTH_M)
	gd.height_at = height_at
	var bad := []
	var placed := 0
	for chunk in range(0, int(ceil(route.length_m / GroundDetails.CHUNK_M)) + 1):
		var stations: PackedVector4Array = gd.chunk_stations(chunk)
		for layer in gd._layers:
			for slot in range(int(layer["per_chunk"])):
				var d: Variant = gd.detail_at(layer["kind"], layer["shape"], chunk, slot, stations)
				if d == null:
					continue
				placed += 1
				var xf: Transform3D = d["xf"]
				var radius: float = GroundDetails.RADIUS_M[layer["kind"]] * xf.basis.get_scale().x
				var edge := _axis_distance(road, xf.origin.x, xf.origin.z) - ROAD_HALF_M - radius
				if edge < 0.0:
					bad.append([-edge, "%s, x = %.1f, z = %.1f : déborde de %.2f m" % [layer["kind"], xf.origin.x, xf.origin.z, -edge]])
	gd.queue_free()
	_check(bad.is_empty(), "%s : rochers, herbes hautes et termitières hors de la chaussée (%d posés, %d dessus)%s" % [
		tag, placed, bad.size(), "" if bad.is_empty() else " — " + _worst(bad)])


func _check_trees(tag: String, route, height_at: Callable, road: Dictionary, theme: Dictionary, bounds: Rect2) -> void:
	var placer := VegetationPlacer.new()
	var tile_m := 1000.0
	var bad := []
	var placed := 0
	var area := bounds.grow(100.0)
	for tz in range(floori(area.position.y / tile_m), floori(area.end.y / tile_m) + 1):
		for tx in range(floori(area.position.x / tile_m), floori(area.end.x / tile_m) + 1):
			var trees: PackedVector4Array = placer.place_tile(tx, tz, tile_m, height_at, route, theme, [])
			for t in trees:
				var edge := _axis_distance(road, t.x, t.z) - ROAD_HALF_M
				if edge == INF:
					continue
				placed += 1
				if edge < TREE_CLEAR_M:
					bad.append([-edge, "x = %.1f, z = %.1f : %.2f m du bord" % [t.x, t.z, edge]])
	_check(bad.is_empty(), "%s : arbres hors de la chaussée (%d près de la route, %d trop près)%s" % [
		tag, placed, bad.size(), "" if bad.is_empty() else " — " + _worst(bad)])
