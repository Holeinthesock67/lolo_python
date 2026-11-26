extends SceneTree

## Tests unitaires sans écran du catalogue des graphismes (graphics_catalog.gd, lot PG1).
## Lancement : godot --headless --path engine --script res://tests/unit/test_graphics_catalog.gd

const Catalog := preload("res://scripts/graphics_catalog.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _shader(tag: String) -> Shader:
	var sh := Shader.new()
	sh.code = "shader_type spatial;\n// %s\nuniform sampler2D tex;\nvoid fragment() { ALBEDO = texture(tex, UV).rgb; }\n" % tag
	return sh


## Maillage indexé avec normales, couleurs, UV et une donnée libre en RGBA8, sommets compressés.
func _rich_mesh(mat: Material) -> ArrayMesh:
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	var n := 6
	var v := PackedVector3Array()
	var nor := PackedVector3Array()
	var col := PackedColorArray()
	var uv := PackedVector2Array()
	var custom := PackedByteArray()
	for i in range(n):
		v.append(Vector3(i, i % 2, 0))
		nor.append(Vector3.UP)
		col.append(Color(0.1 * i, 0.2, 0.3))
		uv.append(Vector2(0.1 * i, 0.5))
		for c in range(4):
			custom.append(i * 4 + c)
	arrays[Mesh.ARRAY_VERTEX] = v
	arrays[Mesh.ARRAY_NORMAL] = nor
	arrays[Mesh.ARRAY_COLOR] = col
	arrays[Mesh.ARRAY_TEX_UV] = uv
	arrays[Mesh.ARRAY_CUSTOM0] = custom
	arrays[Mesh.ARRAY_INDEX] = PackedInt32Array([3, 4, 5, 0, 1, 2])
	var flags := (Mesh.ARRAY_CUSTOM_RGBA8_UNORM << Mesh.ARRAY_FORMAT_CUSTOM0_SHIFT) | Mesh.ARRAY_FLAG_COMPRESS_ATTRIBUTES
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays, [], {}, flags)
	mesh.surface_set_material(0, mat)
	return mesh


func _big_texture() -> ImageTexture:
	var img := Image.create(256, 256, false, Image.FORMAT_RGBA8)
	img.fill(Color.RED)
	return ImageTexture.create_from_image(img)


func _initialize() -> void:
	await process_frame
	var sh := _shader("terrain")
	var mat := ShaderMaterial.new()
	mat.shader = sh
	mat.set_shader_parameter("tex", _big_texture())
	var mesh := _rich_mesh(mat)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh

	# Maillage réduit : un triangle, même format de sommets (sans l'index), même matériau allégé.
	var small := Catalog.tiny_mesh(mesh)
	var f_src := mesh.surface_get_format(0) & ~Mesh.ARRAY_FORMAT_INDEX
	var f_small := small.surface_get_format(0) & ~Mesh.ARRAY_FORMAT_INDEX
	_check(small != null and f_small == f_src, "un triangle au même format de sommets (%d / %d)" % [f_small, f_src])
	var sv: PackedVector3Array = small.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	_check(sv.size() == 3 and sv[0].is_equal_approx(Vector3(3, 1, 0)), "premier triangle de l'index (sommets 3, 4, 5)")
	var lm: ShaderMaterial = small.surface_get_material(0)
	var lt: Texture2D = lm.get_shader_parameter("tex")
	_check(lm.shader == sh and lt != null and lt.get_width() == 4, "même shader, texture de 4 × 4 pixels")

	# Clés stables : même shader, paramètres différents, même clé ; autre format ou autres ombres : autre clé.
	var mat2 := mat.duplicate() as ShaderMaterial
	mat2.set_shader_parameter("tex", null)
	var mi2 := MeshInstance3D.new()
	mi2.mesh = _rich_mesh(mat2)
	_check(Catalog.keys_of(mi) == Catalog.keys_of(mi2), "même shader, autres paramètres : même clé")
	var mi3 := MeshInstance3D.new()
	mi3.mesh = BoxMesh.new()
	mi3.material_override = mat
	_check(Catalog.keys_of(mi3) != Catalog.keys_of(mi), "autre format de sommets : autre clé")
	mi2.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_check(Catalog.keys_of(mi2) != Catalog.keys_of(mi), "ombres coupées : autre clé")
	var std1 := StandardMaterial3D.new()
	std1.albedo_color = Color.RED
	var std2 := StandardMaterial3D.new()
	std2.albedo_color = Color.BLUE
	var std3 := StandardMaterial3D.new()
	std3.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_check(Catalog.material_stable_key(std1) == Catalog.material_stable_key(std2)
		and Catalog.material_stable_key(std1) != Catalog.material_stable_key(std3),
		"matériau standard : couleur sans effet, transparence change la clé")
	var rec_box := Catalog.recipe(mi3)
	_check(rec_box != null and Catalog.keys_of(rec_box) == Catalog.keys_of(mi3),
		"recette d'un maillage primitif (BoxMesh) : mêmes clés")
	if rec_box != null:
		rec_box.free()

	# MultiMesh : recette d'une instance, mêmes options, mêmes clés.
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = mesh
	mm.instance_count = 40
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	var rec := Catalog.recipe(mmi)
	_check(rec is MultiMeshInstance3D and (rec as MultiMeshInstance3D).multimesh.instance_count == 1
		and Catalog.keys_of(rec) == Catalog.keys_of(mmi), "MultiMesh : une instance, mêmes clés")
	rec.free()

	# Écrit puis relu : mêmes clés, fichier petit, rien d'écrit deux fois.
	var dir := "user://test_catalogue_%d" % Time.get_ticks_usec()
	var cat = Catalog.new()
	cat.dir = dir
	cat.record(mi)
	cat.record(mi)   # même clé : une seule recette
	cat.record(mmi)
	var plain := Node3D.new()
	cat.record(plain)   # pas un objet dessiné : ignoré
	plain.free()
	_check(cat.pending_writes() == 2, "deux recettes en attente (objet en double ignoré)")
	_check(cat.flush(1) == 1 and cat.flush() == 1 and cat.pending_writes() == 0, "écrites quelques-unes par appel")
	var back: Array = Catalog.load_all([dir])
	var keys_back: Array = []
	for n in back:
		keys_back.append_array(Catalog.keys_of(n))
	_check(back.size() == 2 and keys_back.has(Catalog.keys_of(mi)[0]) and keys_back.has(Catalog.keys_of(mmi)[0]),
		"relues : les deux doublures, mêmes clés")
	var biggest := 0
	var da := DirAccess.open(dir)
	for f in da.get_files():
		var fa := FileAccess.open(dir.path_join(f), FileAccess.READ)
		biggest = maxi(biggest, fa.get_length())
	_check(biggest < 20000, "fichiers petits (le plus gros : %d octets, texture 256 × 256 non copiée)" % biggest)
	var cat2 = Catalog.new()
	cat2.dir = dir
	cat2.load_index()
	cat2.record(mi)
	_check(cat2.pending_writes() == 0, "clé déjà au catalogue : rien à réécrire au lancement suivant")
	for n in back:
		n.free()
	for f in da.get_files():
		da.remove(f)
	DirAccess.remove_absolute(dir)
	mi.free()
	mi2.free()
	mi3.free()
	mmi.free()
	print("test_graphics_catalog : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
