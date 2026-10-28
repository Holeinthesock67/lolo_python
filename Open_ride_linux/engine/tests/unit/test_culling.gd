extends SceneTree

## Tests unitaires sans écran du tri de ce que la caméra voit (view_culling.gd, lot S1), critère 2 du
## cahier : le tri reçoit la caméra active ; avec la vue subjective puis avec une caméra 6 m derrière et
## 3 m au-dessus, une tuile hors du champ et hors du rayon gardé n'est pas voulue ; une tuile qui entre
## dans le champ après une épingle est voulue assez tôt (vérifié le long de la trajectoire de la route).
## Lancement : godot --headless --path engine --script res://tests/unit/test_culling.gd

const ViewCulling := preload("res://scripts/view_culling.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")

const TILE_M := 1000.0
## Avance demandée sur la trajectoire : une tuile visible en s est voulue dès s − PREP_M (10 s à 36 km/h).
const PREP_M := 100.0
const SPEED_MPS := 10.0

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
	_test_cone()
	_test_cameras()
	_test_hysteresis()
	_test_hairpin()
	_test_seams()
	print("test_culling : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _tile(ix: int, iz: int) -> Rect2:
	return Rect2(ix * TILE_M, iz * TILE_M, TILE_M, TILE_M)


## Secteur seul : devant, derrière, de côté, caméra dans la tuile.
func _test_cone() -> void:
	var half := deg_to_rad(60.0)
	var view := ViewCulling.view_at(Vector2(500.0, 500.0), Vector2(0.0, -1.0), half)
	_check(ViewCulling.rect_in_view(_tile(0, -2), view), "tuile droit devant : dans le champ")
	_check(not ViewCulling.rect_in_view(_tile(0, 2), view), "tuile droit derrière : hors du champ")
	_check(not ViewCulling.rect_in_view(_tile(-2, 1), view) and not ViewCulling.rect_in_view(_tile(2, 1), view),
		"tuiles derrière à gauche et à droite : hors du champ")
	_check(ViewCulling.rect_in_view(_tile(0, 0), view), "tuile qui contient la caméra : toujours voulue")
	_check(ViewCulling.rect_in_view(_tile(-2, -1), view) and ViewCulling.rect_in_view(_tile(2, -1), view),
		"tuiles devant en biais, à cheval sur le bord du champ : gardées")
	_check(ViewCulling.rect_in_view(Rect2(-5000.0, -3000.0, 11000.0, 500.0), view),
		"bande qui traverse tout le champ sans coin dedans : gardée")
	_check(ViewCulling.rect_wanted(_tile(0, 2), [], 1500.0, 400.0), "sans vue (tri coupé) : tout est voulu")
	var h169 := ViewCulling.half_angle_rad(65.0, 16.0 / 9.0)
	_check(absf(rad_to_deg(h169) - (48.6 + ViewCulling.VIEW_MARGIN_DEG)) < 0.5,
		"demi-champ horizontal en 16/9 à 65° de champ vertical : %.1f° marge comprise" % rad_to_deg(h169))
	_check(rad_to_deg(ViewCulling.half_angle_rad(120.0, 4.0)) <= ViewCulling.MAX_HALF_DEG + 1e-3,
		"demi-champ borné à %.0f°" % ViewCulling.MAX_HALF_DEG)


## Caméra hors de l'arbre (test sans écran) : transformation locale posée directement.
func _place(cam: Camera3D, eye: Vector3, target: Vector3) -> void:
	cam.transform = Transform3D(Basis.looking_at(target - eye, Vector3.UP), eye)


## Caméra active passée au tri : vue subjective, puis caméra 6 m derrière et 3 m au-dessus du cycliste.
func _test_cameras() -> void:
	var keep_low := ViewCulling.keep_radius_for(QualityPresets.shadow_distance_m("low"))
	var keep_med := ViewCulling.keep_radius_for(QualityPresets.shadow_distance_m("medium"))
	var rider := Vector3(500.0, 0.0, 500.0)
	var cam := Camera3D.new()
	cam.fov = 65.0
	var setups := {
		"subjective": [rider + Vector3(0.0, 1.4, 0.0), rider + Vector3(0.0, 1.4, -10.0)],
		"6 m derrière, 3 m au-dessus": [rider + Vector3(0.0, 3.0, 6.0), rider + Vector3(0.0, 1.0, 0.0)],
	}
	for label in setups:
		_place(cam, setups[label][0], setups[label][1])
		var views := [ViewCulling.view_of(cam)]
		_check(ViewCulling.rect_wanted(_tile(0, -1), views, WorldStreamer.NEAR_RADIUS_M, keep_low),
			"%s : tuile devant à 500 m voulue" % label)
		_check(not ViewCulling.rect_wanted(_tile(0, 2), views, WorldStreamer.NEAR_RADIUS_M, keep_low),
			"%s : tuile derrière à 1 500 m ni construite ni dessinée" % label)
		_check(not ViewCulling.rect_wanted(_tile(0, 1), views, WorldStreamer.NEAR_RADIUS_M, keep_low),
			"%s : tuile derrière à 500 m écartée en low (rayon gardé %.0f m)" % [label, keep_low])
		_check(ViewCulling.rect_wanted(_tile(0, 1), views, WorldStreamer.NEAR_RADIUS_M, keep_med),
			"%s : la même gardée en medium (rayon gardé %.0f m, ombres)" % [label, keep_med])
		_check(not ViewCulling.rect_wanted(_tile(0, -3), views, WorldStreamer.NEAR_RADIUS_M, keep_low),
			"%s : tuile devant au-delà du rayon des tuiles proches écartée" % label)
	# Caméra latérale (vue de V12) : le champ suit la caméra, pas le cycliste.
	_place(cam, rider + Vector3(8.0, 1.6, 0.0), rider + Vector3(0.0, 1.0, 0.0))
	var side := [ViewCulling.view_of(cam)]
	_check(ViewCulling.rect_wanted(_tile(-1, 0), side, WorldStreamer.NEAR_RADIUS_M, keep_low)
		and not ViewCulling.rect_wanted(_tile(0, -2), side, WorldStreamer.NEAR_RADIUS_M, keep_low),
		"caméra latérale : tuile à sa gauche voulue, tuile devant le cycliste écartée")
	cam.free()


## Une tuile chargée juste au bord du champ reste voulue (marge de maintien) ; non chargée, elle ne l'est pas.
func _test_hysteresis() -> void:
	var st = WorldStreamer.new()
	st.culling_keep_m = 0.0
	# Caméra en (500, 500) regardant vers −z ; coin de la tuile (1, −1) le plus proche du regard à 18,4°
	# de l'axe ; demi-champ mis à 14,4° : 4° hors du champ, dans la marge de maintien de 10°.
	var view := ViewCulling.view_at(Vector2(500.0, 500.0), Vector2(0.0, -1.0), deg_to_rad(14.4))
	var t := Vector2i(1, -1)
	var loaded: bool = st.near_tile_wanted(t, [view], true)
	var fresh: bool = st.near_tile_wanted(t, [view], false)
	_check(loaded and not fresh, "bord du champ : gardée si déjà chargée (%s), pas construite sinon (%s)" % [loaded, fresh])
	st.free()


## Route qui part vers −z, fait une épingle de 50 m de rayon et revient vers +z.
func _hairpin_route():
	var pts := []
	var ds := 10.0
	var straight := 300.0
	var r := 50.0
	var arc := PI * r
	var total := straight + arc + 1500.0
	var s := 0.0
	while s <= total + 1e-6:
		var p: Vector2
		if s <= straight:
			p = Vector2(500.0, 500.0 - s)
		elif s <= straight + arc:
			var a := (s - straight) / r   # 0 → π, centre (550, 200)
			p = Vector2(550.0 - r * cos(a), 200.0 - r * sin(a))
		else:
			p = Vector2(600.0, 200.0 + (s - straight - arc))
		pts.append(p)
		s += ds
	var d := {"version": "1.0", "ds_m": ds, "n": pts.size(), "length_m": (pts.size() - 1) * ds, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for p in pts:
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(250.0)
		d["x"].append(p.x)
		d["z"].append(p.y)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(0.0)
	var route = RouteDataScript.new()
	_check(route.load_route_dict(d), "parcours en épingle chargé")
	return route


func _view_on(route, s: float, half: float) -> Dictionary:
	var p: Vector3 = route.sample_point(s)
	return ViewCulling.view_at(Vector2(p.x, p.z), ViewCulling.route_dir(route, s), half)


## Trajectoire : toute tuile visible en s (dans le champ, à moins de 1 000 m) est voulue dès s − PREP_M.
func _test_hairpin() -> void:
	var route = _hairpin_route()
	var keep := ViewCulling.keep_radius_for(QualityPresets.shadow_distance_m("low"))
	var half := ViewCulling.half_angle_rad(65.0, 16.0 / 9.0)
	# Avant l'épingle, la tuile du retour (0, 1) est derrière et à plus du rayon gardé.
	var before := _view_on(route, 150.0, half)
	_check(not ViewCulling.rect_wanted(_tile(0, 1), [before], WorldStreamer.NEAR_RADIUS_M, keep),
		"épingle : la tuile du retour est hors du champ de la vue actuelle")
	var views := ViewCulling.route_views(before, route, 150.0, SPEED_MPS)
	_check(views.size() > 1, "vues futures le long de la route : %d" % (views.size() - 1))
	_check(ViewCulling.rect_wanted(_tile(0, 1), views, WorldStreamer.NEAR_RADIUS_M, keep),
		"épingle : la tuile du retour est demandée avant le virage")
	var late := 0
	var seen := 0
	var s := PREP_M
	while s <= route.length_m - 10.0:
		var now := _view_on(route, s, half)
		var early := ViewCulling.route_views(_view_on(route, s - PREP_M, half), route, s - PREP_M, SPEED_MPS)
		for ix in range(-2, 4):
			for iz in range(-2, 5):
				var rect := _tile(ix, iz)
				if ViewCulling.rect_distance(rect, now["pos"]) > 1000.0 or not ViewCulling.rect_in_view(rect, now):
					continue
				seen += 1
				if not ViewCulling.rect_wanted(rect, early, WorldStreamer.NEAR_RADIUS_M, keep):
					late += 1
		s += 10.0
	_check(seen > 0 and late == 0,
		"trajectoire : %d tuiles visibles, %d demandées moins de %.0f m avant d'être vues" % [seen, late, PREP_M])
	# Le tri écarte vraiment quelque chose sur ce parcours (sinon il ne servirait à rien).
	var culled := 0
	for ix in range(-2, 4):
		for iz in range(-2, 5):
			if not ViewCulling.rect_wanted(_tile(ix, iz), views, WorldStreamer.NEAR_RADIUS_M, keep):
				culled += 1
	_check(culled > 0, "épingle, vue avant le virage : %d tuiles sur 42 écartées" % culled)


## Jointures (mode test de world_streamer.gd) : deux tuiles proches tirées d'un même relief ont le même
## bord ; une marche d'un mètre est mesurée comme telle, dans les quatre directions.
func _test_seams() -> void:
	var n := TerrainTiles.SAMPLES
	var cell: float = TerrainTiles.LEVELS["near"]["cell"]
	var tiles := {}
	for t in [Vector2i(0, 0), Vector2i(1, 0), Vector2i(0, 1)]:
		var h := PackedFloat32Array()
		h.resize(n * n)
		for j in range(n):
			for i in range(n):
				var x: float = t.x * 1000.0 + i * cell
				var z: float = t.y * 1000.0 + j * cell
				h[j * n + i] = 300.0 + 20.0 * sin(x / 170.0) + 15.0 * cos(z / 230.0)
		tiles[t] = TerrainTiles.build_arrays(h, "near")[Mesh.ARRAY_VERTEX]
	var a: PackedVector3Array = tiles[Vector2i(0, 0)]
	var east: PackedVector3Array = tiles[Vector2i(1, 0)]
	var south: PackedVector3Array = tiles[Vector2i(0, 1)]
	_check(WorldStreamer.seam_gap(a, east, 1, 0) < 1e-4 and WorldStreamer.seam_gap(east, a, -1, 0) < 1e-4
		and WorldStreamer.seam_gap(a, south, 0, 1) < 1e-4 and WorldStreamer.seam_gap(south, a, 0, -1) < 1e-4,
		"jointures : tuiles voisines d'un même relief jointives dans les quatre directions")
	var raised := east.duplicate()
	for k in range(raised.size()):
		raised[k] = raised[k] + Vector3(0.0, 1.0, 0.0)
	var gap := WorldStreamer.seam_gap(a, raised, 1, 0)
	_check(absf(gap - 1.0) < 1e-3 and gap > WorldStreamer.TEST_SEAM_TOL_M,
		"jointures : marche de 1 m détectée (%.3f m, seuil %.2f m)" % [gap, WorldStreamer.TEST_SEAM_TOL_M])
