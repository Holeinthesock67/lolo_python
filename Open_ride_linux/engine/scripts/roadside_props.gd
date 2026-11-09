extends Node3D

## Panneaux et bornes du bord de route (Lot P14), construits par code, texte en Label3D (police par
## défaut de Godot). Pas de class_name : charger par preload("res://scripts/roadside_props.gd").
##
## `add_chunk(route, k, items)` pose les objets du tronçon k (roadside_model.for_chunk) du côté `side` de
## l'objet, à 1,5 m du bord de la chaussée : à droite (`side` 1) face au cycliste qui arrive dans le sens du
## parcours, à gauche (`side` -1) face à celui qui roule à rebours (demi-tour, lot N17) ; `remove_chunk(k)`
## les retire.
## Habillage (lot Y8, retouche du 29/10) :
## - panneaux de col (marron) : plaque de tôle à coins arrondis, liseré et rebord, dimensionnée d'après le
##   texte (le texte ne déborde jamais), sur un poteau, ou deux au-delà de TWO_POSTS_FROM_M de large, avec
##   colliers de fixation ;
## - panneaux d'approche (refaits le 07/11, 4.0) : plaque blanche verticale cadrée de noir, à la manière des
##   panneaux cyclistes des cols (nom, altitude, pictogramme cycliste et distance au sommet en grand, pente
##   moyenne sur un pavé vert, bleu, rouge ou noir), couches peintes minces (props.gdshader, matière 6) ;
## - bornes kilométriques à la française : fût de béton blanc à tête ronde peinte en rouge sur un socle,
##   « km » en blanc sur la tête et le numéro en noir sur le fût, sur les deux faces (lisible dans les deux
##   sens de marche), un seul maillage.
## Texte dimensionné pour être lisible à READABLE_AT_M : lettres de LETTER_HEIGHT_M au moins.
## Maillages partagés, gardés par dimensions (peu de tailles différentes sur un parcours).

const RoadsideModel := preload("res://scripts/roadside_model.gd")
const PropShader := preload("res://shaders/props.gdshader")
## Matières de props.gdshader (lot Y8 étape 3) et faux relief par préréglage, comme les bâtiments.
const KIND_BOARD := 0
const KIND_POST := 1
const KIND_KM := 2
const KIND_LAYER := 6
## Pictogrammes peints sur une couche (props.gdshader, `picto`)
const PICTO_NONE := 0
const PICTO_CYCLIST := 1
const RELIEF := {"low": 0.0, "medium": 1.0, "high": 1.0}

const READABLE_AT_M := 30.0
const LETTER_HEIGHT_M := 0.12        # ~ 14 minutes d'arc à 30 m
## Largeur moyenne d'un caractère de la police par défaut, en hauteur de ligne (majuscules comprises).
const CHAR_WIDTH := 0.6
const LINE_SPACING := 1.25
const FONT_SIZE := 48
## Panneau de col : hauteur des lettres (le nom du col se lit à 25 m, 6 pixels sur 720 lignes au moins : visual_check.py),
## bas de la plaque au-dessus du sol, couleurs, marges et largeurs bornées.
const BOARD := {
	"summit": {"letter_m": 0.32, "bottom_m": 2.0, "color": Color(0.42, 0.25, 0.12), "ink": Color(1, 1, 1)},
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

## Panneaux d'approche (refaits le 07/11, 4.0) : plaque de col verticale, voir approach_layout().
const APPROACH_SCALE := 1.25         # agrandissement voulu (07/11 : « 25 % plus grand »)
const APPROACH_MARGIN_M := 0.1       # à l'échelle 1, comme les autres longueurs de la mise en page
const APPROACH_NAME_M := 0.16
const APPROACH_MIN_W := 1.4
const APPROACH_MAX_W := 2.2
const APPROACH_BOTTOM_M := 1.0       # bas de la plaque au-dessus du sol (déjà à l'échelle)
const INK_DARK := Color(0.08, 0.08, 0.09)
const SIGN_WHITE := Color(0.95, 0.95, 0.93)
## Couleur de la pente moyenne, comme les pistes : vert, bleu, rouge, noir (bornes hautes, %)
const SLOPE_COLORS := [[3, Color(0.10, 0.55, 0.25)], [6, Color(0.10, 0.36, 0.75)], [9, Color(0.80, 0.12, 0.10)],
	[1000, Color(0.08, 0.08, 0.09)]]
const LAYER_DEPTH_M := 0.006
const BOLD_EMBOLDEN := 0.7

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
	_mats["approach_board"] = _material(KIND_BOARD, SIGN_WHITE)
	(_mats["approach_board"] as ShaderMaterial).set_shader_parameter("border_color", INK_DARK)


static func _material(kind: int, color: Color) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = PropShader
	m.set_shader_parameter("kind", kind)
	m.set_shader_parameter("base_color", color)
	return m


## Faux relief des panneaux et bornes selon le préréglage (coupé en low).
func set_preset(preset_name: String) -> void:
	_relief = float(RELIEF.get(preset_name, 1.0))
	for m in _mats.values():
		(m as ShaderMaterial).set_shader_parameter("relief", _relief)


var _relief := 1.0


## Matière d'une couche peinte (fond coloré, bandeau, pictogramme), partagée par couleur et pictogramme.
func _layer_mat(color: Color, picto: int) -> ShaderMaterial:
	var key := "layer_%s_%d" % [color.to_html(false), picto]
	if not _mats.has(key):
		var m := _material(KIND_LAYER, color)
		m.set_shader_parameter("picto", picto)
		m.set_shader_parameter("ink_color", INK_DARK)
		m.set_shader_parameter("relief", _relief)
		_mats[key] = m
	return _mats[key]


## Couleur de la pente moyenne `pct` (SLOPE_COLORS).
static func slope_color(pct: int) -> Color:
	for sc in SLOPE_COLORS:
		if pct < int(sc[0]):
			return sc[1]
	return SLOPE_COLORS[SLOPE_COLORS.size() - 1][1]


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


static var _bold_font: FontVariation


static func _bold() -> FontVariation:
	if _bold_font == null:
		_bold_font = FontVariation.new()
		_bold_font.base_font = ThemeDB.fallback_font
		_bold_font.variation_embolden = BOLD_EMBOLDEN
	return _bold_font


static func _label(text: String, ink: Color, letter_m: float, pos: Vector3, bold: bool = false) -> Label3D:
	var label := Label3D.new()
	if bold:
		label.font = _bold()
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


## Largeur d'un texte d'une ligne en lettres de `letter` m (police par défaut, gras un peu plus large).
static func _text_w(text: String, letter: float, bold: bool) -> float:
	return text.length() * letter * (CHAR_WIDTH + (0.05 if bold else 0.0))


## Lettre la plus grande (≤ `letter`, ≥ LETTER_HEIGHT_M) pour que `text` tienne dans `width`.
static func _fit(text: String, letter: float, width: float, bold: bool) -> float:
	return maxf(LETTER_HEIGHT_M, minf(letter, width / maxf(_text_w(text, 1.0, bold), 0.01)))


## Mise en page d'un panneau d'approche `{name, km, pct, alt_m}` : plaque de col verticale à la française, avec le
## nom du sommet, l'altitude du panneau, le pictogramme cycliste et la distance au sommet en grand, puis la pente
## moyenne en blanc sur un pavé de sa couleur (SLOPE_COLORS). Dessinée en mètres à l'échelle 1, puis agrandie de
## APPROACH_SCALE (choix du 07/11). Coordonnées de la face, origine au centre de la plaque, y vers le haut.
## Rend {w, h, bottom_m, layers: [{x, y, w, h, color, picto}], texts: [{text, x, y, letter, ink, bold}]} ;
## texts[0] est la distance au sommet, la ligne que mesurent les contrôles de lisibilité.
static func approach_layout(item: Dictionary) -> Dictionary:
	var name := str(item.get("name", "Sommet"))
	var km_txt := "%d km" % int(item.get("km", 0))
	var pct := int(item.get("pct", 0))
	var m := APPROACH_MARGIN_M
	var w := clampf(_text_w(name, APPROACH_NAME_M, true) + 2.0 * m, APPROACH_MIN_W, APPROACH_MAX_W)
	var inner := w - 2.0 * m
	var name_l := _fit(name, APPROACH_NAME_M, inner, true)
	# Rangées de haut en bas : nom, altitude, filet, pictogramme et distance, espace, pavé de la pente
	var rows: Array[float] = [name_l * 1.35, 0.13, 0.03, 0.62, 0.06, 0.6]
	var h := 2.0 * m
	for r in rows:
		h += r
	var y := h * 0.5 - m
	var pic := rows[3] - 0.04
	var tx := -inner * 0.5 + pic + (inner - pic) * 0.5
	var y_mid := y - rows[0] - rows[1] - rows[2]
	var y_box := y_mid - rows[3] - rows[4]
	var color := slope_color(pct)
	var layers := [
		{"x": 0.0, "y": y_mid + rows[2] * 0.5, "w": inner, "h": 0.02, "color": INK_DARK, "picto": PICTO_NONE},
		{"x": -inner * 0.5 + pic * 0.5, "y": y_mid - rows[3] * 0.5, "w": pic, "h": pic, "color": SIGN_WHITE, "picto": PICTO_CYCLIST},
		{"x": 0.0, "y": y_box - rows[5] * 0.5, "w": inner, "h": rows[5], "color": color, "picto": PICTO_NONE},
	]
	var texts := [
		{"text": km_txt, "x": tx, "y": y_mid - 0.38, "letter": _fit(km_txt, 0.3, inner - pic, true), "ink": INK_DARK, "bold": true},
		{"text": name, "x": 0.0, "y": y - rows[0] * 0.5, "letter": name_l, "ink": INK_DARK, "bold": true},
		{"text": "Altitude %s m" % RoadsideModel.format_int(int(item.get("alt_m", 0))), "x": 0.0, "y": y - rows[0] - rows[1] * 0.5,
			"letter": 0.1, "ink": INK_DARK, "bold": false},
		{"text": "SOMMET", "x": tx, "y": y_mid - 0.1, "letter": 0.1, "ink": INK_DARK, "bold": true},
		{"text": "%d %%" % pct, "x": 0.0, "y": y_box - 0.25, "letter": 0.32, "ink": SIGN_WHITE, "bold": true},
		{"text": "pente moyenne", "x": 0.0, "y": y_box - 0.5, "letter": 0.1, "ink": SIGN_WHITE, "bold": false},
	]
	var k := APPROACH_SCALE
	for ly in layers:
		for key in ["x", "y", "w", "h"]:
			ly[key] = float(ly[key]) * k
	for t in texts:
		for key in ["x", "y", "letter"]:
			t[key] = float(t[key]) * k
	return {"w": ceilf(w * k * 20.0) / 20.0, "h": ceilf(h * k * 20.0) / 20.0, "bottom_m": APPROACH_BOTTOM_M,
		"layers": layers, "texts": texts}


## Plaque peinte mince (couche d'un panneau d'approche) `w` × `h`, face vers +z.
static func layer_mesh(w: float, h: float) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	_extrude(st, _rounded_rect(w, h, minf(0.03, minf(w, h) * 0.3)), LAYER_DEPTH_M, Vector3.ZERO)
	return _commit(st, Vector2(w, h))


## Panneau d'approche : plaque blanche cadrée, couches peintes et textes de approach_layout().
func _build_approach(root: Node3D, item: Dictionary) -> Label3D:
	var lay := approach_layout(item)
	var w: float = lay["w"]
	var h: float = lay["h"]
	var bottom: float = lay["bottom_m"]
	var top := bottom + h
	var xs := [-w * 0.3, w * 0.3] if w >= TWO_POSTS_FROM_M else [0.0]
	var post_h := top - 0.04
	_mesh(root, _shared("posts_%d_%d_%d" % [xs.size(), roundi(w * 100.0), roundi(post_h * 100.0)],
		posts_mesh.bind(xs, post_h, bottom)), _mats["post"], Vector3(0.0, post_h * 0.5, 0.0))
	var board_y := bottom + h * 0.5
	_mesh(root, _shared("board_%d_%d" % [roundi(w * 100.0), roundi(h * 100.0)], board_mesh.bind(w, h)),
		_mats["approach_board"], Vector3(0.0, board_y, 0.0))
	var zf := BOARD_DEPTH_M * 0.5
	for ly in lay["layers"]:
		var lw: float = ly["w"]
		var lh: float = ly["h"]
		_mesh(root, _shared("layer_%d_%d" % [roundi(lw * 100.0), roundi(lh * 100.0)], layer_mesh.bind(lw, lh)),
			_layer_mat(ly["color"], ly["picto"]), Vector3(ly["x"], board_y + float(ly["y"]), zf + LAYER_DEPTH_M * 0.5))
	var main: Label3D
	for t in lay["texts"]:
		var lb := _label(t["text"], t["ink"], t["letter"], Vector3(t["x"], board_y + float(t["y"]), zf + LAYER_DEPTH_M + 0.004), t["bold"])
		root.add_child(lb)
		if main == null:
			main = lb
	return main


## Nœud d'un objet `{kind, s, lines}`, à placer par add_chunk.
func build_prop(item: Dictionary) -> Node3D:
	var kind: String = item["kind"]
	var lines: Array = item["lines"]
	var root := Node3D.new()
	root.name = "%s_%d%s" % [kind, int(item["s"]), "_rebours" if int(item.get("side", 1)) < 0 else ""]
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
		# Les deux faces (demi-tour, lot N17) : la face arrière est la face avant tournée d'un demi-tour
		for back in [false, true]:
			var turn := Basis(Vector3.UP, PI) if back else Basis()
			var num := _label(number, KM_INK, letter, turn * Vector3(0.0, KM_PLINTH_H + KM_BODY_H * 0.55, zf))
			num.basis = turn
			root.add_child(num)
			if not back:
				label = num
			if parts.size() > 1:
				var head := _label(" ".join(parts.slice(0, parts.size() - 1)), KM_HEAD_INK, 0.075,
					turn * Vector3(0.0, KM_PLINTH_H + KM_BODY_H + KM_W * 0.2, zf))
				head.basis = turn
				root.add_child(head)
	elif kind == "approach":
		label = _build_approach(root, item)
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
		var side := -1 if int(it.get("side", 1)) < 0 else 1
		var pos := RoadsideModel.prop_position(route, s, road_width_m, side)
		var h := deg_to_rad(route.sample_heading_deg(s))
		var fwd := Vector3(sin(h), 0.0, -cos(h))
		# +z local (face du panneau) vers le cycliste qui arrive : vers -fwd à droite, vers +fwd à gauche (rebours)
		var face := -fwd * float(side)
		prop.transform = Transform3D(Basis(Vector3.UP, atan2(face.x, face.z)), pos)
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
