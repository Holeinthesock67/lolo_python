extends SceneTree

## Rendu hors écran des véhicules du lot P25 (shaders/vehicle.gdshader) : le shader compile ; une berline
## proche (peinture du matériau) et la même en MultiMesh (couleur d'instance) ont la même peinture et des
## vitres sombres ; phares éteints puis allumés (INSTANCE_CUSTOM.x et `lights`).

const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")
const VehicleShader := preload("res://shaders/vehicle.gdshader")

const SIZE := 96
const TOL := 10.0 / 255.0

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


func _viewport(unshaded: bool) -> SubViewport:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	if unshaded:
		vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	else:
		# Nuit noire : ni ciel ni lumière ambiante, seuls les phares allumés brillent
		var env := Environment.new()
		env.background_mode = Environment.BG_COLOR
		env.background_color = Color.BLACK
		env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		env.ambient_light_color = Color.BLACK
		env.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
		var we := WorldEnvironment.new()
		we.environment = env
		vp.add_child(we)
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	vp.transparent_bg = true
	root.add_child(vp)
	return vp


func _camera(vp: SubViewport, from: Vector3, to: Vector3, size: float) -> Camera3D:
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = size
	vp.add_child(cam)
	cam.look_at_from_position(from, to)
	cam.current = true
	return cam


func _pixel(vp: SubViewport, cam: Camera3D, p: Vector3) -> Color:
	var img := vp.get_texture().get_image()
	var q := cam.unproject_position(p)
	return img.get_pixel(clampi(int(q.x), 0, SIZE - 1), clampi(int(q.y), 0, SIZE - 1))


func _near(lights: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = VehicleMesh.build_full("car_a")
	var mat := ShaderMaterial.new()
	mat.shader = VehicleShader
	mat.set_shader_parameter("paint", VehicleMesh.paint("car_a", 1))
	mat.set_shader_parameter("lights", lights)
	mi.material_override = mat
	return mi


func _instanced(lights: float) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.use_custom_data = true
	mm.mesh = VehicleMesh.build_full("car_a")
	mm.instance_count = 1
	mm.set_instance_transform(0, Transform3D.IDENTITY)
	mm.set_instance_color(0, VehicleMesh.paint("car_a", 1))
	mm.set_instance_custom_data(0, Color(lights, 0.0, 0.0, 0.0))
	var mat := ShaderMaterial.new()
	mat.shader = VehicleShader
	mat.set_shader_parameter("instanced", true)
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.material_override = mat
	return mmi


func _run() -> void:
	var paint: Color = VehicleMesh.paint("car_a", 1)
	# 1. Sans éclairage : peinture et vitres, véhicule proche puis en MultiMesh, vu de côté
	for instanced in [false, true]:
		var vp := _viewport(true)
		var car: GeometryInstance3D = _instanced(0.0) if instanced else _near(0.0)
		vp.add_child(car)
		var cam := _camera(vp, Vector3(10.0, 0.9, 0.0), Vector3(0.0, 0.9, 0.0), 5.0)
		for i in 5:
			await process_frame
		var door := _pixel(vp, cam, Vector3(0.9, 0.7, 0.4))
		var glass := _pixel(vp, cam, Vector3(0.9, 1.15, -0.2))
		var label := "MultiMesh" if instanced else "proche"
		_check(_close(door, paint), "%s : portière à la couleur de la peinture (%s, attendu %s)" % [label, str(door), str(paint)])
		_check(glass.get_luminance() < 0.15 and glass.a > 0.5, "%s : vitre sombre (%s)" % [label, str(glass)])
		vp.queue_free()
		await process_frame
	# 2. Éclairé, sans lumière ni ciel : phares éteints sombres, allumés brillants (vus de face)
	for instanced in [false, true]:
		var lum := []
		for lights in [0.0, 1.0]:
			var vp := _viewport(false)
			var car: GeometryInstance3D = _instanced(lights) if instanced else _near(lights)
			vp.add_child(car)
			var cam := _camera(vp, Vector3(0.0, 0.55, -10.0), Vector3(0.0, 0.55, 0.0), 2.4)
			for i in 5:
				await process_frame
			lum.append(_pixel(vp, cam, Vector3(0.6, 0.55, -2.3)).get_luminance())
			vp.queue_free()
			await process_frame
		_check(lum[0] < 0.1 and lum[1] > 0.8, "%s : phares éteints %.2f, allumés %.2f" % ["MultiMesh" if instanced else "proche", lum[0], lum[1]])
	print("test_vehicle_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
