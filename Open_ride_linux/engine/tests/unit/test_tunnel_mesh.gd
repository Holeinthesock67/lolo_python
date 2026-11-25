extends SceneTree

## Tests unitaires sans écran des tunnels dessinés (lot EA5) : maillage `tunnel_mesh.gd` (rien dans le gabarit de
## la route, voûte, portails aux deux bouts, lampes, normales et sens des faces), volume de découpe du terrain
## (`cut_contains`, même calcul que tunnel_cut.gdshaderinc), registre `tunnel_cut.gd` (tronçons les plus proches de
## la caméra, boîte, mise à jour seulement quand il faut), lecture de la couche `tunnels` par `osm_layers.gd`.
## Lancement : godot --headless --path engine --script res://tests/unit/test_tunnel_mesh.gd

const TunnelMesh := preload("res://scripts/tunnel_mesh.gd")
const TunnelCut := preload("res://scripts/tunnel_cut.gd")
const OsmLayers := preload("res://scripts/osm_layers.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const BiomeShader := preload("res://shaders/terrain_biomes.gdshader")
const WorldStreamer := preload("res://scripts/world_streamer.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Tunnel droit de 120 m vers le nord (z décroissant), chaussée à 100 m.
func _tunnel(x0: float = 0.0) -> Dictionary:
	var pts := []
	for i in range(13):
		pts.append([x0, -10.0 * i, 100.0])
	return {"id": "t0", "kind": "tunnel", "length_m": 120.0, "half_width_m": 3.0, "points": pts}


func _test_geometry() -> void:
	var m := TunnelMesh.build([_tunnel()])
	var shell: Dictionary = m["shell"]
	var v: PackedVector3Array = shell["vertices"]
	var nrm: PackedVector3Array = shell["normals"]
	var idx: PackedInt32Array = shell["indices"]
	_check(int(m["built"]) == 1 and v.size() == nrm.size() and idx.size() % 3 == 0,
		"un tunnel, tableaux cohérents (%d sommets)" % v.size())
	# Gabarit de la route : rien entre la chaussée et la naissance de la voûte au-dessus de la chaussée (|x| < 3 m),
	# sur toute la longueur du tube et de l'approche
	var w := 3.0 + TunnelMesh.SIDEWALK_M
	var clear := true
	for p in v:
		if absf(p.x) < 3.0 - 1e-3 and p.y > 100.0 + 1e-3 and p.y < 100.0 + TunnelMesh.WALL_H_M - 1e-3:
			clear = false
	_check(clear, "gabarit de la route libre (chaussée de 6 m, %.1f m de haut)" % TunnelMesh.WALL_H_M)
	var hi_inner := -INF
	var xmax := 0.0
	var zmin := INF
	var zmax := -INF
	for p in v:
		xmax = maxf(xmax, absf(p.x))
		zmin = minf(zmin, p.z)
		zmax = maxf(zmax, p.z)
		if absf(p.x) < 0.01 and p.z < -1.0 and p.z > -119.0 and p.y < 100.0 + TunnelMesh.WALL_H_M + TunnelMesh.VAULT_RISE_M + 0.01:
			hi_inner = maxf(hi_inner, p.y)
	_check(is_equal_approx(hi_inner, 100.0 + TunnelMesh.WALL_H_M + TunnelMesh.VAULT_RISE_M),
		"clé de voûte à %.1f m au-dessus de la route (%.2f)" % [TunnelMesh.WALL_H_M + TunnelMesh.VAULT_RISE_M, hi_inner - 100.0])
	_check(is_equal_approx(xmax, w + TunnelMesh.SHELL_M + TunnelMesh.PORTAL_SIDE_M), "têtes de portail de %.1f m de demi-largeur" % xmax)
	var reach := TunnelMesh.PORTAL_DEPTH_M + TunnelMesh.APRON_M
	_check(is_equal_approx(zmax, reach) and is_equal_approx(zmin, -120.0 - reach),
		"portail et murs d'approche aux deux bouts (z de %.1f à %.1f)" % [zmin, zmax])
	var unit := true
	var winding := true
	for t in range(0, idx.size(), 3):
		var a := v[idx[t]]
		var b := v[idx[t + 1]]
		var c := v[idx[t + 2]]
		var n := nrm[idx[t]]
		unit = unit and absf(n.length() - 1.0) < 1e-4
		var cr := (b - a).cross(c - a)
		if cr.length() > 1e-6 and cr.normalized().dot(n) > -0.99:
			winding = false
	_check(unit and winding, "normales unitaires, faces dans le sens de Godot vues de leur normale")
	# Intérieur de la voûte tourné vers l'axe, coque tournée vers le dehors
	var inner_down := false
	var outer_up := false
	for t in range(0, idx.size(), 3):
		var a := v[idx[t]]
		var n := nrm[idx[t]]
		if a.z < -20.0 and a.z > -100.0 and absf(a.x) < 0.5:
			if absf(a.y - (100.0 + TunnelMesh.WALL_H_M + TunnelMesh.VAULT_RISE_M)) < 0.3 and n.y < -0.9:
				inner_down = true
			if absf(a.y - (100.0 + TunnelMesh.WALL_H_M + TunnelMesh.VAULT_RISE_M + TunnelMesh.SHELL_M)) < 0.3 and n.y > 0.9:
				outer_up = true
	_check(inner_down and outer_up, "voûte : face intérieure vers le bas, coque vers le haut")
	# Lampes : deux rangées tous les LAMP_STEP_M (10 sur 120 m), sous la naissance de la voûte
	var lamps: Dictionary = m["lamps"]
	_check(int(m["lamp_count"]) == 20, "20 lampes sur 120 m (%d)" % int(m["lamp_count"]))
	var lamp_ok := true
	for p in (lamps["vertices"] as PackedVector3Array):
		if p.y > 100.0 + TunnelMesh.WALL_H_M or absf(p.x) > w or absf(p.x) < w - 0.2:
			lamp_ok = false
	_check(lamp_ok, "lampes contre les piédroits, sous la voûte")
	var bad := TunnelMesh.build([{"id": "x", "points": [[0.0, 0.0, 1.0]]}, 42])
	_check(int(bad["built"]) == 0 and int(bad["skipped"]) == 2, "tunnel d'un seul point et élément non objet ignorés")


func _test_cut() -> void:
	var cut: PackedFloat32Array = TunnelMesh.build([_tunnel()])["cut"]
	_check(cut.size() == TunnelMesh.CUT_FLOATS * (12 + 2), "12 tronçons du tube et 2 approches (%d)" % (cut.size() / TunnelMesh.CUT_FLOATS))
	var top := TunnelMesh.WALL_H_M + TunnelMesh.VAULT_RISE_M
	_check(TunnelMesh.cut_contains(cut, Vector3(0.0, 103.0, -60.0)), "terrain au milieu du tube : découpé")
	_check(TunnelMesh.cut_contains(cut, Vector3(3.9, 100.5, -60.0)), "terrain sur le trottoir : découpé")
	_check(not TunnelMesh.cut_contains(cut, Vector3(0.0, 100.0 + top + TunnelMesh.SHELL_M + 0.5, -60.0)),
		"colline au-dessus de la coque : gardée")
	_check(not TunnelMesh.cut_contains(cut, Vector3(0.0, 99.0, -60.0)), "sol sous la chaussée : gardé")
	_check(not TunnelMesh.cut_contains(cut, Vector3(4.0 + TunnelMesh.SHELL_M + 0.3, 102.0, -60.0)), "flanc hors de la coque : gardé")
	_check(not TunnelMesh.cut_contains(cut, Vector3(3.9, 100.0 + top, -60.0)), "coin au-dessus de la naissance, hors de la voûte : gardé")
	_check(TunnelMesh.cut_contains(cut, Vector3(0.0, 102.0, 5.0)), "terrain dans l'approche d'un portail : découpé")
	_check(not TunnelMesh.cut_contains(cut, Vector3(0.0, 102.0, 15.0)), "au-delà de l'approche : gardé")


func _test_registry() -> void:
	TunnelCut.clear()
	_check(not TunnelCut.update(Vector3.ZERO) or TunnelCut.active_count() == 0, "registre vide : rien d'actif")
	var near: PackedFloat32Array = TunnelMesh.build([_tunnel()])["cut"]
	var far: PackedFloat32Array = TunnelMesh.build([_tunnel(5000.0)])["cut"]
	TunnelCut.set_chunk(1, near)
	TunnelCut.set_chunk(2, far)
	_check(TunnelCut.segment_count() == 28, "deux tunnels enregistrés (%d tronçons)" % TunnelCut.segment_count())
	var big := PackedFloat32Array()
	for k in range(5):
		big.append_array(TunnelMesh.build([_tunnel(1000.0 + 20.0 * k)])["cut"])
	TunnelCut.set_chunk(3, big)
	var sel := TunnelCut.select(Vector3(0.0, 100.0, -60.0))
	_check(sel.size() == TunnelCut.MAX_SEGMENTS * TunnelMesh.CUT_FLOATS, "au plus %d tronçons gardés" % TunnelCut.MAX_SEGMENTS)
	var has_near := false
	for s in range(0, sel.size(), TunnelMesh.CUT_FLOATS):
		has_near = has_near or is_equal_approx(sel[s], 0.0)
	_check(has_near and TunnelMesh.cut_contains(sel, Vector3(0.0, 103.0, -60.0)), "le tunnel de la caméra est gardé")
	var box := TunnelCut.box_of(near)
	_check(box.x < -4.0 and box.z > 4.0 and box.y < -130.0 and box.w > 10.0, "boîte du tunnel et de ses approches %s" % str(box))
	_check(TunnelCut.update(Vector3(0.0, 100.0, -60.0)) and TunnelCut.active_count() == TunnelCut.MAX_SEGMENTS,
		"paramètres du shader écrits (%d tronçons)" % TunnelCut.active_count())
	_check(not TunnelCut.update(Vector3(1.0, 100.0, -60.0)), "caméra immobile : rien à réécrire")
	TunnelCut.remove_chunk(3)
	TunnelCut.remove_chunk(2)
	_check(TunnelCut.update(Vector3(1.0, 100.0, -60.0)) and TunnelCut.active_count() == 14, "tronçon libéré : registre à jour (%d)" % TunnelCut.active_count())
	TunnelCut.clear()
	_check(TunnelCut.update(Vector3(1.0, 100.0, -60.0)) and TunnelCut.active_count() == 0, "registre vidé : plus de trou")


## Variante TUNNEL_CUT : seules les tuiles qui touchent un tunnel ont le trou (le discard alourdit tout le terrain).
func _test_variant() -> void:
	TunnelCut.clear()
	var v0 := TunnelCut.version()
	var cut: PackedFloat32Array = TunnelMesh.build([_tunnel()])["cut"]
	TunnelCut.set_chunk(1, cut)
	_check(TunnelCut.version() != v0, "tunnel enregistré : numéro du registre changé")
	_check(TunnelCut.touches(Rect2(-500.0, -1000.0, 1000.0, 1000.0)), "tuile qui contient le tunnel : touchée")
	_check(TunnelCut.touches(Rect2(4.5, -60.0, 100.0, 10.0)), "tuile au ras de l'approche (marge) : touchée")
	_check(not TunnelCut.touches(Rect2(1000.0, -1000.0, 1000.0, 1000.0)), "tuile voisine sans tunnel : pas touchée")
	var mat := TerrainMaterial.create_material({})
	var base: Shader = mat.shader
	_check(not base.code.contains("#define TUNNEL_CUT"), "shader de base sans le trou")
	var var_s := TunnelCut.shader_for(base, true)
	_check(var_s != base and var_s.code.contains("#define TUNNEL_CUT") and var_s.code.begins_with("shader_type"),
		"variante : #define après la ligne shader_type")
	_check(TunnelCut.shader_for(base, true) == var_s and TunnelCut.shader_for(var_s, true) == var_s,
		"variante faite une seule fois")
	_check(TunnelCut.shader_for(var_s, false) == base and TunnelCut.is_variant(var_s) and not TunnelCut.is_variant(base),
		"retour au shader de base depuis la variante")
	var bv := TunnelCut.shader_for(BiomeShader, true)
	_check(bv != var_s and bv.code.contains("#define TUNNEL_CUT"), "variante propre au shader des biomes")
	mat.set_shader_parameter("snow_line_m", 1234.0)
	mat.shader = var_s
	_check(is_equal_approx(float(mat.get_shader_parameter("snow_line_m")), 1234.0), "paramètres gardés en changeant de variante")
	TunnelCut.remove_chunk(1)
	_check(not TunnelCut.touches(Rect2(-500.0, -1000.0, 1000.0, 1000.0)), "tunnel retiré : plus de tuile touchée")
	TunnelCut.clear()


## Tuiles affichées par world_streamer.gd : la variante suit le registre, sans refaire les maillages.
func _test_streamer_tiles() -> void:
	TunnelCut.clear()
	var ws = WorldStreamer.new()
	var tiles := {}
	for key in ["near:0:-1", "near:3:3", "far:0:-1"]:
		var arr := []
		arr.resize(Mesh.ARRAY_MAX)
		arr[Mesh.ARRAY_VERTEX] = PackedVector3Array([Vector3.ZERO, Vector3(1, 0, 0), Vector3(0, 0, 1)])
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		mesh.surface_set_material(0, ws._terrain_material_for(key))
		var mi := MeshInstance3D.new()
		mi.mesh = mesh
		ws._instances[key] = mi
		tiles[key] = mesh
	var base: Material = ws._terrain_material
	_check((tiles["near:0:-1"] as Mesh).surface_get_material(0) == base, "sans tunnel : matériau du thème")
	TunnelCut.set_chunk(1, TunnelMesh.build([_tunnel()])["cut"])
	ws._process(0.0)
	var m0: Material = (tiles["near:0:-1"] as Mesh).surface_get_material(0)
	_check(m0 != base and TunnelCut.is_variant((m0 as ShaderMaterial).shader), "tuile proche du tunnel : variante TUNNEL_CUT")
	_check((tiles["near:3:3"] as Mesh).surface_get_material(0) == base, "tuile proche sans tunnel : matériau du thème")
	_check((tiles["far:0:-1"] as Mesh).surface_get_material(0) == base, "tuile lointaine : jamais de trou")
	(base as ShaderMaterial).set_shader_parameter("snow_line_m", 987.0)
	ws._process(0.0)
	_check(is_equal_approx(float((m0 as ShaderMaterial).get_shader_parameter("snow_line_m")), 987.0),
		"réglage du thème recopié sur la variante")
	TunnelCut.clear()
	ws._process(0.0)
	_check((tiles["near:0:-1"] as Mesh).surface_get_material(0) == base, "tunnel retiré : matériau du thème rendu")
	for key in tiles:
		(ws._instances[key] as MeshInstance3D).free()
	ws._instances.clear()
	ws.free()


func _test_layer_reading() -> void:
	var dir := OS.get_temp_dir().path_join("openride_ea5_%d" % Time.get_ticks_usec())
	DirAccess.make_dir_recursive_absolute(dir.path_join("tunnels"))
	var doc := {"version": "1.0", "tunnels": [_tunnel(), {"id": "", "kind": "tunnel", "half_width_m": 3.0, "points": []},
		{"id": "b", "kind": "bridge", "half_width_m": 3.0, "points": [[0, 0, 0], [0, -10, 0]], "piers": []}]}
	var f := FileAccess.open(dir.path_join("tunnels/chunk_0.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(doc))
	f.close()
	var res := OsmLayers.load_chunk(dir, "tunnels", 0)
	_check(res["ok"] and (res["items"] as Array).size() == 1 and int(res["ignored"]) == 2,
		"couche tunnels : un tunnel valide, deux ignorés (%s)" % str(res.get("error", "")))
	_check(OsmLayers.layers_present({"layers": {"tunnels": {"present": true}}}).has("tunnels"), "couche tunnels reconnue au manifeste")
	DirAccess.make_dir_recursive_absolute(dir.path_join("live/tunnels"))
	f = FileAccess.open(dir.path_join("live/tunnels/tile_2_-1.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"version": "1.0", "tunnels": [_tunnel()]}))
	f.close()
	var one := OsmLayers._load_file(dir.path_join("live/tunnels/tile_2_-1.json"), "tunnels", Vector2(2000.0, -1000.0))
	var t: Dictionary = one["items"][0]
	_check(is_equal_approx(float(t["points"][1][0]), 2000.0) and is_equal_approx(float(t["points"][1][1]), -1010.0)
		and is_equal_approx(float(t["points"][1][2]), 100.0), "monde vivant : axe ramené au repère de la séance")


func _test_performance() -> void:
	var items := []
	for k in range(10):
		items.append(_tunnel(50.0 * k))
	var t0 := Time.get_ticks_usec()
	var m := TunnelMesh.build(items)
	var ms := (Time.get_ticks_usec() - t0) / 1000.0
	var tris := ((m["shell"] as Dictionary)["indices"] as PackedInt32Array).size() / 3
	_check(tris < 10 * 120 * 8, "10 tunnels de 120 m : %d triangles (moins de 8 par mètre, portails compris), %.1f ms" % [tris, ms])


func _init() -> void:
	_test_geometry()
	_test_cut()
	_test_registry()
	_test_variant()
	_test_streamer_tiles()
	_test_layer_reading()
	_test_performance()
	print("test_tunnel_mesh : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
