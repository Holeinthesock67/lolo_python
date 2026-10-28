extends RefCounted

## Objets de la scène du Cyber-Rogue qui marquent les repères de la salle (lot R10 §4.2) : arches, cibles
## d'attaque, zones de parade, pavés, balises de purge, tunnels de cadence, rochers. Primitives Godot et
## matériaux de la charte (R17) ; aucun modèle ni texture. Pas de class_name :
## preload("res://scripts/rogue/marker_views.gd").

const Catalog := preload("res://scripts/rogue/neon_catalog.gd")
const Materials := preload("res://scripts/rogue/neon_materials.gd")
const SheetScript := preload("res://scripts/rogue/rogue_style_sheet.gd")

## Marqueur de l'IPC 1.4 -> objet du catalogue R17.
const CATALOG_OF := {
	"arch": "perfect_shift_arch",
	"strike_target": "attack_target",
	"parry_zone": "parry_zone",
	"pad": "boost_pad",
	"purge": "purge_beacon",
	"tunnel": "cadence_tunnel",
	"rock": "armor_rock",
	"shockwave": "firewall",
}
const RING_SPACING_M := 10.0
const MAX_RINGS := 30
const ACTIVE_SCALE := 1.18


static func catalog_id(kind: String) -> String:
	return CATALOG_OF.get(kind, "")


## Nœud du marqueur, centré en (0, 0, 0) : l'appelant le place. Le tunnel est une suite d'anneaux espacés de
## 10 m sur `len_m`, les autres un seul volume.
static func make(kind: String, len_m: float, preset: String = "low", adapted: bool = false) -> Node3D:
	var node := Node3D.new()
	node.name = "Marker_%s" % kind
	var id := catalog_id(kind)
	if id == "":
		return node
	var spec: Dictionary = Catalog.OBJECTS[id]
	if kind == "tunnel":
		var rings := clampi(int(len_m / RING_SPACING_M), 1, MAX_RINGS)
		for i in rings:
			var ring := MeshInstance3D.new()
			ring.mesh = SheetScript._mesh_for("ring")
			ring.rotation.x = PI * 0.5
			ring.position = Vector3(0.0, 1.5, -(float(i) + 0.5) * RING_SPACING_M + len_m * 0.5)
			ring.material_override = Materials.edge(spec["token"], 2.0, preset, adapted)
			node.add_child(ring)
		return node
	var body := MeshInstance3D.new()
	body.name = "Body"
	body.mesh = SheetScript._mesh_for(spec["shape"])
	match spec["shape"]:
		"slab":
			body.scale = Vector3(3.0, 1.0, maxf(len_m, 2.0) * 0.5)
			body.position.y = 0.05
		"wall":
			body.position.y = 1.0
			body.scale = Vector3(2.0, 1.2, 1.0)
		_:
			body.position.y = 1.2
	match spec["shape"]:
		"wall":
			body.material_override = Materials.wall(spec["token"], preset, adapted)
		_:
			body.material_override = Materials.edge(spec["token"], 2.0, preset, adapted)
	node.add_child(body)
	return node


## Fenêtre active (state.rogue.windows) : le marqueur grossit un peu.
static func set_active(node: Node3D, active: bool) -> void:
	node.scale = Vector3.ONE * (ACTIVE_SCALE if active else 1.0)
