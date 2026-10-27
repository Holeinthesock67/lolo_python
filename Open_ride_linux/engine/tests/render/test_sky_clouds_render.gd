extends SceneTree

## Rendu hors écran du ciel nuageux (Lot P6, critère 2) : une caméra regarde le ciel vers le nord,
## légèrement vers le haut, avec un soleil dans le dos.
## - couverture 0 : image identique au ciel procédural actuel (main.gd, moteur Compatibility) à 3/255 près ;
## - couverture 0,6 : au moins 30 % de pixels clairs au-dessus de l'horizon ;
## - deux images à 2 s d'écart avec un vent d'ouest : le motif s'est déplacé vers l'est (corrélation).
## Lancé par run_engine_tests.sh sous Xvfb avec le moteur Compatibility, comme test_terrain_render.gd.

const SkyClouds := preload("res://scripts/sky_clouds.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")

const W := 96
const H := 64
const TOLERANCE := 3.0 / 255.0

var _failures := 0
var _checked := 0
var _vp: SubViewport
var _env: Environment
var _cam: Camera3D


func _init() -> void:
	call_deferred("_run")


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _setup() -> void:
	_vp = SubViewport.new()
	_vp.size = Vector2i(W, H)
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_vp.own_world_3d = true
	root.add_child(_vp)
	_env = Environment.new()
	_env.background_mode = Environment.BG_SKY
	_env.sky = Sky.new()
	_env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new()
	we.environment = _env
	_vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-40.0, 0.0, 0.0)   # soleil au sud, dans le dos de la caméra
	_vp.add_child(sun)
	_cam = Camera3D.new()
	_cam.fov = 70.0
	_cam.rotation_degrees = Vector3(18.0, 0.0, 0.0)   # vers le nord (−z), un peu vers le haut
	_vp.add_child(_cam)
	_cam.current = true


func _shot(mat: Material) -> Image:
	_env.sky.sky_material = mat
	for i in 4:
		await process_frame
	return _vp.get_texture().get_image()


## Ligne de l'horizon dans l'image (y vers le bas) : au-dessus, le ciel.
func _horizon_row() -> int:
	var half := tan(deg_to_rad(_cam.fov * 0.5))
	var y := tan(deg_to_rad(-_cam.rotation_degrees.x)) / half   # −1 en bas, +1 en haut
	return clampi(int((1.0 - (y * 0.5 + 0.5)) * H), 0, H)


func _max_diff(a: Image, b: Image) -> float:
	var worst := 0.0
	for y in range(H):
		for x in range(W):
			var ca := a.get_pixel(x, y)
			var cb := b.get_pixel(x, y)
			worst = maxf(worst, maxf(absf(ca.r - cb.r), maxf(absf(ca.g - cb.g), absf(ca.b - cb.b))))
	return worst


## Part des pixels du ciel nettement plus clairs (et moins bleus) que le ciel sans nuage.
func _bright_share(img: Image, clear: Image, rows: int) -> float:
	var n := 0
	for y in range(rows):
		for x in range(W):
			var c := img.get_pixel(x, y)
			var c0 := clear.get_pixel(x, y)
			if c.r - c0.r > 0.15:
				n += 1
	return float(n) / float(maxi(rows * W, 1))


## Luminance des lignes 0..rows décalée de `dx` colonnes (b par rapport à a) : corrélation centrée.
func _correlation(a: Image, b: Image, dx: int, rows: int) -> float:
	var xs := PackedFloat32Array()
	var ys := PackedFloat32Array()
	for y in range(rows):
		for x in range(W):
			var xb := x + dx
			if xb < 0 or xb >= W:
				continue
			xs.append(a.get_pixel(x, y).get_luminance())
			ys.append(b.get_pixel(xb, y).get_luminance())
	var n := xs.size()
	var ma := 0.0
	var mb := 0.0
	for i in range(n):
		ma += xs[i]
		mb += ys[i]
	ma /= n
	mb /= n
	var sab := 0.0
	var saa := 0.0
	var sbb := 0.0
	for i in range(n):
		sab += (xs[i] - ma) * (ys[i] - mb)
		saa += (xs[i] - ma) * (xs[i] - ma)
		sbb += (ys[i] - mb) * (ys[i] - mb)
	return sab / sqrt(maxf(saa * sbb, 1e-12))


func _run() -> void:
	_setup()
	var rows := _horizon_row()
	var current := await _shot(SkyClouds.current_sky_material())

	# Couverture 0 : le shader de nuages forcé sans nuage rend le ciel actuel
	var params := ThemeRenderParams.cloud_params({})
	var zero: ShaderMaterial = SkyClouds.build_material(params, "flat")
	zero.set_shader_parameter("coverage", 0.0)
	var no_cloud := await _shot(zero)
	var diff := _max_diff(current, no_cloud)
	_check(diff <= TOLERANCE, "couverture 0 : ciel identique au ciel actuel (écart max %.1f/255)" % (diff * 255.0))

	params["coverage"] = 0.6
	var cloudy: ShaderMaterial = SkyClouds.build_material(params, "flat")
	var a := await _shot(cloudy)
	var share := _bright_share(a, current, rows)
	_check(share >= 0.30, "couverture 0,6 : %.0f %% de pixels clairs au-dessus de l'horizon (≥ 30 %%)" % (share * 100.0))

	# Vent d'ouest (vers +x, l'est est à droite de l'image) : 2 s plus tard, le motif est décalé vers la droite
	var wind := {"dir": Vector3(1, 0, 0), "strength": 1.0, "gust": 0.0, "phase": 0.0}
	SkyClouds.update(cloudy, wind, 2.0 * 12.0)   # vent fort et accéléré pour un décalage de quelques pixels
	var b := await _shot(cloudy)
	var best_dx := 0
	var best := -2.0
	for dx in range(-12, 13):
		var r := _correlation(a, b, dx, rows / 2)
		if r > best:
			best = r
			best_dx = dx
	_check(_max_diff(a, b) > TOLERANCE, "avec vent : les nuages ont bougé")
	_check(best_dx > 0 and best > 0.5,
		"les nuages vont dans le sens du vent : décalage de %d pixels vers l'est (corrélation %.2f)" % [best_dx, best])
	var layered: ShaderMaterial = SkyClouds.build_material(params, "layered")
	var c := await _shot(layered)
	_check(_bright_share(c, current, rows) >= _bright_share(a, current, rows) * 0.9, "deux couches : rendu sans erreur, au moins autant de nuages")
	print("test_sky_clouds_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
