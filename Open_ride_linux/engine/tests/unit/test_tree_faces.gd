extends SceneTree

## Sens des faces des arbres construits par code (tree_species.gd, LOD 0) : Godot ne dessine que l'avant des
## faces (tree_sway.gdshader et StandardMaterial3D en cull_back), l'avant étant le côté d'où les sommets sont
## vus dans le sens des aiguilles d'une montre. Une face tournée vers l'intérieur fait disparaître le devant
## d'un houppier ou d'un tronc : on voit alors l'intérieur du fond du cône, et le tronc qu'il contient passe
## devant le feuillage (défaut vu en recette vélo le 7 novembre sur les pins et épicéas).
## Contrôle : depuis une couronne de points tout autour de l'arbre, la première face touchée par chaque rayon
## visé sur l'axe de l'arbre doit être tournée vers le point de vue (palmes et frondes exceptées : elles ont
## leurs deux côtés). La normale du sommet doit aussi être du même côté que l'avant de la face.
## Lancement : godot --headless --path engine --script res://tests/unit/test_tree_faces.gd

const BiomeIds := preload("res://scripts/biome_ids.gd")
const TreeSpecies := preload("res://scripts/tree_species.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")

## Espèces à tronc unique sous le houppier (le premier fût de tree_species.build) : le haut du tronc doit être
## pris dans le feuillage, sans jour entre les deux (défaut vu le 7 novembre sur le pin parasol : tronc arrêté à
## 9,5 m sous un houppier qui commence à 9,8 m). Les arbres à fourche (olivier, acacia, baobab) et à palmes
## (palmier, fougère) ont leurs branches jusqu'au feuillage.
const SINGLE_TRUNK := ["oak", "beech", "spruce", "pine", "birch", "larch", "holm_oak", "cypress", "stone_pine"]

var _failures := 0
var _checked := 0


func _init() -> void:
	for kind in BiomeIds.SPECIES:
		var built := TreeSpecies.build(kind)
		if built.is_empty():
			continue
		_check_mesh(kind, built["lod0"], float(built["height"]))
		if built.has("lod0_bare"):
			_check_mesh(kind + " (hiver, charpente du lot P18)", built["lod0_bare"], float(built["height"]))
			_check(TreeSpecies.triangle_count(built["lod0_bare"]) < 300, "%s l'hiver : moins de 300 triangles (%d)" % [kind, TreeSpecies.triangle_count(built["lod0_bare"])])
		if kind in SINGLE_TRUNK:
			_check_trunk_in_crown(kind, built["lod0"])
	_check_mesh("generic", TreeRenderer.build_lod0_mesh(), 5.4)
	print("test_tree_faces : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Avant d'une face selon Godot : sommets a, b, c dans le sens des aiguilles d'une montre vus de devant.
static func front_normal(a: Vector3, b: Vector3, c: Vector3) -> Vector3:
	return (c - a).cross(b - a)


func _check_mesh(kind: String, mesh: ArrayMesh, height: float) -> void:
	var arrays := mesh.surface_get_arrays(0)
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var normals: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
	var tris := []
	var normal_bad := 0
	for t in range(verts.size() / 3):
		var a := verts[3 * t]
		var b := verts[3 * t + 1]
		var c := verts[3 * t + 2]
		var fn := front_normal(a, b, c)
		if fn.length_squared() < 1e-12:
			continue
		var two_sided := int(round(colors[3 * t].a * 16.0)) == TreeSpecies.MAT_FRONDS
		tris.append([a, b, c, fn.normalized(), two_sided])
		if not two_sided and fn.dot(normals[3 * t]) <= 0.0:
			normal_bad += 1
	_check(normal_bad == 0, "%s : normales du côté de l'avant des faces (%d faces à l'envers)" % [kind, normal_bad])
	# Rayons de 16 directions décalées × 9 hauteurs (plus 4 de dessus et 4 de dessous), visant l'axe de l'arbre
	var hits := 0
	var back := 0
	var dist := height * 4.0 + 20.0
	var rays := []
	for k in range(9):
		var y := height * (0.05 + 0.9 * k / 8.0)
		for i in range(16):
			var ang := TAU * i / 16.0 + 0.17   # décalé des arêtes des troncs à 6 et 8 côtés (rayon rasant)
			rays.append([Vector3(cos(ang) * dist, y + height * 0.2, sin(ang) * dist), Vector3(0, y, 0)])
	for i in range(4):
		var ang := TAU * i / 4.0 + 0.4
		rays.append([Vector3(cos(ang) * height, height * 3.0, sin(ang) * height), Vector3(0, height * 0.8, 0)])
		rays.append([Vector3(cos(ang) * height, -height, sin(ang) * height), Vector3(0, height * 0.5, 0)])
	for r in rays:
		var o: Vector3 = r[0]
		var d: Vector3 = (r[1] - o).normalized()
		var best := INF
		var best_tri = null
		for tri in tris:
			var tt := _ray(o, d, tri[0], tri[1], tri[2])
			if tt > 0.0 and tt < best:
				best = tt
				best_tri = tri
		if best_tri == null or best_tri[4]:
			continue
		hits += 1
		if (best_tri[3] as Vector3).dot(-d) <= 0.0:
			back += 1
	_check(hits > 0 and back == 0, "%s : première face vue de dehors tournée vers l'œil (%d sur %d à l'envers)" % [kind, back, hits])


## Haut du premier fût (ses 12 premiers triangles, sommets de la moitié haute) : un rayon tiré vers le haut depuis
## son centre doit sortir d'un volume de feuillage de plus qu'il n'en entre : le point est dans le houppier.
func _check_trunk_in_crown(kind: String, mesh: ArrayMesh) -> void:
	var verts: PackedVector3Array = mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	var colors: PackedColorArray = mesh.surface_get_arrays(0)[Mesh.ARRAY_COLOR]
	var n := TreeSpecies.SIDES * 6
	var lo := INF
	var hi := -INF
	for i in range(n):
		lo = minf(lo, verts[i].y)
		hi = maxf(hi, verts[i].y)
	var top := Vector3.ZERO
	var count := 0
	for i in range(n):
		if verts[i].y > (lo + hi) * 0.5:
			top += verts[i]
			count += 1
	top /= float(count)
	# Sorties moins entrées des volumes de feuillage le long du rayon : au moins 1 si le point est dedans
	# (houppiers qui se chevauchent : dessous d'un étage supérieur dans le cône inférieur).
	var depth := 0
	for t in range(n / 3, verts.size() / 3):
		var a := verts[3 * t]
		var b := verts[3 * t + 1]
		var c := verts[3 * t + 2]
		if int(round(colors[3 * t].a * 16.0)) < TreeSpecies.MAT_LEAVES or _ray(top, Vector3.UP, a, b, c) <= 0.0:
			continue
		depth += 1 if front_normal(a, b, c).y > 0.0 else -1
	var inside := depth >= 1
	_check(inside, "%s : haut du tronc (%.1f m) pris dans le feuillage" % [kind, top.y])


## Möller-Trumbore, des deux côtés : distance au point touché, ou -1.
static func _ray(o: Vector3, d: Vector3, a: Vector3, b: Vector3, c: Vector3) -> float:
	var e1 := b - a
	var e2 := c - a
	var p := d.cross(e2)
	var det := e1.dot(p)
	if absf(det) < 1e-9:
		return -1.0
	var inv := 1.0 / det
	var s := o - a
	var u := s.dot(p) * inv
	if u < 0.0 or u > 1.0:
		return -1.0
	var q := s.cross(e1)
	var v := d.dot(q) * inv
	if v < 0.0 or u + v > 1.0:
		return -1.0
	return e2.dot(q) * inv
