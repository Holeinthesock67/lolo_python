extends SceneTree

## Rendu hors écran du shader triplanaire (lot E2, revue R4) : vérifie sur une vraie image que le shader
## compilé reproduit la fonction de référence ThemeRenderParams.blend_weights (lot L3).
## Demande un serveur d'affichage (Xvfb) et le pilote OpenGL : lancé par run_engine_tests.sh avec
##   xvfb-run -a godot --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/render/test_terrain_render.gd
## Rendu sans éclairage (Viewport.DEBUG_DRAW_UNSHADED) : la couleur lue est l'albédo du shader.
## Le moteur Compatibility travaille en espace sRGB : les couleurs du thème y sont mélangées telles quelles.
## (Avec Forward+, sur le PC cible, le même mélange se fait en espace linéaire ; les poids sont identiques.)

const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")

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


## Couleur au centre d'un plan de pente `slope_deg` à l'altitude `alt`, vu de face par une caméra orthogonale.
func _shot(mat: ShaderMaterial, slope_deg: float, alt: float) -> Color:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.debug_draw = Viewport.DEBUG_DRAW_UNSHADED
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	var pivot := Node3D.new()
	vp.add_child(pivot)
	pivot.position = Vector3(0.0, alt, 0.0)
	pivot.rotation = Vector3(deg_to_rad(slope_deg), 0.0, 0.0)
	var mi := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(20.0, 20.0)
	mi.mesh = plane
	mi.material_override = mat
	pivot.add_child(mi)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 4.0
	cam.position = Vector3(0.0, 10.0, 0.0)
	pivot.add_child(cam)
	cam.rotation = Vector3(-PI / 2.0, 0.0, 0.0)
	cam.current = true
	for i in 5:
		await process_frame
	var c := vp.get_texture().get_image().get_pixel(SIZE / 2, SIZE / 2)
	vp.queue_free()
	await process_frame
	return c


## Couleur attendue : mélange des couleurs du thème par les poids de blend_weights (lot L3).
func _expected(theme: Dictionary, slope_deg: float, alt: float) -> Color:
	var u := ThemeRenderParams.terrain_uniforms(theme)
	var n := Vector3(0.0, cos(deg_to_rad(slope_deg)), sin(deg_to_rad(slope_deg)))
	var w := ThemeRenderParams.blend_weights(n, alt, u)
	var g: Color = u["grass_color"]
	var r: Color = u["rock_color"]
	var s: Color = u["snow_color"]
	return Color(g.r * w.x + r.r * w.y + s.r * w.z, g.g * w.x + r.g * w.y + s.g * w.z,
		g.b * w.x + r.b * w.y + s.b * w.z)


func _close(a: Color, b: Color) -> bool:
	return absf(a.r - b.r) <= TOLERANCE and absf(a.g - b.g) <= TOLERANCE and absf(a.b - b.b) <= TOLERANCE


func _write_png(file_path: String, color: Color) -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(file_path.get_base_dir()))
	var img := Image.create(8, 8, false, Image.FORMAT_RGBA8)
	img.fill(color)
	img.save_png(ProjectSettings.globalize_path(file_path))


func _run() -> void:
	# 1. Cas du critère 2 de L3 (thème par défaut), plus deux cas de transition (pente au seuil, fonte de la neige).
	# Couleurs d'E2 inchangées avec detail_strength = 0 (Lot E3 / SRS §8.1).
	var mat := TerrainMaterial.create_material({})
	mat.set_shader_parameter("detail_strength", 0.0)
	var cases := [
		[0.0, 1000.0, "sol plat à 1 000 m : herbe"],
		[30.0, 1000.0, "pente de 30° à 1 000 m : roche"],
		[0.0, 2400.0, "sol plat à 2 400 m : neige"],
		[60.0, 2400.0, "pente de 60° à 2 400 m : roche"],
		[22.0, 1000.0, "pente de 22° (seuil) : mélange herbe et roche"],
		[0.0, 2225.0, "sol plat à 2 225 m : neige à moitié fondue"],
		[47.0, 2400.0, "pente de 47° à 2 400 m : neige et roche raide"],
	]
	for c in cases:
		var got := await _shot(mat, c[0], c[1])
		var want := _expected({}, c[0], c[1])
		_check(_close(got, want), "%s (rendu #%s, attendu #%s)" % [c[2], got.to_html(false), want.to_html(false)])

	# 2. Thème personnalisé : seuil de pente à 30°, une pente de 26° reste en herbe.
	var custom := {"terrain": {"slope_threshold_deg": 30.0, "grass": {"color": "#336699"}}}
	var mat_custom := TerrainMaterial.create_material(custom)
	mat_custom.set_shader_parameter("detail_strength", 0.0)
	var got_custom := await _shot(mat_custom, 26.0, 1000.0)
	_check(_close(got_custom, _expected(custom, 26.0, 1000.0)), "seuil de 30° du thème : pente de 26° en herbe #336699 (rendu #%s)" % got_custom.to_html(false))

	# 3. Texture d'herbe unie : la couleur rendue est celle de la texture, pas la couleur de repli.
	var tmp_dir := "user://test_terrain_render"
	var tex_color := Color.html("#c08040")
	_write_png(tmp_dir.path_join("textures/grass.png"), tex_color)
	var tex_theme := {"terrain": {"grass": {"texture": "textures/grass.png", "color": "#6f9a4a", "scale_m": 6.0}}}
	var mat_tex := TerrainMaterial.create_material(tex_theme, tmp_dir)
	mat_tex.set_shader_parameter("detail_strength", 0.0)
	var got_tex := await _shot(mat_tex, 0.0, 1000.0)
	_check(_close(got_tex, tex_color), "texture d'herbe utilisée (rendu #%s, attendu #%s)" % [got_tex.to_html(false), tex_color.to_html(false)])

	# 4. Décor activé (detail_strength = 1.0) : variation de l'herbe bornée à ± 8 %
	var mat_detail := TerrainMaterial.create_material({})
	mat_detail.set_shader_parameter("detail_strength", 1.0)
	var got_detail := await _shot(mat_detail, 0.0, 1000.0)
	var want_flat := _expected({}, 0.0, 1000.0)
	var ratio := got_detail.r / want_flat.r if want_flat.r > 0.0 else 1.0
	_check(abs(ratio - 1.0) <= 0.08 + TOLERANCE, "variation d herbe avec detail=1.0 bornee a +- 8 %% (ratio %.3f)" % ratio)

	print("test_terrain_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
