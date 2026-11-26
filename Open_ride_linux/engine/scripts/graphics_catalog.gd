extends RefCounted

## Catalogue des graphismes (lot PG1) : une recette de doublure par couple (shader, format de sommets, ombres) déjà
## rencontré. Une recette est un objet d'un seul triangle par surface, au même format de sommets et avec les mêmes
## matériaux (textures remplacées par des textures de 4 × 4 pixels, qui ne changent pas les pipelines), écrit en
## `.scn`. Rejoué une fois à la préparation des graphismes (graphics_prep.gd), il fait compiler les pipelines de
## tout le jeu avant que le décor ne naisse : un objet coûte déjà un pipeline par shader nouveau à sa création,
## même caché ou détaché du monde (essais du 26/11, cahier docs/lots/LOT_PG1_preparation_graphismes.md).
## Le catalogue est le même pour toutes les cartes graphiques : un catalogue de départ est livré avec le jeu
## (`BUNDLED_DIR`), celui du joueur grandit au fil des séances (`USER_DIR`).
## Pas de class_name : charger par preload("res://scripts/graphics_catalog.gd").

const BUNDLED_DIR := "res://data/graphismes"
const USER_DIR := "user://graphismes/catalogue"
## Bits d'attributs d'un format de surface (Mesh.ARRAY_FORMAT_VERTEX à ARRAY_FORMAT_INDEX) : le reste du format
## (formats des données libres, compression, 8 os) se repasse tel quel à add_surface_from_arrays.
const ATTRIBUTE_BITS := 0x1FFF
## Écritures par appel de `flush` : quelques petits fichiers par image au plus.
const FLUSH_PER_CALL := 4

## Dossier où `flush` écrit (USER_DIR, ou celui de l'outil qui produit le catalogue de départ).
var dir := USER_DIR
## Clés déjà au catalogue (lues au lancement ou écrites depuis).
var _have: Dictionary = {}
## Recettes à écrire : [[clé, doublure]].
var _todo: Array = []
## Objets déjà vus, par identifiants (maillage, matériau d'objet, ombres) : un objet de plus du même genre ne coûte
## qu'une recherche (foules, herbe, arbres : des milliers d'objets au changement de qualité).
var _fast: Dictionary = {}


## Clé stable d'une surface, d'un lancement à l'autre (les clés de shader_warm.gd prennent des identifiants
## d'objets, qui changent) : forme de l'objet, format de sommets sans l'index, matériau, ombres.
static func stable_key(gi: GeometryInstance3D, mesh: Mesh, surface: int, prefix: String) -> String:
	var fmt := -1
	if mesh is ArrayMesh:   # lu sans copier les sommets (tuiles : à chaque création)
		fmt = (mesh as ArrayMesh).surface_get_format(surface) & ~Mesh.ARRAY_FORMAT_INDEX
	elif mesh != null:   # maillage primitif, petit : format vu par le serveur de rendu
		fmt = int(RenderingServer.mesh_get_surface(mesh.get_rid(), surface).get("format", -1)) \
			& ~Mesh.ARRAY_FORMAT_INDEX
	return "%s|%d|%s|%d|%d" % [prefix, fmt, material_stable_key(_material_of(gi, mesh, surface)),
		int(gi.cast_shadow), int(gi.transparency > 0.0)]


static func _material_of(gi: GeometryInstance3D, mesh: Mesh, surface: int) -> Material:
	if gi.material_override != null:
		return gi.material_override
	if gi is MeshInstance3D:
		var m: Material = (gi as MeshInstance3D).get_surface_override_material(surface)
		if m != null:
			return m
	return mesh.surface_get_material(surface) if mesh != null else null


## Shader par son chemin (ou son code s'il n'en a pas) ; matériau standard par ses options et ses emplacements de
## texture remplis (ce qui choisit le shader que Godot en tire), pas par ses couleurs ni ses valeurs.
static func material_stable_key(mat: Material) -> String:
	if mat == null:
		return "-"
	var k := ""
	if mat is ShaderMaterial:
		var sh: Shader = (mat as ShaderMaterial).shader
		if sh == null:
			k = "s-"
		elif sh.resource_path != "" and not sh.resource_path.contains("::"):
			k = "s" + sh.resource_path
		else:
			k = "c" + sh.code.md5_text()
	else:
		var parts: Array = [mat.get_class()]
		for p in mat.get_property_list():
			if int(p["usage"]) & PROPERTY_USAGE_STORAGE == 0:
				continue
			var t := int(p["type"])
			var name := str(p["name"])
			if name == "next_pass" or name.begins_with("resource_"):
				continue
			if t == TYPE_BOOL or t == TYPE_INT:
				parts.append("%s=%s" % [name, str(mat.get(name))])
			elif t == TYPE_OBJECT:
				parts.append("%s=%d" % [name, int(mat.get(name) != null)])
		k = "b" + ",".join(parts).md5_text()
	if mat.next_pass != null:
		k += "+" + material_stable_key(mat.next_pass)
	return k


## Clés stables de toutes les surfaces d'un objet dessiné ; vide si ce n'en est pas un.
static func keys_of(n: Node) -> Array:
	var out: Array = []
	var info := _mesh_of(n)
	if info.is_empty():
		return out
	var mesh: Mesh = info["mesh"]
	for i in range(mesh.get_surface_count()):
		out.append(stable_key(n as GeometryInstance3D, mesh, i, str(info["prefix"])))
	return out


static func _mesh_of(n: Node) -> Dictionary:
	if n is MeshInstance3D and (n as MeshInstance3D).mesh != null:
		return {"mesh": (n as MeshInstance3D).mesh, "prefix": "m"}
	if n is MultiMeshInstance3D:
		var mm: MultiMesh = (n as MultiMeshInstance3D).multimesh
		if mm != null and mm.mesh != null:
			return {"mesh": mm.mesh, "prefix": "mm%d%d%d" % [mm.transform_format, int(mm.use_colors),
				int(mm.use_custom_data)]}
	return {}


## Maillage d'un triangle par surface, au même format de sommets (formats des données libres et compression
## compris) et avec les mêmes matériaux de surface allégés. Null si une surface ne se laisse pas réduire.
static func tiny_mesh(mesh: Mesh) -> ArrayMesh:
	var out := ArrayMesh.new()
	for i in range(mesh.get_surface_count()):
		var arrays: Array = mesh.surface_get_arrays(i)
		var flags := 0
		var prim := Mesh.PRIMITIVE_TRIANGLES
		if mesh is ArrayMesh:
			flags = (mesh as ArrayMesh).surface_get_format(i) & ~ATTRIBUTE_BITS
			prim = (mesh as ArrayMesh).surface_get_primitive_type(i)
		var small := _first_triangle(arrays)
		if small.is_empty():
			return null
		out.add_surface_from_arrays(prim, small, [], {}, flags)
		out.surface_set_material(out.get_surface_count() - 1, light_material(mesh.surface_get_material(i)))
	return out


## Les trois premiers sommets (ceux du premier triangle indexé s'il y a un index), chaque tableau gardant son
## nombre de valeurs par sommet.
static func _first_triangle(arrays: Array) -> Array:
	var verts = arrays[Mesh.ARRAY_VERTEX] if arrays.size() > Mesh.ARRAY_VERTEX else null
	if verts == null or verts.size() < 3:
		return []
	var n: int = verts.size()
	var pick: Array = [0, 1, 2]
	var idx = arrays[Mesh.ARRAY_INDEX] if arrays.size() > Mesh.ARRAY_INDEX else null
	if idx != null and idx.size() >= 3:
		pick = [int(idx[0]), int(idx[1]), int(idx[2])]
	var out: Array = []
	out.resize(Mesh.ARRAY_MAX)
	for t in range(mini(arrays.size(), Mesh.ARRAY_MAX)):
		var a = arrays[t]
		if a == null or t == Mesh.ARRAY_INDEX:
			continue
		var stride: int = int(a.size() / n)
		if stride <= 0:
			return []
		var b = a.duplicate()
		b.resize(stride * 3)
		for v in range(3):
			for c in range(stride):
				b[v * stride + c] = a[pick[v] * stride + c]
		out[t] = b
	return out


## Copie d'un matériau aux textures remplacées par des textures de 4 × 4 pixels de même nature (le shader et ses
## variantes restent les mêmes, le fichier reste petit). Un shader ou une texture venus d'un fichier du jeu sont
## gardés par leur chemin.
static func light_material(mat: Material) -> Material:
	if mat == null:
		return null
	var m: Material
	if mat is ShaderMaterial:
		var sm := ShaderMaterial.new()
		sm.shader = (mat as ShaderMaterial).shader
		for u in (sm.shader.get_shader_uniform_list() if sm.shader != null else []):
			var v = (mat as ShaderMaterial).get_shader_parameter(str(u["name"]))
			if v is Texture:
				sm.set_shader_parameter(str(u["name"]), _placeholder(v))
		sm.render_priority = mat.render_priority
		m = sm
	else:
		m = mat.duplicate(false)
		for p in m.get_property_list():
			if int(p["usage"]) & PROPERTY_USAGE_STORAGE != 0 and int(p["type"]) == TYPE_OBJECT:
				var v = m.get(str(p["name"]))
				if v is Texture:
					m.set(str(p["name"]), _placeholder(v))
	m.next_pass = light_material(mat.next_pass)
	return m


static func _placeholder(tex: Texture) -> Texture:
	if tex.resource_path != "" and not tex.resource_path.contains("::"):
		return tex   # fichier du jeu : gardé par son chemin
	var img := Image.create(4, 4, false, Image.FORMAT_RGBA8)
	img.fill(Color(0.5, 0.5, 0.5, 1.0))
	if tex is Texture2DArray:
		var arr := Texture2DArray.new()
		arr.create_from_images([img])
		return arr
	if tex is Texture3D:
		var t3 := ImageTexture3D.new()
		t3.create(Image.FORMAT_RGBA8, 4, 4, 1, false, [img])
		return t3
	if tex is Cubemap:
		var cube := Cubemap.new()
		cube.create_from_images([img, img, img, img, img, img])
		return cube
	return ImageTexture.create_from_image(img)


## Doublure d'un objet, prête à écrire : un triangle par surface, une instance pour un MultiMesh, mêmes ombres.
static func recipe(n: GeometryInstance3D) -> GeometryInstance3D:
	var info := _mesh_of(n)
	if info.is_empty():
		return null
	var small := tiny_mesh(info["mesh"])
	if small == null:
		return null
	var p: GeometryInstance3D
	if n is MultiMeshInstance3D:
		var src: MultiMesh = (n as MultiMeshInstance3D).multimesh
		var mm := MultiMesh.new()
		mm.transform_format = src.transform_format
		mm.use_colors = src.use_colors
		mm.use_custom_data = src.use_custom_data
		mm.mesh = small
		mm.instance_count = 1
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		p = mmi
	else:
		var mi := MeshInstance3D.new()
		mi.mesh = small
		var src_mi := n as MeshInstance3D
		for i in range(src_mi.get_surface_override_material_count()):
			mi.set_surface_override_material(i, light_material(src_mi.get_surface_override_material(i)))
		p = mi
	p.material_override = light_material(n.material_override)
	p.cast_shadow = n.cast_shadow
	p.transparency = n.transparency
	p.name = "recette"
	return p


## Lit les clés déjà au catalogue (fichiers `<md5 de la clé>.scn` des deux dossiers).
func load_index() -> void:
	for d in [BUNDLED_DIR, dir]:
		for f in _files(d):
			_have[f.get_basename()] = true


static func _files(d: String) -> Array:
	var out: Array = []
	var da := DirAccess.open(d)
	if da == null:
		return out
	for f in da.get_files():
		if f.ends_with(".scn"):
			out.append(f)
	return out


## Retient un objet dessiné dont une clé n'est pas encore au catalogue ; écrit plus tard (`flush`).
func record(n: Node) -> void:
	if not (n is GeometryInstance3D):
		return
	var info := _mesh_of(n)
	if info.is_empty():
		return
	var gi := n as GeometryInstance3D
	var fast := "%d|%d|%d|%s" % [(info["mesh"] as Mesh).get_instance_id(),
		gi.material_override.get_instance_id() if gi.material_override != null else 0, int(gi.cast_shadow),
		str(info["prefix"])]
	if n is MeshInstance3D:
		for i in range((n as MeshInstance3D).get_surface_override_material_count()):
			var o: Material = (n as MeshInstance3D).get_surface_override_material(i)
			fast += ",%d" % (o.get_instance_id() if o != null else 0)
	if _fast.has(fast):
		return
	_fast[fast] = true
	for k in keys_of(n):
		var h: String = k.md5_text()
		if _have.has(h):
			continue
		var r := recipe(n as GeometryInstance3D)
		_have[h] = true
		if r != null:
			_todo.append([h, r])
		return   # une recette porte toutes les surfaces de l'objet


## Écrit au plus `count` recettes en attente ; renvoie le nombre écrit.
func flush(count: int = FLUSH_PER_CALL) -> int:
	if _todo.is_empty():
		return 0
	DirAccess.make_dir_recursive_absolute(dir)
	var done := 0
	while done < count and not _todo.is_empty():
		var item: Array = _todo.pop_front()
		var r: Node = item[1]
		var ps := PackedScene.new()
		if ps.pack(r) == OK:
			ResourceSaver.save(ps, dir.path_join(str(item[0]) + ".scn"))
		r.free()
		done += 1
	return done


func pending_writes() -> int:
	return _todo.size()


## Doublures de tout le catalogue (dossier livré puis celui du joueur), à rejouer ; un fichier illisible est passé.
static func load_all(dirs: Array = [BUNDLED_DIR, USER_DIR]) -> Array:
	var out: Array = []
	var seen: Dictionary = {}
	for d in dirs:
		for f in _files(d):
			if seen.has(f):
				continue
			seen[f] = true
			var ps = ResourceLoader.load(str(d).path_join(f), "PackedScene", ResourceLoader.CACHE_MODE_IGNORE)
			if ps is PackedScene:
				var n = (ps as PackedScene).instantiate()
				if n is GeometryInstance3D:
					out.append(n)
				elif n != null:
					(n as Node).free()
	return out


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE:
		for item in _todo:
			if is_instance_valid(item[1]):
				(item[1] as Node).free()
