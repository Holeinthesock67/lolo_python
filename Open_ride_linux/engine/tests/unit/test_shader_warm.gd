extends SceneTree

## Tests unitaires sans écran du premier affichage à froid (shader_warm.gd, lot AC6).
## Lancement : godot --headless --path engine --script res://tests/unit/test_shader_warm.gd

const ShaderWarm := preload("res://scripts/shader_warm.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _shader(code_tag: String) -> Shader:
	var sh := Shader.new()
	sh.code = "shader_type spatial;\n// %s\nvoid fragment() { ALBEDO = vec3(0.5); }\n" % code_tag
	return sh


func _tile(mat: Material) -> MeshInstance3D:
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array([Vector3.ZERO, Vector3.RIGHT, Vector3.FORWARD])
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	mesh.surface_set_material(0, mat)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	return mi


func _trees(mat: Material) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = BoxMesh.new()
	mm.instance_count = 50
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.material_override = mat
	return mmi


func _proxies(warm: Node) -> int:
	var n := 0
	for c in warm.get_children():
		if String(c.name).contains("doublure") and not c.is_queued_for_deletion():
			n += 1
	return n


## Images jusqu'à ce que plus rien n'attende (au plus `limit`) ; renvoie le nombre d'images.
func _run(warm, cam: Node3D, limit := 100) -> int:
	var frames := 0
	while warm.pending() > 0 and frames < limit:
		warm.step(cam)
		frames += 1
	return frames


func _initialize() -> void:
	await process_frame   # la racine n'entre dans l'arbre qu'après _initialize
	var world := Node3D.new()
	root.add_child(world)
	var cam := Camera3D.new()
	world.add_child(cam)
	cam.position = Vector3(10, 2, 5)
	var warm = ShaderWarm.new()
	world.add_child(warm)

	# Clés : même shader (matériau dupliqué par tuile) = même clé ; autre shader, MultiMesh ou ombres : autre clé.
	var terrain_sh := _shader("terrain")
	var m1 := ShaderMaterial.new()
	m1.shader = terrain_sh
	var m2 := m1.duplicate() as ShaderMaterial
	m2.set_shader_parameter("x", 1.0)
	var t1 := _tile(m1)
	var t2 := _tile(m2)
	_check(ShaderWarm.keys_of(t1) == ShaderWarm.keys_of(t2) and ShaderWarm.keys_of(t1).size() == 1,
		"deux tuiles du même shader : une seule clé")
	var bark := ShaderMaterial.new()
	bark.shader = _shader("écorce")
	var tr := _trees(bark)
	var plain := _tile(bark)
	_check(ShaderWarm.keys_of(tr)[0].begins_with("mm") and ShaderWarm.keys_of(tr) != ShaderWarm.keys_of(plain),
		"MultiMesh et maillage simple du même shader : clés différentes")
	plain.free()
	var t_shadow := _tile(m1)
	t_shadow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_check(ShaderWarm.keys_of(t_shadow) != ShaderWarm.keys_of(t1), "ombres coupées : autre clé")
	t_shadow.free()
	var bare := Node3D.new()
	_check(ShaderWarm.keys_of(bare).is_empty(), "nœud sans maillage : aucune clé")
	bare.free()

	# Première tuile et ses arbres : retirés de la scène, une doublure par clé nouvelle, pas encore dans la scène.
	world.add_child(t1)
	world.add_child(tr)
	_check(warm.hold([t1, tr]) and not t1.is_inside_tree() and not tr.is_inside_tree(),
		"tuile et arbres nouveaux : retirés de la scène (rien n'y compile)")
	_check(warm.is_held(t1) and warm.is_held(tr) and t1.visible, "retirés, visibilité inchangée")
	_check(_proxies(warm) == 0 and warm.pending() == 3, "deux doublures préparées hors de la scène, tuile en attente")

	# Une doublure entre dans la scène par image, cachée ; dessinée SETTLE_FRAMES images plus tard.
	warm.step(cam)
	_check(_proxies(warm) == 1 and warm.shown == 0, "image 1 : une seule doublure entre dans la scène")
	var proxy_mm: MultiMeshInstance3D = null
	var entered: Node3D = null
	for c in warm.get_children():
		if String(c.name).contains("doublure"):
			entered = c
	_check(entered != null and not entered.visible, "doublure entrée cachée (pipelines de surface)")
	warm.step(cam)
	_check(_proxies(warm) == 2 and warm.shown == 0, "image 2 : la seconde entre, rien n'est encore dessiné")
	for c in warm.get_children():
		if c is MultiMeshInstance3D:
			proxy_mm = c
	_check(proxy_mm != null and proxy_mm.multimesh.instance_count == 1 and proxy_mm.multimesh.use_colors
		and proxy_mm.material_override == bark, "doublure d'arbres : une instance, même format et même matériau")
	for i in range(ShaderWarm.SETTLE_FRAMES - 1):
		warm.step(cam)
	var showing: Node3D = null
	var n_visible := 0
	for c in warm.get_children():
		if c.visible:
			showing = c
			n_visible += 1
	_check(warm.shown == 1 and n_visible == 1, "puis une seule doublure dessinée à la fois")
	var ahead := cam.global_transform.affine_inverse() * showing.global_position
	_check(ahead.z < -1.0 and absf(ahead.x) < 0.01 and showing.global_transform.basis.get_scale().x < 0.01,
		"doublure minuscule, devant la caméra")
	_check(not t1.is_inside_tree(), "tuile hors de la scène tant qu'une doublure attend")
	warm.step(cam)
	_check(warm.shown == 2 and not t1.is_inside_tree(), "deuxième doublure, l'image suivante")
	warm.step(cam)
	_check(t1.get_parent() == world and tr.get_parent() == world and warm.pending() == 0,
		"toutes les clés dessinées : tuile et arbres revenus sous leur parent")

	# Tuile suivante du même shader : rien à attendre, rien de retiré.
	world.add_child(t2)
	_check(not warm.hold([t2]) and t2.is_inside_tree() and warm.pending() == 0,
		"shader déjà dessiné : tuile affichée tout de suite")

	# Banc PC du 25/11 : des tuiles nouvelles à chaque image ne doivent pas retarder les doublures déjà entrées.
	var stream: Array = []
	var first_shown := -1
	for f in range(12):
		var mf := ShaderMaterial.new()
		mf.shader = _shader("flot %d" % f)
		var tf := _tile(mf)
		world.add_child(tf)
		warm.hold([tf])
		stream.append(tf)
		warm.step(cam)
		if first_shown < 0 and warm.shown > 2:
			first_shown = f
	_check(first_shown >= 0 and first_shown <= ShaderWarm.SETTLE_FRAMES + 1,
		"tuiles nouvelles à chaque image : la première doublure passe quand même (image %d)" % first_shown)
	_run(warm, cam, 200)
	var all_back := true
	for tf in stream:
		all_back = all_back and tf.is_inside_tree()
	_check(all_back and warm.pending() == 0, "flot fini : toutes les tuiles revenues")

	# Nouvelle espèce : un objet libéré pendant qu'il est hors de la scène ne bloque rien.
	var leaves := ShaderMaterial.new()
	leaves.shader = _shader("feuilles")
	var tr2 := _trees(leaves)
	world.add_child(tr2)
	warm.hold([tr2])
	tr2.free()
	_run(warm, cam)
	_check(warm.pending() == 0, "objet libéré pendant l'attente : préchauffage fini sans erreur")

	# Parent libéré pendant l'attente : l'objet est libéré avec lui, sans erreur.
	var holder := Node3D.new()
	world.add_child(holder)
	var other := ShaderMaterial.new()
	other.shader = _shader("autre")
	var orphan := _tile(other)
	holder.add_child(orphan)
	warm.hold([orphan])
	holder.free()
	_run(warm, cam)
	_check(not is_instance_valid(orphan) and warm.pending() == 0, "parent disparu : objet libéré")

	# En séance : rien de retiré ; passage en séance pendant une attente : tout revient.
	var m3 := ShaderMaterial.new()
	m3.shader = _shader("séance")
	var t3 := _tile(m3)
	world.add_child(t3)
	warm.hold([t3])
	_check(not t3.is_inside_tree(), "avant le départ : hors de la scène")
	warm.set_active(false)
	_check(t3.is_inside_tree() and warm.pending() == 0, "séance partie : tout revient, plus rien n'attend")
	var t4 := _tile(m3)
	world.add_child(t4)
	_check(not warm.hold([t4]) and t4.is_inside_tree(), "en séance : affichage direct")
	warm.set_active(true)
	_check(warm.hold([t4]) and not t4.is_inside_tree(), "clé jetée par la séance : reprise au chargement suivant")
	_run(warm, cam)
	_check(t4.is_inside_tree(), "puis affichée après sa doublure")

	# Sans caméra : on attend ; le garde-fou remet tout dans la scène.
	var m5 := ShaderMaterial.new()
	m5.shader = _shader("sans caméra")
	var t5 := _tile(m5)
	world.add_child(t5)
	warm.hold([t5])
	for i in range(ShaderWarm.MAX_HOLD_FRAMES + 1):
		warm.step(null)
	_check(t5.is_inside_tree() and warm.pending() == 0, "garde-fou : de retour après MAX_HOLD_FRAMES images sans caméra")

	world.free()
	print("test_shader_warm : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
