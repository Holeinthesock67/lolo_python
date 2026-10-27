extends SceneTree

## Rendu hors écran des animaux du lot P11 (shaders/fauna.gdshader) : le shader compile, une vache et un
## oiseau apparaissent à l'image avec la couleur de leur espèce, et rien n'est dessiné sans animal.
## Demande Xvfb et le pilote OpenGL (lancé par run_engine_tests.sh, comme test_terrain_render.gd).

const FaunaRenderer := preload("res://scripts/fauna_renderer.gd")

const SIZE := 48
const TOLERANCE := 6.0 / 255.0

var _failures := 0
var _checked := 0


func _init() -> void:
	call_deferred("_run")


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _shot(groups: Array, cam_pos: Vector3, look_at: Vector3, ortho: float) -> Image:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	vp.transparent_bg = true
	root.add_child(vp)
	var r = FaunaRenderer.new()
	vp.add_child(r)
	r.set_preset("high")
	r.set_chunk(0, groups)
	r.update(cam_pos, Vector3(10000.0, 0.0, 0.0), 0.0)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = ortho
	vp.add_child(cam)
	cam.look_at_from_position(cam_pos, look_at)
	cam.current = true
	for i in 5:
		await process_frame
	var img := vp.get_texture().get_image()
	vp.queue_free()
	await process_frame
	return img


func _close(a: Color, b: Color) -> bool:
	return absf(a.r - b.r) <= TOLERANCE and absf(a.g - b.g) <= TOLERANCE and absf(a.b - b.b) <= TOLERANCE


func _run() -> void:
	var cow := [{"type": "herd", "id": "h", "species": "cow", "members": [{"pos": Vector3.ZERO, "yaw": PI / 2.0}]}]
	var img: Image = await _shot(cow, Vector3(0.0, 1.1, 10.0), Vector3(0.0, 1.1, 0.0), 3.0)
	var c := img.get_pixel(SIZE / 2, SIZE / 2)
	_check(_close(c, FaunaRenderer.ALBEDO["cow"]), "vache vue de côté : couleur de l'espèce au centre (%s)" % str(c))

	var bird := [{"type": "birds", "id": "f", "center": Vector3(0.0, 40.0, 0.0), "ground_y": 0.0, "radius_m": 0.01,
		"members": [{"angle": 0.0, "r": 0.0, "h": 0.0, "phase": 0.0, "omega": 0.0}]}]
	var img_b: Image = await _shot(bird, Vector3(0.0, 50.0, 0.01), Vector3(0.0, 40.0, 0.0), 1.2)
	var found := false
	for y in range(SIZE):
		for x in range(SIZE):
			if _close(img_b.get_pixel(x, y), FaunaRenderer.ALBEDO["bird"]) and img_b.get_pixel(x, y).a > 0.9:
				found = true
	_check(found, "oiseau vu de dessus : présent à l'image")

	var img_e: Image = await _shot([], Vector3(0.0, 1.1, 10.0), Vector3(0.0, 1.1, 0.0), 3.0)
	_check(img_e.get_pixel(SIZE / 2, SIZE / 2).a < 0.1, "sans animal : rien n'est dessiné")
	print("test_fauna_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
