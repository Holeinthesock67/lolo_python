extends Node3D

## Panneaux et bornes du bord de route (Lot P14), construits par code, texte en Label3D (police par
## défaut de Godot). Pas de class_name : charger par preload("res://scripts/roadside_props.gd").
##
## `add_chunk(route, k, items)` pose les objets du tronçon k (roadside_model.for_chunk) sur le côté
## droit, à 1,5 m du bord de la chaussée, face au cycliste qui arrive ; `remove_chunk(k)` les retire.
## Habillage (lot Y8, retouche du 29/10) :
## - panneaux de col (marron) et d'approche (blancs) : plaque de tôle à coins arrondis, liseré et rebord,
##   dimensionnée d'après le texte (le texte ne déborde jamais), sur un poteau, ou deux au-delà de
##   TWO_POSTS_FROM_M de large, avec colliers de fixation ;
## - bornes kilométriques à la française : fût de béton blanc à tête ronde peinte en rouge sur un socle,
##   « km » en blanc sur la tête et le numéro en noir sur le fût, un seul maillage.
## Texte dimensionné pour être lisible à READABLE_AT_M : lettres de LETTER_HEIGHT_M au moins.
## Maillages partagés, gardés par dimensions (peu de tailles différentes sur un parcours).

const RoadsideModel := preload("res://scripts/roadside_model.gd")
const PropShader := preload("res://shaders/props.gdshader")
## Matières de props.gdshader (lot Y8 étape 3) et faux relief par préréglage, comme les bâtiments.
const KIND_BOARD := 0
const KIND_POST := 1
const KIND_KM := 2
const RELIEF := {"low": 0.0, "medium": 1.0, "high": 1.0}

const READABLE_AT_M := 30.0
const LETTER_HEIGHT_M := 0.12        # ~ 14 minutes d'arc à 30 m
## Largeur moyenne d'un caractère de la police par défaut, en hauteur de ligne (majuscules comprises).
const CHAR_WIDTH := 0.6
const LINE_SPACING := 1.25
const FONT_SIZE := 48
## Panneaux : hauteur des lettres (le nom du col se lit à 25 m, 6 pixels sur 720 lignes au moins : visual_check.py),
## bas de la plaque au-dessus du sol, couleurs, marges et largeurs bornées.
const BOARD := {
	"summit": {"letter_m": 0.32, "bottom_m": 2.0, "color": Color(0.42, 0.25, 0.12), "ink": Color(1, 1, 1)},
	"approach": {"letter_m": 0.2, "bottom_m": 1.8, "color": Color(0.95, 0.95, 0.93), "ink": Color(0.1, 0.1, 0.1)},
}
const BOARD_MARGIN_M := 0.1          # entre le texte et le liseré
const BOARD_MIN_W := 0.9
const BOARD_MAX_W := 3.2
const BOARD_DEPTH_M := 0.04
const CORNER_R := 0.06
const POST_R := 0.035
const TWO_POSTS_FROM_M := 1.3
## Borne : socle, fût jusqu'à KM_BODY_H, tête en demi-cercle (rayon = demi-largeur).
const KM_W := 0.4
const KM_DEPTH := 0.22
const KM_PLINTH_H := 0.06
const KM_BODY_H := 0.52
const KM_INK := Color(0.08, 0.08, 0.08)
const KM_HEAD_INK := Color(1, 1, 1)

var road_width_m := 6.0
var _chunks: Dictionary = {}        # k -> Array[Node3D]
var _meshes: Dictionary = {}        # gardés ici : maillages partagés, par clé de dimensions
var _mats: Dictionary = {}


func _init() -> void:
	for kind in BOARD:
		_mats[kind] = _material(KIND_BOARD, BOARD[kind]["color"])
	_mats["post"] = _material(KIND_POST, Color(0.6, 0.6, 0.62))
	_mats["km"] = _material(KIND_KM, Color(0.95, 0.95, 0.93))
	(_mats["km"] as ShaderMaterial).set_shader_parameter("head_from_m", KM_PLINTH_H + KM_BODY_H)


static func _material(kind: int, color: Color) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = PropShader
	m.set_shader_parameter("kind", kind)
	m.set_shader_parameter("base_color", color)
	return m


## Faux relief des panneaux et bornes selon le préréglage (coupé en low).
func set_preset(preset_name: String) -> void:
	for m in _mats.values():
		(m as ShaderMaterial).set_shader_parameter("relief", float(RELIEF.get(preset_name, 1.0)))


# ---------- Maillages ----------

## Triangle tourné vers `n` (Godot : face avant dans le sens horaire vue de devant).
static func _tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, n: Vector3) -> void:
	if (b - a).cross(c - a).dot(n) > 0.0:
		var t := b
		b = c
		c = t
	st.set_normal(n)
	st.add_vertex(a)
	st.set_normal(n)
	st.add_vertex(b)
	st.set_normal(n)
	st.add_vertex(c)


## Profil convexe (x, y, sens trigonométrique) extrudé de `depth` autour de z = 0, décalé de `offset`.
static func _extrude(st: SurfaceTool, profile: PackedVector2Array, depth: float, offset: Vector3) -> void:
	var zf := depth * 0.5
	var c := Vector2.ZERO
	for p in profile:
		c += p
	c /= profile.size()
	var n := profile.size()
	for i in n:
		var a := profile[i]
		var b := profile[(i + 1) % n]
		var a3 := Vector3(a.x, a.y, 0.0) + offset
		var b3 := Vector3(b.x, b.y, 0.0) + offset
		var c3 := Vector3(c.x, c.y, 0.0) + offset
		_tri(st, c3 + Vector3(0, 0, zf), a3 + Vector3(0, 0, zf), b3 + Vector3(0, 0, zf), Vector3.BACK)
		_tri(st, c3 - Vector3(0, 0, zf), a3 - Vector3(0, 0, zf), b3 - Vector3(0, 0, zf), Vector3.FORWARD)
		var e := b - a
		var side := Vector3(e.y, -e.x, 0.0).normalized()
		_tri(st, a3 + Vector3(0, 0, zf), b3 + Vector3(0, 0, zf), b3 - Vector3(0, 0, zf), side)
		_tri(st, a3 + Vector3(0, 0, zf), b3 - Vector3(0, 0, zf), a3 - Vector3(0, 0, zf), side)


## Rectangle `w` × `h` centré, coins arrondis de rayon `r`, sens trigonométrique.
static func _rounded_rect(w: float, h: float, r: float, seg: int = 5) -> PackedVector2Array:
	var out := PackedVector2Array()
	var centers := [Vector2(w * 0.5 - r, h * 0.5 - r), Vector2(-w * 0.5 + r, h * 0.5 - r),
		Vector2(-w * 0.5 + r, -h * 0.5 + r), Vector2(w * 0.5 - r, -h * 0.5 + r)]
	for k in 4:
		for i in seg + 1:
			var a := (k + float(i) / seg) * PI * 0.5
			out.append(centers[k] + Vector2(cos(a), sin(a)) * r)
	return out


## Maillage fini : dimensions de la pièce en UV2 (lues par props.gdshader), centré verticalement.
static func _commit(st: SurfaceTool, extent: Vector2) -> ArrayMesh:
	var arrays := st.commit_to_arrays()
	var uv2 := PackedVector2Array()
	uv2.resize((arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size())
	uv2.fill(extent)
	arrays[Mesh.ARRAY_TEX_UV2] = uv2
	var m := ArrayMesh.new()
	m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return m


## Plaque de panneau `w` × `h`, centrée sur l'origine, face vers +z.
static func board_mesh(w: float, h: float) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_extrude(st, _rounded_rect(w, h, CORNER_R), BOARD_DEPTH_M, Vector3.ZERO)
	return _commit(st, Vector2(w, h))


## Poteaux (aux abscisses `xs`) de `height` m, derrière une plaque dont le bas est à `board_bottom`
## et le haut à `height`, avec un collier en haut et en bas de la plaque. Centré verticalement.
static func posts_mesh(xs: Array, height: float, board_bottom: float) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var cyl := CylinderMesh.new()
	cyl.top_radius = POST_R
	cyl.bottom_radius = POST_R
	cyl.height = height
	cyl.radial_segments = 8
	cyl.rings = 1
	var clamp := BoxMesh.new()
	clamp.size = Vector3(POST_R * 2.6, 0.05, POST_R * 2.0 + 0.02)
	var z := -(BOARD_DEPTH_M * 0.5 + POST_R)
	for x in xs:
		st.append_from(cyl, 0, Transform3D(Basis(), Vector3(x, 0.0, z)))
		for y in [board_bottom + 0.12, height - 0.12]:
			st.append_from(clamp, 0, Transform3D(Basis(), Vector3(x, y - height * 0.5, z + 0.005)))
	return _commit(st, Vector2(2.0 * POST_R, height))


## Borne kilométrique : socle, fût et tête en demi-cercle, centrée verticalement.
static func km_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var total := KM_PLINTH_H + KM_BODY_H + KM_W * 0.5
	var y0 := -total * 0.5
	var r := KM_W * 0.5
	var prof := PackedVector2Array([Vector2(r, y0 + KM_PLINTH_H), Vector2(r, y0 + KM_PLINTH_H + KM_BODY_H)])
	for i in range(1, 12):
		var a := PI * i / 12.0
		prof.append(Vector2(cos(a) * r, y0 + KM_PLINTH_H + KM_BODY_H + sin(a) * r))
	prof.append(Vector2(-r, y0 + KM_PLINTH_H + KM_BODY_H))
	prof.append(Vector2(-r, y0 + KM_PLINTH_H))
	_extrude(st, prof, KM_DEPTH, Vector3.ZERO)
	var plinth := PackedVector2Array([Vector2(r + 0.04, y0), Vector2(r + 0.04, y0 + KM_PLINTH_H),
		Vector2(-r - 0.04, y0 + KM_PLINTH_H), Vector2(-r - 0.04, y0)])
	_extrude(st, plinth, KM_DEPTH + 0.06, Vector3.ZERO)
	return _commit(st, Vector2(KM_W, total))


func _shared(key: String, maker: Callable) -> ArrayMesh:
	if not _meshes.has(key):
		_meshes[key] = maker.call()
	return _meshes[key]


func _mesh(parent: Node3D, mesh: ArrayMesh, mat: Material, pos: Vector3) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = pos
	parent.add_child(mi)
	return mi


static func _label(text: String, ink: Color, letter_m: float, pos: Vector3) -> Label3D:
	var label := Label3D.new()
	label.text = text
	label.modulate = ink
	label.outline_size = 0
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.font_size = FONT_SIZE
	label.pixel_size = letter_m / FONT_SIZE
	label.double_sided = false
	label.position = pos
	return label


## Dimensions de la plaque et hauteur des lettres pour `lines` : la plaque s'élargit avec le texte jusqu'à
## BOARD_MAX_W, puis les lettres rapetissent (jamais sous LETTER_HEIGHT_M). {w, h, letter_m}
static func board_layout(kind: String, lines: Array) -> Dictionary:
	var longest := 1
	for l in lines:
		longest = maxi(longest, str(l).length())
	var letter: float = BOARD[kind]["letter_m"]
	var inner := BOARD_MAX_W - 2.0 * (BOARD_MARGIN_M + 0.05)
	letter = maxf(LETTER_HEIGHT_M, minf(letter, inner / (longest * CHAR_WIDTH)))
	var w := clampf(longest * CHAR_WIDTH * letter + 2.0 * (BOARD_MARGIN_M + 0.05), BOARD_MIN_W, BOARD_MAX_W)
	var h := lines.size() * LINE_SPACING * letter + 2.0 * (BOARD_MARGIN_M + 0.03)
	# Au pas de 5 cm : peu de maillages différents
	return {"w": ceilf(w * 20.0) / 20.0, "h": ceilf(h * 20.0) / 20.0, "letter_m": letter}


## Nœud d'un objet `{kind, s, lines}`, à placer par add_chunk.
func build_prop(item: Dictionary) -> Node3D:
	var kind: String = item["kind"]
	var lines: Array = item["lines"]
	var root := Node3D.new()
	root.name = "%s_%d" % [kind, int(item["s"])]
	var label: Label3D
	if kind == "km":
		var total := KM_PLINTH_H + KM_BODY_H + KM_W * 0.5
		_mesh(root, _shared("km", km_mesh), _mats["km"], Vector3(0.0, total * 0.5, 0.0))
		# « km 12 » : « km » sur la tête rouge, le numéro sur le fût
		var parts := str(lines[0] if not lines.is_empty() else "").split(" ", false)
		var number: String = parts[parts.size() - 1] if parts.size() > 0 else ""
		var zf := KM_DEPTH * 0.5 + 0.004
		var digits := maxi(1, number.length())
		var letter := minf(0.2, (KM_W - 0.08) / (digits * CHAR_WIDTH))
		label = _label(number, KM_INK, letter, Vector3(0.0, KM_PLINTH_H + KM_BODY_H * 0.55, zf))
		root.add_child(label)
		if parts.size() > 1:
			root.add_child(_label(" ".join(parts.slice(0, parts.size() - 1)), KM_HEAD_INK, 0.075,
				Vector3(0.0, KM_PLINTH_H + KM_BODY_H + KM_W * 0.2, zf)))
	else:
		var spec: Dictionary = BOARD[kind]
		var lay := board_layout(kind, lines)
		var w: float = lay["w"]
		var h: float = lay["h"]
		var bottom: float = spec["bottom_m"]
		var top := bottom + h
		var xs := [-w * 0.3, w * 0.3] if w >= TWO_POSTS_FROM_M else [0.0]
		var post_h := top - 0.04
		_mesh(root, _shared("posts_%d_%d_%d" % [xs.size(), roundi(w * 100.0), roundi(post_h * 100.0)],
			posts_mesh.bind(xs, post_h, bottom)), _mats["post"], Vector3(0.0, post_h * 0.5, 0.0))
		var board_y := bottom + h * 0.5
		_mesh(root, _shared("board_%d_%d" % [roundi(w * 100.0), roundi(h * 100.0)], board_mesh.bind(w, h)),
			_mats[kind], Vector3(0.0, board_y, 0.0))
		label = _label("\n".join(lines), spec["ink"], lay["letter_m"], Vector3(0.0, board_y, BOARD_DEPTH_M * 0.5 + 0.004))
		root.add_child(label)
	root.set_meta("label", label)
	return root


## Hauteur des lettres (m) d'un objet construit par build_prop.
static func letter_height_m(prop: Node3D) -> float:
	var label: Label3D = prop.get_meta("label")
	return label.font_size * label.pixel_size


func add_chunk(route, k: int, chunk_items: Array) -> void:
	remove_chunk(k)
	var nodes: Array[Node3D] = []
	for it in chunk_items:
		var prop := build_prop(it)
		var s := float(it["s"])
		var pos := RoadsideModel.prop_position(route, s, road_width_m)
		var h := deg_to_rad(route.sample_heading_deg(s))
		var fwd := Vector3(sin(h), 0.0, -cos(h))
		# +z local (face du panneau) vers le cycliste qui arrive, donc vers -fwd
		prop.transform = Transform3D(Basis(Vector3.UP, atan2(-fwd.x, -fwd.z)), pos)
		add_child(prop)
		nodes.append(prop)
	_chunks[k] = nodes


func remove_chunk(k: int) -> void:
	if not _chunks.has(k):
		return
	for n in _chunks[k]:
		n.queue_free()
	_chunks.erase(k)


func prop_count() -> int:
	var n := 0
	for k in _chunks:
		n += (_chunks[k] as Array).size()
	return n
