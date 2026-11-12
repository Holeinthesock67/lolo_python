extends Node3D

## Décor néon sur les côtés du ruban du Cyber-Rogue (lot R22, point 10 : « monde trop vide », maquette F validée
## le 12 novembre) : pylônes lumineux le long des deux bords, blocs de données plus loin, anneaux d'hologrammes
## au-dessus. Procédural et déterministe (graine = numéro de salle), quatre MultiMesh seulement (une passe de
## dessin chacun), densité selon le préréglage pour tenir les budgets GPU 8 / 13 / 16 ms (low / medium / high).
## Deux usages : `build_room` le long du ruban d'une salle (suit son relief) ; `build_strip` une bande plate de
## STRIP_M mètres pour l'échauffement, les couloirs et le retour au calme, que `follow_strip` recale sous le joueur.
## Pas de class_name : preload("res://scripts/rogue/rogue_side_decor.gd").

const Materials := preload("res://scripts/rogue/neon_materials.gd")
const RibbonBuilder := preload("res://scripts/rogue/ribbon_builder.gd")

## Écart entre deux pylônes d'un même bord (m) selon le préréglage ; blocs et anneaux en découlent.
const SPACING_M := {"low": 26.0, "medium": 18.0, "high": 12.0}
const PYLON_X := RibbonBuilder.WIDTH_M * 0.5 + 2.5
const PYLON_H := 12.0             # de 8 m sous le ruban à 4 m au-dessus : le ruban flotte dans le vide
const BLOCK_X := Vector2(7.0, 14.0)
const RING_X := 9.0
const RING_UP := 6.0
const STRIP_M := 600.0
const MAX_INSTANCES := 900        # par MultiMesh : borne de sécurité pour une salle très longue
const PATTERN := 6                # période du motif en pylônes (alternance des couleurs et des anneaux)

var preset := "low"
var adapted := false
var pylons_a: MultiMeshInstance3D
var pylons_b: MultiMeshInstance3D
var blocks: MultiMeshInstance3D
var rings: MultiMeshInstance3D
var _strip_period := 0.0


func _ready() -> void:
	pylons_a = _mmi("PylonsA", _box(Vector3(0.18, PYLON_H, 0.18)))
	pylons_b = _mmi("PylonsB", _box(Vector3(0.18, PYLON_H, 0.18)))
	blocks = _mmi("Blocks", _box(Vector3(1.0, 1.0, 1.0)))
	var t := TorusMesh.new()
	t.inner_radius = 0.9
	t.outer_radius = 1.0
	t.rings = 20
	t.ring_segments = 4
	rings = _mmi("Rings", t)
	set_style(preset, adapted)


func _mmi(n: String, mesh: Mesh) -> MultiMeshInstance3D:
	var m := MultiMeshInstance3D.new()
	m.name = n
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	m.multimesh = mm
	m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(m)
	return m


static func _box(size: Vector3) -> BoxMesh:
	var b := BoxMesh.new()
	b.size = size
	return b


func set_style(new_preset: String, new_adapted: bool) -> void:
	preset = new_preset
	adapted = new_adapted
	if pylons_a == null:
		return
	pylons_a.material_override = Materials.edge("player", 2.0, preset, adapted)
	pylons_b.material_override = Materials.edge("glitch", 2.0, preset, adapted)
	blocks.material_override = Materials.edge("parry", 1.5, preset, adapted)
	rings.material_override = Materials.edge("gold", 2.0, preset, adapted)


static func spacing(p: String) -> float:
	return float(SPACING_M.get(p, SPACING_M["low"]))


## Positions du décor sur [0, length] (m) ; `y_of` : altitude du ruban à une distance (Callable), graine fixe.
## Renvoie {pylons_a, pylons_b, blocks, rings} : listes de Transform3D. Fonction pure (testée sans scène).
## `periodic` : le motif se répète tous les PATTERN pylônes (bande hors salle, recalée sans saut visible).
static func layout(length_m: float, p: String, seed_value: int, y_of: Callable, periodic: bool = false) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	var step := spacing(p)
	var out := {"pylons_a": [], "pylons_b": [], "blocks": [], "rings": []}
	var i := 0
	var s := step * 0.5
	while s < length_m and i < MAX_INSTANCES:
		var y: float = y_of.call(s)
		rng.seed = hash([seed_value, i % PATTERN if periodic else i])
		for side in [-1.0, 1.0]:
			var key := "pylons_a" if (i + (1 if side > 0 else 0)) % 2 == 0 else "pylons_b"
			out[key].append(Transform3D(Basis(), Vector3(side * PYLON_X, y + 4.0 - PYLON_H * 0.5, -s)))
			if rng.randf() < 0.6:
				var sz := Vector3(rng.randf_range(0.8, 2.2), rng.randf_range(1.2, 3.5), rng.randf_range(0.8, 2.2))
				var x: float = side * rng.randf_range(BLOCK_X.x, BLOCK_X.y)
				var b := Basis().scaled(sz)
				out["blocks"].append(Transform3D(b, Vector3(x, y - 1.0 + rng.randf_range(-3.0, 2.0) + sz.y * 0.5, -s - rng.randf_range(0.0, step))))
		if i % 3 == 1:
			var side2: float = -1.0 if (i / 3) % 2 == 0 else 1.0
			var rb := Basis().scaled(Vector3(2.2, 2.2, 2.2))
			out["rings"].append(Transform3D(rb, Vector3(side2 * RING_X, y + RING_UP, -s)))
		i += 1
		s += step
	return out


func _fill(mmi: MultiMeshInstance3D, xs: Array) -> void:
	var mm := mmi.multimesh
	mm.instance_count = 0
	mm.instance_count = mini(xs.size(), MAX_INSTANCES)
	for k in mm.instance_count:
		mm.set_instance_transform(k, xs[k])


func _apply(lay: Dictionary) -> void:
	_fill(pylons_a, lay["pylons_a"])
	_fill(pylons_b, lay["pylons_b"])
	_fill(blocks, lay["blocks"])
	_fill(rings, lay["rings"])


## Décor le long du ruban d'une salle (stations de RibbonBuilder) ; graine = numéro de salle.
func build_room(stations: Array, length_m: float, room_id: int) -> void:
	_strip_period = 0.0
	position = Vector3.ZERO
	_apply(layout(length_m, preset, room_id, func(s): return RibbonBuilder.y_at(stations, s)))


## Bande plate hors salle (échauffement, couloir, retour au calme), recalée par `follow_strip`.
func build_strip() -> void:
	_strip_period = spacing(preset) * PATTERN
	_apply(layout(STRIP_M, preset, 7, func(_s): return 0.0, true))


## Recale la bande sous le joueur à `s` (multiple de la période du motif : le décor ne saute pas).
func follow_strip(s: float) -> void:
	if _strip_period <= 0.0:
		return
	position = Vector3(0.0, 0.0, -floorf(maxf(s - 60.0, 0.0) / _strip_period) * _strip_period)


func instance_total() -> int:
	return pylons_a.multimesh.instance_count + pylons_b.multimesh.instance_count + blocks.multimesh.instance_count \
		+ rings.multimesh.instance_count
