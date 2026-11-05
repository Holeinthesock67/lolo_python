extends SceneTree

## Planche des personnages du bord de route (Lot Y21) : spectateurs de face, un par geste et par attitude,
## tenues variées (short, jupe, veste, casquette, chapeau, cheveux longs), porte-drapeaux aux quatre motifs
## et porteurs de pancarte, au niveau de détail de près (`planche_pres.png`) et au loin
## (`planche_loin.png`), plus un gros plan de profil (`profil.png`). Mêmes maillages et shader que le jeu
## (people_mesh.gd, crowd.gdshader), sans core ni parcours.
##
##   xvfb-run -a $GODOT --path engine --rendering-driver vulkan --rendering-method forward_plus \
##     --audio-driver Dummy --script res://tests/vitrine_personnages.gd -- --out DOSSIER [--size 1600x900]
##
## Écrit aussi DOSSIER/personnages.csv (maillage ; niveau ; triangles).

const PeopleMesh := preload("res://scripts/people_mesh.gd")
const CrowdShader := preload("res://shaders/crowd.gdshader")
const CrowdRenderer := preload("res://scripts/crowd_renderer.gd")
const SETTLE_FRAMES := 20

var _out_dir := "user://vitrine_personnages"
var _size := Vector2i(1600, 900)


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--out":
			_out_dir = args[i + 1]
		elif args[i] == "--size":
			var wh := args[i + 1].split("x")
			_size = Vector2i(int(wh[0]), int(wh[1]))
	call_deferred("_run")


## Distribution de la planche : [sorte, x, z, encourage, tenue, couleur, phase].
func _cast() -> Array:
	var out := []
	var looks := [
		[0, 1, 0, PeopleMesh.STYLE_JACKET, PeopleMesh.BOTTOM_TROUSERS, PeopleMesh.HAT_CAP],
		[1, 3, 2, PeopleMesh.STYLE_LONG_HAIR, PeopleMesh.BOTTOM_SKIRT, PeopleMesh.HAT_NONE],
		[2, 0, 1, PeopleMesh.STYLE_STRIPE, PeopleMesh.BOTTOM_SHORTS, PeopleMesh.HAT_NONE],
		[3, 4, 3, 0, PeopleMesh.BOTTOM_TROUSERS, PeopleMesh.HAT_SUN],
		[0, 5, 4, PeopleMesh.STYLE_LONG_HAIR | PeopleMesh.STYLE_JACKET, PeopleMesh.BOTTOM_TROUSERS, PeopleMesh.HAT_NONE],
		[1, 2, 5, 0, PeopleMesh.BOTTOM_SHORTS, PeopleMesh.HAT_CAP],
		[2, 1, 0, PeopleMesh.STYLE_LONG_HAIR, PeopleMesh.BOTTOM_SKIRT, PeopleMesh.HAT_SUN],
		[3, 0, 2, PeopleMesh.STYLE_STRIPE, PeopleMesh.BOTTOM_TROUSERS, PeopleMesh.HAT_NONE],
	]
	# Premier rang : les huit gestes (encourage) ; deuxième rang : les quatre attitudes au calme, deux fois
	for g in range(PeopleMesh.GESTURES):
		var l: Array = looks[g]
		out.append(["plain", -4.2 + g * 1.2, 0.0, true, PeopleMesh.outfit(l[0], l[1], l[2], l[3], l[4], l[5], g), g, 0.1 * g])
	for g in range(8):
		var l: Array = looks[7 - g]
		out.append(["plain", -4.2 + g * 1.2, -2.2, false, PeopleMesh.outfit(l[0], l[1], l[2], l[3], l[4], l[5], g % 4), 7 - g, 0.0])
	# Fond : porte-drapeaux (motif = cheveux % 4) et porteurs de pancarte
	for k in range(4):
		out.append(["flag", -4.4 + k * 1.5, -4.6, true, PeopleMesh.outfit(k, k, k + 1, 0, 0, k % 3, 0), k * 2, 0.2 * k])
	for k in range(2):
		out.append(["sign", 2.0 + k * 1.6, -4.6, true, PeopleMesh.outfit(k + 1, 2, k * 3 + 1, 0, k, 0, 0), 5 - k * 3, 0.3])
	return out


func _world() -> SubViewport:
	var vp := SubViewport.new()
	vp.size = _size
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = ProceduralSkyMaterial.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.basis = Basis.looking_at(Vector3(-0.4, -0.8, -0.5), Vector3.UP)
	sun.shadow_enabled = true
	vp.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(60.0, 60.0)
	ground.mesh = plane
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.42, 0.6, 0.3)
	ground.material_override = gm
	vp.add_child(ground)
	var cam := Camera3D.new()
	cam.name = "Camera"
	vp.add_child(cam)
	cam.current = true
	return vp


func _crowd(vp: SubViewport, lod: int) -> int:
	var mat := ShaderMaterial.new()
	mat.shader = CrowdShader
	PeopleMesh.apply_palettes(mat)
	var cast := _cast()
	var tris := 0
	for kind in ["plain", "flag", "sign"]:
		var mesh: ArrayMesh = PeopleMesh.build_sign_holder(lod) if kind == "sign" else PeopleMesh.build_person(kind == "flag", false, lod)
		var list := cast.filter(func(c): return c[0] == kind)
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.use_custom_data = true
		mm.mesh = mesh
		mm.instance_count = list.size()
		for k in range(list.size()):
			var c: Array = list[k]
			mm.set_instance_transform(k, Transform3D(CrowdRenderer.morph(k * 3 + lod, 0.0), Vector3(c[1], 0.0, c[2])))
			mm.set_instance_color(k, CrowdRenderer.PALETTE[int(c[5]) % CrowdRenderer.PALETTE.size()])
			mm.set_instance_custom_data(k, Color(float(c[6]), 1.0 if c[3] else 0.0,
				float(CrowdRenderer.SIGN_ANIM) if kind == "sign" else 0.0, float(c[4])))
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.material_override = mat
		vp.add_child(mmi)
		tris = mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX].size() / 3
		_csv.store_line("%s;%d;%d" % [kind, lod, tris])
	return tris


var _csv: FileAccess


func _shot(vp: SubViewport, name: String, from: Vector3, to: Vector3, fov: float) -> void:
	var cam: Camera3D = vp.get_node("Camera")
	cam.fov = fov
	cam.look_at_from_position(from, to)
	for f in range(SETTLE_FRAMES):
		await process_frame
	var path := _out_dir.path_join(name)
	vp.get_texture().get_image().save_png(path)
	print("[vitrine_personnages] ", path)


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	_csv = FileAccess.open(_out_dir.path_join("personnages.csv"), FileAccess.WRITE)
	_csv.store_line("maillage;niveau;triangles")
	for lod in [0, 1]:
		var vp := _world()
		_crowd(vp, lod)
		await _shot(vp, "planche_%s.png" % ("pres" if lod == 0 else "loin"), Vector3(0.0, 2.3, 7.5), Vector3(0.0, 1.3, -1.5), 50.0)
		if lod == 0:
			await _shot(vp, "visages.png", Vector3(-1.8, 1.65, 2.2), Vector3(-1.8, 1.45, -0.5), 40.0)
			await _shot(vp, "profil.png", Vector3(-8.5, 1.3, 0.4), Vector3(0.0, 1.0, -1.0), 30.0)
		vp.queue_free()
		await process_frame
	_csv.close()
	quit(0)
