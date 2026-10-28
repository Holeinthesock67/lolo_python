extends SceneTree

## Rendu hors écran du terrain multi-biome (lot U6, terrain_biomes.gdshader), même principe que
## test_terrain_render.gd (E2) : Xvfb, OpenGL, rendu sans éclairage (la couleur lue est l'albédo).
##   xvfb-run -a godot --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/render/test_terrain_biomes_render.gd
## 1. Deux biomes en bandes (prairie, méditerranéen) sur deux tuiles voisines : teinte moyenne de chaque
##    bande à moins de 5 % de la couleur du thème, pas de marche au bord commun des tuiles (moins de 3 %).
## 2. low : une tuile à 4 biomes dont le plus faible a une couleur témoin ; l'image ne change pas quand la
##    couleur témoin change (3 biomes échantillonnés), elle change en medium.
## 3. Couche texturée : la couleur rendue est celle de la texture du tableau ground_a.

const BiomeTextures := preload("res://scripts/biome_textures.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

const SIZE := 64
const TILE_M := 1000.0

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


## Image vue de dessus (caméra orthogonale) des tuiles proches `tiles` : chaque tuile est un plan de
## 1 000 m à son origine, avec le matériau de `bt`. La zone filmée va de x0 à x0 + width (m), z de 0 à width.
func _shot(bt, tiles: Array, x0: float, width: float, px: Vector2i = Vector2i(SIZE, SIZE)) -> Image:
	var vp := SubViewport.new()
	vp.size = px
	vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	for t in tiles:
		var mi := MeshInstance3D.new()
		var plane := PlaneMesh.new()
		plane.size = Vector2(TILE_M, TILE_M)
		mi.mesh = plane
		mi.position = Vector3(t.x * TILE_M + TILE_M / 2.0, 100.0, t.y * TILE_M + TILE_M / 2.0)
		mi.material_override = bt.tile_material("near", t.x, t.y)
		vp.add_child(mi)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.keep_aspect = Camera3D.KEEP_WIDTH
	cam.size = width
	cam.position = Vector3(x0 + width / 2.0, 500.0, width * float(px.y) / float(px.x) / 2.0)
	vp.add_child(cam)
	cam.rotation = Vector3(-PI / 2.0, 0.0, 0.0)
	cam.current = true
	for i in 5:
		await process_frame
	var img := vp.get_texture().get_image()
	vp.queue_free()
	await process_frame
	return img


## Grille 17 × 17 d'un biome : poids w(i) pour la colonne i.
func _column_grid(f: Callable) -> PackedFloat32Array:
	var g := PackedFloat32Array()
	g.resize(BiomeLayer.POINTS)
	for j in range(BiomeLayer.GRID):
		for i in range(BiomeLayer.GRID):
			g[j * BiomeLayer.GRID + i] = f.call(i)
	return g


func _tile(biomes: Array, grids: Array) -> Dictionary:
	var names: Array[String] = []
	for b in biomes:
		names.append(b)
	var g: Array[PackedFloat32Array] = []
	for x in grids:
		g.append(x)
	return {"biomes": names, "weights": g, "variant": null}


func _mean(img: Image, x0: int, x1: int) -> Color:
	var s := Vector3.ZERO
	var n := 0
	for y in range(img.get_height()):
		for x in range(x0, x1):
			var c := img.get_pixel(x, y)
			s += Vector3(c.r, c.g, c.b)
			n += 1
	s /= float(n)
	return Color(s.x, s.y, s.z)


func _rel(a: Color, b: Color) -> float:
	return maxf(maxf(absf(a.r - b.r), absf(a.g - b.g)), absf(a.b - b.b)) / maxf(maxf(b.r, b.g), maxf(b.b, 1e-3))


func _no_detail(bt) -> void:
	bt.material.set_shader_parameter("detail_strength", 0.0)


func _run() -> void:
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]

	# 1. Bandes : tuile (0, 0) prairie puis fondu vers le méditerranéen sur ses 4 dernières colonnes,
	# tuile (1, 0) fondu depuis son bord ouest (mêmes poids au bord commun) puis méditerranéen.
	var layer := BiomeLayer.new()
	var ramp_a := func(i): return 1.0 if i <= 12 else 1.0 - float(i - 12) / 8.0
	var ramp_b := func(i): return 0.5 - float(i) / 8.0 if i < 4 else 0.0
	layer.put_tile("near", 0, 0, _tile(["temperate_grassland", "mediterranean"],
		[_column_grid(ramp_a), _column_grid(func(i): return 1.0 - ramp_a.call(i))]))
	layer.put_tile("near", 1, 0, _tile(["temperate_grassland", "mediterranean"],
		[_column_grid(ramp_b), _column_grid(func(i): return 1.0 - ramp_b.call(i))]))
	var model := BiomeModel.new(theme, layer)
	var bt := BiomeTextures.new(model, "", "medium")
	_no_detail(bt)
	var img := await _shot(bt, [Vector2i(0, 0), Vector2i(1, 0)], 0.0, 2000.0, Vector2i(128, 64))
	var grass: Color = model.params("temperate_grassland")["terrain"]["grass_color"]
	var med: Color = model.params("mediterranean")["terrain"]["grass_color"]
	var band_a := _mean(img, 4, 40)
	var band_b := _mean(img, 88, 124)
	_check(_rel(band_a, grass) < 0.05, "bande prairie : #%s pour #%s (écart %.1f %%)" % [band_a.to_html(false), grass.to_html(false), 100.0 * _rel(band_a, grass)])
	_check(_rel(band_b, med) < 0.05, "bande méditerranéenne : #%s pour #%s (écart %.1f %%)" % [band_b.to_html(false), med.to_html(false), 100.0 * _rel(band_b, med)])
	# Pixel par pixel de part et d'autre du bord (les deux tuiles rangent leurs biomes dans des canaux différents)
	# (vue de 200 m centrée sur le bord : 1,6 m par pixel)
	var edge_img := await _shot(bt, [Vector2i(0, 0), Vector2i(1, 0)], 900.0, 200.0, Vector2i(128, 64))
	var step := 0.0
	for y in range(edge_img.get_height()):
		step = maxf(step, _rel(edge_img.get_pixel(63, y), edge_img.get_pixel(64, y)))
	_check(step < 0.015, "bord commun des tuiles : pas de marche (écart au pire %.1f %%, critère 3 %%, seuil du test 1,5 %%)" % (100.0 * step))
	var mid := _mean(img, 60, 68)
	_check(_rel(mid, grass) > 0.05 and _rel(mid, med) > 0.05, "transition : mélange des deux biomes (#%s)" % mid.to_html(false))
	# Fondu cassé par le bruit : la limite entre les biomes n'est pas une droite
	var edge_cols := []
	for y in [8, 24, 40, 56]:
		var best := 0
		for x in range(40, 88):
			if _rel(img.get_pixel(x, y), grass) < _rel(img.get_pixel(x, y), med):
				best = x
		edge_cols.append(best)
	_check(edge_cols.max() - edge_cols.min() >= 1, "limite modulée par le bruit (colonnes %s)" % str(edge_cols))

	# 2. low : 3 biomes au plus. Tuile à 4 biomes, le plus faible (volcanique) en couleur témoin.
	var parts := [100, 70, 50, 35]
	var biomes4 := ["alpine", "temperate_forest", "farmland", "volcanic"]
	var shots := {}
	for quality in ["low", "medium"]:
		for witness in ["#ff00ff", "#00ffff"]:
			var th := theme.duplicate(true)
			th["biomes"]["volcanic"]["ground"]["layers"][0]["color"] = witness
			var l4 := BiomeLayer.new()
			var grids := []
			for p in parts:
				grids.append(_column_grid(func(_i): return float(p) / 255.0))
			l4.put_tile("near", 0, 0, _tile(biomes4, grids))
			var bt4 := BiomeTextures.new(BiomeModel.new(th, l4), "", quality)
			_no_detail(bt4)
			shots[quality + witness] = await _shot(bt4, [Vector2i(0, 0)], 0.0, 1000.0)
	_check((shots["low#ff00ff"] as Image).get_data() == (shots["low#00ffff"] as Image).get_data(), "low : couleur témoin du 4e biome absente de l'image")
	_check((shots["medium#ff00ff"] as Image).get_data() != (shots["medium#00ffff"] as Image).get_data(), "medium : le 4e biome est échantillonné")

	# 3. Couche texturée (carte A) : la couleur rendue est celle de la texture
	var dir := "user://test_terrain_biomes_render"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(dir.path_join("textures")))
	var tex_color := Color.html("#c08040")
	var timg := Image.create(8, 8, false, Image.FORMAT_RGBA8)
	timg.fill(tex_color)
	timg.save_png(ProjectSettings.globalize_path(dir.path_join("textures/sand.png")))
	var th3 := theme.duplicate(true)
	th3["biomes"]["sand_desert"]["ground"]["layers"][0]["texture"] = "textures/sand.png"
	var m3 := BiomeModel.new(th3, BiomeLayer.new())
	m3.set_forced("sand_desert")
	var bt3 := BiomeTextures.new(m3, dir, "low")
	_no_detail(bt3)
	_check(bt3.texture_px == 1024 and bt3.log_line.contains("1024 px"), "texture chargée au niveau 1 024 : « %s »" % bt3.log_line)
	var got := _mean(await _shot(bt3, [Vector2i(0, 0)], 0.0, 1000.0), 0, SIZE)
	_check(_rel(got, tex_color) < 0.03, "couleur de la texture du tableau (#%s pour #%s)" % [got.to_html(false), tex_color.to_html(false)])

	print("test_terrain_biomes_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
