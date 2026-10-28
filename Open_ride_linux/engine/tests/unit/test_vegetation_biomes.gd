extends SceneTree

## Tests sans écran des espèces construites par code et de la végétation par biome (lot U7, série U).
## Lancement : godot --headless --path engine --script res://tests/unit/test_vegetation_biomes.gd

const BiomeIds := preload("res://scripts/biome_ids.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const TreeSpecies := preload("res://scripts/tree_species.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

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
	print("[PERF] préparation d'une tuile méditerranéenne : %.1f ms" % ms)
	_check(PerfBudget.check("vegetation_tile_biomes", ms), "préparation d'une tuile avec biomes : %.1f ms (seuil d'O1)" % ms)
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
	var jun := TreeRenderer.new()
	jun.biome_model = BiomeModel.new(theme, null)
	jun.biome_model.set_forced("jungle")
	var tj := Time.get_ticks_usec()
	jun.prepare_tile(0, 0, heights, null, theme, 1.0)
	print("[PERF] préparation d'une tuile de jungle : %.1f ms (%s)" % [(Time.get_ticks_usec() - tj) / 1000.0, str(jun.last_profile)])
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

	# 6. Limite des arbres du biome : alpin à 2 300 m, aucun arbre au-dessus de 2 100 m
	var alp := TreeRenderer.new()
	alp.biome_model = BiomeModel.new(theme, null)
	alp.biome_model.set_forced("alpine")
	_check(_species_counts(alp.prepare_tile(0, 0, _flat(2300.0), null, theme, 1.0)).is_empty(), "alpin à 2 300 m : au-dessus de la limite des arbres (2 100 m)")

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
	med.clear()
	_check(med.get_child_count() == 0, "clear : plus aucun MultiMeshInstance3D")
	for r in [plain, muted, med, des, pol, sav, alp]:
		r.free()

	print("test_vegetation_biomes : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
