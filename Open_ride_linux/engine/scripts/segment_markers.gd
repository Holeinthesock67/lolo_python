extends Node3D

## Lignes, portiques, panneaux des segments et arches de bonus dans la scène (lot T8, série T), construits
## par code d'après segment_markers_model.gd. Pas de class_name : charger par
## preload("res://scripts/segment_markers.gd"). Créé par main.gd.
##
## - `set_route(route, arch_every_m, road_width_m)` : marques du parcours (couche `segments` de la route,
##   arches tous les `arch_every_m`) ; route sans couche : seulement les arches.
## - `update(cam_s, arches_on)` une fois par image : ne garde en scène que les marques entre BEHIND_M
##   derrière et AHEAD_M devant la caméra (quelques nœuds, aucun quand rien n'est proche). `arches_on`
##   faux (ERG, option « Bonus » coupée, hors séance : la trame `state` n'a pas de champ `powerup`) :
##   aucune arche.
## Portique : deux poteaux et une banderole au-dessus de la route, verte pour un sprint, blanche à pois
## rouges pour une montée ; ligne peinte au sol (blanche au départ, en damier à l'arrivée). Panneaux à
## gauche de la route, face au cycliste qui arrive. Arche de bonus : violette, lumineuse.

const Model := preload("res://scripts/segment_markers_model.gd")

const GANTRY_HEIGHT_M := 4.6
const BANNER_HEIGHT_M := 0.9
const POST_SIDE_M := 0.25
const POST_OUT_M := 0.6              # poteaux à 0,6 m du bord de la chaussée
const LINE_DEPTH_M := 0.5
const LINE_LIFT_M := 0.03            # au-dessus de la chaussée, contre le scintillement
const PANEL_SIZE := Vector3(1.4, 0.8, 0.05)
const PANEL_HEIGHT_M := 1.9
const PANEL_OUT_M := 1.5
const LETTER_HEIGHT_M := 0.14
const COLORS := {
	"sprint": Color(0.10, 0.55, 0.22),
	"arch": Color(0.55, 0.20, 0.85),
	"post": Color(0.85, 0.85, 0.87),
	"panel": Color(0.96, 0.96, 0.94),
	"line": Color(0.97, 0.97, 0.97),
}

var road_width_m := 6.0
var marks: Array = []
var _starts := PackedFloat64Array()
var _route = null
var _nodes: Dictionary = {}         # indice de la marque -> Node3D
var _box: ArrayMesh = null
var _mats: Dictionary = {}


func _init() -> void:
	var b := BoxMesh.new()
	b.size = Vector3.ONE
	_box = ArrayMesh.new()
	_box.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, b.get_mesh_arrays())
	for key in COLORS:
		var m := StandardMaterial3D.new()
		m.albedo_color = COLORS[key]
		_mats[key] = m
	_mats["arch"].emission_enabled = true
	_mats["arch"].emission = COLORS["arch"]
	_mats["arch"].emission_energy_multiplier = 0.8
	_mats["climb"] = _textured(_polka_image(), Vector3(8.0, 1.0, 1.0))      # pois répétés le long de la banderole
	_mats["finish_line"] = _textured(_checker_image(), Vector3(1.0, 1.0, 1.0))


static func _polka_image() -> Image:
	var img := Image.create(64, 64, false, Image.FORMAT_RGB8)
	img.fill(Color(0.97, 0.97, 0.97))
	var red := Color(0.80, 0.08, 0.08)
	for c in [Vector2(16, 16), Vector2(48, 48)]:
		for y in range(64):
			for x in range(64):
				if Vector2(x, y).distance_to(c) <= 8.0:
					img.set_pixel(x, y, red)
	return img


static func _checker_image() -> Image:
	var img := Image.create(64, 16, false, Image.FORMAT_RGB8)
	for y in range(16):
		for x in range(64):
			var dark := ((x >> 3) + (y >> 3)) % 2 == 0
			img.set_pixel(x, y, Color(0.08, 0.08, 0.08) if dark else Color(0.97, 0.97, 0.97))
	return img


func _textured(img: Image, uv_scale: Vector3) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	img.generate_mipmaps()
	m.albedo_texture = ImageTexture.create_from_image(img)
	# filtre linéaire anisotrope : damier et pois sans scintillement vus en rasant
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	m.uv1_scale = uv_scale
	return m


func set_route(route, arch_every_m: float = Model.DEFAULT_ARCH_EVERY_M, p_road_width_m: float = 6.0) -> void:
	clear()
	_route = route
	road_width_m = p_road_width_m
	marks = []
	if route != null:
		var segs = route.get("segments")
		if typeof(segs) != TYPE_ARRAY:
			segs = []
		marks = Model.items(route, segs, arch_every_m)
	_starts = Model.starts(marks)


func clear() -> void:
	for i in _nodes:
		(_nodes[i] as Node3D).queue_free()
	_nodes.clear()


func update(cam_s: float, arches_on: bool) -> void:
	if _route == null or marks.is_empty():
		return
	var want := {}
	for i in Model.window(_starts, cam_s, float(_route.length_m), _route.is_loop()):
		if marks[i]["kind"] == "arch" and not arches_on:
			continue
		want[i] = true
	for i in _nodes.keys():
		if not want.has(i):
			(_nodes[i] as Node3D).queue_free()
			_nodes.erase(i)
	for i in want:
		if not _nodes.has(i):
			var node := build_mark(marks[i])
			_place(node, marks[i])
			add_child(node)
			_nodes[i] = node


## Marques en scène (tests).
func shown() -> Array:
	var out: Array = []
	for i in _nodes:
		out.append(marks[i])
	return out


## Nœuds actifs (budget du lot : moins de 50).
func active_node_count() -> int:
	var n := 0
	for i in _nodes:
		n += 1 + (_nodes[i] as Node3D).get_child_count()
	return n


func _mesh(parent: Node3D, mat_key: String, pos: Vector3, size: Vector3) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = _box
	mi.material_override = _mats[mat_key]
	mi.position = pos
	mi.scale = size
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mi)
	return mi


func _label(parent: Node3D, lines: Array, pos: Vector3, width_m: float, height_m: float, ink: Color) -> Label3D:
	var label := Label3D.new()
	label.text = "\n".join(lines)
	label.modulate = ink
	label.outline_size = 6
	label.outline_modulate = Color(0, 0, 0, 0.8)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.font_size = 48
	var longest := 1
	for l in lines:
		longest = maxi(longest, str(l).length())
	var by_width := width_m * 0.92 / (longest * 0.55 * label.font_size)
	var by_height := height_m * 0.85 / (lines.size() * 1.2 * label.font_size)
	label.pixel_size = maxf(LETTER_HEIGHT_M / label.font_size, minf(by_width, by_height))
	label.position = pos
	parent.add_child(label)
	return label


## Nœud d'une marque `{kind, type, lines}` (repère local : x vers la droite, -z vers l'avant du parcours).
func build_mark(mark: Dictionary) -> Node3D:
	var root := Node3D.new()
	var kind: String = mark["kind"]
	root.name = "%s_%d" % [kind, int(mark["s"])]
	var half := road_width_m * 0.5
	if kind == "panel":
		_mesh(root, "post", Vector3(0.0, PANEL_HEIGHT_M * 0.5, 0.0), Vector3(0.08, PANEL_HEIGHT_M, 0.08))
		var board_y := PANEL_HEIGHT_M + PANEL_SIZE.y * 0.5
		_mesh(root, "panel", Vector3(0.0, board_y, 0.0), PANEL_SIZE)
		var text := _label(root, mark["lines"], Vector3(0.0, board_y, PANEL_SIZE.z * 0.5 + 0.005), PANEL_SIZE.x,
			PANEL_SIZE.y, Color(0.1, 0.1, 0.1))
		text.outline_size = 0
		return root
	var x_post := half + POST_OUT_M
	var colour := "arch" if kind == "arch" else str(mark["type"])
	for side in [-1.0, 1.0]:
		_mesh(root, "post" if kind != "arch" else "arch", Vector3(side * x_post, GANTRY_HEIGHT_M * 0.5, 0.0),
			Vector3(POST_SIDE_M, GANTRY_HEIGHT_M, POST_SIDE_M))
	var banner_y := GANTRY_HEIGHT_M - BANNER_HEIGHT_M * 0.5
	var width := 2.0 * x_post + POST_SIDE_M
	_mesh(root, colour, Vector3(0.0, banner_y, 0.0), Vector3(width, BANNER_HEIGHT_M, 0.12))
	_label(root, [" · ".join(mark["lines"])], Vector3(0.0, banner_y, 0.065), width * 0.8, BANNER_HEIGHT_M,
		Color(1, 1, 1))
	if kind != "arch":
		_mesh(root, "finish_line" if kind == "finish" else "line", Vector3(0.0, LINE_LIFT_M, 0.0),
			Vector3(road_width_m, 0.02, LINE_DEPTH_M))
	return root


func _place(node: Node3D, mark: Dictionary) -> void:
	var s := float(mark["s"])
	var smp: Dictionary = _route.sample(s)
	var h := deg_to_rad(float(smp["heading_deg"]))
	var right := Vector3(cos(h), 0.0, sin(h))
	var fwd := Vector3(sin(h), 0.0, -cos(h))
	var pos := Vector3(smp["x"], smp["y"], smp["z"])
	if int(mark["side"]) != 0:
		pos += right * float(mark["side"]) * (road_width_m * 0.5 + PANEL_OUT_M)
	# +z local (face des panneaux et banderoles) vers le cycliste qui arrive, donc vers -fwd
	node.transform = Transform3D(Basis(Vector3.UP, atan2(-fwd.x, -fwd.z)), pos)
