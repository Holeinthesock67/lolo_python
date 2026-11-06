extends SceneTree

## Ombres simplifiées du terrain (6 novembre 2026) : faux relief des ombres (TerrainTiles.shadow_proxy_arrays)
## toujours sous le vrai relief, exact sur une pente régulière, crêtes gardées ; modes `full`, `proxy` et `off` de
## WorldStreamer.relief_shadow (ombre portée des tuiles, faux relief actif, route non concernée), clé `relief_shadow`
## des préréglages et essai `ombres_terrain=` d'OPENRIDE_RENDER_DIAG.
## Lancement : godot --headless --path engine --script res://tests/unit/test_relief_shadow.gd

const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const RenderDiag := preload("res://scripts/render_diag.gd")

const S := TerrainTiles.SAMPLES

var _failures := 0
var _checked := 0


func _init() -> void:
	_test_counts()
	_test_below_everywhere()
	_test_plane_exact()
	_test_ridge_kept()
	_test_streamer_modes()
	_test_presets_and_diag()
	print("test_relief_shadow : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Sommets d'une tuile proche dont la hauteur est f(x, z) (build_arrays, relief exagéré éventuel).
func _tile(f: Callable, k: float = 1.0) -> PackedVector3Array:
	var h := PackedFloat32Array()
	h.resize(S * S)
	for j in range(S):
		for i in range(S):
			h[j * S + i] = float(f.call(i * 10.0, j * 10.0))
	return TerrainTiles.build_arrays(h, "near", {}, k, 300.0)[Mesh.ARRAY_VERTEX]


## Hauteur du faux relief en (x, z) : même découpage des triangles que la tuile (a, b, c) et (b, d, c).
func _proxy_height(pv: PackedVector3Array, x: float, z: float) -> float:
	var n := TerrainTiles.CELLS / TerrainTiles.PROXY_STEP
	var cell := 10.0 * TerrainTiles.PROXY_STEP
	var fi := clampf(x / cell, 0.0, n)
	var fj := clampf(z / cell, 0.0, n)
	var i := mini(int(fi), n - 1)
	var j := mini(int(fj), n - 1)
	var u := fi - i
	var v := fj - j
	var ns := n + 1
	var a := pv[j * ns + i].y
	var b := pv[j * ns + i + 1].y
	var c := pv[(j + 1) * ns + i].y
	var d := pv[(j + 1) * ns + i + 1].y
	return a + u * (b - a) + v * (c - a) if u + v <= 1.0 else d + (1.0 - u) * (c - d) + (1.0 - v) * (b - d)


## Relief accidenté : vallée en V à 45 %, bosses de 30 m sur 70 m, crête fine, pente générale de 12 %.
func _rough(x: float, z: float) -> float:
	return 300.0 + 0.12 * z + 0.45 * absf(x - 430.0) + 30.0 * sin(x / 11.0) * cos(z / 13.0) \
		+ maxf(0.0, 60.0 - 4.0 * absf(z - 615.0))


func _test_counts() -> void:
	var verts := _tile(_rough)
	var t0 := Time.get_ticks_usec()
	var arrays := TerrainTiles.shadow_proxy_arrays(verts)
	print("faux relief d'une tuile : %.1f ms (tâche de fond, mode proxy seulement)" % ((Time.get_ticks_usec() - t0) / 1000.0))
	var n := TerrainTiles.CELLS / TerrainTiles.PROXY_STEP
	var tris := (arrays[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
	_check(tris == n * n * 2 + 4 * n * 2, "faux relief : %d triangles (grille %d × %d et jupes)" % [tris, n, n])
	var drawn := TerrainTiles.CELLS * TerrainTiles.CELLS * 2 + 4 * TerrainTiles.CELLS * 4
	_check(drawn >= 13 * tris, "au moins 13 fois moins de triangles que la tuile dessinée (%d contre %d)" % [tris, drawn])


func _test_below_everywhere() -> void:
	for k in [1.0, 2.5]:
		var verts := _tile(_rough, k)
		var pv: PackedVector3Array = TerrainTiles.shadow_proxy_arrays(verts)[Mesh.ARRAY_VERTEX]
		var worst := -INF
		for j in range(S):
			for i in range(S):
				var p := verts[j * S + i]
				worst = maxf(worst, _proxy_height(pv, p.x, p.z) - p.y)
		# Entre deux sommets fins aussi (milieux des arêtes et des mailles fines)
		var worst_mid := -INF
		for j in range(S - 1):
			for i in range(S - 1):
				var p := verts[j * S + i]
				var q := verts[(j + 1) * S + i + 1]
				var b := verts[j * S + i + 1]
				var c := verts[(j + 1) * S + i]
				for m in [[(p + b) * 0.5], [(p + c) * 0.5], [(b + c) * 0.5], [(b + q) * 0.5]]:
					var pt: Vector3 = m[0]
					worst_mid = maxf(worst_mid, _proxy_height(pv, pt.x, pt.z) - pt.y)
		_check(worst <= -TerrainTiles.PROXY_MARGIN_M + 1e-3 and worst_mid <= -TerrainTiles.PROXY_MARGIN_M + 1e-3,
			"relief ×%.1f : faux relief toujours sous le vrai d'au moins %.1f m (au plus près %.3f m, entre sommets %.3f m)"
			% [k, TerrainTiles.PROXY_MARGIN_M, -worst, -worst_mid])


func _test_plane_exact() -> void:
	var verts := _tile(func(x: float, z: float) -> float: return 250.0 + 0.3 * x - 0.08 * z)
	var pv: PackedVector3Array = TerrainTiles.shadow_proxy_arrays(verts)[Mesh.ARRAY_VERTEX]
	var worst := 0.0
	for j in range(0, S, 7):
		for i in range(0, S, 7):
			var p := verts[j * S + i]
			worst = maxf(worst, absf(p.y - TerrainTiles.PROXY_MARGIN_M - _proxy_height(pv, p.x, p.z)))
	_check(worst < 1e-3, "pente régulière à 30 %% : faux relief exactement %.1f m sous le vrai (écart %.4f m)" % [TerrainTiles.PROXY_MARGIN_M, worst])


## Une colline de 150 m de rayon garde sa hauteur : son ombre reste à sa place (sommet sur un sommet de la maille de 40 m).
func _test_ridge_kept() -> void:
	var hill := func(x: float, z: float) -> float:
		var r := Vector2(x - 520.0, z - 520.0).length()
		return 300.0 + 120.0 * maxf(0.0, cos(clampf(r / 150.0, 0.0, 1.0) * PI * 0.5))
	var verts := _tile(hill)
	var pv: PackedVector3Array = TerrainTiles.shadow_proxy_arrays(verts)[Mesh.ARRAY_VERTEX]
	var top := -INF
	for p in pv:
		top = maxf(top, p.y)
	_check(top > 420.0 - 3.0, "colline de 120 m : sommet du faux relief à %.1f m du vrai" % (420.0 - top))


func _test_streamer_modes() -> void:
	var st = WorldStreamer.new()
	get_root().add_child(st)
	var tiles := {}
	for key in ["near:0:0", "near:1:1", "far:0:0", "flat:1:0", "road:0"]:
		var mi := MeshInstance3D.new()
		if key == "near:0:0":
			var proxy := MeshInstance3D.new()
			proxy.name = WorldStreamer.PROXY_NODE
			proxy.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
			mi.add_child(proxy)
		mi.mesh = BoxMesh.new()
		st.add_child(mi)
		st._instances[key] = mi
		st._apply_relief_shadow(key, mi)
		tiles[key] = mi
	var ON := GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	var OFF := GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var proxy_of := func() -> MeshInstance3D: return (tiles["near:0:0"] as MeshInstance3D).get_node(WorldStreamer.PROXY_NODE)
	_check(st.relief_shadow == "full" and tiles["near:0:0"].cast_shadow == ON and tiles["far:0:0"].cast_shadow == ON
		and tiles["flat:1:0"].cast_shadow == ON and not proxy_of.call().visible, "full (défaut) : rendu d'avant, faux relief inactif")
	st.relief_shadow = "proxy"
	_check(tiles["near:0:0"].cast_shadow == OFF and tiles["far:0:0"].cast_shadow == OFF and tiles["flat:1:0"].cast_shadow == OFF
		and proxy_of.call().visible and st.relief_shadow_counts() == {"tiles": 0, "proxies": 1},
		"proxy : seul le faux relief porte l'ombre (%s)" % [st.relief_shadow_counts()])
	_check(tiles["road:0"].cast_shadow == ON, "proxy : la route garde son ombre")
	_check(not st._instances.has("near:1:1") and not is_instance_valid(tiles["near:1:1"]),
		"proxy : une tuile proche préparée sans faux relief est libérée pour être refaite")
	tiles.erase("near:1:1")
	st.relief_shadow = "off"
	_check(st.relief_shadow_counts() == {"tiles": 0, "proxies": 0}, "off : le relief ne porte aucune ombre")
	st.relief_shadow = "n'importe quoi"
	_check(st.relief_shadow == "full" and st.relief_shadow_counts() == {"tiles": 3, "proxies": 0}, "valeur inconnue : full")
	for key in tiles:
		st._free_instance(key)
	st.free()


func _test_presets_and_diag() -> void:
	for name in ["low", "medium", "high"]:
		_check(str(QualityPresets.image(name)["relief_shadow"]) in WorldStreamer.RELIEF_SHADOW_MODES,
			"préréglage %s : relief_shadow = %s" % [name, QualityPresets.image(name)["relief_shadow"]])
	RenderDiag._parsed = true
	RenderDiag._flags = PackedStringArray()
	RenderDiag._values = {"ombres_terrain": "proxy"}
	_check(RenderQuality.diagnostic_image(QualityPresets.image("high"))["relief_shadow"] == "proxy",
		"essai ombres_terrain=proxy : clé remplacée")
	RenderDiag._values = {}
