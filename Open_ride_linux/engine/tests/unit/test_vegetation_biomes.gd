extends SceneTree

## Tests sans écran des espèces construites par code et de la végétation par biome (lot U7, série U).
## Lancement : godot --headless --path engine --script res://tests/unit/test_vegetation_biomes.gd

const PerfBudget := preload("res://tests/perf_budget.gd")
const BiomeIds := preload("res://scripts/biome_ids.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const TreeSpecies := preload("res://scripts/tree_species.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _flat(alt: float) -> PackedFloat32Array:
	var h := PackedFloat32Array()
	h.resize(101 * 101)
	h.fill(alt)
	return h


func _species_counts(prep: Dictionary) -> Dictionary:
	var counts := {}
	for sp in prep["species"]:
		for v in sp:
			var k := TreeSpecies.kind_of(v)
			counts[k] = int(counts.get(k, 0)) + 1
	return counts


func _positions(prep: Dictionary, kind: String) -> Array:
	var out := []
	var idx := TreeSpecies.index_of(kind)
	for c in range(prep["cells"].size()):
		var trees: PackedVector4Array = prep["cells"][c]
		var sp: PackedByteArray = prep["species"][c]
		for i in range(trees.size()):
			if int(sp[i]) == idx:
				out.append(Vector2(trees[i].x, trees[i].z))
	return out


func _init() -> void:
	# 1. Espèces : maillage valide, moins de 300 triangles, dimensions plausibles
	for kind in BiomeIds.SPECIES:
		var b := TreeSpecies.build(kind)
		var ok: bool = not b.is_empty() and b["lod0"] is ArrayMesh
		var tris := TreeSpecies.triangle_count(b["lod0"]) if ok else 9999
		var aabb: AABB = (b["lod0"] as ArrayMesh).get_aabb() if ok else AABB()
		var h := aabb.end.y
		ok = ok and tris > 0 and tris < 300 and TreeSpecies.triangle_count(b["lod1"]) <= 40
		ok = ok and absf(h - TreeSpecies.height_m(kind)) <= 0.25 * TreeSpecies.height_m(kind) and aabb.position.y >= -0.4
		_check(ok, "%s : %d triangles, hauteur %.1f m (nominale %.1f)" % [kind, tris, h, TreeSpecies.height_m(kind)])
	# 1 bis. Matières (lot Y8 étape 2) : chaque face porte un code d'écorce ou de feuillage connu
	for kind in BiomeIds.SPECIES + ["generic"]:
		var meshes: Array = [TreeRenderer.build_lod0_mesh(), TreeRenderer.build_lod1_mesh()] if kind == "generic" \
			else [TreeSpecies.build(kind)["lod0"], TreeSpecies.build(kind)["lod1"]]
		var codes := {}
		for mesh in meshes:
			for c in ((mesh as ArrayMesh).surface_get_arrays(0)[Mesh.ARRAY_COLOR] as PackedColorArray):
				codes[int(roundf(c.a * 16.0))] = true
		var known: bool = codes.keys().all(func(k): return k >= TreeSpecies.MAT_BARK and k <= TreeSpecies.MAT_FRONDS)
		var foliage: bool = codes.keys().any(func(k): return k >= TreeSpecies.MAT_LEAVES) or kind in ["cactus", "reed"]
		_check(known and foliage, "%s : matières %s (écorce 1 à 7, feuillage 8 à 10)" % [kind, str(codes.keys())])
	# 1 ter. Japon (lot JP5) : quatre espèces, cèdre sugi le plus haut, érable momiji seul caduc (feuillage d'automne)
	var jp := ["sugi", "hinoki", "momiji", "bamboo"]
	_check(jp.all(func(k): return BiomeIds.SPECIES.has(k) and TreeSpecies.CROWNS.has(k)), "espèces du Japon connues")
	_check(TreeSpecies.height_m("sugi") > TreeSpecies.height_m("hinoki") and TreeSpecies.height_m("hinoki") > TreeSpecies.height_m("bamboo")
		and TreeSpecies.height_m("bamboo") > TreeSpecies.height_m("momiji"), "Japon : sugi > hinoki > bambou > érable")
	_check(TreeSpecies.is_deciduous("momiji") and not TreeSpecies.is_deciduous("sugi") and not TreeSpecies.is_deciduous("bamboo")
		and TreeSpecies.build("momiji").has("lod0_bare"), "Japon : érable caduc (charpente d'hiver), sugi et bambou persistants")
	var cactus_h := (TreeSpecies.build("cactus")["lod0"] as ArrayMesh).get_aabb().end.y
	var baobab_h := (TreeSpecies.build("baobab")["lod0"] as ArrayMesh).get_aabb().end.y
	_check(cactus_h >= 1.0 and cactus_h <= 6.0 and baobab_h >= 8.0 and baobab_h <= 20.0, "cactus %.1f m (1 à 6), baobab %.1f m (8 à 20)" % [cactus_h, baobab_h])

	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	var heights := _flat(300.0)

	# 2. Sans biome : préparation identique à aujourd'hui (même liste d'arbres), espèce GENERIC
	var plain := TreeRenderer.new()
	var ref: Dictionary = plain.prepare_tile(0, 0, heights, null, theme, 1.0)
	var muted := TreeRenderer.new()
	muted.biome_model = BiomeModel.new(theme, null)
	var same: Dictionary = muted.prepare_tile(0, 0, heights, null, theme, 1.0)
	_check(var_to_str(same["cells"]) == var_to_str(ref["cells"]) and _species_counts(same).keys() == ["generic"], "modèle inactif : mêmes arbres qu'avant, arbre d'avant la série U")

	# 3. Tuile 100 % méditerranéenne : plus de 80 % d'oliviers, chênes verts, cyprès, pins parasols
	var med := TreeRenderer.new()
	med.biome_model = BiomeModel.new(theme, null)
	med.biome_model.set_forced("mediterranean")
	var t0 := Time.get_ticks_usec()
	var pm: Dictionary = med.prepare_tile(0, 0, heights, null, theme, 1.0)
	var ms := (Time.get_ticks_usec() - t0) / 1000.0
	var cm := _species_counts(pm)
	var total := 0
	var medi := 0
	for k in cm.keys():
		total += cm[k]
		if k in ["olive", "holm_oak", "cypress", "stone_pine"]:
			medi += cm[k]
	_check(total > 0 and float(medi) / total > 0.8, "méditerranéen : %d arbres, %.0f %% d'espèces méditerranéennes" % [total, 100.0 * medi / maxi(total, 1)])
	_check(total < VegetationPlacer.new().place_tile(0, 0, 1000.0, func(_x, _z): return 300.0, null, theme).size(), "méditerranéen : moins dense que la prairie (150 contre 400 arbres/ha)")
	_check(PerfBudget.check("vegetation_tile_biomes", ms), "préparation d'une tuile méditerranéenne : %.1f ms" % ms)
	# Coût de préparation proportionnel à la densité : aucun biome du thème par défaut plus dense que la forêt
	# tempérée (600 arbres/ha), jungle comprise
	var densest := ""
	var dmax := 0.0
	for b in theme["biomes"]:
		var d := float(theme["biomes"][b]["vegetation"]["max_density_per_ha"])
		if d > dmax:
			dmax = d
			densest = b
	_check(dmax <= 600.0, "densité la plus forte des biomes : %s, %.0f arbres/ha (au plus 600)" % [densest, dmax])
	# Paysages (lot U25) : même plafond de 600 arbres/ha dans les blocs des biomes de base
	var lmax := 0.0
	for l in theme.get("landscapes", {}):
		for b in theme["landscapes"][l]["biomes"]:
			lmax = maxf(lmax, float(theme["landscapes"][l]["biomes"][b]["vegetation"]["max_density_per_ha"]))
	_check(lmax > 0.0 and lmax <= 600.0, "paysages : densité la plus forte %.0f arbres/ha (au plus 600)" % lmax)
	# Tuile de côte avec et sans paysage de fjord : bouleaux et épicéas, plus de palmiers ni de pins parasols
	var counts_by := {}
	for land in ["", "fjord"]:
		var layer = preload("res://scripts/biome_layer.gd").new()
		var g := []
		for p in range(289):
			g.append(255)
		var errs := PackedStringArray()
		var tile := preload("res://scripts/biome_layer.gd").parse_tile({"version": "1.0", "biomes": ["coast"], "grid": 17,
			"weights": [g], "variant": {"ground": null, "roofs": null, "landscape": land if land != "" else null}}, errs)
		layer.put_tile("near", 0, 0, tile)
		var tr := TreeRenderer.new()
		tr.biome_model = BiomeModel.new(theme, layer)
		counts_by[land] = _species_counts(tr.prepare_tile(0, 0, heights, null, theme, 1.0))
		tr.free()
	var cf: Dictionary = counts_by["fjord"]
	var cc: Dictionary = counts_by[""]
	_check(int(cc.get("stone_pine", 0)) > 0 and not cf.has("stone_pine") and not cf.has("palm")
		and int(cf.get("birch", 0)) > int(cf.get("spruce", 0)) and int(cf.get("spruce", 0)) > 0,
		"paysage fjord : côte de bouleaux et d'épicéas (%s), côte sans paysage (%s)" % [str(cf), str(cc)])
	var jun := TreeRenderer.new()
	jun.biome_model = BiomeModel.new(theme, null)
	jun.biome_model.set_forced("jungle")
	var tj := Time.get_ticks_usec()
	jun.prepare_tile(0, 0, heights, null, theme, 1.0)
	print("Profil de la préparation d'une tuile de jungle : %.1f ms (%s)" % [(Time.get_ticks_usec() - tj) / 1000.0, str(jun.last_profile)])
	jun.free()
	var again: Dictionary = med.prepare_tile(0, 0, heights, null, theme, 1.0)
	_check(var_to_str(again["species"]) == var_to_str(pm["species"]) and var_to_str(again["cells"]) == var_to_str(pm["cells"]), "même graine, même forêt")

	# 4. Désert de sable : aucun palmier sans eau ; avec un lac, palmiers à moins de 80 m de la rive
	var des := TreeRenderer.new()
	des.biome_model = BiomeModel.new(theme, null)
	des.biome_model.set_forced("sand_desert")
	var dry: Dictionary = des.prepare_tile(0, 0, heights, null, theme, 1.0)
	_check(_positions(dry, "palm").is_empty(), "désert sans eau : aucun palmier")
	var lake := Rect2(400.0, 400.0, 200.0, 200.0)
	des.near_water = func(x: float, z: float) -> bool:
		var dx := maxf(maxf(lake.position.x - x, 0.0), x - lake.end.x)
		var dz := maxf(maxf(lake.position.y - z, 0.0), z - lake.end.y)
		return sqrt(dx * dx + dz * dz) <= 80.0
	var oasis: Dictionary = des.prepare_tile(0, 0, heights, null, theme, 1.0)
	var palms := _positions(oasis, "palm")
	var near_ok := true
	for p in palms:
		if not des.near_water.call(p.x, p.y):
			near_ok = false
	_check(palms.size() > 0 and near_ok, "oasis : %d palmiers, tous à moins de 80 m du lac" % palms.size())

	# 5. Polaire : aucune végétation ; savane : acacias et baobabs
	var pol := TreeRenderer.new()
	pol.biome_model = BiomeModel.new(theme, null)
	pol.biome_model.set_forced("polar")
	_check(_species_counts(pol.prepare_tile(0, 0, heights, null, theme, 1.0)).is_empty(), "polaire : aucun arbre")
	var sav := TreeRenderer.new()
	sav.biome_model = BiomeModel.new(theme, null)
	sav.biome_model.set_forced("savanna")
	var cs := _species_counts(sav.prepare_tile(0, 0, heights, null, theme, 1.0))
	_check(cs.keys().size() == 2 and cs.has("acacia") and cs.has("baobab") and cs["acacia"] > cs["baobab"], "savane : acacias et quelques baobabs %s" % str(cs))

	# 6. Limite des arbres du biome : alpin à 2 300 m, aucun arbre au-dessus de 2 000 m
	var alp := TreeRenderer.new()
	alp.biome_model = BiomeModel.new(theme, null)
	alp.biome_model.set_forced("alpine")
	_check(_species_counts(alp.prepare_tile(0, 0, _flat(2300.0), null, theme, 1.0)).is_empty(), "alpin à 2 300 m : au-dessus de la limite des arbres (2 000 m)")

	# 7. Affichage : une paire de MultiMeshInstance3D par espèce, budget respecté
	med.add_tile(pm)
	var parts_ok := true
	var n_parts := 0
	for cell in med._tiles[Vector2i(0, 0)].values():
		var n := 0
		for part in cell["parts"]:
			n += int(part["count"])
			n_parts += 1
			if part["lod0"].multimesh.mesh == med._lod0_mesh:
				parts_ok = false
		if n != int(cell["count"]):
			parts_ok = false
	_check(parts_ok and n_parts >= 4, "méditerranéen : %d groupes par espèce, maillages propres à chaque espèce" % n_parts)
	med.set_preset("low")
	med.add_tile(med.prepare_tile(1, 0, heights, null, theme, 1.0))
	med.add_tile(med.prepare_tile(0, 1, heights, null, theme, 1.0))
	med._budget = 3000
	med.enforce_budget(Vector3(500, 300, 500))
	_check(med.get_active_tree_count() <= 3000, "budget : %d arbres actifs (≤ 3 000)" % med.get_active_tree_count())
	# Un seul Shader par niveau de détail pour toutes les espèces (pas de pipelines compilés en double, lot Y8)
	med.set_preset("medium")
	var shaders := {}
	for cell in med._tiles[Vector2i(0, 0)].values():
		for part in cell["parts"]:
			for key in ["lod0", "lod1"]:
				var m = (part[key] as MultiMeshInstance3D).material_override
				if m is ShaderMaterial:
					shaders[(m as ShaderMaterial).shader.get_instance_id()] = key
	_check(shaders.size() == 2, "matériaux des espèces : %d shaders en tout (un par niveau de détail)" % shaders.size())
	med.clear()
	_check(med.get_child_count() == 0, "clear : plus aucun MultiMeshInstance3D")
	for r in [plain, muted, med, des, pol, sav, alp]:
		r.free()
	_test_vine_lod()

	print("test_vegetation_biomes : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


## Lot « herbe au loin » : rangs de vigne des cultures simplifiés au-delà de TreeSpecies.lod0_m (200 m), arbre
## par arbre dans le shader ; modèle lointain en haie d'un rang ; arbres inchangés (passage par case à 450 m).
func _test_vine_lod() -> void:
	var vine := TreeSpecies.index_of("vine_row")
	var oak := TreeSpecies.index_of("oak")
	var hedge: ArrayMesh = TreeSpecies.build("vine_row")["lod1"]
	var hb := hedge.get_aabb()
	_check(TreeSpecies.triangle_count(hedge) == 10 and absf(hb.size.x - 6.0) < 0.01 and hb.size.z < 1.0
		and hb.position.y > 0.3 and hb.end.y <= TreeSpecies.height_m("vine_row"),
		"vigne au loin : haie d'un rang (%d triangles, %.1f × %.1f m, de %.2f à %.2f m)" % [
			TreeSpecies.triangle_count(hedge), hb.size.x, hb.size.z, hb.position.y, hb.end.y])
	_check(is_equal_approx(TreeSpecies.lod0_m("vine_row"), 200.0) and is_zero_approx(TreeSpecies.lod0_m("oak"))
		and is_zero_approx(TreeSpecies.lod0_m("generic")), "passage propre : vigne à 200 m, chêne et arbre d'avant sans")
	var vr := TreeRenderer.lod_ranges(vine, true)
	_check(TreeRenderer.lod_ranges(oak, true) == Vector2(TreeRenderer.LOD0_MAX_DIST_M, TreeRenderer.LOD0_MAX_DIST_M)
		and TreeRenderer.lod_ranges(vine, false) == Vector2(TreeRenderer.LOD0_MAX_DIST_M, TreeRenderer.LOD0_MAX_DIST_M)
		and TreeRenderer.lod_ranges(TreeSpecies.GENERIC, true) == Vector2(TreeRenderer.LOD0_MAX_DIST_M, TreeRenderer.LOD0_MAX_DIST_M),
		"chêne, arbre d'avant et vigne sans shader : passage par case à %.0f m comme avant" % TreeRenderer.LOD0_MAX_DIST_M)
	# Un rang au coin de sa case est au plus à CELL_RADIUS_M du centre : jamais coupé par la plage de la case.
	_check(vr.x >= 200.0 + TreeRenderer.SPECIES_LOD_BLEND_M + CELL_SIZE_HALF_DIAG and vr.x < TreeRenderer.LOD0_MAX_DIST_M
		and vr.y <= maxf(0.0, 200.0 - TreeRenderer.SPECIES_LOD_BLEND_M - CELL_SIZE_HALF_DIAG),
		"vigne : modèle proche écarté au-delà de %.0f m du centre de la case (au lieu de %.0f), lointain dès %.0f m" % [
			vr.x, TreeRenderer.LOD0_MAX_DIST_M, vr.y])
	var r = TreeRenderer.new()
	r.set_preset("medium")
	var look: Dictionary = r._look(vine)
	var m0: ShaderMaterial = look["m0"]
	var m1: ShaderMaterial = look["m1"]
	var oak_m0: ShaderMaterial = r._look(oak)["m0"]
	_check(is_equal_approx(_param(m0, "lod_end_m"), 200.0) and is_equal_approx(_param(m1, "lod_begin_m"), 200.0)
		and is_zero_approx(_param(oak_m0, "lod_end_m")) and is_zero_approx(_param(m0, "fade_end_m")),
		"matériaux de la vigne : modèle proche jusqu'à 200 m, lointain au-delà ; chêne sans borne")
	r.free()


const CELL_SIZE_HALF_DIAG := 250.0 * 0.7071


## Paramètre de shader (0 quand il garde sa valeur par défaut, nulle pour les bornes du niveau de détail).
static func _param(m: ShaderMaterial, name: String) -> float:
	var v: Variant = m.get_shader_parameter(name)
	return 0.0 if v == null else float(v)
