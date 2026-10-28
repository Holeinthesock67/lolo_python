extends RefCounted

## Construction du ruban 3D du Cyber-Rogue depuis le profil d'une salle (lot R10 §4.2) : largeur 6 m,
## épaisseur 0,3 m, une section tous les 10 m, couleur de chaque tronçon selon sa pente. L'avant du ruban est
## la direction −Z de Godot : un point à la distance `s` de la salle est en z = −s. La pente visible est
## exagérée (`exaggeration`) pour la lisibilité. Pas de class_name :
## preload("res://scripts/rogue/ribbon_builder.gd").

const Colors := preload("res://scripts/rogue/ribbon_colors.gd")

const WIDTH_M := 6.0
const THICKNESS_M := 0.3
const DEFAULT_EXAGGERATION := 2.0


## Sections du ruban : Vector2(s_m, y_m) à chaque point du profil, plus la fin de la salle. L'altitude part
## de 0 et suit la pente × exagération.
static func stations(profile: Array, length_m: float, exaggeration: float = DEFAULT_EXAGGERATION) -> Array:
	var out: Array = []
	if profile.is_empty():
		return [Vector2(0.0, 0.0), Vector2(maxf(length_m, 1.0), 0.0)]
	var y := 0.0
	for i in profile.size():
		var s := float(profile[i][0])
		out.append(Vector2(s, y))
		var s_next := float(profile[i + 1][0]) if i + 1 < profile.size() else length_m
		y += float(profile[i][1]) / 100.0 * maxf(s_next - s, 0.0) * exaggeration
	var last_s := float(profile[profile.size() - 1][0])
	if length_m > last_s + 0.01:
		out.append(Vector2(length_m, y))
	return out


## Altitude du ruban à la distance `s_m` (interpolation entre sections, bornée aux extrémités).
static func y_at(sts: Array, s_m: float) -> float:
	if sts.is_empty():
		return 0.0
	if s_m <= sts[0].x:
		return sts[0].y
	for i in range(1, sts.size()):
		if s_m <= sts[i].x:
			var a: Vector2 = sts[i - 1]
			var b: Vector2 = sts[i]
			var t := (s_m - a.x) / maxf(b.x - a.x, 0.0001)
			return lerpf(a.y, b.y, t)
	return sts[sts.size() - 1].y


## Tableaux du maillage : 4 sommets par section (haut gauche, haut droit, bas droit, bas gauche), 8
## triangles par tronçon (dessus, deux côtés, dessous). UV.x vaut 0 à gauche et 1 à droite (arêtes lumineuses
## du shader), UV.y la distance. Couleur de section = couleur du tronçon qui la suit (le dernier garde la
## précédente).
static func arrays(profile: Array, length_m: float, exaggeration: float = DEFAULT_EXAGGERATION,
		adapted: bool = false) -> Dictionary:
	var sts := stations(profile, length_m, exaggeration)
	var colors_seg := Colors.segment_colors(profile, adapted)
	var verts := PackedVector3Array()
	var cols := PackedColorArray()
	var uvs := PackedVector2Array()
	var normals := PackedVector3Array()
	var idx := PackedInt32Array()
	var half := WIDTH_M * 0.5
	for k in sts.size():
		var st: Vector2 = sts[k]
		var c: Color = Color.WHITE
		if not colors_seg.is_empty():
			c = colors_seg[mini(k, colors_seg.size() - 1)]
		var z := -st.x
		verts.append(Vector3(-half, st.y, z))
		verts.append(Vector3(half, st.y, z))
		verts.append(Vector3(half, st.y - THICKNESS_M, z))
		verts.append(Vector3(-half, st.y - THICKNESS_M, z))
		for _j in 4:
			cols.append(c)
			normals.append(Vector3.UP)
		uvs.append(Vector2(0.0, st.x))
		uvs.append(Vector2(1.0, st.x))
		uvs.append(Vector2(1.0, st.x))
		uvs.append(Vector2(0.0, st.x))
	for k in range(sts.size() - 1):
		var a := k * 4
		var b := (k + 1) * 4
		# faces : dessus (0-1), côté droit (1-2), dessous (2-3), côté gauche (3-0)
		for e in 4:
			var e2 := (e + 1) % 4
			idx.append_array([a + e, b + e, a + e2, a + e2, b + e, b + e2])
	return {"vertices": verts, "colors": cols, "uvs": uvs, "normals": normals, "indices": idx,
		"stations": sts, "triangle_count": int(idx.size() / 3.0)}


static func mesh(profile: Array, length_m: float, exaggeration: float = DEFAULT_EXAGGERATION,
		adapted: bool = false) -> ArrayMesh:
	var d := arrays(profile, length_m, exaggeration, adapted)
	var m := ArrayMesh.new()
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = d["vertices"]
	arr[Mesh.ARRAY_COLOR] = d["colors"]
	arr[Mesh.ARRAY_TEX_UV] = d["uvs"]
	arr[Mesh.ARRAY_NORMAL] = d["normals"]
	arr[Mesh.ARRAY_INDEX] = d["indices"]
	m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	return m
