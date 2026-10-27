extends Node3D

## Silhouettes des bots sur la route (Lot O7) : forme stylisée et légère (cadre, deux roues, coureur),
## couleur par `kind` (bots_view_model.gd), posée à `s` avec le cap de route_data.gd et décalée de
## LATERAL_M vers la droite pour ne pas masquer la route devant la caméra ; nom au-dessus à moins de
## NAME_M. Une silhouette par bot visible (moins de 300 m), maillages et matériaux partagés ;
## sans bot, aucun nœud. Ne décide rien : affiche la sortie de bots_view_model.view().
## Pas de class_name : charger par preload("res://scripts/bots_view.gd").

const BotsViewModel := preload("res://scripts/bots_view_model.gd")

const LATERAL_M := 1.5
const NAME_HEIGHT_M := 2.1
const GHOST_ALPHA := 0.55

var _nodes := {}        # id → Node3D
var _materials := {}    # kind → StandardMaterial3D
var _wheel: CylinderMesh
var _frame: BoxMesh
var _rider: CapsuleMesh


func _init() -> void:
	name = "BotsView"
	_wheel = CylinderMesh.new()
	_wheel.top_radius = 0.34
	_wheel.bottom_radius = 0.34
	_wheel.height = 0.04
	_wheel.radial_segments = 16
	_wheel.rings = 1
	_frame = BoxMesh.new()
	_frame.size = Vector3(0.06, 0.08, 1.05)
	_rider = CapsuleMesh.new()
	_rider.radius = 0.22
	_rider.height = 1.15
	_rider.radial_segments = 8
	_rider.rings = 2


func _material(kind: String) -> StandardMaterial3D:
	if not _materials.has(kind):
		var m := StandardMaterial3D.new()
		var c: Color = BotsViewModel.color_of(kind)
		if kind == "ghost":
			c.a = GHOST_ALPHA
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.albedo_color = c
		_materials[kind] = m
	return _materials[kind]


func _make_node(kind: String) -> Node3D:
	var root := Node3D.new()
	var mat := _material(kind)
	for z in [-0.52, 0.52]:
		var w := MeshInstance3D.new()
		w.mesh = _wheel
		w.material_override = mat
		w.position = Vector3(0.0, 0.34, z)
		w.rotation.z = PI / 2.0   # axe des roues en travers de la route
		root.add_child(w)
	var f := MeshInstance3D.new()
	f.mesh = _frame
	f.material_override = mat
	f.position = Vector3(0.0, 0.62, 0.0)
	root.add_child(f)
	var r := MeshInstance3D.new()
	r.mesh = _rider
	r.material_override = mat
	r.position = Vector3(0.0, 1.15, 0.12)
	r.rotation.x = -0.75      # buste penché vers l'avant (−Z)
	root.add_child(r)
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


## `view` : sortie de bots_view_model.view() ; `route` : route_data.gd ; relief exagéré comme la
## caméra (`grade_scale`, `alt0` : altitude de référence du parcours).
func update_view(view: Array, route, grade_scale := 1.0, alt0 := 0.0) -> void:
	var seen := {}
	for b in view:
		var id: String = b["id"]
		if not b["visible"] or route == null:
			continue
		seen[id] = true
		var key := id + ":" + str(b["kind"])
		if not _nodes.has(key):
			_nodes[key] = _make_node(str(b["kind"]))
		var node: Node3D = _nodes[key]
		var smp: Dictionary = route.sample(route.wrap_s(float(b["s"])))
		var pos := Vector3(smp["x"], smp["y"], smp["z"])
		if grade_scale != 1.0:
			pos.y = alt0 + (pos.y - alt0) * grade_scale
		var h := deg_to_rad(float(smp["heading_deg"]))
		var right := Vector3(cos(h), 0.0, sin(h))
		node.position = pos + right * LATERAL_M
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


## Pour les tests graphiques : silhouettes affichées et celles dans le champ de la caméra.
func test_info(camera: Camera3D) -> Dictionary:
	var shown := 0
	var in_view := 0
	for key in _nodes:
		var n: Node3D = _nodes[key]
		if n.visible:
			shown += 1
			if camera != null and camera.is_position_in_frustum(n.global_position + Vector3(0.0, 1.0, 0.0)):
				in_view += 1
	return {"shown": shown, "in_view": in_view}
