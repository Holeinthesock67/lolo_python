extends SceneTree

## Rendu hors écran de l'habillage des arbres (Lot Y8 étape 2, shaders/tree_sway.gdshader) : chêne, bouleau,
## épicéa et palmier de tree_species.gd avec le matériau de la scène principale (tree_renderer.gd).
## - Aucun point parasite sur les houppiers et les troncs éclairés, relief en marche (détecteur speckle.gd) ;
## - houppier dessiné (bouquets et trouées : luminance variée sans éclairage) ;
## - houppier à contre-jour encore vert, pas noir (lumière à travers les feuilles) ;
## - bouleau blanc à lenticelles sombres.
##   xvfb-run -a godot --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/render/test_tree_render.gd

const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const TreeSpecies := preload("res://scripts/tree_species.gd")
const Speckle := preload("res://tests/render/speckle.gd")

const SIZE := 384
const KINDS := ["oak", "birch", "spruce", "palm"]
const SPACING_M := 25.0
## Même seuil que les bâtiments (test_building_render.gd). Feuillage sans habillage : écart type de 0,014 à 0,024 ;
## avec : 0,031 à 0,049 (seuil 0,028). Chêne à contre-jour sans habillage : 81 % de feuillage noir.
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
	env.ambient_light_color = Color(0.2, 0.22, 0.25)
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.basis = Basis.looking_at(Vector3(-0.3, -0.6, -0.75), Vector3.UP)
	vp.add_child(sun)
	for i in range(KINDS.size()):
		var built := TreeSpecies.build(KINDS[i])
		var mi := MeshInstance3D.new()
		mi.mesh = built["lod0"]
		var mat := TreeRenderer.sway_material(false, TreeRenderer.RELIEF["medium"])
		mat.set_shader_parameter("sway_height_m", float(built["height"]))
		mi.material_override = mat
		mi.position = Vector3(i * SPACING_M, 0.0, 0.0)
		vp.add_child(mi)
	var cam := Camera3D.new()
	cam.name = "Camera"
	vp.add_child(cam)
	cam.current = true
	return vp


func _shot(vp: SubViewport, from: Vector3, to: Vector3, fov: float = 50.0) -> Image:
	var cam: Camera3D = vp.get_node("Camera")
	cam.fov = fov
	cam.look_at_from_position(from, to, Vector3.UP)
	for i in 4:
		await process_frame
	return vp.get_texture().get_image()


## Pixels du feuillage : verts, loin du fond bleu-gris.
func _is_leaf(c: Color) -> bool:
	return c.g > c.r * 1.05 and c.g > c.b * 1.05


func _run() -> void:
	TreeRenderer.apply_wind({"dir": Vector3.ZERO, "strength": 0.0, "gust": 0.0, "phase": 0.0})
	var lit := _viewport(false)
	var flat := _viewport(true)
	for i in range(KINDS.size()):
		var kind: String = KINDS[i]
		var x := i * SPACING_M
		var h := TreeSpecies.height_m(kind)
		# Houppier et tronc éclairés, de près
		var crown: Image = await _shot(lit, Vector3(x + 5.0, h * 0.75, 9.0), Vector3(x, h * 0.75, 0.0))
		var trunk: Image = await _shot(lit, Vector3(x + 1.0, 1.6, 3.0), Vector3(x, 1.6, 0.0))
		var r_c := Speckle.isolated_ratio(crown)
		var r_t := Speckle.isolated_ratio(trunk)
		_check(r_c <= MAX_ISOLATED and r_t <= MAX_ISOLATED,
			"%s : pas de points parasites (houppier %.4f, tronc %.4f, seuil %.3f)" % [kind, r_c, r_t, MAX_ISOLATED])
		# Feuillage dessiné : écart type de la luminance des pixels verts sans éclairage
		var albedo: Image = await _shot(flat, Vector3(x + 5.0, h * 0.75, 9.0), Vector3(x, h * 0.75, 0.0))
		var n := 0
		var s1 := 0.0
		var s2 := 0.0
		for yy in range(SIZE):
			for xx in range(SIZE):
				var c := albedo.get_pixel(xx, yy)
				if _is_leaf(c):
					var l := Speckle._lum(c)
					n += 1
					s1 += l
					s2 += l * l
		var mean := s1 / maxf(n, 1.0)
		var sd := sqrt(maxf(s2 / maxf(n, 1.0) - mean * mean, 0.0))
		_check(n > SIZE * SIZE / 20 and sd > 0.028, "%s : feuillage varié (%d pixels, écart type %.3f)" % [kind, n, sd])
	# Chêne à contre-jour (le soleil derrière le houppier) : feuillage vert, pas noir
	var back: Image = await _shot(lit, Vector3(-3.0, 2.0, -12.0), Vector3(0.0, 8.0, 0.0), 60.0)
	var leaves := 0
	var black := 0
	for yy in range(SIZE):
		for xx in range(SIZE):
			var c := back.get_pixel(xx, yy)
			if c.g >= c.r and c.g >= c.b and c.b < 0.5:
				leaves += 1
				if Speckle._lum(c) < 0.03:
					black += 1
	var share := float(black) / maxf(leaves, 1.0)
	_check(leaves > 1000 and share < 0.25, "chêne à contre-jour : %.0f %% de feuillage noir (moins de 25 %%)" % (share * 100.0))
	# Bouleau sans éclairage : écorce blanche et lenticelles sombres sur le tronc
	var bark: Image = await _shot(flat, Vector3(SPACING_M, 2.5, 2.5), Vector3(SPACING_M + 0.2, 2.5, 0.0), 40.0)
	var white := 0
	var dark := 0
	for yy in range(SIZE / 4, SIZE * 3 / 4):
		for xx in range(SIZE * 2 / 5, SIZE * 3 / 5):
			var l := Speckle._lum(bark.get_pixel(xx, yy))
			if l > 0.7:
				white += 1
			elif l < 0.25:
				dark += 1
	_check(white > dark and dark > 50, "bouleau : écorce blanche (%d pixels) à lenticelles sombres (%d)" % [white, dark])
	lit.queue_free()
	flat.queue_free()
	await process_frame
	print("test_tree_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
