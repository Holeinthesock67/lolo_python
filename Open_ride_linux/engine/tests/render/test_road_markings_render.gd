extends SceneTree

## Rendu hors écran des marquages de la route (Lot P14, shaders/road_markings.gdshader) sur un vrai ruban
## de road_builder.gd : ligne médiane claire au centre, motif de 13 m (3 m peints), bandes de rive aux
## deux bords, chiffre peint sur la voie de droite. Rendu sans éclairage : la couleur lue est l'albédo.

const RoadBuilder := preload("res://scripts/road_builder.gd")
const ClimbTest := preload("res://tests/unit/test_climb_detector.gd")
const MarkingsShader := preload("res://shaders/road_markings.gdshader")

const SIZE := 256
const ORTHO_M := 16.0
const TOL := 0.06

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


func _flat(_s: float) -> float:
	return 0.0


func _close(a: Color, b: Color) -> bool:
	return absf(a.r - b.r) <= TOL and absf(a.g - b.g) <= TOL and absf(a.b - b.b) <= TOL


func _run() -> void:
	var route = ClimbTest.make_route(1000.0, Callable(self, "_flat"))   # route droite vers l'est (s = x, droite = +z)
	var arrays := RoadBuilder.build_chunk_arrays(route, 0)
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var mat := ShaderMaterial.new()
	mat.shader = MarkingsShader
	mat.set_shader_parameter("wear", 0.0)
	mat.set_shader_parameter("marks", PackedVector2Array([Vector2(40.0, 1.0)]))
	mat.set_shader_parameter("mark_count", 1)
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	vp.add_child(mi)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = ORTHO_M
	vp.add_child(cam)
	var y0: float = route.sample_point(0.0).y
	var shots := {}
	for cx in [6.0, 19.0, 42.0]:
		cam.look_at_from_position(Vector3(cx, y0 + 50.0, 0.0), Vector3(cx, y0, 0.0), Vector3(0, 0, -1))
		cam.current = true
		for i in 5:
			await process_frame
		shots[cx] = vp.get_texture().get_image()
	var road := Color(0.29, 0.29, 0.30)
	var line := Color(0.95, 0.95, 0.95)
	var px := func(cx: float, s: float, lat: float) -> Color:
		var img: Image = shots[cx]
		cam.look_at_from_position(Vector3(cx, y0 + 50.0, 0.0), Vector3(cx, y0, 0.0), Vector3(0, 0, -1))
		var p := cam.unproject_position(Vector3(s, y0, lat))
		return img.get_pixel(clampi(int(p.x), 0, SIZE - 1), clampi(int(p.y), 0, SIZE - 1))
	# Trait médian de 12 cm (2 pixels ici) : le plus clair des pixels à ± 4 cm de l'axe
	var center := func(cx: float, s: float) -> Color:
		var best: Color = px.call(cx, s, 0.0)
		for d in [-0.04, 0.04]:
			var c: Color = px.call(cx, s, d)
			if c.r > best.r:
				best = c
		return best
	_check(_close(center.call(6.0, 1.5), line), "ligne médiane claire au centre, dans le trait (s = 1,5 m)")
	_check(_close(px.call(6.0, 8.0, 0.0), road), "trou de la ligne médiane (s = 8 m)")
	_check(_close(center.call(19.0, 14.5), line) and _close(px.call(19.0, 20.0, 0.0), road),
		"motif de 13 m : trait à 14,5 m, trou à 20 m")
	var edge := 3.0 - 0.2 - 0.075
	_check(_close(px.call(6.0, 8.0, edge), line) and _close(px.call(6.0, 8.0, -edge), line),
		"bandes de rive aux deux bords")
	_check(_close(px.call(6.0, 8.0, 1.0), road) and _close(px.call(6.0, 8.0, -1.0), road), "chaussée entre les traits")
	# Chiffre 1 : segments b et c (côté droit du chiffre, vu du cycliste) sur la voie de droite
	_check(_close(px.call(42.0, 41.2, 2.0), line) and _close(px.call(42.0, 41.2, 1.0), road),
		"chiffre « 1 » peint sur la voie de droite à 40 m")
	vp.queue_free()
	await process_frame
	print("test_road_markings_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
