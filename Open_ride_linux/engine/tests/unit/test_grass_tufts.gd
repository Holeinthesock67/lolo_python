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

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite plein sud le long de x = 500, de 2 km.
func _route() -> Variant:
	var ds := 10.0
	var n := 201
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": ds * (n - 1), "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(1000.0)
		d["x"].append(500.0)
		d["z"].append(i * ds)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(180.0)
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
	var mat: ShaderMaterial = g._mmi.material_override
	_check(is_equal_approx(float(mat.get_shader_parameter("fade_end_m")), GrassTufts.FADE_END_M)
		and GrassTufts.FADE_END_M <= GrassTufts.CHUNKS_AHEAD * GrassTufts.CHUNK_M and g._mm.use_colors,
		"fondu à %.0f m, avant la fin de la fenêtre (%.0f m) ; couleurs d'instance" % [GrassTufts.FADE_END_M, GrassTufts.CHUNKS_AHEAD * GrassTufts.CHUNK_M])
	g.free()


func _init() -> void:
	_test_blades_and_tints()
	_test_tree_materials()
	_test_budget_and_low()
	_test_determinism_and_exclusions()
	_test_cost()
	print("test_grass_tufts : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
