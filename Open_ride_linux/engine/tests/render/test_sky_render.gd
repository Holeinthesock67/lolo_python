extends SceneTree

## Rendu hors écran du ciel du lot P26 : les shaders shaders/vehicle_far.gdshader et contrail.gdshader
## compilent ; un avion de ligne dans un brouillard épais garde sa couleur avec vehicle_far (fog_disabled)
## alors que le même avion avec vehicle.gdshader disparaît dans le brouillard ; une traînée est opaque au
## réacteur, s'efface vers son bout et sur ses bords.

const SkyMesh := preload("res://scripts/sky_mesh.gd")
const VehicleShader := preload("res://shaders/vehicle.gdshader")
const VehicleFarShader := preload("res://shaders/vehicle_far.gdshader")
const ContrailShader := preload("res://shaders/contrail.gdshader")

const SIZE := 96
const FOG := Color(1.0, 0.0, 0.0)

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


func _viewport(fog: bool) -> SubViewport:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.6, 0.6, 0.6)
	env.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
	if fog:
		env.fog_enabled = true
		env.fog_light_color = FOG
		env.fog_density = 0.05
		env.fog_sky_affect = 1.0
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-60.0, 30.0, 0.0)
	vp.add_child(sun)
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	return vp


func _camera(vp: SubViewport, from: Vector3, to: Vector3, size: float, up: Vector3 = Vector3.UP) -> Camera3D:
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = size
	cam.far = 5000.0
	vp.add_child(cam)
	cam.look_at_from_position(from, to, up)
	cam.current = true
	return cam


func _pixel(vp: SubViewport, cam: Camera3D, p: Vector3) -> Color:
	var img := vp.get_texture().get_image()
	var q := cam.unproject_position(p)
	return img.get_pixel(clampi(int(q.x), 0, SIZE - 1), clampi(int(q.y), 0, SIZE - 1))


## Luminance la plus forte sur la ligne d'image qui passe par `p` (les traînées fines tombent entre deux pixels).
func _row_max(vp: SubViewport, cam: Camera3D, p: Vector3) -> float:
	var img := vp.get_texture().get_image()
	var row := clampi(int(cam.unproject_position(p).y), 0, SIZE - 1)
	var best := 0.0
	for x in range(SIZE):
		best = maxf(best, img.get_pixel(x, row).get_luminance())
	return best


func _plane(shader: Shader) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = SkyMesh.build("airliner")
	var mat := ShaderMaterial.new()
	mat.shader = shader
	var col: Array = SkyMesh.colors("airliner", 0)
	mat.set_shader_parameter("paint", col[0])
	mat.set_shader_parameter("second", col[1])
	mi.material_override = mat
	return mi


func _run() -> void:
	# 1. Brouillard épais : l'avion lointain n'est pas noyé, l'avion ordinaire l'est
	var seen := {}
	for far in [true, false]:
		var vp := _viewport(true)
		vp.add_child(_plane(VehicleFarShader if far else VehicleShader))
		var cam := _camera(vp, Vector3(0.0, -2000.0, 0.0), Vector3.ZERO, 60.0, Vector3.FORWARD)
		for i in 5:
			await process_frame
		seen[far] = _pixel(vp, cam, Vector3(0.0, 0.0, 0.0))
		vp.queue_free()
		await process_frame
	var f: Color = seen[true]
	var n: Color = seen[false]
	_check(f.g > 0.3 and f.b > 0.3, "vehicle_far.gdshader : fuselage clair dans le brouillard (%s)" % str(f))
	_check(n.r > 0.8 and n.g < 0.15 and n.b < 0.15, "vehicle.gdshader : le même avion noyé dans le brouillard rouge (%s)" % str(n))

	# 2. Traînée de 200 m vue d'en dessous
	var vp2 := _viewport(true)
	var trail := MeshInstance3D.new()
	trail.mesh = SkyMesh.build("contrail")
	var cm := ShaderMaterial.new()
	cm.shader = ContrailShader
	trail.material_override = cm
	trail.scale = Vector3(1.0, 1.0, 200.0)
	vp2.add_child(trail)
	var cam2 := _camera(vp2, Vector3(SkyMesh.ENGINE_X, -1000.0, 100.0), Vector3(SkyMesh.ENGINE_X, 0.0, 100.0), 220.0, Vector3.FORWARD)
	for i in 5:
		await process_frame
	var y := SkyMesh.ENGINE_Y
	var start := _row_max(vp2, cam2, Vector3(SkyMesh.ENGINE_X, y, 15.0))
	var mid := _row_max(vp2, cam2, Vector3(SkyMesh.ENGINE_X, y, 100.0))
	var tip := _row_max(vp2, cam2, Vector3(SkyMesh.ENGINE_X, y, 195.0))
	var side := _pixel(vp2, cam2, Vector3(SkyMesh.ENGINE_X + 0.97 * lerpf(SkyMesh.CONTRAIL_WIDTH_M.x, SkyMesh.CONTRAIL_WIDTH_M.y, 0.5), y, 100.0)).get_luminance()
	_check(start > 0.3 and start > mid and mid > tip and tip < 0.05,
		"traînée sans brouillard, effacée vers son bout : %.2f, %.2f puis %.2f" % [start, mid, tip])
	_check(side < _pixel(vp2, cam2, Vector3(SkyMesh.ENGINE_X, y, 100.0)).get_luminance() * 0.5, "traînée effacée sur ses bords : %.2f contre %.2f au milieu" % [side, mid])
	vp2.queue_free()
	await process_frame
	print("test_sky_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
