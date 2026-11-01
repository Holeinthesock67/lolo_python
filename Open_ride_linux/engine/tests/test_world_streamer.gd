extends SceneTree

## Tests sans écran du rendu par tronçons (lot E1, §4.6) : raccord route-terrain, durée sans fuite,
## jointures du ruban, parcours sans terrain ; plus remplacement des NaN, sens des faces et
## mesures de temps de construction (critère 3).
## Lancement : godot --headless --path engine --script res://tests/test_world_streamer.gd -- <démo avec terrain>
## (dossier écrit par `python -m openride_core.tools.fake_world --demo --terrain`).
## Code de sortie : 0 si tout passe, 1 sinon.

const RouteDataScript := preload("res://scripts/route_data.gd")
const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")

const PLAIN_WORLD := "res://demo/demo.world"
const EYE := Vector3(0.0, 1.4, 0.0)

var failures := 0


func _check(ok: bool, what: String) -> void:
	if ok:
		print("  [OK] ", what)
	else:
		failures += 1
		printerr("  [ÉCHEC] ", what)


func _load_route(dir: String):
	var route = RouteDataScript.new()
	if not route.load_world_dir(dir):
		printerr("Parcours illisible : ", dir)
		quit(1)
		return null
	return route


func _new_streamer(route, dir: String):
	var st = WorldStreamer.new()
	st.set_world(route, dir)
	return st


func _cam(route, s_pos: float) -> Vector3:
	return route.sample_point(s_pos) + EYE


func _right(route, s_pos: float) -> Vector3:
	var h := deg_to_rad(route.sample_heading_deg(s_pos))
	return Vector3(cos(h), 0.0, sin(h))


## Fenêtre attendue, calculée indépendamment de world_streamer.gd (lot E1, §4.3, à v = 0).
func _expected_keys(route, dir: String, s_pos: float) -> Array:
	var keys := []
	var count := RoadBuilder.chunk_count(route)
	# Amorces avant le départ (k = −1) et après l'arrivée (k = count) sur un parcours ouvert : l'arrivée de la démo
	# est à plus de 200 m du départ.
	var start: Vector3 = route.sample_point(0.0)
	var finish: Vector3 = route.sample_point(route.length_m)
	var k_first := 0 if route.type == "loop" else -1
	var k_last := count - 1 if route.type == "loop" or Vector2(finish.x - start.x, finish.z - start.z).length() <= 200.0 else count
	for k in range(k_first, k_last + 1):
		if k * 1000.0 < s_pos + 3000.0 and (k + 1) * 1000.0 > s_pos - 1000.0:
			keys.append("road:%d" % k)
	var cam := _cam(route, s_pos)
	for level in ["near", "far"]:
		var radius := 1500.0 if level == "near" else 12000.0
		var size: float = TerrainTiles.LEVELS[level]["size"]
		for t in TerrainTiles.scan_index(dir, level):
			var dx := maxf(maxf(t.x * size - cam.x, 0.0), cam.x - (t.x + 1) * size)
			var dz := maxf(maxf(t.y * size - cam.z, 0.0), cam.z - (t.y + 1) * size)
			if Vector2(dx, dz).length() <= radius:
				keys.append("%s:%d:%d" % [level, t.x, t.y])
	keys.sort()
	return keys


## Altitudes affichées d'une tuile, relues dans le maillage de son MeshInstance3D.
func _instance_heights(mi: MeshInstance3D) -> PackedFloat32Array:
	var verts: PackedVector3Array = mi.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var out := PackedFloat32Array()
	for v in verts:
		out.append(v.y)
	return out


# --- 1. raccord route-terrain ------------------------------------------------------------

func test_junction(terrain_dir: String) -> void:
	print("Test 1 – raccord route-terrain")
	var route = _load_route(terrain_dir)
	var st = _new_streamer(route, terrain_dir)
	_check(st.has_terrain and not st.has_ground(), "couche terrain détectée")
	for s_pos in [0.0, 2500.0]:
		st.update_window(s_pos, 0.0, _cam(route, s_pos))
		st.flush()
		var expected := _expected_keys(route, terrain_dir, s_pos)
		_check(st.loaded_keys() == expected, "s = %.0f : chargés = fenêtre (%d objets : %s)" % [
			s_pos, expected.size(), ", ".join(expected)])
		var worst_center := 0.0
		var worst_gap := -INF
		var best_gap := INF
		for ds in [0.0, 1.0, 7.3, 15.0]:
			var sp: float = route.wrap_s(s_pos + ds)
			var k := mini(int(sp / 1000.0), RoadBuilder.chunk_count(route) - 1)
			var road_mi: MeshInstance3D = st.instance("road:%d" % k)
			var road_y := RoadBuilder.center_height(road_mi.mesh.surface_get_arrays(0), route, k, sp)
			var center: Vector3 = route.sample_point(sp)
			worst_center = maxf(worst_center, absf(road_y - center.y))
			for side in [-1.0, 1.0]:
				var p: Vector3 = center + _right(route, sp) * (6.0 * side)   # 3 m du bord de la chaussée
				var t := TerrainTiles.tile_of("near", p.x, p.z)
				var tile_mi: MeshInstance3D = st.instance("near:%d:%d" % [t.x, t.y])
				if tile_mi == null:
					_check(false, "tuile proche %s chargée sous la route" % t)
					continue
				var y := TerrainTiles.mesh_height_at(_instance_heights(tile_mi), "near", t.x, t.y, p.x, p.z)
				var gap := road_y - y
				worst_gap = maxf(worst_gap, gap)
				best_gap = minf(best_gap, gap)
		_check(worst_center <= 0.01, "s = %.0f : centre du ruban = sample_point(s).y (écart max %.4f m)" % [s_pos, worst_center])
		_check(best_gap >= 0.0 and worst_gap < 0.20,
				"s = %.0f : terrain à 3 m du bord sous la route de %.3f à %.3f m (< 0,20 m)" % [s_pos, best_gap, worst_gap])
	# Le lointain est dessiné 2 m sous ses valeurs, le proche à son altitude exacte.
	var any_far: String = st.loaded_keys().filter(func(k): return k.begins_with("far:"))[0]
	var parts := any_far.split(":")
	var raw := TerrainTiles.load_tile(terrain_dir, "far", int(parts[1]), int(parts[2]))
	var shown := _instance_heights(st.instance(any_far))
	_check(is_equal_approx(shown[5000], raw[5000] - TerrainTiles.FAR_DROP_M), "tuile lointaine abaissée de 2 m")
	st.clear()
	st.free()


# --- 2. durée sans fuite -----------------------------------------------------------------

func test_long_run(terrain_dir: String) -> void:
	print("Test 2 – durée sans fuite (0 → fin à 20 m/s simulés, 60 images/s)")
	var route = _load_route(terrain_dir)
	var st = _new_streamer(route, terrain_dir)
	var v := 20.0
	var step := v / 60.0
	var s_pos := 0.0
	var max_meshes := 0
	var holes := 0
	var frames := 0
	var count_third := -1.0
	st.update_window(0.0, v, _cam(route, 0.0))
	st.flush()
	while true:
		var cam := _cam(route, s_pos)
		st.update_window(s_pos, v, cam)
		st.wait_jobs()
		st.integrate(WorldStreamer.MAX_NEW_PER_FRAME)
		frames += 1
		max_meshes = maxi(max_meshes, st.get_child_count())
		# Aucun trou devant : le tronçon sous la caméra et celui 10 s plus loin sont affichés.
		for ahead in [0.0, v * 10.0]:
			var k := mini(int(route.wrap_s(s_pos + ahead) / 1000.0), RoadBuilder.chunk_count(route) - 1)
			if st.instance("road:%d" % k) == null:
				holes += 1
		if count_third < 0.0 and s_pos >= route.length_m / 3.0:
			st.flush()
			count_third = Performance.get_monitor(Performance.OBJECT_COUNT)
		if s_pos >= route.length_m:
			break
		s_pos = minf(s_pos + step, route.length_m)
	st.flush()
	var count_end := Performance.get_monitor(Performance.OBJECT_COUNT)
	# Borne : 5 tronçons (fenêtre de 4 km), 16 tuiles proches (rayon 1,5 km) et les tuiles lointaines.
	var bound := 5 + 16 + TerrainTiles.scan_index(terrain_dir, "far").size()
	_check(max_meshes <= bound, "%d images ; MeshInstance3D vivants au plus %d (borne %d)" % [frames, max_meshes, bound])
	_check(holes == 0, "aucun trou devant la caméra (%d manques)" % holes)
	var drift := (count_end - count_third) / count_third
	_check(absf(drift) <= 0.05, "objets : %d au premier tiers, %d en fin (%+.1f %%, tolérance ± 5 %%)" % [
		count_third, count_end, drift * 100.0])
	st.clear()
	st.free()


# --- 3. jointures --------------------------------------------------------------------------

func test_joints(terrain_dir: String) -> void:
	print("Test 3 – jointures du ruban")
	for dir in [terrain_dir, PLAIN_WORLD]:
		var route = _load_route(dir)
		var count := RoadBuilder.chunk_count(route)
		var bad := 0
		for k in range(count - 1):
			var a: PackedVector3Array = RoadBuilder.build_chunk_arrays(route, k)[Mesh.ARRAY_VERTEX]
			var b: PackedVector3Array = RoadBuilder.build_chunk_arrays(route, k + 1)[Mesh.ARRAY_VERTEX]
			var n := RoadBuilder.VERTS_PER_SECTION
			for c in range(n):
				if a[a.size() - n + c] != b[c]:
					bad += 1
		_check(bad == 0, "%s : %d jointures, sommets identiques (%d différences)" % [dir.get_file(), count - 1, bad])


# --- 4. terrain absent ---------------------------------------------------------------------

func test_no_terrain() -> void:
	print("Test 4 – parcours sans couche terrain")
	var route = _load_route(PLAIN_WORLD)
	var st = _new_streamer(route, PLAIN_WORLD)
	st.update_window(0.0, 0.0, _cam(route, 0.0))
	st.flush()
	var min_alt := INF
	for a in route.alt_m:
		min_alt = minf(min_alt, a)
	_check(not st.has_terrain and st.has_ground(), "sol plat présent")
	_check(is_equal_approx(st.ground_height(), min_alt - 5.0), "sol plat 5 m sous l'altitude minimale (%.2f m)" % st.ground_height())
	_check(st.loaded_keys() == ["road:-1", "road:0", "road:1", "road:2"], "ruban affiché (amorce du départ comprise) : %s" % ", ".join(st.loaded_keys()))
	st.clear()
	st.free()


# --- compléments ---------------------------------------------------------------------------

func test_nan_and_winding(terrain_dir: String) -> void:
	print("Compléments – NaN, sens des faces")
	var route = _load_route(terrain_dir)
	var heights := TerrainTiles.flat_heights(1000.0)
	heights[50 * 101 + 50] = NAN
	heights[50 * 101 + 51] = 1010.0
	var filled := TerrainTiles.fill_nan(heights, "near", 0, 0, func(_x, _z): return -1.0)
	_check(is_equal_approx(filled[50 * 101 + 50], (7.0 * 1000.0 + 1010.0) / 8.0), "NaN remplacé par la moyenne des voisins valides")
	var all_nan := PackedFloat32Array()
	all_nan.resize(101 * 101)
	all_nan.fill(NAN)
	filled = TerrainTiles.fill_nan(all_nan, "near", 0, 0, func(_x, _z): return 1234.0)
	_check(filled[0] == 1234.0 and filled[101 * 101 - 1] == 1234.0, "sans voisin valide : valeur de repli")
	_check(is_equal_approx(TerrainTiles.nearest_route_alt(route, route.x[100] + 1.0, route.z[100]), route.alt_m[100]),
			"dernier repli : altitude de la route la plus proche")
	# Faces avant de Godot dans le sens horaire : la normale du plan (a, b, c) doit monter.
	var t_arrays := TerrainTiles.build_arrays(TerrainTiles.flat_heights(0.0), "near")
	var tv: PackedVector3Array = t_arrays[Mesh.ARRAY_VERTEX]
	var ti: PackedInt32Array = t_arrays[Mesh.ARRAY_INDEX]
	_check(Plane(tv[ti[0]], tv[ti[1]], tv[ti[2]]).normal.y > 0.99, "terrain : faces tournées vers le haut")
	var r_arrays := RoadBuilder.build_chunk_arrays(route, 0)
	var rv: PackedVector3Array = r_arrays[Mesh.ARRAY_VERTEX]
	var ri: PackedInt32Array = r_arrays[Mesh.ARRAY_INDEX]
	var rn: PackedVector3Array = r_arrays[Mesh.ARRAY_NORMAL]
	var ok := true
	for tri in range(0, ri.size(), 3):
		var pn := Plane(rv[ri[tri]], rv[ri[tri + 1]], rv[ri[tri + 2]]).normal
		if pn.y <= 0.0 or pn.dot(rn[ri[tri]]) < 0.99:
			ok = false
			break
	_check(ok, "ruban : faces vers le haut, normales cohérentes")


func measure(terrain_dir: String) -> void:
	print("Mesures de temps CPU (fil principal, sans écran)")
	var route = _load_route(terrain_dir)
	var reps := 5
	var t0 := Time.get_ticks_usec()
	for i in range(reps):
		RoadBuilder.build_chunk_arrays(route, 1)
	var road_ms := (Time.get_ticks_usec() - t0) / 1000.0 / reps
	var t: Vector2i = TerrainTiles.scan_index(terrain_dir, "near").keys()[0]
	t0 = Time.get_ticks_usec()
	for i in range(reps):
		var h := TerrainTiles.load_filled(terrain_dir, "near", t.x, t.y, route)
		TerrainTiles.build_arrays(h, "near", TerrainTiles.load_neighbour_edges(terrain_dir, "near", t.x, t.y))
	var near_ms := (Time.get_ticks_usec() - t0) / 1000.0 / reps
	var arrays := TerrainTiles.build_arrays(TerrainTiles.flat_heights(0.0), "near")
	t0 = Time.get_ticks_usec()
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var mesh_ms := (Time.get_ticks_usec() - t0) / 1000.0
	print("  tronçon de route (1 000 m, 501 coupes) : %.1f ms" % road_ms)
	print("  tuile proche (101 × 101, lecture + NaN + normales) : %.1f ms" % near_ms)
	print("  création de l'ArrayMesh d'une tuile (fil principal) : %.1f ms" % mesh_ms)


# --- 5. amorces de chaussée avant le départ et après l'arrivée -----------------------------------

## Demande du 1er novembre (« la route qui commence nulle part ») : la chaussée continue tout droit avant le départ
## et après l'arrivée, raccordée sans marche au ruban, posée sur le terrain affiché, sans arbre dessus.
func test_leads(terrain_dir: String) -> void:
	print("Test 5 – amorces avant le départ et après l'arrivée")
	var route = _load_route(terrain_dir)
	var st = _new_streamer(route, terrain_dir)
	var count := RoadBuilder.chunk_count(route)
	_check(RoadBuilder.has_chunk(route, -1) and RoadBuilder.has_chunk(route, count), "démo ouverte : deux amorces")
	_check(not RoadBuilder.has_chunk(route, -2) and not RoadBuilder.has_chunk(route, count + 1), "pas de tronçon au-delà des amorces")
	for spec in [[0.0, -1, 0], [route.length_m, count, count - 1]]:
		var s_end: float = spec[0]
		var k_lead: int = spec[1]
		var k_road: int = spec[2]
		st.update_window(s_end, 0.0, _cam(route, s_end))
		st.flush()
		var lead_mi: MeshInstance3D = st.instance("road:%d" % k_lead)
		var road_mi: MeshInstance3D = st.instance("road:%d" % k_road)
		if lead_mi == null or road_mi == null:
			_check(false, "amorce road:%d et tronçon road:%d affichés" % [k_lead, k_road])
			continue
		var lead_v: PackedVector3Array = lead_mi.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
		var road_v: PackedVector3Array = road_mi.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
		var n := RoadBuilder.VERTS_PER_SECTION
		# Coupe commune : dernière de l'amorce du départ = première du tronçon 0 ; première de l'amorce d'arrivée = dernière du dernier tronçon.
		var lead_base := lead_v.size() - n if k_lead < 0 else 0
		var road_base := 0 if k_lead < 0 else road_v.size() - n
		var worst := 0.0
		for c in range(n):
			worst = maxf(worst, lead_v[lead_base + c].distance_to(road_v[road_base + c]))
		_check(worst < 0.001, "road:%d : raccord au ruban sans marche (écart %.4f m)" % [k_lead, worst])
		var rng := RoadBuilder.chunk_range(route, k_lead)
		var far_c := (lead_v[0] + lead_v[5]) * 0.5 if k_lead < 0 else (lead_v[lead_v.size() - 6] + lead_v[lead_v.size() - 1]) * 0.5
		var end_p: Vector3 = route.sample_point(s_end)
		var reach := Vector2(far_c.x - end_p.x, far_c.z - end_p.z).length()
		_check(absf(reach - (rng.y - rng.x)) < 0.5, "road:%d : %.0f m de chaussée en plus (attendu %.0f m)" % [k_lead, reach, rng.y - rng.x])
		# Terrain affiché sous l'axe de l'amorce, au-delà du raccord : sous la chaussée, pas trop loin dessous.
		var worst_above := -INF
		var worst_below := -INF
		for i in range(0, lead_v.size(), n):
			var c := (lead_v[i + 2] + lead_v[i + 3]) * 0.5
			var t := TerrainTiles.tile_of("near", c.x, c.z)
			var tile_mi: MeshInstance3D = st.instance("near:%d:%d" % [t.x, t.y])
			if tile_mi == null:
				continue
			var hs := _instance_heights(tile_mi)
			var y_t := TerrainTiles.mesh_height_at(hs, "near", t.x, t.y, c.x, c.z)
			worst_above = maxf(worst_above, y_t - c.y)
			worst_below = maxf(worst_below, c.y - y_t)
		_check(worst_above <= 0.0, "road:%d : terrain sous la chaussée (dépasse au plus de %.3f m)" % [k_lead, worst_above])
		_check(worst_below < 1.0, "road:%d : chaussée posée sur le terrain (au plus %.2f m au-dessus)" % [k_lead, worst_below])
	# Arbres : l'axe des amorces est dans le couloir de la route où vegetation_placer.gd n'en pose pas.
	var outside := 0
	var looked := 0
	for seg in RoadBuilder.lead_segments(route):
		var a: Vector2 = seg[0]
		var b: Vector2 = seg[1]
		var rect := Rect2(a, Vector2.ZERO).expand(b).grow(10.0)
		var buckets := VegetationPlacer._road_buckets(route, rect, 4.0)
		for i in range(1, 21):
			var p := a.lerp(b, i / 20.0)
			looked += 1
			if not VegetationPlacer._near_road(buckets, p.x, p.y, 4.0):
				outside += 1
	_check(looked > 0 and outside == 0, "amorces dans le couloir sans arbre (%d points hors couloir sur %d)" % [outside, looked])
	st.clear()
	st.free()


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		printerr("Usage : … --script res://tests/test_world_streamer.gd -- <dossier demo.world avec terrain>")
		quit(2)
		return
	var terrain_dir: String = args[0]
	test_junction(terrain_dir)
	test_long_run(terrain_dir)
	test_joints(terrain_dir)
	test_no_terrain()
	test_leads(terrain_dir)
	test_nan_and_winding(terrain_dir)
	measure(terrain_dir)
	print("Rendu par tronçons : %s" % ("tous les tests passent" if failures == 0 else "%d échec(s)" % failures))
	quit(1 if failures > 0 else 0)
