extends SceneTree

## Rendu hors écran des bateaux du lot P29 : coque d'un voilier vue de côté à la couleur de sa palette
## (shaders/vehicle.gdshader), plancher d'une barque en zone bois ; sillage (shaders/wake.gdshader) opaque à
## la poupe, effacé vers son bout.

const BoatMesh := preload("res://scripts/boat_mesh.gd")
const VehicleShader := preload("res://shaders/vehicle.gdshader")
const WakeShader := preload("res://shaders/wake.gdshader")

const SIZE := 96
const TOL := 10.0 / 255.0
const WOOD := Color(0.46, 0.3, 0.17)

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


func _close(a: Color, b: Color) -> bool:
	return absf(a.r - b.r) <= TOL and absf(a.g - b.g) <= TOL and absf(a.b - b.b) <= TOL


func _viewport() -> SubViewport:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	vp.transparent_bg = true
	root.add_child(vp)
	return vp


func _camera(vp: SubViewport, from: Vector3, to: Vector3, size: float, up: Vector3 = Vector3.UP) -> Camera3D:
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = size
	vp.add_child(cam)
	cam.look_at_from_position(from, to, up)
	cam.current = true
	return cam


func _image_pixel(vp: SubViewport, cam: Camera3D, p: Vector3) -> Color:
	var q := cam.unproject_position(p)
	return vp.get_texture().get_image().get_pixel(clampi(int(q.x), 0, SIZE - 1), clampi(int(q.y), 0, SIZE - 1))


func _boat(kind: String, index: int) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = BoatMesh.build(kind)
	var mat := ShaderMaterial.new()
	mat.shader = VehicleShader
	var col: Array = BoatMesh.colors(kind, index)
	mat.set_shader_parameter("paint", col[0])
	mat.set_shader_parameter("second", col[1])
	mi.material_override = mat
	return mi


func _run() -> void:
	# 1. Voilier vu de côté : coque à sa couleur au-dessus de l'eau
	var vp := _viewport()
	vp.add_child(_boat("sailboat", 2))
	var cam := _camera(vp, Vector3(20.0, 0.5, 1.0), Vector3(0.0, 0.5, 1.0), 10.0)
	for i in 5:
		await process_frame
	var hull := _image_pixel(vp, cam, Vector3(1.4, 0.5, 1.5))
	var paint: Color = BoatMesh.colors("sailboat", 2)[0]
	_check(_close(hull, paint), "coque du voilier à la couleur de sa palette (%s, attendu %s)" % [str(hull), str(paint)])
	vp.queue_free()
	await process_frame

	# 2. Barque vue de dessus : plancher en bois
	var vp2 := _viewport()
	vp2.add_child(_boat("rowboat", 0))
	var cam2 := _camera(vp2, Vector3(0.0, 20.0, 0.0), Vector3.ZERO, 5.0, Vector3.FORWARD)
	for i in 5:
		await process_frame
	var floor_px := _image_pixel(vp2, cam2, Vector3(0.0, 0.0, -1.5))
	_check(_close(floor_px, WOOD), "plancher de la barque en bois (%s)" % str(floor_px))
	vp2.queue_free()
	await process_frame

	# 3. Sillage de 40 m vu de dessus, sur fond noir
	var vp3 := _viewport()
	vp3.transparent_bg = false
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	var we := WorldEnvironment.new()
	we.environment = env
	vp3.add_child(we)
	var wake := MeshInstance3D.new()
	wake.mesh = BoatMesh.build("wake")
	var wm := ShaderMaterial.new()
	wm.shader = WakeShader
	wake.material_override = wm
	wake.scale = Vector3(3.0, 1.0, 40.0)
	vp3.add_child(wake)
	var cam3 := _camera(vp3, Vector3(0.0, 50.0, 20.0), Vector3(0.0, 0.0, 20.0), 44.0, Vector3.FORWARD)
	for i in 5:
		await process_frame
	var img := vp3.get_texture().get_image()
	var row_max := func(z: float) -> float:
		var y := clampi(int(cam3.unproject_position(Vector3(0.0, 0.03, z)).y), 0, SIZE - 1)
		var best := 0.0
		for x in range(SIZE):
			best = maxf(best, img.get_pixel(x, y).get_luminance())
		return best
	var near: float = row_max.call(4.0)
	var far: float = row_max.call(38.0)
	_check(near > 0.25 and far < near * 0.2, "sillage marqué à la poupe (%.2f), effacé vers son bout (%.2f)" % [near, far])
	vp3.queue_free()
	await process_frame
	print("test_boat_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
