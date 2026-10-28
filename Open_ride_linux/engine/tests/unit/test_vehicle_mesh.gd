extends SceneTree

## Tests sans écran des maillages de véhicules `vehicle_mesh.gd` (Lot P25) : chaque sorte construite, à la
## taille de traffic_model.gd (rétroviseurs compris), posée sur le sol, avant vers -z (phares devant, feux
## derrière), toutes ses zones de couleur, faces orientées comme leurs normales, roues à leur place, nombre
## de triangles, déterminisme et palettes.
## Lancement : godot --headless --path engine --script res://tests/unit/test_vehicle_mesh.gd

const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")
const TrafficModel := preload("res://scripts/traffic_model.gd")

const MAX_TRIANGLES := 2000
const WHEELS := {"car_a": 4, "car_b": 4, "van": 4, "truck": 6, "bus": 4, "moto": 2, "tractor": 4, "tractor_field": 4}

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	var sizes_ok := true
	var ground_ok := true
	var regions_ok := true
	var front_ok := true
	var faces_ok := true
	var tris_ok := true
	var report := []
	var t0 := Time.get_ticks_usec()
	for kind in VehicleMesh.KINDS:
		var mesh: ArrayMesh = VehicleMesh.build_full(kind)
		var arr := mesh.surface_get_arrays(0)
		var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var normals: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
		var custom: PackedFloat32Array = arr[Mesh.ARRAY_CUSTOM0]
		var aabb := mesh.get_aabb()
		var tris := verts.size() / 3
		report.append("%s %d" % [kind, tris])
		tris_ok = tris_ok and tris <= MAX_TRIANGLES
		if TrafficModel.KINDS.has(kind):
			var k: Dictionary = TrafficModel.KINDS[kind]
			sizes_ok = sizes_ok and absf(aabb.size.x * 0.5 - float(k["half_width"])) <= 0.05 \
				and aabb.size.z <= float(k["length"]) + 0.05 and aabb.size.z >= float(k["length"]) - 0.25
		ground_ok = ground_ok and absf(aabb.position.y) <= 0.01
		var seen := {}
		var head_z := 0.0
		var head_n := 0
		var tail_z := 0.0
		var tail_n := 0
		for i in range(verts.size()):
			var region := int(round(custom[i * 4]))
			seen[region] = true
			if region == VehicleMesh.VEH_HEAD:
				head_z += verts[i].z
				head_n += 1
			elif region == VehicleMesh.VEH_TAIL:
				tail_z += verts[i].z
				tail_n += 1
		for r in [VehicleMesh.VEH_PAINT, VehicleMesh.VEH_GLASS, VehicleMesh.VEH_DARK, VehicleMesh.VEH_METAL,
				VehicleMesh.VEH_HEAD, VehicleMesh.VEH_TAIL]:
			regions_ok = regions_ok and seen.has(r)
		front_ok = front_ok and head_n > 0 and tail_n > 0 and head_z / head_n < 0.0 and tail_z / tail_n > 0.0
		# Même sens que Builder.box : (b - a) × (c - a) opposé à la normale du triangle
		var bad := 0
		for t in range(0, verts.size(), 3):
			var fn := (verts[t + 1] - verts[t]).cross(verts[t + 2] - verts[t])
			if fn.length() < 1e-7:
				continue
			var n := normals[t] + normals[t + 1] + normals[t + 2]
			if fn.dot(n) > 0.0:
				bad += 1
		faces_ok = faces_ok and bad == 0
		if bad > 0:
			printerr("%s : %d triangles à l'envers" % [kind, bad])
	var build_ms := (Time.get_ticks_usec() - t0) / 1000.0
	_check(tris_ok, "au plus %d triangles par véhicule (%s)" % [MAX_TRIANGLES, ", ".join(report)])
	_check(sizes_ok, "taille hors tout de traffic_model.gd KINDS (largeur à 5 cm, longueur à 25 cm)")
	_check(ground_ok, "roues posées sur le sol (y = 0)")
	_check(regions_ok, "peinture, vitres, noir, métal, phares et feux arrière sur chaque véhicule")
	_check(front_ok, "phares devant (-z), feux derrière (+z)")
	_check(faces_ok, "faces orientées comme leurs normales")
	_check(build_ms < 400.0, "les %d maillages construits en %.0f ms" % [VehicleMesh.KINDS.size(), build_ms])

	# Roues à part (véhicules proches) : nombre, centre sur l'axe, rayon
	var wheels_ok := true
	for kind in VehicleMesh.KINDS:
		var list := VehicleMesh.wheel_list(kind)
		wheels_ok = wheels_ok and list.size() == WHEELS[kind]
		for i in range(list.size()):
			var a := VehicleMesh.build_wheel(kind, i).get_aabb()
			var r: float = list[i]["radius"]
			var pos: Vector3 = list[i]["pos"]
			wheels_ok = wheels_ok and a.get_center().length() < 0.03 and absf(a.size.y * 0.5 - r) < 0.03 \
				and absf(pos.y - r) < 1e-4
	_check(wheels_ok, "roues : nombre par sorte, centrées sur leur axe, rayon = hauteur de l'axe")
	var body := VehicleMesh.build_body("car_a").surface_get_arrays(0)[Mesh.ARRAY_VERTEX] as PackedVector3Array
	var full := VehicleMesh.build_full("car_a").surface_get_arrays(0)[Mesh.ARRAY_VERTEX] as PackedVector3Array
	_check(full.size() > body.size(), "caisse sans roues pour les véhicules proches")
	var again := VehicleMesh.build_full("truck").surface_get_arrays(0)[Mesh.ARRAY_VERTEX] as PackedVector3Array
	_check(again == (VehicleMesh.build_full("truck").surface_get_arrays(0)[Mesh.ARRAY_VERTEX] as PackedVector3Array),
		"même maillage à chaque construction")
	_check(VehicleMesh.paint("car_a", 0) == VehicleMesh.CAR_PAINT[0] and VehicleMesh.paint("car_a", 9) == VehicleMesh.CAR_PAINT[1]
		and VehicleMesh.paint("tractor", 1) == VehicleMesh.TRACTOR_PAINT[1] and VehicleMesh.paint("bus", 2) == VehicleMesh.BUS_PAINT[2]
		and VehicleMesh.paint("tractor_field", 0) == VehicleMesh.TRACTOR_PAINT[0],
		"palettes : voitures, tracteurs, autocars ; indice repris modulo la palette")
	print("test_vehicle_mesh : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
