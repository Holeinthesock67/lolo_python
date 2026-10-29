extends RefCounted

## Ruban de route en 3D, par tronçons de 1 000 m de s (lot E1, §4.1).
##
## - Tronçon k : s de k × 1 000 à min((k + 1) × 1 000, longueur), même découpage que les couches du format.
## - Une coupe tous les 2 m, placée par route_data.sample_point (Catmull-Rom du lot A) ; la dernière
##   coupe d'un tronçon est calculée au même s que la première du suivant, donc aux mêmes coordonnées.
## - Coupe : chaussée plate de 6 m, perpendiculaire au cap, plus deux bas-côtés de 0,5 m qui descendent
##   de 5 cm (ils masquent la jonction avec le terrain, posé 5 cm sous la chaussée).
## - UV : u en travers de 0 (bord gauche du bas-côté) à 1 (bord droit), v = s / 6 m (lot E2).
## - Sommets en coordonnées du monde (pas de décalage par tronçon : jointures exactes).
## Les tableaux se calculent dans une tâche de fond ; seule la création du maillage reste sur le
## fil principal. Pas de class_name (charger par preload).

const CHUNK_LENGTH_M := 1000.0
const SECTION_STEP_M := 2.0
const ROAD_WIDTH_M := 6.0          # défaut, à lire plus tard dans le thème (road.width_m)
const SHOULDER_WIDTH_M := 0.5
const SHOULDER_DROP_M := 0.05
const V_REPEAT_M := 6.0
const VERTS_PER_SECTION := 6       # bas-côté gauche (2), chaussée (2), bas-côté droit (2)
## Places en travers de la chaussée (lot P32, demande du 29 octobre : « on roule à droite, pas au milieu ») :
## écart à l'axe, positif à droite du sens du parcours. Le cycliste (caméra, avatar) roule dans la voie de
## droite, les bots à sa droite vers le bord ; les véhicules prennent le milieu de leur voie (celle d'en face
## à −LANE_CENTER_M). traffic_model.gd, road_cyclists_model.gd et bots_view.gd se placent d'après elles.
const RIDER_LATERAL_M := 1.2
const BOT_LATERAL_M := 2.1
const LANE_CENTER_M := 1.5

const ROAD_COLOR := Color(0.29, 0.29, 0.30)
const LINE_COLOR := Color(0.95, 0.95, 0.95)


static func chunk_count(route) -> int:
	return maxi(1, ceili(route.length_m / CHUNK_LENGTH_M))


## Positions s des coupes du tronçon k : tous les 2 m, plus la fin exacte du tronçon.
static func section_s(route, k: int) -> PackedFloat64Array:
	var s0 := k * CHUNK_LENGTH_M
	var s1 := minf((k + 1) * CHUNK_LENGTH_M, route.length_m)
	var out := PackedFloat64Array()
	var count := ceili((s1 - s0) / SECTION_STEP_M - 1e-9)
	for j in range(count):
		out.append(s0 + j * SECTION_STEP_M)
	out.append(s1)
	return out


## Tableaux de maillage (Mesh.ARRAY_MAX) du tronçon k.
## Hauteurs à l'échelle du relief affiché (`route.relief_k`, lot Q2) : l'axe suit `sample()["y"]`, la pente des normales
## est multipliée par le même facteur.
static func build_chunk_arrays(route, k: int, road_width_m: float = ROAD_WIDTH_M) -> Array:
	var half := road_width_m * 0.5
	var outer := half + SHOULDER_WIDTH_M
	# Décalages en travers (m, vers la droite) et descente de chaque sommet de la coupe.
	var offsets := [-outer, -half, -half, half, half, outer]
	var drops := [SHOULDER_DROP_M, 0.0, 0.0, 0.0, 0.0, SHOULDER_DROP_M]
	var total_width := 2.0 * outer
	var s_values := section_s(route, k)
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	var relief_k: float = route.relief_k
	for s_cut in s_values:
		var smp: Dictionary = route.sample(s_cut)
		var center := Vector3(smp["x"], smp["y"], smp["z"])
		var h := deg_to_rad(float(smp["heading_deg"]))
		# Cap horaire depuis le nord (−z) : avant = (sin h, 0, −cos h), droite = (cos h, 0, sin h).
		var right := Vector3(cos(h), 0.0, sin(h))
		var grade := (float(smp["grade_pct"]) / 100.0) * relief_k
		var forward := Vector3(sin(h), grade, -cos(h))
		var up_road := right.cross(forward).normalized()
		var left_shoulder := (right * SHOULDER_WIDTH_M + Vector3.UP * SHOULDER_DROP_M).cross(forward).normalized()
		var right_shoulder := (right * SHOULDER_WIDTH_M - Vector3.UP * SHOULDER_DROP_M).cross(forward).normalized()
		var section_normals := [left_shoulder, left_shoulder, up_road, up_road, right_shoulder, right_shoulder]
		for c in range(VERTS_PER_SECTION):
			vertices.append(center + right * float(offsets[c]) - Vector3.UP * float(drops[c]))
			normals.append(section_normals[c])
			uvs.append(Vector2((float(offsets[c]) + outer) / total_width, s_cut / V_REPEAT_M))
	var indices := PackedInt32Array()
	for j in range(s_values.size() - 1):
		var base := j * VERTS_PER_SECTION
		for strip in range(3):
			var l0 := base + strip * 2
			var r0 := l0 + 1
			var l1 := l0 + VERTS_PER_SECTION
			var r1 := r0 + VERTS_PER_SECTION
			# Sens horaire vu du dessus, coupe suivante « devant ».
			indices.append_array(PackedInt32Array([l0, l1, r0, r0, l1, r1]))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_INDEX] = indices
	return arrays


## Ruban le long d'une polyligne (amorce de branche d'un carrefour, lot W10) : chaussée de `width_m`,
## alpha de 1 à 0 sur les `fade_m` derniers mètres (couleur de sommet ; le matériau doit s'en servir).
## `xs`, `ys`, `zs` : positions du monde, au moins deux points. Renvoie [] sinon.
static func build_polyline_arrays(xs: Array, ys: Array, zs: Array, width_m: float, fade_m: float) -> Array:
	var count := xs.size()
	if count < 2 or ys.size() != count or zs.size() != count:
		return []
	var cum := PackedFloat64Array([0.0])
	for i in range(1, count):
		cum.append(cum[i - 1] + Vector2(float(xs[i]) - float(xs[i - 1]), float(zs[i]) - float(zs[i - 1])).length())
	var total: float = cum[count - 1]
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	var uvs := PackedVector2Array()
	var colors := PackedColorArray()
	for i in range(count):
		var a := maxi(i - 1, 0)
		var b := mini(i + 1, count - 1)
		var dx := float(xs[b]) - float(xs[a])
		var dz := float(zs[b]) - float(zs[a])
		var norm := Vector2(dx, dz).length()
		var dir := Vector2(dx, dz) / norm if norm > 1e-9 else Vector2(0.0, -1.0)
		var right := Vector3(-dir.y, 0.0, dir.x)
		var centre := Vector3(float(xs[i]), float(ys[i]), float(zs[i]))
		var alpha := 1.0
		if fade_m > 0.0:
			alpha = clampf((total - float(cum[i])) / fade_m, 0.0, 1.0)
		for side in [-1.0, 1.0]:
			vertices.append(centre + right * (0.5 * width_m * side))
			normals.append(Vector3.UP)
			uvs.append(Vector2(0.5 + 0.5 * side, float(cum[i]) / V_REPEAT_M))
			colors.append(Color(1.0, 1.0, 1.0, alpha))
	var indices := PackedInt32Array()
	for j in range(count - 1):
		var l0 := j * 2
		indices.append_array(PackedInt32Array([l0, l0 + 2, l0 + 1, l0 + 1, l0 + 2, l0 + 3]))
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_INDEX] = indices
	return arrays


## Matériau des amorces : couleur de la route, transparence portée par la couleur de sommet.
static func make_preview_material(road_color: Color = ROAD_COLOR) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = road_color
	mat.vertex_color_use_as_albedo = true
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.roughness = 0.9
	return mat


## Hauteur du centre de la chaussée en s, lue dans les tableaux du tronçon (pour les tests).
static func center_height(arrays: Array, route, k: int, s_pos: float) -> float:
	var s_values := section_s(route, k)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	for j in range(s_values.size() - 1):
		if s_pos <= s_values[j + 1] or j == s_values.size() - 2:
			var t := clampf((s_pos - s_values[j]) / (s_values[j + 1] - s_values[j]), 0.0, 1.0)
			var a := (vertices[j * VERTS_PER_SECTION + 2] + vertices[j * VERTS_PER_SECTION + 3]) * 0.5
			var b := (vertices[(j + 1) * VERTS_PER_SECTION + 2] + vertices[(j + 1) * VERTS_PER_SECTION + 3]) * 0.5
			return lerpf(a.y, b.y, t)
	return NAN


## Matériau de la route : couleur ou texture du thème (lot E2), avec la ligne médiane blanche
## discontinue (3 m peints, 3 m vides) peinte par-dessus. Avec les UV d'E1 (v = s / 6 m), une
## texture de thème se répète tous les 6 m le long de la route. À créer sur le fil principal.
static func make_material(road_color: Color = ROAD_COLOR, road_texture: Texture2D = null) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	var src: Image = road_texture.get_image() if road_texture != null else null
	mat.albedo_texture = ImageTexture.create_from_image(road_image(road_color, src))
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	mat.roughness = 0.9
	return mat


## Matériau de la route avec les marquages de P14 (Lot P17, shaders/road_markings.gdshader) : ligne
## médiane, bandes de rive, chiffres des kilomètres restants (`marks`, au plus 8 : `[{s, digit}]`).
## Couleur de la chaussée du thème ; la texture du thème n'est pas reprise. À créer sur le fil principal.
static func make_markings_material(road_color: Color = ROAD_COLOR, road_width_m: float = ROAD_WIDTH_M,
		marks: Array = []) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/road_markings.gdshader")
	mat.set_shader_parameter("road_color", Color(road_color.r, road_color.g, road_color.b))
	mat.set_shader_parameter("road_width_m", road_width_m)
	mat.set_shader_parameter("shoulder_m", SHOULDER_WIDTH_M)
	mat.set_shader_parameter("v_repeat_m", V_REPEAT_M)
	set_marks(mat, marks)
	return mat


static func set_marks(mat: ShaderMaterial, marks: Array) -> void:
	var arr := PackedVector2Array()
	for m in marks:
		if arr.size() >= 8:
			break
		arr.append(Vector2(float(m["s"]), float(m["digit"])))
	while arr.size() < 8:
		arr.append(Vector2(-1.0e6, 0.0))
	mat.set_shader_parameter("marks", arr)
	mat.set_shader_parameter("mark_count", mini((marks as Array).size(), 8))


## Image de la chaussée : image du thème si elle est lisible (non vide, non compressée), sinon couleur
## unie ; ligne médiane d'une largeur de 1/32 de l'image (au moins 2 pixels) sur la moitié haute.
static func road_image(road_color: Color, src: Image = null) -> Image:
	var img: Image = null
	if src != null:
		if not src.is_empty() and not src.is_compressed():
			img = src.duplicate()
			img.clear_mipmaps()
			img.convert(Image.FORMAT_RGB8)
	if img == null:
		img = Image.create(64, 64, false, Image.FORMAT_RGB8)
		img.fill(road_color)
	var w := img.get_width()
	var half_line := maxi(1, w / 64)
	for y in range(img.get_height() / 2):
		for x in range(w / 2 - half_line, w / 2 + half_line):
			img.set_pixel(x, y, LINE_COLOR)
	img.generate_mipmaps()
	return img
