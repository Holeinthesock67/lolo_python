extends SceneTree

## Rendu hors écran de l'eau qui scintille (Lot P12, shaders/water_shimmer.gdshader) : le shader compile,
## la couleur de base est celle de l'eau d'E4, et la même image deux fois de suite (aucun clignotement
## sans défilement). Le matériau sans reflets reste le StandardMaterial3D d'E4 (test_water_mesh.gd).

const WaterMesh := preload("res://scripts/water_mesh.gd")

const SIZE := 32
const TOLERANCE := 3.0 / 255.0

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


func _shot(mat: Material) -> Image:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	var mi := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(20.0, 20.0)
	mi.mesh = plane
	mi.material_override = mat
	vp.add_child(mi)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 4.0
	vp.add_child(cam)
	cam.look_at_from_position(Vector3(0.0, 10.0, 0.01), Vector3.ZERO)
	cam.current = true
	for i in 5:
		await process_frame
	var img := vp.get_texture().get_image()
	vp.queue_free()
	await process_frame
	return img


func _run() -> void:
	var sh: Material = WaterMesh.make_material(true)
	WaterMesh.update_shimmer(sh, {"dir": Vector3(1, 0, 0), "strength": 0.5}, 2.0)
	var a: Image = await _shot(sh)
	var c := a.get_pixel(SIZE / 2, SIZE / 2)
	var w := WaterMesh.WATER_COLOR
	_check(absf(c.r - w.r) <= TOLERANCE and absf(c.g - w.g) <= TOLERANCE and absf(c.b - w.b) <= TOLERANCE,
		"shader compilé : couleur de base de l'eau d'E4 (%s)" % str(c))
	var b: Image = await _shot(sh)
	_check(a.get_data() == b.get_data(), "même matériau, même image : aucun clignotement")
	print("test_water_shimmer_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
