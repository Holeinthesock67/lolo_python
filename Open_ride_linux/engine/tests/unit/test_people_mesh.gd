extends SceneTree

## Tests unitaires sans écran des personnages construits par code `people_mesh.gd` (Lot Y14) : tenues,
## zones de couleur, articulations, taille des maillages.
## Lancement : godot --headless --path engine --script res://tests/unit/test_people_mesh.gd

const PeopleMesh := preload("res://scripts/people_mesh.gd")
const CrowdShader := preload("res://shaders/crowd.gdshader")

## Triangles au plus par personnage : 160 spectateurs et 80 passants en `high` restent sous 200 000.
const MAX_PERSON_TRIS := 800

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _test_outfits() -> void:
	var ns := PeopleMesh.SKIN_TONES.size()
	var nh := PeopleMesh.HAIR_COLORS.size()
	var nt := PeopleMesh.TROUSER_COLORS.size()
	var ok := true
	for s in range(ns):
		for h in range(nh):
			for t in range(nt):
				var o := int(PeopleMesh.outfit(s, h, t))
				ok = ok and o % ns == s and (o / ns) % nh == h and (o / (ns * nh)) % nt == t
	_check(ok, "tenue : peau, cheveux et pantalon relus tels quels (%d tenues)" % (ns * nh * nt))
	var seen := {}
	var in_range := true
	for i in range(200):
		var o := PeopleMesh.outfit_of(i)
		in_range = in_range and o >= 0.0 and o < float(ns * nh * nt) and o == floorf(o)
		seen[o] = true
	_check(in_range, "outfit_of : entier dans les %d tenues" % (ns * nh * nt))
	_check(seen.size() >= 60, "200 personnes : %d tenues différentes" % seen.size())
	_check(PeopleMesh.outfit_of(42) == PeopleMesh.outfit_of(42), "même numéro : même tenue")


func _arrays(mesh: ArrayMesh) -> Array:
	return mesh.surface_get_arrays(0)


func _test_person(with_flag: bool) -> void:
	var name := "porte-drapeau" if with_flag else "personnage"
	var a := _arrays(PeopleMesh.build_person(with_flag))
	var verts: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
	var custom: PackedFloat32Array = a[Mesh.ARRAY_CUSTOM0]
	var uv2: PackedVector2Array = a[Mesh.ARRAY_TEX_UV2]
	var tris := verts.size() / 3
	_check(tris <= MAX_PERSON_TRIS, "%s : %d triangles (au plus %d)" % [name, tris, MAX_PERSON_TRIS])
	var regions := {}
	var lo := INF
	var hi := -INF
	var shin_ok := true
	var holder := 0
	for i in range(verts.size()):
		regions[int(custom[i * 4])] = true
		if int(custom[i * 4]) != PeopleMesh.REGION_POLE and custom[i * 4 + 2] < 0.5:
			lo = minf(lo, verts[i].y)
			hi = maxf(hi, verts[i].y)
		if custom[i * 4 + 1] > 0.5:
			shin_ok = shin_ok and absf(uv2[i].x) > 0.5 and verts[i].y <= PeopleMesh.KNEE_Y + 1e-3
		holder += 1 if custom[i * 4 + 2] > 0.5 else 0
	var expected := [PeopleMesh.REGION_TOP, PeopleMesh.REGION_SKIN, PeopleMesh.REGION_HAIR,
		PeopleMesh.REGION_TROUSERS, PeopleMesh.REGION_SHOES]
	if with_flag:
		expected.append(PeopleMesh.REGION_POLE)
	var all := true
	for r in expected:
		all = all and regions.has(r)
	_check(all and regions.size() == expected.size(), "%s : zones %s" % [name, str(regions.keys())])
	_check(absf(lo) < 0.01 and hi > 1.7 and hi < 1.8, "%s : pieds au sol, %.2f m de haut" % [name, hi])
	_check(shin_ok, "%s : tibias sous le genou et sur une jambe" % name)
	_check((holder > 0) == with_flag, "%s : %d sommets de porte-drapeau" % [name, holder])


func _test_others() -> void:
	var dog := _arrays(PeopleMesh.build_dog())
	var dv: PackedVector3Array = dog[Mesh.ARRAY_VERTEX]
	var duv2: PackedVector2Array = dog[Mesh.ARRAY_TEX_UV2]
	var legs := {}
	for i in range(dv.size()):
		if absf(duv2[i].x) > 0.5:
			legs[Vector2i(signi(int(signf(dv[i].x))), signi(int(signf(dv[i].z))))] = duv2[i].x
	_check(legs.size() == 4 and legs[Vector2i(-1, 1)] == legs[Vector2i(1, -1)] and legs[Vector2i(1, 1)] == legs[Vector2i(-1, -1)]
		and legs[Vector2i(1, 1)] != legs[Vector2i(-1, 1)], "chien : quatre pattes, trot en diagonale")
	var bench: PackedVector3Array = _arrays(PeopleMesh.build_bench())[Mesh.ARRAY_VERTEX]
	var seat := false
	for v in bench:
		seat = seat or absf(v.y - 0.44) < 0.01
	_check(seat, "banc : assise à 0,42 m")
	var mat := ShaderMaterial.new()
	mat.shader = CrowdShader
	PeopleMesh.apply_palettes(mat)
	var j: Vector4 = mat.get_shader_parameter("joints")
	_check(is_equal_approx(j.x, PeopleMesh.HIP_Y) and is_equal_approx(j.y, PeopleMesh.KNEE_Y)
		and is_equal_approx(j.z, PeopleMesh.SHOULDER_Y) and (mat.get_shader_parameter("skin_tones") as PackedVector3Array).size() == PeopleMesh.SKIN_TONES.size(),
		"matériau : articulations et palettes passées au shader")


func _init() -> void:
	_test_outfits()
	_test_person(false)
	_test_person(true)
	_test_others()
	print("test_people_mesh : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
