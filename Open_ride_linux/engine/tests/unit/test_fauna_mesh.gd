extends SceneTree

## Tests unitaires sans écran des maillages d'animaux de `fauna_renderer.gd` (Lot Y14, construits avec le
## Builder de people_mesh.gd) : taille, pieds au sol et avant vers +z, poids de l'aile (UV.x) et de la tête
## (UV.y) lus par shaders/fauna.gdshader, zones de couleur ; espèces des biomes du lot U12 comprises.
## Lancement : godot --headless --path engine --script res://tests/unit/test_fauna_mesh.gd

const FaunaRenderer := preload("res://scripts/fauna_renderer.gd")

## Triangles au plus par animal : 80 oiseaux et 80 bêtes en `high` restent sous 250 000.
const MAX_TRIS := 1500

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
	for sp in FaunaRenderer.SPECIES:
		var arrays := FaunaRenderer.build_mesh(sp).surface_get_arrays(0)
		var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
		var custom: PackedFloat32Array = arrays[Mesh.ARRAY_CUSTOM0]
		var tris := verts.size() / 3
		_check(tris > 100 and tris <= MAX_TRIS, "%s : %d triangles (au plus %d)" % [sp, tris, MAX_TRIS])
		var lo := Vector3(INF, INF, INF)
		var hi := -lo
		var regions := {}
		for i in range(verts.size()):
			lo = lo.min(verts[i])
			hi = hi.max(verts[i])
			regions[int(custom[i * 4] + 0.5)] = true
		_check(regions.has(FaunaRenderer.FAUNA_COAT) and regions.has(FaunaRenderer.FAUNA_DARK),
			"%s : robe et parties sombres (zones %s)" % [sp, str(regions.keys())])
		if sp in FaunaRenderer.BIRD_SPECIES:
			# Ailes le long de x (0,9 m d'envergure), poids 0 à l'attache et 1 au bout ; bec vers +z
			var root_ok := true
			var tip_ok := true
			for i in range(verts.size()):
				if absf(verts[i].x) < 0.04:
					root_ok = root_ok and uvs[i].x == 0.0
				if absf(verts[i].x) > 0.3:
					tip_ok = tip_ok and uvs[i].x == 1.0
			_check(absf(hi.x - 0.45) < 0.01 and absf(lo.x + 0.45) < 0.01, "oiseau : envergure 0,9 m le long de x")
			_check(root_ok and tip_ok, "oiseau : poids de l'aile 0 sur le corps, 1 au bout des ailes")
			_check(hi.z > -lo.z * 0.6 and hi.z > 0.2, "oiseau : tête et bec vers +z")
		else:
			# Pieds au sol, tête devant (+z) et seule partie qui broute
			var head_z := -INF
			var still_ok := true
			for i in range(verts.size()):
				if uvs[i].y > 0.99:
					head_z = maxf(head_z, verts[i].z)
				if verts[i].y < 0.3 * hi.y:   # bas des pattes, à l'échelle de la bête (lièvre de 0,5 m, P24)
					still_ok = still_ok and uvs[i].y == 0.0
			_check(absf(lo.y) < 1e-3, "%s : pieds à y = 0" % sp)
			_check(head_z >= hi.z - 1e-3, "%s : la tête (UV.y = 1) est à l'avant, vers +z" % sp)
			_check(still_ok, "%s : pattes immobiles quand la tête broute (UV.y = 0)" % sp)
	print("test_fauna_mesh : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
