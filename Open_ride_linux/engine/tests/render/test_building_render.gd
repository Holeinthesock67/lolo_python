extends SceneTree

## Rendu hors écran des bâtiments habillés (Lot Y8, shaders/building.gdshader) : une maison par style
## d'architecture (variantes du contrat U1), maillée par building_mesh.gd comme dans la scène principale.
## - Aucun point parasite sur les façades et les toits éclairés, relief en marche (detecteur speckle.gd) ;
## - fenêtres dessinées sur chaque façade (part de pixels sombres du vitrage) ;
## - teinte du toit propre au style : tuiles rondes chaudes, ardoise grise, toit plat blanc clair.
##   xvfb-run -a godot --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/render/test_building_render.gd

const BuildingMesh := preload("res://scripts/building_mesh.gd")
const BuildingStyles := preload("res://scripts/building_styles.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const Speckle := preload("res://tests/render/speckle.gd")

const SIZE := 256
const SPACING_M := 20.0
const STYLES := ["tuile_plate", "tuile_ronde", "ardoise", "pierre_seche", "toit_plat_blanc", "bois"]
## Part maximale de pixels isolés (le défaut corrigé pendant Y8 en donnait plusieurs pour cent)
const MAX_ISOLATED := 0.003

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


## Maison de 11 × 8 m et 6 m de murs par style, façade principale en z = 0 tournée vers +z.
func _village() -> MeshInstance3D:
	var items := []
	for i in range(STYLES.size()):
		var x0 := i * SPACING_M
		items.append({"id": "rendu_%d" % i, "outer": [[x0, 0.0], [x0, -8.0], [x0 + 11.0, -8.0], [x0 + 11.0, 0.0]],
			"holes": [], "base_y": 0.0, "height_m": 6.0, "roof": "flat", "style": STYLES[i],
			"hint": {"building": "house", "colour": null}})
	var m := BuildingMesh.build(items, ThemeLoader.new().load_named("default")["theme"], 1.0)
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = m["vertices"]
	arr[Mesh.ARRAY_NORMAL] = m["normals"]
	arr[Mesh.ARRAY_COLOR] = m["colors"]
	arr[Mesh.ARRAY_TEX_UV] = m["uvs"]
	arr[Mesh.ARRAY_TEX_UV2] = m["uvs2"]
	arr[Mesh.ARRAY_INDEX] = m["indices"]
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	var mat := BuildingMesh.make_material()
	BuildingMesh.apply_preset(mat, "medium")
	mi.material_override = mat
	return mi


func _viewport(unshaded: bool) -> SubViewport:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.own_world_3d = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	if unshaded:
		vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	root.add_child(vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.6, 0.7, 0.8)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.5, 0.5, 0.55)
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.basis = Basis.looking_at(Vector3(-0.4, -0.7, -0.6), Vector3.UP)
	vp.add_child(sun)
	vp.add_child(_village())
	var cam := Camera3D.new()
	cam.name = "Camera"
	vp.add_child(cam)
	cam.current = true
	return vp


func _shot(vp: SubViewport, from: Vector3, to: Vector3, ortho_m: float = 0.0) -> Image:
	var cam: Camera3D = vp.get_node("Camera")
	if ortho_m > 0.0:
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = ortho_m
	else:
		cam.projection = Camera3D.PROJECTION_PERSPECTIVE
		cam.fov = 60.0
	var up := Vector3(0, 0, -1) if absf(from.x - to.x) + absf(from.z - to.z) < 1e-3 else Vector3.UP
	cam.look_at_from_position(from, to, up)
	for i in 4:
		await process_frame
	return vp.get_texture().get_image()


func _run() -> void:
	var lit := _viewport(false)
	var flat := _viewport(true)
	for i in range(STYLES.size()):
		var xc := i * SPACING_M + 5.5
		var st: String = STYLES[i]
		# Façade éclairée vue de face à 12 m, puis toit vu de trois quarts
		var facade: Image = await _shot(lit, Vector3(xc, 3.0, 12.0), Vector3(xc, 3.0, 0.0))
		var roof: Image = await _shot(lit, Vector3(xc + 6.0, 16.0, 8.0), Vector3(xc, 6.0, -4.0))
		var r_f := Speckle.isolated_ratio(facade)
		var r_r := Speckle.isolated_ratio(roof)
		_check(r_f <= MAX_ISOLATED and r_r <= MAX_ISOLATED,
			"%s : pas de points parasites (façade %.4f, toit %.4f, seuil %.3f)" % [st, r_f, r_r, MAX_ISOLATED])
		# Vitrage : pixels sombres de la façade sans éclairage (albédo), entre 1 % et 40 %
		var albedo: Image = await _shot(flat, Vector3(xc, 3.0, 12.0), Vector3(xc, 3.0, 0.0))
		var dark := 0
		for y in range(SIZE):
			for x in range(SIZE):
				var c := albedo.get_pixel(x, y)
				if c.r + c.g + c.b < 0.6 and c.b >= c.r - 0.02:
					dark += 1
		var share := float(dark) / float(SIZE * SIZE)
		_check(share > 0.01 and share < 0.4, "%s : fenêtres dessinées sur la façade (%.1f %% de vitrage)" % [st, share * 100.0])
		# Teinte du toit vue d'en haut, dans le pan arrière (z = -6 m)
		var top: Image = await _shot(flat, Vector3(xc, 40.0, -6.0), Vector3(xc, 0.0, -6.0), 6.0)
		var sum := Color(0, 0, 0)
		for y in range(96, 160):
			for x in range(96, 160):
				sum += top.get_pixel(x, y)
		var c := sum / (64.0 * 64.0)
		match st:
			"tuile_ronde":
				_check(c.r > c.g + 0.08 and c.g > c.b, "tuile_ronde : toit ocre chaud (%s)" % c.to_html(false))
			"ardoise":
				_check(absf(c.r - c.g) < 0.06 and c.b >= c.r - 0.02 and c.r < 0.5, "ardoise : toit gris sombre (%s)" % c.to_html(false))
			"toit_plat_blanc":
				_check(c.r > 0.6 and c.g > 0.6 and c.b > 0.55, "toit_plat_blanc : toit plat clair (%s)" % c.to_html(false))
	lit.queue_free()
	flat.queue_free()
	await process_frame
	print("test_building_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
