extends SceneTree

## Rendu hors écran des spectateurs du lot P15 (shaders/crowd.gdshader) : le shader compile, un
## spectateur apparaît avec la couleur de son haut (couleur d'instance), la peau et le pantalon de sa
## tenue (people_mesh.gd, Lot Y13).

const CrowdRenderer := preload("res://scripts/crowd_renderer.gd")
const PeopleMesh := preload("res://scripts/people_mesh.gd")

const SIZE := 64
const TOL := 8.0 / 255.0

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


class FakePassersby:
	var people := [{"role": "dog_walker", "color": 1, "phase": 0.0, "yaw": 0.0, "pos": Vector3.ZERO}]
	var selection_serial := 1
	var dog_count := 1
	var bench_count := 0
	func visible(_c, _s, _t, _b) -> Array:
		return [{"i": 0, "pos": Vector3(0.0, 0.0, -3.0), "yaw": 0.0, "anim": "stand", "wave": false, "dirty": true,
			"dog": 0, "dog_pos": Vector3(0.0, 0.0, 0.0), "dog_yaw": PI * 0.5, "bench": -1}]


class FakeModel:
	var spectators := [{"s": 0.0, "side": 1, "pos": Vector3.ZERO, "yaw": 0.0, "color": 2, "flag": false, "phase": 0.0, "delay": 0.0, "group": 0}]
	var groups := []
	var states := {}


func _close(a: Color, b: Color) -> bool:
	return absf(a.r - b.r) <= TOL and absf(a.g - b.g) <= TOL and absf(a.b - b.b) <= TOL


func _run() -> void:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	vp.transparent_bg = true
	root.add_child(vp)
	var r = CrowdRenderer.new()
	vp.add_child(r)
	r.setup(FakeModel.new())
	r.set_preset("low")
	r.update(Vector3(0.0, 1.0, 5.0), 0.0, 0.0)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 2.0
	vp.add_child(cam)
	cam.look_at_from_position(Vector3(0.0, 1.0, 10.0), Vector3(0.0, 1.0, 0.0))
	cam.current = true
	for i in 5:
		await process_frame
	var img := vp.get_texture().get_image()
	var body := img.get_pixel(img.get_width() / 2, int(cam.unproject_position(Vector3(0.0, 1.17, 0.0)).y))
	var head := img.get_pixel(img.get_width() / 2, int(cam.unproject_position(Vector3(0.0, 1.58, 0.0)).y))
	var legs := img.get_pixel(int(cam.unproject_position(Vector3(PeopleMesh.LEG_X, 0.7, 0.0)).x),
		int(cam.unproject_position(Vector3(PeopleMesh.LEG_X, 0.7, 0.0)).y))
	var outfit := int(PeopleMesh.outfit_of(0))
	var skin: Color = PeopleMesh.SKIN_TONES[outfit % PeopleMesh.SKIN_TONES.size()]
	var trousers: Color = PeopleMesh.TROUSER_COLORS[(outfit / (PeopleMesh.SKIN_TONES.size() * PeopleMesh.HAIR_COLORS.size())) % PeopleMesh.TROUSER_COLORS.size()]
	_check(_close(body, CrowdRenderer.PALETTE[2]), "buste à la couleur du haut (%s)" % str(body))
	_check(_close(head, skin), "visage à la couleur de peau de sa tenue (%s, attendu %s)" % [str(head), str(skin)])
	_check(_close(legs, trousers), "jambes à la couleur du pantalon de sa tenue (%s, attendu %s)" % [str(legs), str(trousers)])
	r.queue_free()
	# Lot P21 : chien des passants, de profil, à la couleur de sa robe
	var pr = CrowdRenderer.new("passersby")
	vp.add_child(pr)
	pr.setup_passersby(FakePassersby.new())
	pr.set_preset("low")
	pr.update_passersby(Vector3(0.0, 1.0, 5.0), 0.0, 0.0)
	cam.size = 1.2
	cam.look_at_from_position(Vector3(0.0, 0.45, 10.0), Vector3(0.0, 0.45, 0.0))
	for i in 5:
		await process_frame
	img = vp.get_texture().get_image()
	var dog := img.get_pixel(img.get_width() / 2, int(cam.unproject_position(Vector3(0.0, 0.45, 0.0)).y))
	_check(_close(dog, CrowdRenderer.DOG_PALETTE[1]), "passants : chien à la couleur de sa robe (%s)" % str(dog))
	vp.queue_free()
	await process_frame
	print("test_crowd_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
