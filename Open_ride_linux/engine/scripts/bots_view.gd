extends Node3D

## Bots sur la route (Lot O7) : coureur casqué et vélo de people_mesh.gd (lot Y14, comme les cyclistes du
## décor), pédalier animé par crowd.gdshader, maillot à la couleur du bot (bots_view_model.gd) ; fantôme translucide
## (bot_ghost.gdshader), posée à `s` avec le cap de route_data.gd et décalée vers la droite de son `lane_m`
## (écart à l'axe donné par le core, lot AS2 : placement dans la roue et dépassements ; sans lui, BOT_LATERAL_M
## de road_builder.gd, lot P32) ; nom au-dessus à moins de
## NAME_M. Une silhouette par bot visible (moins de 300 m), maillages et matériaux partagés ;
## sans bot, aucun nœud. Ne décide rien : affiche la sortie de bots_view_model.view().
## Pas de class_name : charger par preload("res://scripts/bots_view.gd").

const BotsViewModel := preload("res://scripts/bots_view_model.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")
const PeopleMesh := preload("res://scripts/people_mesh.gd")
const CrowdShader := preload("res://shaders/crowd.gdshader")
const GhostShader := preload("res://shaders/bot_ghost.gdshader")

const NAME_HEIGHT_M := 2.1
const GHOST_ALPHA := 0.55

var _nodes := {}        # id:kind → Node3D
var _poses := {}        # id:kind → {phase, color} (tests : le rendu factice ne relit pas les MultiMesh)
var _rider_mesh: ArrayMesh
var _bike_mesh: ArrayMesh
var _solid: ShaderMaterial
var _ghost: ShaderMaterial


func _init() -> void:
	name = "BotsView"
	_rider_mesh = PeopleMesh.build_person(false, true)
	_bike_mesh = PeopleMesh.build_bike()
	_solid = ShaderMaterial.new()
	_solid.shader = CrowdShader
	PeopleMesh.apply_palettes(_solid)
	_ghost = ShaderMaterial.new()
	_ghost.shader = GhostShader
	PeopleMesh.apply_palettes(_ghost)
	_ghost.set_shader_parameter("ghost_alpha", GHOST_ALPHA)


## Coureur et vélo d'un bot : un MultiMesh d'une instance chacun, pour passer au shader la couleur du maillot
## (couleur d'instance) et l'animation (INSTANCE_CUSTOM : pédalier, 7 coureur, 8 vélo, tenue).
func _make_node(kind: String, index: int) -> Node3D:
	var root := Node3D.new()
	var outfit := PeopleMesh.outfit(index % 4, (index * 3 + 1) % 6, PeopleMesh.RIDER_OUTFIT_TROUSERS, PeopleMesh.STYLE_STRIPE)
	for part in ["Rider", "Bike"]:
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.use_custom_data = true
		mm.mesh = _rider_mesh if part == "Rider" else _bike_mesh
		mm.instance_count = 1
		mm.set_instance_transform(0, Transform3D.IDENTITY)
		var mmi := MultiMeshInstance3D.new()
		mmi.name = part
		mmi.multimesh = mm
		mmi.rotation.y = PI       # maillages face à +z, bot face à −Z (sens de la route)
		mmi.material_override = _ghost if kind == "ghost" else _solid
		if kind == "ghost":
			mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(mmi)
	root.set_meta("outfit", outfit)
	var label := Label3D.new()
	label.name = "Name"
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.position = Vector3(0.0, NAME_HEIGHT_M, 0.0)
	label.font_size = 48
	label.pixel_size = 0.006
	label.outline_size = 10
	label.modulate = BotsViewModel.color_of(kind).lightened(0.3)
	root.add_child(label)
	add_child(root)
	return root


## Maillot (couleur du bot) et pédalier : la phase suit la distance parcourue `s` (un tour par DEVELOPMENT_M),
## donc les jambes tournent avec la vitesse du bot et s'arrêtent avec lui.
func _pose(key: String, color: Color, s: float) -> void:
	var node: Node3D = _nodes[key]
	var phase := fposmod(s / RoadCyclistsModel.DEVELOPMENT_M, 1.0)
	var outfit: float = node.get_meta("outfit")
	for part in ["Rider", "Bike"]:
		var mm: MultiMesh = (node.get_node(part) as MultiMeshInstance3D).multimesh
		mm.set_instance_color(0, color if part == "Rider" else color.darkened(0.3))
		mm.set_instance_custom_data(0, Color(phase, 0.0, 7.0 if part == "Rider" else 8.0, outfit))
	_poses[key] = {"phase": phase, "color": color}


## Pédalier (phase de 0 à 1) et maillot du bot `id` affiché ; {} s'il ne l'est pas.
func pose_of(id: String) -> Dictionary:
	for key in _poses:
		if str(key).get_slice(":", 0) == id:
			return _poses[key]
	return {}


## `view` : sortie de bots_view_model.view() ; `route` : route_data.gd (hauteur affichée, relief exagéré comme la
## caméra).
func update_view(view: Array, route) -> void:
	var seen := {}
	for b in view:
		var id: String = b["id"]
		if not b["visible"] or route == null:
			continue
		seen[id] = true
		var key := id + ":" + str(b["kind"])
		if not _nodes.has(key):
			_nodes[key] = _make_node(str(b["kind"]), _nodes.size())
		var node: Node3D = _nodes[key]
		_pose(key, b.get("color", BotsViewModel.color_of(str(b["kind"]))), float(b["s"]))
		var smp: Dictionary = route.sample(route.wrap_s(float(b["s"])))
		var pos := Vector3(smp["x"], smp["y"], smp["z"])
		var h := deg_to_rad(float(smp["heading_deg"]))
		var right := Vector3(cos(h), 0.0, sin(h))
		var before: float = route.wrap_s(float(b["s"])) - float(b["s"])   # grille de départ derrière le départ (lot AS2)
		if before > 0.0:
			pos -= Vector3(sin(h), 0.0, -cos(h)) * before
		var lane := float(b.get("lane_m", RoadBuilder.BOT_LATERAL_M))
		node.position = pos + right * lane
		node.set_meta("lane_m", lane)
		node.rotation = Vector3(0.0, -h, 0.0)
		var label: Label3D = node.get_node("Name")
		label.text = str(b["name"])
		label.visible = bool(b["show_name"])
		node.visible = true
	for key in _nodes.keys():
		if not seen.has(str(key).get_slice(":", 0)):
			remove_child(_nodes[key])
			_nodes[key].queue_free()
			_nodes.erase(key)
			_poses.erase(key)


## Position dans le monde de la silhouette du bot `id` (jauge d'abri, draft_gauge.gd) ; null s'il n'est pas affiché.
func anchor_of(id: String) -> Variant:
	for key in _nodes:
		if str(key).get_slice(":", 0) == id and _nodes[key].visible:
			return _nodes[key].global_position
	return null


## Pour les tests graphiques : silhouettes affichées, celles dans le champ de la caméra et leur écart à l'axe (lot AS2).
func test_info(camera: Camera3D) -> Dictionary:
	var shown := 0
	var in_view := 0
	var lanes := {}
	for key in _nodes:
		var n: Node3D = _nodes[key]
		if n.visible:
			shown += 1
			lanes[str(key).get_slice(":", 0)] = float(n.get_meta("lane_m", RoadBuilder.BOT_LATERAL_M))
			if camera != null and _on_screen(camera, n.global_position + Vector3(0.0, 1.0, 0.0)):
				in_view += 1
	return {"shown": shown, "in_view": in_view, "lanes": lanes}


## Devant la caméra et dans l'image (comme les panneaux de col de living_decor.gd).
static func _on_screen(camera: Camera3D, point: Vector3) -> bool:
	if camera.is_position_behind(point):
		return false
	return camera.get_viewport().get_visible_rect().has_point(camera.unproject_position(point))
