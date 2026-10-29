extends SceneTree

## Rendu hors écran de l'habillage des objets du bord de route (Lot Y8 étape 3, shaders/props.gdshader) :
## panneau de col, panneau d'approche et borne de roadside_props.gd, matériaux de la scène principale.
## - Aucun point parasite sur les objets éclairés, relief en marche (détecteur speckle.gd) ;
## - liseré blanc autour de la face marron du panneau de col ;
## - poteau en acier galvanisé, pas d'un gris uni ; pied de la borne sali ;
## - mât d'éolienne : pied en dégradé vert, haut blanc.
##   xvfb-run -a godot --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/render/test_props_render.gd

const RoadsideProps := preload("res://scripts/roadside_props.gd")
const WindTurbines := preload("res://scripts/wind_turbines.gd")
const Speckle := preload("res://tests/render/speckle.gd")

const SIZE := 384
## Même seuil que les bâtiments et les arbres
const MAX_ISOLATED := 0.001

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
	env.ambient_light_color = Color(0.4, 0.4, 0.45)
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.basis = Basis.looking_at(Vector3(-0.3, -0.6, -0.75), Vector3.UP)
	vp.add_child(sun)
	var props = RoadsideProps.new()
	props.set_preset("medium")
	vp.add_child(props)
	var items := [{"kind": "summit", "s": 0.0, "lines": ["COL"]}, {"kind": "approach", "s": 0.0, "lines": ["2 km"]},
		{"kind": "km", "s": 0.0, "lines": ["3"]}]
	for i in range(items.size()):
		var node: Node3D = props.build_prop(items[i])
		node.position = Vector3(i * 5.0, 0.0, 0.0)
		props.add_child(node)
	var turbines = WindTurbines.new()
	turbines.set_preset("medium")
	vp.add_child(turbines)
	turbines.set_points([{"kind": "wind_turbine", "id": "test", "x": 200.0, "y": 0.0, "z": -60.0, "height_m": 100.0}])
	turbines.update({"dir": Vector3(0.0, 0.0, 1.0), "strength": 0.0}, Vector3(200.0, 0.0, 0.0), 0.0)
	var cam := Camera3D.new()
	cam.name = "Camera"
	vp.add_child(cam)
	cam.current = true
	return vp


func _shot(vp: SubViewport, from: Vector3, to: Vector3, fov: float) -> Image:
	var cam: Camera3D = vp.get_node("Camera")
	cam.fov = fov
	cam.look_at_from_position(from, to, Vector3.UP)
	for i in 4:
		await process_frame
	return vp.get_texture().get_image()


func _run() -> void:
	var lit := _viewport(false)
	var flat := _viewport(true)
	# Les trois objets éclairés, de près
	var spots := [[Vector3(1.0, 2.4, 2.5), Vector3(0.0, 2.2, 0.0)], [Vector3(5.8, 1.2, 2.0), Vector3(5.0, 1.0, 0.0)],
		[Vector3(10.6, 0.6, 1.4), Vector3(10.0, 0.4, 0.0)]]
	for i in range(spots.size()):
		var img: Image = await _shot(lit, spots[i][0], spots[i][1], 50.0)
		var r := Speckle.isolated_ratio(img)
		_check(r <= MAX_ISOLATED, "objet %d : pas de points parasites (%.4f, seuil %.3f)" % [i, r, MAX_ISOLATED])
	# Panneau de col sans éclairage, de face : en descendant depuis le haut du panneau, liseré clair puis fond marron
	var board: Image = await _shot(flat, Vector3(0.0, 2.45, 2.0), Vector3(0.0, 2.45, 0.0), 30.0)
	var bg := board.get_pixel(SIZE - 1, SIZE - 1)
	var y0 := 0
	while y0 < SIZE - 1 and board.get_pixel(SIZE / 2, y0).is_equal_approx(bg):
		y0 += 1
	var edge := board.get_pixel(SIZE / 2, y0 + 3)
	var inner := board.get_pixel(SIZE / 2, y0 + 30)
	_check(edge.r > 0.8 and edge.g > 0.8 and inner.r > inner.g + 0.1 and inner.g > inner.b,
		"panneau de col : liseré clair (%s) autour du fond marron (%s)" % [edge.to_html(false), inner.to_html(false)])
	# Poteau sans éclairage : écart type de la luminance sur une bande verticale
	var post: Image = await _shot(flat, Vector3(5.0, 1.0, 0.5), Vector3(5.0, 1.0, 0.0), 20.0)
	var n := 0
	var s1 := 0.0
	var s2 := 0.0
	for y in range(SIZE / 4, SIZE * 3 / 4):
		var c := post.get_pixel(SIZE / 2, y)
		var l := Speckle._lum(c)
		n += 1
		s1 += l
		s2 += l * l
	var mean := s1 / n
	var sd := sqrt(maxf(s2 / n - mean * mean, 0.0))
	_check(sd > 0.01, "poteau galvanisé : luminance variée (écart type %.3f)" % sd)
	# Borne sans éclairage : pied plus sombre que le haut du fût
	var km: Image = await _shot(flat, Vector3(10.0, 0.35, 1.2), Vector3(10.0, 0.35, 0.0), 40.0)
	var col_x := SIZE * 3 / 10   # à gauche du chiffre
	var top := Speckle._lum(km.get_pixel(col_x, SIZE * 3 / 10))
	var foot_y := SIZE / 2
	for y in range(SIZE - 1, SIZE / 2, -1):
		if not km.get_pixel(col_x, y).is_equal_approx(km.get_pixel(0, SIZE - 1)):
			foot_y = y
			break
	var foot := Speckle._lum(km.get_pixel(col_x, foot_y - 2))
	_check(foot < top - 0.15, "borne : pied sali (%.2f) plus sombre que le fût (%.2f)" % [foot, top])
	# Mât d'éolienne sans éclairage, vu du côté opposé à la porte : pied verdi, haut blanc
	var tower: Image = await _shot(flat, Vector3(200.0, 6.0, -72.0), Vector3(200.0, 6.0, -60.0), 60.0)
	var low_c := tower.get_pixel(SIZE / 2, SIZE * 9 / 10)
	var high_c := tower.get_pixel(SIZE / 2, SIZE / 10)
	_check(low_c.g > low_c.r + 0.03 and high_c.r > 0.8 and absf(high_c.r - high_c.g) < 0.05,
		"éolienne : pied en dégradé vert (%s), haut du mât blanc (%s)" % [low_c.to_html(false), high_c.to_html(false)])
	lit.queue_free()
	flat.queue_free()
	await process_frame
	print("test_props_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
