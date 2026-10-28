extends SceneTree

## Tests unitaires sans écran des maillages de véhicules de `vehicle_mesh.gd` (lots P13 et P25, construits
## avec le Builder de people_mesh.gd) : taille conforme à KINDS, roues au sol qui tournent autour de leur
## axe, phares devant (-z) et feux derrière, zones de couleur lues par shaders/vehicle.gdshader.
## Lancement : godot --headless --path engine --script res://tests/unit/test_vehicle_mesh.gd

const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")

## Triangles au plus par véhicule : 8 véhicules sur la route et 24 au loin restent sous 100 000.
const MAX_TRIS := 3000

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
	var kinds: Array = VehicleMesh.KINDS.keys()
	kinds.append("far")
	for kind in kinds:
		var arrays := VehicleMesh.build(kind).surface_get_arrays(0)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var uv2s: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV2]
		var custom: PackedFloat32Array = arrays[Mesh.ARRAY_CUSTOM0]
		var tris := verts.size() / 3
		_check(tris >= (12 if kind == "far" else 300) and tris <= MAX_TRIS, "%s : %d triangles (au plus %d)" % [kind, tris, MAX_TRIS])
		var lo := Vector3(INF, INF, INF)
		var hi := -lo
		var regions := {}
		var head_z := []
		var tail_z := []
		var wheel_lo := INF
		var wheel_ok := true
		for i in range(verts.size()):
			var p := verts[i]
			lo = lo.min(p)
			hi = hi.max(p)
			var region := int(custom[i * 4] + 0.5)
			regions[region] = true
			if region == VehicleMesh.VEH_HEAD:
				head_z.append(p.z)
			elif region == VehicleMesh.VEH_TAIL:
				tail_z.append(p.z)
			if custom[i * 4 + 1] > 0.5:
				wheel_lo = minf(wheel_lo, p.y)
				# Axe (y, z) dans UV2 : rayon de la roue = hauteur de l'axe (roue posée au sol)
				var axle := uv2s[i]
				wheel_ok = wheel_ok and Vector2(p.y, p.z).distance_to(axle) <= axle.x * 1.15 + 0.01
		_check(regions.has(VehicleMesh.VEH_PAINT) and regions.has(VehicleMesh.VEH_HEAD) and regions.has(VehicleMesh.VEH_TAIL),
			"%s : peinture, phares et feux arrière (zones %s)" % [kind, str(regions.keys())])
		_check(head_z.max() < 0.0 and tail_z.min() > 0.0, "%s : phares vers l'avant (-z), feux vers l'arrière" % kind)
		if kind == "far":
			_check(absf(lo.y) < 0.01 and absf(hi.x - 0.5) < 0.02 and absf(hi.z - 0.51) < 0.02 and hi.y <= 1.01,
				"far : boîte d'un mètre posée au sol (%s, %s)" % [str(lo), str(hi)])
			continue
		var k: Dictionary = VehicleMesh.KINDS[kind]
		var length := hi.z - lo.z
		_check(absf(lo.y) < 0.02, "%s : posé au sol (y min %.3f)" % [kind, lo.y])
		_check(absf(length - float(k["length"])) <= 0.06 * float(k["length"]) + 0.12,
			"%s : longueur %.2f m (KINDS %.2f)" % [kind, length, float(k["length"])])
		_check(hi.x <= float(k["half_width"]) + 0.2 and -lo.x <= float(k["half_width"]) + 0.2 and hi.x >= float(k["half_width"]) * 0.8,
			"%s : demi-largeur %.2f m (KINDS %.2f, rétroviseurs compris)" % [kind, hi.x, float(k["half_width"])])
		_check(hi.y <= float(k["height"]) + 0.08 and hi.y >= float(k["height"]) - 0.15,
			"%s : hauteur %.2f m (KINDS %.2f)" % [kind, hi.y, float(k["height"])])
		_check(wheel_ok and absf(wheel_lo) < 0.02, "%s : roues posées au sol, autour de leur axe" % kind)
		_check(regions.has(VehicleMesh.VEH_GLASS) and regions.has(VehicleMesh.VEH_TYRE), "%s : vitres et pneus" % kind)
	var tractor := VehicleMesh.build("tractor").surface_get_arrays(0)
	var beacon := false
	for i in range(0, (tractor[Mesh.ARRAY_CUSTOM0] as PackedFloat32Array).size(), 4):
		beacon = beacon or int(tractor[Mesh.ARRAY_CUSTOM0][i] + 0.5) == VehicleMesh.VEH_BEACON
	_check(beacon, "tracteur : gyrophare")
	var bus := VehicleMesh.build("bus").surface_get_arrays(0)
	var accent := false
	for i in range(0, (bus[Mesh.ARRAY_CUSTOM0] as PackedFloat32Array).size(), 4):
		accent = accent or int(bus[Mesh.ARRAY_CUSTOM0][i] + 0.5) == VehicleMesh.VEH_ACCENT
	_check(accent, "bus : carrosserie claire (teinte d'appoint), bande à la couleur d'instance")
	var sh := load("res://shaders/vehicle.gdshader") as Shader
	_check(sh != null and sh.get_code().contains("lights_on"), "shader des véhicules chargé, phares commandés par lights_on")
	print("test_vehicle_mesh : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
