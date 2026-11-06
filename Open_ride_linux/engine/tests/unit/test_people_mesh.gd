extends SceneTree

## Tests unitaires sans écran des personnages construits par code `people_mesh.gd` (Lot Y14) : tenues,
## zones de couleur, articulations, taille des maillages.
## Lancement : godot --headless --path engine --script res://tests/unit/test_people_mesh.gd

const PeopleMesh := preload("res://scripts/people_mesh.gd")
const CrowdShader := preload("res://shaders/crowd.gdshader")

## Triangles au plus par personnage, de près et au loin (Lot Y21) : 160 spectateurs et 80 passants en
## `high`, dont les plus proches seulement détaillés.
const MAX_PERSON_TRIS := [3300, 1200]

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
	var sizes := {"skin": PeopleMesh.SKIN_TONES.size(), "hair": PeopleMesh.HAIR_COLORS.size(),
		"trousers": PeopleMesh.TROUSER_COLORS.size(), "style": PeopleMesh.STYLES, "bottom": PeopleMesh.BOTTOMS,
		"hat": PeopleMesh.HATS, "gesture": PeopleMesh.GESTURES, "detail": PeopleMesh.DETAILS}
	var total := 1
	for k in sizes:
		total *= int(sizes[k])
	var ok := true
	var n := 0
	for s in range(sizes["skin"]):
		for h in range(sizes["hair"]):
			for t in range(sizes["trousers"]):
				for st in range(sizes["style"]):
					for b in range(sizes["bottom"]):
						for hat in range(sizes["hat"]):
							for g in range(sizes["gesture"]):
								for d in range(sizes["detail"]):
									var f := PeopleMesh.outfit_fields(PeopleMesh.outfit(s, h, t, st, b, hat, g, d))
									ok = ok and f["skin"] == s and f["hair"] == h and f["trousers"] == t and f["style"] == st \
										and f["bottom"] == b and f["hat"] == hat and f["gesture"] == g and f["detail"] == d
									n += 1
	_check(ok and total < 1 << 24, "tenue : huit champs relus tels quels (%d tenues, exactes en flottant 32 bits)" % n)
	# Donnée d'instance (instance_custom) relue comme crowd.gdshaderinc : entiers exacts sous 2 048
	var ic := PeopleMesh.instance_custom(0.25, 1.0, 9.0, PeopleMesh.outfit(3, 5, 4, 6, 2, 1, 7, 5))
	var w := int(ic.a)
	var zq := int(ic.b)
	var q := zq / 10
	_check(w % 4 == 3 and (w / 4) % 6 == 5 and (w / 24) % 6 == 4 and (w / 144) % 8 == 6 and zq % 10 == 9
		and q % 3 == 2 and (q / 3) % 3 == 1 and (q / 9) % 8 == 7 and int(floorf(ic.r)) == 5
		and is_equal_approx(fposmod(ic.r, 1.0), 0.25), "donnée d'instance : champs relus comme le shader (%s)" % str(ic))
	var max_c := PeopleMesh.instance_custom(0.999, 1.0, 9.0, float(total - 1))
	_check(max_c.r < 2048.0 and max_c.b < 2048.0 and max_c.a < 2048.0, "donnée d'instance : composantes sous 2 048 (%s)" % str(max_c))
	var seen := {}
	var in_range := true
	var count := {"bottom": [0, 0, 0], "hat": [0, 0, 0], "gesture": [0, 0, 0, 0, 0, 0, 0, 0]}
	for i in range(400):
		var v := PeopleMesh.outfit_of(i)
		in_range = in_range and v >= 0.0 and v < float(total) and v == floorf(v)
		seen[v] = true
		var f := PeopleMesh.outfit_fields(v)
		for k in count:
			count[k][int(f[k])] += 1
	_check(in_range, "outfit_of : entier dans les %d tenues" % total)
	_check(seen.size() >= 300, "400 personnes : %d tenues différentes" % seen.size())
	_check(count["bottom"][0] > 200 and count["bottom"][1] > 40 and count["bottom"][2] > 15,
		"bas : %d pantalons, %d shorts, %d jupes sur 400" % count["bottom"])
	_check(count["hat"][1] > 70 and count["hat"][2] > 20, "coiffes : %d casquettes, %d chapeaux sur 400" % [count["hat"][1], count["hat"][2]])
	_check(count["gesture"].min() > 25, "gestes : les huit tirés (%s)" % str(count["gesture"]))
	_check(PeopleMesh.outfit_of(42) == PeopleMesh.outfit_of(42), "même numéro : même tenue")


func _arrays(mesh: ArrayMesh) -> Array:
	return mesh.surface_get_arrays(0)


func _test_person(kind: String, lod: int) -> void:
	var name := "%s (niveau %d)" % [kind, lod]
	var mesh: ArrayMesh
	match kind:
		"porte-drapeau":
			mesh = PeopleMesh.build_person(true, false, lod)
		"pancarte":
			mesh = PeopleMesh.build_sign_holder(lod)
		_:
			mesh = PeopleMesh.build_person(false, false, lod)
	var a := _arrays(mesh)
	var verts: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
	var custom: PackedFloat32Array = a[Mesh.ARRAY_CUSTOM0]
	var uv: PackedVector2Array = a[Mesh.ARRAY_TEX_UV]
	var uv2: PackedVector2Array = a[Mesh.ARRAY_TEX_UV2]
	var tris := verts.size() / 3
	_check(tris <= MAX_PERSON_TRIS[lod], "%s : %d triangles (au plus %d)" % [name, tris, MAX_PERSON_TRIS[lod]])
	var regions := {}
	var extras := {}
	var lo := INF
	var hi := -INF
	var joint_ok := true
	var holder := 0
	for i in range(verts.size()):
		var region := int(custom[i * 4])
		var extra := int(custom[i * 4 + 3])
		regions[region] = true
		extras[extra] = true
		if region != PeopleMesh.REGION_POLE and region != PeopleMesh.REGION_SIGN and custom[i * 4 + 2] < 0.5 and extra == 0:
			lo = minf(lo, verts[i].y)
			hi = maxf(hi, verts[i].y)
		if custom[i * 4 + 1] > 0.5:
			# Sous une articulation : tibia (sur une jambe, sous le genou) ou avant-bras (bras libre, sous le coude)
			var shin := absf(uv2[i].x) > 0.5 and verts[i].y <= PeopleMesh.KNEE_Y + 1e-3
			var forearm := uv[i].y > 0.5 and verts[i].y <= PeopleMesh.ELBOW_Y + 0.05
			joint_ok = joint_ok and (shin or forearm or custom[i * 4 + 2] > 0.5)
		holder += 1 if custom[i * 4 + 2] > 0.5 else 0
	var expected := [PeopleMesh.REGION_TOP, PeopleMesh.REGION_SKIN, PeopleMesh.REGION_HAIR, PeopleMesh.REGION_TROUSERS,
		PeopleMesh.REGION_SHOES, PeopleMesh.REGION_METAL, PeopleMesh.REGION_POLE, PeopleMesh.REGION_ARM,
		PeopleMesh.REGION_ACCESSORY]
	if lod == 0:
		expected.append_array([PeopleMesh.REGION_EYE, PeopleMesh.REGION_LIPS])
	if kind == "pancarte":
		expected.append(PeopleMesh.REGION_SIGN)
	var all := true
	for r in expected:
		all = all and regions.has(r)
	_check(all and regions.size() == expected.size(), "%s : zones %s" % [name, str(regions.keys())])
	_check(absf(lo) < 0.01 and hi > 1.7 and hi < 1.8, "%s : pieds au sol, %.2f m de haut" % [name, hi])
	_check(joint_ok, "%s : tibias sous le genou, avant-bras sous le coude" % name)
	_check((holder > 0) == (kind != "personnage"), "%s : %d sommets de porteur" % [name, holder])
	var pieces := [PeopleMesh.EXTRA_LONG_HAIR, PeopleMesh.EXTRA_CAP, PeopleMesh.EXTRA_SUN_HAT, PeopleMesh.EXTRA_SKIRT,
		PeopleMesh.EXTRA_PONYTAIL, PeopleMesh.EXTRA_BUN, PeopleMesh.EXTRA_BACKPACK, PeopleMesh.EXTRA_SCARF]
	if lod == 0:
		pieces.append_array([PeopleMesh.EXTRA_BEARD, PeopleMesh.EXTRA_MOUSTACHE, PeopleMesh.EXTRA_SUNGLASSES])
	if kind == "personnage" and lod == 0:
		pieces.append(PeopleMesh.EXTRA_PHONE)
	if kind == "porte-drapeau":
		pieces.append(PeopleMesh.EXTRA_FLAG)
	if kind == "pancarte":
		pieces.append(PeopleMesh.EXTRA_SIGN)
	var has_all := true
	for e in pieces:
		has_all = has_all and extras.has(e)
	_check(has_all, "%s : pièces de tenue %s" % [name, str(extras.keys())])


func _test_lod() -> void:
	for kind in [[false, "personnage"], [true, "porte-drapeau"]]:
		var near: int = _arrays(PeopleMesh.build_person(kind[0], false, 0))[Mesh.ARRAY_VERTEX].size()
		var far: int = _arrays(PeopleMesh.build_person(kind[0], false, 1))[Mesh.ARRAY_VERTEX].size()
		_check(far * 2 < near, "%s : au loin %d triangles, de près %d" % [kind[1], far / 3, near / 3])
	var r: Vector4 = PeopleMesh.sign_rect()
	_check(r.z - r.x > 0.7 and r.y > 1.8, "pancarte au-dessus de la tête (%s)" % str(r))


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
	for lod in [0, 1]:
		for kind in ["personnage", "porte-drapeau", "pancarte"]:
			_test_person(kind, lod)
	_test_lod()
	_test_others()
	print("test_people_mesh : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
