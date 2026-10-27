extends Node3D

## Panneaux et bornes du bord de route (Lot P14), construits par code, texte en Label3D (police par
## défaut de Godot). Pas de class_name : charger par preload("res://scripts/roadside_props.gd").
##
## `add_chunk(route, k, items)` pose les objets du tronçon k (roadside_model.for_chunk) sur le côté
## droit, à 1,5 m du bord de la chaussée, face au cycliste qui arrive ; `remove_chunk(k)` les retire.
## Panneau de col (marron, 2 lignes), panneaux d'approche (blancs), bornes (blanches à tête rouge).
## Texte dimensionné pour être lisible à READABLE_AT_M : lettres de LETTER_HEIGHT_M au moins.

const RoadsideModel := preload("res://scripts/roadside_model.gd")

const READABLE_AT_M := 30.0
const LETTER_HEIGHT_M := 0.12        # ~ 14 minutes d'arc à 30 m
const BOARD := {
	"summit": {"size": Vector3(1.6, 0.9, 0.05), "height": 2.0, "color": Color(0.42, 0.25, 0.12), "ink": Color(1, 1, 1)},
	"approach": {"size": Vector3(1.3, 0.7, 0.05), "height": 1.8, "color": Color(0.95, 0.95, 0.93), "ink": Color(0.1, 0.1, 0.1)},
	"km": {"size": Vector3(0.45, 0.7, 0.25), "height": 0.0, "color": Color(0.95, 0.95, 0.93), "ink": Color(0.1, 0.1, 0.1)},
}

var road_width_m := 6.0
var _chunks: Dictionary = {}        # k -> Array[Node3D]
var _meshes: Dictionary = {}        # gardés ici : maillages partagés
var _mats: Dictionary = {}


func _init() -> void:
	for kind in BOARD:
		var b := BoxMesh.new()
		b.size = BOARD[kind]["size"]
		var am := ArrayMesh.new()
		am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, b.get_mesh_arrays())
		_meshes[kind] = am
		var m := StandardMaterial3D.new()
		m.albedo_color = BOARD[kind]["color"]
		_mats[kind] = m
	var post := CylinderMesh.new()
	post.top_radius = 0.04
	post.bottom_radius = 0.04
	post.height = 1.0
	post.radial_segments = 6
	post.rings = 1
	var pam := ArrayMesh.new()
	pam.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, post.get_mesh_arrays())
	_meshes["post"] = pam
	var cap := BoxMesh.new()
	cap.size = Vector3(0.47, 0.18, 0.27)
	var cam := ArrayMesh.new()
	cam.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, cap.get_mesh_arrays())
	_meshes["cap"] = cam
	var grey := StandardMaterial3D.new()
	grey.albedo_color = Color(0.6, 0.6, 0.62)
	_mats["post"] = grey
	var red := StandardMaterial3D.new()
	red.albedo_color = Color(0.75, 0.1, 0.08)
	_mats["cap"] = red


func _mesh(parent: Node3D, key: String, pos: Vector3, scale: Vector3 = Vector3.ONE) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = _meshes[key]
	mi.material_override = _mats[key]
	mi.position = pos
	mi.scale = scale
	parent.add_child(mi)
	return mi


## Nœud d'un objet `{kind, s, lines}`, à placer par add_chunk.
func build_prop(item: Dictionary) -> Node3D:
	var kind: String = item["kind"]
	var spec: Dictionary = BOARD[kind]
	var size: Vector3 = spec["size"]
	var root := Node3D.new()
	root.name = "%s_%d" % [kind, int(item["s"])]
	var board_y: float
	if kind == "km":
		board_y = size.y * 0.5
		_mesh(root, "km", Vector3(0.0, board_y, 0.0))
		_mesh(root, "cap", Vector3(0.0, size.y + 0.09, 0.0))
	else:
		var h: float = spec["height"]
		_mesh(root, "post", Vector3(0.0, h * 0.5, 0.0), Vector3(1.0, h, 1.0))
		board_y = h + size.y * 0.5
		_mesh(root, kind, Vector3(0.0, board_y, 0.0))
	var lines: Array = item["lines"]
	var label := Label3D.new()
	label.text = "\n".join(lines)
	label.modulate = spec["ink"]
	label.outline_size = 0
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.font_size = 48
	# Hauteur d'une ligne = font_size × pixel_size ; au moins LETTER_HEIGHT_M, et le texte tient sur le panneau
	var longest := 1
	for l in lines:
		longest = maxi(longest, str(l).length())
	var by_width := size.x * 0.92 / (longest * 0.55 * label.font_size)
	var by_height := size.y * 0.85 / (lines.size() * 1.2 * label.font_size)
	label.pixel_size = maxf(LETTER_HEIGHT_M / label.font_size, minf(by_width, by_height))
	# Face du panneau vers le cycliste qui arrive : -z local vers l'arrière du parcours
	label.position = Vector3(0.0, board_y, size.z * 0.5 + 0.005)
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
