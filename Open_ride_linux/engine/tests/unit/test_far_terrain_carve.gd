extends SceneTree

## Terrain lointain abaissé sous la route (terrain_tiles.gd, carve_under_route). Défaut trouvé au
## banc simulé le 25 octobre : la maille lointaine de 50 m dépassait la chaussée dans les virages
## et sur les flancs raides malgré FAR_DROP_M.

const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_far_terrain_carve : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route en S à 7 % au fond d'une vallée en V (flancs à 30 %), dans la tuile lointaine (0, 0).
func _route_x(s: float) -> float:
	return 2500.0 + 60.0 * sin(TAU * s / 900.0)


func _make_route():
	var d := {"version": "1.0", "ds_m": 10.0, "n": 0, "length_m": 0.0, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var n := 301
	for k in range(n):
		var s := k * 10.0
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(500.0 + 0.07 * s)
		d["x"].append(_route_x(s))
		d["z"].append(1000.0 + s)
		d["grade_pct"].append(7.0)
		d["heading_deg"].append(180.0)
	d["n"] = n
	d["length_m"] = (n - 1) * 10.0
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _valley_heights() -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(TerrainTiles.SAMPLES * TerrainTiles.SAMPLES)
	for j in range(TerrainTiles.SAMPLES):
		for i in range(TerrainTiles.SAMPLES):
			var x := i * 50.0
			var z := j * 50.0
			var s := clampf(z - 1000.0, 0.0, 3000.0)
			out[j * TerrainTiles.SAMPLES + i] = 500.0 + 0.07 * s + 0.30 * absf(x - _route_x(s))
	return out


## Plus grand dépassement du terrain dessiné (y_offset compris) au-dessus de la chaussée, sur l'axe
## et jusqu'à 3,5 m de part et d'autre, tous les 2 m.
func _worst_above(heights: PackedFloat32Array, route) -> float:
	var worst := -INF
	var drop: float = TerrainTiles.LEVELS["far"]["y_offset"]
	var s := 0.0
	while s <= route.length_m:
		var p: Vector3 = route.sample_point(s)
		var hd: float = deg_to_rad(route.sample_heading_deg(s))
		var right := Vector3(cos(hd), 0.0, sin(hd))
		for off in [-3.5, -1.75, 0.0, 1.75, 3.5]:
			var q: Vector3 = p + right * off
			var h := TerrainTiles.mesh_height_at(heights, "far", 0, 0, q.x, q.z) + drop
			worst = maxf(worst, h - p.y)
		s += 2.0
	return worst


func _run() -> void:
	var route = _make_route()
	var raw := _valley_heights()
	var before := _worst_above(raw, route)
	_check(before > 0.0, "sans correctif, le terrain lointain dépasse la route : %.2f m" % before)
	var carved := TerrainTiles.carve_under_route(raw, "far", 0, 0, route)
	var after := _worst_above(carved, route)
	_check(after <= -TerrainTiles.FAR_DROP_M + 0.01,
		"après abaissement, terrain lointain sous la route d'au moins %.1f m : %.2f m" % [TerrainTiles.FAR_DROP_M, after])
	var changed := 0
	var raised := 0
	for idx in range(raw.size()):
		if carved[idx] != raw[idx]:
			changed += 1
		if carved[idx] > raw[idx]:
			raised += 1
	_check(raised == 0, "aucun sommet relevé")
	_check(changed > 0 and changed < 2000, "sommets abaissés seulement le long de la route : %d sur %d" % [changed, raw.size()])
	# Tuile voisine : les sommets du bord commun reçoivent la même valeur des deux côtés.
	var east := PackedFloat32Array()
	east.resize(raw.size())
	for j in range(TerrainTiles.SAMPLES):
		for i in range(TerrainTiles.SAMPLES):
			east[j * TerrainTiles.SAMPLES + i] = raw[j * TerrainTiles.SAMPLES + TerrainTiles.CELLS]
	var r2 = _make_route()
	for k in range(r2.n):
		r2.x[k] = 5000.0 + 20.0 * sin(k / 10.0)   # route le long du bord x = 5 000 m
	var west_c := TerrainTiles.carve_under_route(raw, "far", 0, 0, r2)
	var east_c := TerrainTiles.carve_under_route(east, "far", 1, 0, r2)
	var same := true
	for j in range(TerrainTiles.SAMPLES):
		if west_c[j * TerrainTiles.SAMPLES + TerrainTiles.CELLS] != east_c[j * TerrainTiles.SAMPLES]:
			same = false
	_check(same, "bord commun de deux tuiles voisines abaissé à l'identique")
	var none := TerrainTiles.carve_under_route(raw, "far", 3, 3, route)
	_check(none == raw, "tuile loin de la route inchangée")
