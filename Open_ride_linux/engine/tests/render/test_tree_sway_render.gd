extends SceneTree

## Rendu hors écran du balancement des arbres (Lot P5, critère 2) : un arbre seul, vu de côté par une
## caméra orthogonale. Vent nul : deux images à 0,5 s d'écart identiques. Vent fort : le pied de
## l'arbre ne bouge pas (à 2/255 près), la cime bouge.
## Lancé par run_engine_tests.sh sous Xvfb avec le moteur Compatibility, comme test_terrain_render.gd.

const TreeRenderer := preload("res://scripts/tree_renderer.gd")

const SIZE := 96
const TOLERANCE := 2.0 / 255.0

var _failures := 0
var _checked := 0
var _vp: SubViewport


func _init() -> void:
	call_deferred("_run")


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _setup() -> void:
	_vp = SubViewport.new()
	_vp.size = Vector2i(SIZE, SIZE)
	_vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_vp.own_world_3d = true
	root.add_child(_vp)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = TreeRenderer.build_lod0_mesh()
	mm.instance_count = 1
	mm.set_instance_transform(0, Transform3D.IDENTITY)
	mm.set_instance_color(0, Color.WHITE)
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.material_override = TreeRenderer.sway_material(false)
	_vp.add_child(mmi)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 7.0
	cam.position = Vector3(0.0, 2.9, 10.0)   # de côté, regarde vers −z
	_vp.add_child(cam)
	cam.current = true


func _shot(strength: float, phase: float) -> Image:
	TreeRenderer.apply_wind({"dir": Vector3(1, 0, 0), "strength": strength, "gust": 0.0, "phase": phase})
	for i in 4:
		await process_frame
	return _vp.get_texture().get_image()


## Nombre de pixels différents (au-delà de la tolérance) entre les lignes y0 et y1 (y vers le bas).
func _diff_rows(a: Image, b: Image, y0: int, y1: int) -> int:
	var n := 0
	for y in range(y0, y1):
		for x in range(SIZE):
			var ca := a.get_pixel(x, y)
			var cb := b.get_pixel(x, y)
			if absf(ca.r - cb.r) > TOLERANCE or absf(ca.g - cb.g) > TOLERANCE or absf(ca.b - cb.b) > TOLERANCE:
				n += 1
	return n


func _run() -> void:
	_setup()
	# L'image couvre y de −0,6 à 6,4 m : la cime (5,4 m) est vers la ligne 14, le pied vers la ligne 82.
	var base_rows := [SIZE - 16, SIZE - 8]   # 0 à 0,6 m de hauteur : tronc
	var top_rows := [0, SIZE / 3]
	var calm_a := await _shot(0.0, 0.0)
	var calm_b := await _shot(0.0, 1.0)   # 0,5 s plus tard (phase à 2 s par seconde)
	_check(_diff_rows(calm_a, calm_b, 0, SIZE) == 0, "vent nul : deux images identiques")
	var windy_a := await _shot(1.0, 0.0)
	var windy_b := await _shot(1.0, 1.0)
	var base_diff := _diff_rows(windy_a, windy_b, base_rows[0], base_rows[1])
	var top_diff := _diff_rows(windy_a, windy_b, top_rows[0], top_rows[1])
	_check(base_diff == 0, "vent fort : pied de l'arbre immobile (%d pixels changés)" % base_diff)
	_check(top_diff > 0, "vent fort : la cime bouge (%d pixels changés)" % top_diff)
	var lean := _diff_rows(calm_a, windy_a, top_rows[0], top_rows[1])
	_check(lean > 0, "vent fort : l'arbre penche par rapport au vent nul (%d pixels)" % lean)
	print("test_tree_sway_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
