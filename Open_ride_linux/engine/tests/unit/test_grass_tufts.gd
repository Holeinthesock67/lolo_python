extends SceneTree

## Tests unitaires sans écran des touffes d'herbe `grass_tufts.gd` et des matériaux de balancement de
## `tree_renderer.gd` (Lot P5).
## Lancement : godot --headless --path engine --script res://tests/unit/test_grass_tufts.gd

const GrassTufts := preload("res://scripts/grass_tufts.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const WindModel := preload("res://scripts/wind_model.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite plein sud le long de x = 500, de 2 km (ou plein nord, cap alterné 359° / 1° : il passe par 0).
func _route(north: bool = false) -> Variant:
	var ds := 10.0
	var n := 201
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": ds * (n - 1), "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(1000.0)
		d["x"].append(500.0)
		d["z"].append(-i * ds if north else i * ds)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append((359.0 if i % 2 == 0 else 1.0) if north else 180.0)
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _settle(g, cam_s: float) -> void:
	for i in range(400):
		g.update(cam_s)
		if g.is_settled():
			return


func _positions(g) -> PackedVector3Array:
	return g.get_positions()


func _test_budget_and_low() -> void:
	var route = _route()
	var low = GrassTufts.new()
	root.add_child(low)
	low.configure(QualityPresets.living("low", false)["grass_tufts"], route)
	low.update(100.0)
	_check(low.get_child_count() == 0 and low.get_capacity() == 0, "décor vivant coupé : 0 touffe, nœud vide")
	for preset in ["medium", "high"]:
		var budget: int = QualityPresets.living(preset)["grass_tufts"]
		var g = GrassTufts.new()
		root.add_child(g)
		g.configure(budget, route)
		_settle(g, 300.0)
		_check(g.get_capacity() <= budget and g.get_visible_count() <= budget and g.get_visible_count() > 0,
			"%s : %d touffes placées, capacité %d, budget %d" % [preset, g.get_visible_count(), g.get_capacity(), budget])
		g.queue_free()
	low.queue_free()


func _test_determinism_and_exclusions() -> void:
	var route = _route()
	var a = GrassTufts.new()
	var b = GrassTufts.new()
	root.add_child(a)
	root.add_child(b)
	a.configure(4000, route, 6.0, 7)
	b.configure(4000, route, 6.0, 7)
	_settle(a, 500.0)
	_settle(b, 500.0)
	var pa := _positions(a)
	var pb := _positions(b)
	_check(pa == pb and pa.size() > 0, "même graine : mêmes positions (%d touffes)" % pa.size())
	var c = GrassTufts.new()
	root.add_child(c)
	c.configure(4000, route, 6.0, 8)
	_settle(c, 500.0)
	_check(_positions(c) != pa, "autre graine : autres positions")

	var on_road := 0
	var out_band := 0
	for p in pa:
		var lateral := absf(p.x - 500.0)
		if lateral < 3.0 + GrassTufts.BAND_MIN_M - 1e-3:
			on_road += 1
		if lateral > 3.0 + GrassTufts.BAND_MAX_M + 1e-3:
			out_band += 1
	_check(on_road == 0, "aucune touffe sur la route ni à moins de 2 m de son bord")
	_check(out_band == 0, "toutes les touffes dans la bande de 2 à 15 m du bord")

	# Cap qui passe par le nord entre deux stations : la normale à la route reste perpendiculaire
	var nr = GrassTufts.new()
	root.add_child(nr)
	nr.configure(4000, _route(true), 6.0, 7)
	_settle(nr, 500.0)
	var on_road_n := 0
	for p in _positions(nr):
		if absf(p.x - 500.0) < 3.0 + GrassTufts.BAND_MIN_M - 0.05:
			on_road_n += 1
	_check(on_road_n == 0 and _positions(nr).size() > 0,
		"cap 359° / 1° : aucune touffe sur la route (%d sur %d)" % [on_road_n, _positions(nr).size()])
	nr.queue_free()

	# Bâtiment et étang : rectangles à droite et à gauche de la route
	var house := PackedVector2Array([Vector2(506, 400), Vector2(520, 400), Vector2(520, 600), Vector2(506, 600)])
	var pond := PackedVector2Array([Vector2(480, 450), Vector2(494, 450), Vector2(494, 550), Vector2(480, 550)])
	var e = GrassTufts.new()
	root.add_child(e)
	e.exclusions = [house, pond]
	e.configure(4000, route, 6.0, 7)
	_settle(e, 500.0)
	var inside := 0
	for p in _positions(e):
		var p2 := Vector2(p.x, p.z)
		if Geometry2D.is_point_in_polygon(p2, house) or Geometry2D.is_point_in_polygon(p2, pond):
			inside += 1
	_check(inside == 0 and _positions(e).size() < pa.size(),
		"aucune touffe dans le bâtiment ni dans l'étang (%d placées contre %d)" % [_positions(e).size(), pa.size()])

	# Pente : terrain à 100 % de pente à droite, plat à gauche
	var s = GrassTufts.new()
	root.add_child(s)
	s.height_at = func(x: float, _z: float) -> float: return maxf(x - 500.0, 0.0) * 1.0 + 1000.0
	s.configure(4000, route, 6.0, 7)
	_settle(s, 500.0)
	var right := 0
	var left := 0
	for p in _positions(s):
		if p.x > 500.0:
			right += 1
		else:
			left += 1
	_check(right == 0 and left > 0, "pente de 100 %% : aucune touffe côté pentu (%d), %d côté plat" % [right, left])
	for n in [a, b, c, e, s]:
		n.queue_free()


# Critère 5 : coût par image (vent global + vent apparent + mise à jour des touffes)
func _test_cost() -> void:
	var route = _route()
	var g = GrassTufts.new()
	root.add_child(g)
	g.configure(12000, route)
	var wind = WindModel.new()
	wind.on_state({"wind": {"speed_mps": 7.0, "from_deg": 270.0, "head_mps": 0.0, "gust": 0.3}}, 0.0)
	var frames := 900   # 15 s à 60 images/s, à 10 m/s : la fenêtre glisse de 150 m
	var t0 := Time.get_ticks_usec()
	for i in range(frames):
		var now := i / 60.0
		TreeRenderer.apply_wind(wind.evaluate(now))
		g.set_apparent_wind(wind.apparent(10.0, 180.0))
		g.update(100.0 + now * 10.0)
	var per_frame_ms := (Time.get_ticks_usec() - t0) / 1000.0 / frames
	_check(PerfBudget.check("grass_tufts_frame", per_frame_ms), "coût par image du lot : %.3f ms" % per_frame_ms)
	g.queue_free()


# Saccades du 04/11 : sur la demo intégrée sans tuile de terrain, la hauteur d'une touffe vient de la route
# (repli de terrain_height_fn) ; 120 places par image faisaient 60 à 80 ms au début de chaque tronçon de 40 m.
# Pire image du remplissage, dans les trois qualités, et fenêtre toujours remplie avant d'arriver au tronçon.
func _test_fill_without_terrain() -> void:
	var route = RouteDataScript.new()
	_check(route.load_world_dir("res://demo/demo.world"), "demo intégrée chargée")
	for preset in ["low", "medium", "high"]:
		var g = GrassTufts.new()
		root.add_child(g)
		g.configure(QualityPresets.living(preset)["grass_tufts"], route)
		g.height_at = OsmStreamer.terrain_height_fn("res://demo/demo.world", route)
		var worst := 0.0
		var late := 0          # images où le tronçon de la caméra n'est pas encore rempli
		var s := 50.0
		_settle(g, s)
		for i in range(60 * 20):   # 20 s à 60 km/h : 330 m, huit tronçons
			var t0 := Time.get_ticks_usec()
			g.update(s)
			worst = maxf(worst, (Time.get_ticks_usec() - t0) / 1000.0)
			var k := int(floor(s / GrassTufts.CHUNK_M))
			for job in g._queue:
				if int(job[1]) <= k:
					late += 1
			s += (60.0 / 3.6) / 60.0
		PerfBudget.check("grass_tufts_fill_frame", worst)
		# Seuil dur, quel que soit le mode des budgets : jamais une image entière à 60 images/s (avant : 60 à 80 ms).
		_check(worst < 16.7, "%s sans terrain : pire image du remplissage %.2f ms (sous 16,7 ms)" % [preset, worst])
		_check(late == 0, "%s sans terrain : tronçon de la caméra toujours rempli à 60 km/h (%d image(s) en retard)" % [preset, late])
		g.queue_free()


# Critère 3 : tree_sway faux -> StandardMaterial3D d'origine ; vrai -> shader de balancement
func _test_tree_materials() -> void:
	var r = TreeRenderer.new()
	root.add_child(r)
	_check(r._lod0_material is StandardMaterial3D and r._lod1_material is StandardMaterial3D,
		"avant set_preset : matériaux d'origine")
	r.set_preset("low", false)
	_check(not r.is_tree_sway() and r._lod0_material is StandardMaterial3D,
		"décor vivant coupé : matériaux d'origine (rendu inchangé)")
	var std0: StandardMaterial3D = r._lod0_material
	var std1: StandardMaterial3D = r._lod1_material
	_check(std0.vertex_color_use_as_albedo and is_equal_approx(std0.roughness, 0.85)
		and std1.cull_mode == BaseMaterial3D.CULL_DISABLED, "matériaux d'origine : mêmes réglages qu'avant le lot")
	r.set_preset("low")
	_check(r.is_tree_sway() and r._lod0_material is ShaderMaterial and r._lod1_material is ShaderMaterial,
		"low avec décor vivant : shader de balancement sur les deux LOD")
	var lod1: ShaderMaterial = r._lod1_material
	_check("cull_disabled" in lod1.shader.code and float(lod1.get_shader_parameter("sway_amplitude_m")) < 0.45,
		"LOD 1 : vu des deux côtés, amplitude réduite")
	_check(ProjectSettings.has_setting("shader_globals/wind_dir")
		and ProjectSettings.has_setting("shader_globals/wind_phase"),
		"paramètres globaux du vent déclarés dans project.godot")
	r.queue_free()


## Lot Y11 (H4) : gerbe de brins, teintes d'instance, fondu au loin dans le matériau.
func _test_blades_and_tints() -> void:
	var mesh := GrassTufts.build_tuft_mesh()
	var verts: PackedVector3Array = mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	_check(verts.size() == GrassTufts.BLADES * 9, "touffe : %d brins de trois triangles (%d sommets)" % [GrassTufts.BLADES, verts.size()])
	var top := 0.0
	for v in verts:
		top = maxf(top, v.y)
	_check(top <= GrassTufts.TUFT_HEIGHT_M + 1e-4 and top > GrassTufts.TUFT_HEIGHT_M * 0.5, "hauteur de la gerbe : %.2f m" % top)
	var g = GrassTufts.new()
	g.tuft_seed = 7
	var seen := {}
	for slot in range(400):
		seen[g.tint_index(3, slot)] = true
	_check(seen.size() == GrassTufts.TINTS.size(), "les %d teintes sont tirées" % GrassTufts.TINTS.size())
	g.configure(1000, _route())
	var mat: ShaderMaterial = g._near_mmi[0].material_override
	_check(is_equal_approx(float(mat.get_shader_parameter("fade_end_m")), GrassTufts.FADE_END_M)
		and GrassTufts.FADE_END_M <= GrassTufts.CHUNKS_AHEAD * GrassTufts.CHUNK_M and g._near_mm[0].use_colors,
		"fondu à %.0f m, avant la fin de la fenêtre (%.0f m) ; couleurs d'instance" % [GrassTufts.FADE_END_M, GrassTufts.CHUNKS_AHEAD * GrassTufts.CHUNK_M])
	g.free()


## Lot « herbe au loin » : gerbe simplifiée au-delà de LOD_SWITCH_M, un MultiMesh par tronçon et par niveau,
## tirage du fondu partagé CPU / GPU, boîtes et plages de visibilité qui ne coupent jamais une touffe montrée.
func _test_far_lod() -> void:
	var far := GrassTufts.build_far_tuft_mesh()
	var near := GrassTufts.build_tuft_mesh()
	var fv: PackedVector3Array = far.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var nv: PackedVector3Array = near.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var top := 0.0
	for v in fv:
		top = maxf(top, v.y)
	_check(fv.size() == GrassTufts.FAR_BLADES * 3 and fv.size() * 6 <= nv.size() and top > GrassTufts.TUFT_HEIGHT_M * 0.6
		and top <= GrassTufts.TUFT_HEIGHT_M + 1e-4,
		"gerbe lointaine : %d sommets au lieu de %d, hauteur %.2f m" % [fv.size(), nv.size(), top])
	_check(is_equal_approx(GrassTufts.keep_at(GrassTufts.THIN_START_M), 1.0) and is_zero_approx(GrassTufts.keep_at(GrassTufts.FADE_END_M))
		and GrassTufts.keep_at(80.0) < GrassTufts.keep_at(50.0) and GrassTufts.LOD_SWITCH_M + GrassTufts.LOD_BLEND_M < GrassTufts.FADE_END_M,
		"courbe du fondu : 1 à %.0f m, 0 à %.0f m ; passage à %.0f m avant la fin du fondu" % [GrassTufts.THIN_START_M, GrassTufts.FADE_END_M, GrassTufts.LOD_SWITCH_M])
	var route = _route()
	var g = GrassTufts.new()
	root.add_child(g)
	g.tuft_seed = 3
	g.configure(int(QualityPresets.living("high")["grass_tufts"]), route)
	var groups := GrassTufts.CHUNKS_BEHIND + GrassTufts.CHUNKS_AHEAD + 1
	var near_mat: ShaderMaterial = g._near_material
	var far_mat: ShaderMaterial = g._far_material
	_check(g.get_child_count() == groups * 2 and g._near_mm[0].use_custom_data and g._far_mm[0].use_custom_data
		and bool(near_mat.get_shader_parameter("pick_from_custom")) and bool(far_mat.get_shader_parameter("pick_from_custom"))
		and is_equal_approx(float(near_mat.get_shader_parameter("lod_end_m")), GrassTufts.LOD_SWITCH_M)
		and is_zero_approx(float(near_mat.get_shader_parameter("lod_begin_m")))
		and is_equal_approx(float(far_mat.get_shader_parameter("lod_begin_m")), GrassTufts.LOD_SWITCH_M)
		and is_zero_approx(float(far_mat.get_shader_parameter("lod_end_m"))),
		"%d MultiMesh (2 par tronçon) ; gerbe complète jusqu'à %.0f m, simplifiée au-delà" % [g.get_child_count(), GrassTufts.LOD_SWITCH_M])
	_settle(g, 300.0)
	var threshold := GrassTufts.keep_at(GrassTufts.LOD_SWITCH_M - GrassTufts.LOD_BLEND_M)
	var bad_pick := 0
	var outside := 0
	var range_short := 0
	var expected_far := 0
	for gi in range(groups):
		var k: int = g._slot_chunk[gi]
		var mm: MultiMesh = g._near_mm[gi]
		var fm: MultiMesh = g._far_mm[gi]
		var box: AABB = mm.custom_aabb
		var c := box.get_center()
		for f in range(fm.visible_instance_count):
			if fm.get_instance_custom_data(f).r >= threshold:
				bad_pick += 1
		for slot in range(g._filled[gi]):
			if g._placed[gi * g._per_chunk + slot] != 1:
				continue
			var p: Vector3 = mm.get_instance_transform(slot).origin
			var pick := mm.get_instance_custom_data(slot).r
			if not is_equal_approx(pick, g.pick_of(k, slot)):
				bad_pick += 1
			expected_far += 1 if pick < threshold else 0
			if not box.has_point(p):
				outside += 1
			# Une touffe encore montrée par la gerbe complète (d < passage + fondu) ne doit jamais tomber hors
			# de la plage du MultiMesh, ni une touffe lointaine encore dans le fondu hors de celle du lointain.
			var r := p.distance_to(c)
			if g._near_mmi[gi].visibility_range_end < GrassTufts.LOD_SWITCH_M + GrassTufts.LOD_BLEND_M + r \
					or g._far_mmi[gi].visibility_range_end < GrassTufts.FADE_END_M + r \
					or g._far_mmi[gi].visibility_range_begin > maxf(0.0, GrassTufts.LOD_SWITCH_M - GrassTufts.LOD_BLEND_M - r):
				range_short += 1
	_check(bad_pick == 0 and expected_far == g.get_far_count() and g.get_far_count() > 0,
		"gerbe lointaine : %d touffes, toutes celles que le fondu montre au-delà du passage (tirage CPU = GPU)" % g.get_far_count())
	_check(outside == 0 and range_short == 0,
		"boîtes des tronçons et plages de visibilité : aucune touffe montrée coupée (%d hors boîte, %d hors plage)" % [outside, range_short])
	var radius := 0.0
	for gi in range(groups):
		radius = maxf(radius, g._near_mm[gi].custom_aabb.size.length() * 0.5)
	_check(radius < GrassTufts.CHUNK_M,
		"tronçon de route droite : demi-diagonale de boîte %.0f m (gerbe complète écartée à %.0f m du centre)" % [radius, GrassTufts.LOD_SWITCH_M + GrassTufts.LOD_BLEND_M + radius])
	# Tronçon recyclé : ses anciennes touffes ne sont plus dessinées ni comptées avant d'être recalculées.
	var before := g.get_visible_count()
	g.update(300.0 + GrassTufts.CHUNK_M)
	var recycled := posmod(int(floor((300.0 + GrassTufts.CHUNK_M) / GrassTufts.CHUNK_M)) + GrassTufts.CHUNKS_AHEAD, groups)
	_check(g._near_mm[recycled].visible_instance_count <= g._filled[recycled] and g._far_mm[recycled].visible_instance_count == g._far_count[recycled]
		and g.get_visible_count() <= before and g.get_positions().size() == g.get_visible_count(),
		"tronçon recyclé : %d touffes comptées après le pas (avant %d), positions = compte" % [g.get_visible_count(), before])
	_settle(g, 300.0 + GrassTufts.CHUNK_M)
	_check(g.get_visible_count() > 0 and g.get_visible_count() <= g.get_capacity(), "fenêtre remplie de nouveau : %d touffes" % g.get_visible_count())
	g.queue_free()


class _DesertModel:
	var dry := 1.0
	func active() -> bool:
		return true
	func weights_at(_x: float, _z: float) -> Dictionary:
		return {"sand_desert": dry, "temperate_meadow": 1.0 - dry}


## Désert (03/11) : herbe sèche (teintes DRY_TINTS) et clairsemée ; hors désert ou sans modèle, herbe d'avant.
func _test_desert() -> void:
	var g = GrassTufts.new()
	_check(g.dry_draw(0, 0, Vector3.ZERO) == 0, "sans modèle de biome : herbe d'avant")
	var m := _DesertModel.new()
	g.biome_model = m
	var kept := 0
	var green_in_desert := 0
	var n := 400
	for slot in range(n):
		var d: int = g.dry_draw(3, slot, Vector3.ZERO)
		green_in_desert += 1 if d == 0 else 0
		kept += 1 if d == 1 else 0
	_check(green_in_desert == 0, "désert pur : jamais d'herbe verte")
	var part := float(kept) / n
	_check(absf(part - GrassTufts.DRY_KEEP) < 0.08, "désert : %.0f %% des places gardées (cible %.0f %%)" % [part * 100.0, GrassTufts.DRY_KEEP * 100.0])
	m.dry = 0.0
	var green := 0
	for slot in range(n):
		green += 1 if g.dry_draw(3, slot, Vector3.ZERO) == 0 else 0
	_check(green == n, "prairie : toutes les touffes d'avant")
	for t in GrassTufts.DRY_TINTS:
		var c: Color = t * Color(0.4, 0.56, 0.24)
		_check(c.r > c.g and c.g > c.b, "teinte sèche %s : paille ou ocre (rouge > vert > bleu)" % c.to_html(false))
	g.free()


func _init() -> void:
	_test_blades_and_tints()
	_test_far_lod()
	_test_tree_materials()
	_test_budget_and_low()
	_test_determinism_and_exclusions()
	_test_cost()
	_test_fill_without_terrain()
	_test_desert()
	print("test_grass_tufts : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
