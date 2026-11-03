extends SceneTree

## Règle des couleurs (03/11, shaders/couleur_srgb.gdshaderinc) : une couleur écrite en sRGB s'affiche telle
## qu'écrite, quelle que soit sa voie d'entrée. Gris 0,5 sur des carrés sans éclairage, vus de face :
## - couleur de sommet (COLOR) d'un shader, convertie par lineaire() ;
## - couleur d'instance d'un MultiMesh (COLOR), même conversion ;
## - constante du shader, convertie par lineaire() ;
## - uniforme `source_color` (déjà linéaire), ramené en sRGB par srgb() puis reconverti ;
## - StandardMaterial3D à couleurs de sommet avec vertex_color_is_srgb.
## Témoin : la couleur de sommet brute, sans conversion, sort plus claire en Forward+ (le défaut du gravier
## pâle). Le test tourne dans le moteur du jeu (engine/tests/rendu_jeu.py) : s'il passait en Compatibility, le
## témoin ne serait plus plus clair et le test échouerait.

const SIZE := 64
const TOL := 3.0 / 255.0
const GREY := Color(0.5, 0.5, 0.5)
const INC := "#include \"res://shaders/couleur_srgb.gdshaderinc\"\n"
const HEAD := "shader_type spatial;\nrender_mode unshaded, cull_disabled;\n" + INC

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


func _material(body: String) -> ShaderMaterial:
	var sh := Shader.new()
	sh.code = HEAD + body
	var m := ShaderMaterial.new()
	m.shader = sh
	return m


func _quad_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for v in [Vector3(-1, -1, 0), Vector3(1, -1, 0), Vector3(1, 1, 0), Vector3(-1, -1, 0), Vector3(1, 1, 0),
			Vector3(-1, 1, 0)]:
		st.set_color(GREY)
		st.set_normal(Vector3(0, 0, 1))
		st.add_vertex(v)
	return st.commit()


## Pixel central d'un carré de 2 m vu de face, seul dans son monde.
func _shot(node: Node3D) -> Color:
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.own_world_3d = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0, 0, 0)
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	vp.add_child(node)
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 1.0
	cam.position = Vector3(0, 0, 5)
	vp.add_child(cam)
	cam.current = true
	for i in 6:
		await process_frame
	var c := vp.get_texture().get_image().get_pixel(SIZE / 2, SIZE / 2)
	vp.queue_free()
	return c


func _mesh(mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = _quad_mesh()
	mi.material_override = mat
	return mi


func _near(c: Color, want: Color) -> bool:
	return absf(c.r - want.r) <= TOL and absf(c.g - want.g) <= TOL and absf(c.b - want.b) <= TOL


func _run() -> void:
	var method := RenderingServer.get_current_rendering_method()
	_check(method == "forward_plus", "moteur de rendu du jeu (%s)" % method)

	var raw: Color = await _shot(_mesh(_material("void fragment() { ALBEDO = COLOR.rgb; }")))
	_check(raw.r > GREY.r + 0.15, "témoin : couleur de sommet brute plus claire en Forward+ (%s)" % raw.to_html(false))

	var vert: Color = await _shot(_mesh(_material("void fragment() { ALBEDO = lineaire(COLOR.rgb); }")))
	_check(_near(vert, GREY), "couleur de sommet convertie : affichée telle qu'écrite (%s)" % vert.to_html(false))

	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	var qm := QuadMesh.new()
	qm.size = Vector2(2, 2)
	mm.mesh = qm
	mm.instance_count = 1
	mm.set_instance_transform(0, Transform3D())
	mm.set_instance_color(0, GREY)
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.material_override = _material("void fragment() { ALBEDO = lineaire(COLOR.rgb); }")
	var inst: Color = await _shot(mmi)
	_check(_near(inst, GREY), "couleur d'instance convertie : affichée telle qu'écrite (%s)" % inst.to_html(false))

	var cst: Color = await _shot(_mesh(_material(
		"const vec3 GRIS = vec3(0.5);\nvoid fragment() { ALBEDO = lineaire(GRIS); }")))
	_check(_near(cst, GREY), "constante convertie : affichée telle qu'écrite (%s)" % cst.to_html(false))

	var um := _material("uniform vec3 teinte : source_color;\nvoid fragment() { ALBEDO = lineaire(srgb(teinte)); }")
	um.set_shader_parameter("teinte", GREY)
	var uni: Color = await _shot(_mesh(um))
	_check(_near(uni, GREY), "uniforme source_color aller-retour par srgb() : inchangé (%s)" % uni.to_html(false))

	var std := StandardMaterial3D.new()
	std.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	std.cull_mode = BaseMaterial3D.CULL_DISABLED
	std.vertex_color_use_as_albedo = true
	std.vertex_color_is_srgb = true
	var smat: Color = await _shot(_mesh(std))
	_check(_near(smat, GREY), "StandardMaterial3D, vertex_color_is_srgb : affichée telle qu'écrite (%s)" % smat.to_html(false))

	print("test_couleur_sommet_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
