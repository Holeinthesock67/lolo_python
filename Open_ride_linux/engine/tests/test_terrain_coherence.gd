extends SceneTree

## Cohérence du terrain affiché sur un vrai parcours (couche terrain), au relief réel et au relief de séance :
## le pipeline de world_streamer.gd (remplissage, abaissement sous la route, raccord blend_to_far, lointain
## enfoncé sous le proche par sink_under_near) est rejoué sur toutes les tuiles, puis comparé en chiffres.
## Défauts visés : lointain qui perce le proche, coutures entre tuiles proches (28 octobre), lointain creusé
## bien plus que nécessaire (jusqu'à 94 m à ×2,5, vu sur les flancs le 29 octobre).
##
##   $GODOT --headless --path engine --script res://tests/test_terrain_coherence.gd -- DOSSIER.world [K ...]
##
## K : facteurs de relief (défaut 1.0 et EngineArgs.DEFAULT_VISUAL_GRADE). Code de sortie 1 si un seuil est dépassé.

const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")

## Lointain au plus 0,5 m au-dessus du proche affiché (bords de tuile lointaine, où seuls les échantillons du
## bord comptent) ; au plus 2 % des sommets lointains sous le proche enfoncés de plus de 10 m.
const MAX_POKE_M := 0.5
const DEEP_SINK_M := 10.0
const MAX_DEEP_SHARE := 0.02
const MAX_SEAM_M := 0.0001

var _failures := 0
var _checked := 0


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		printerr("Usage : -- DOSSIER.world [K ...]")
		quit(2)
		return
	var ks: Array[float] = []
	for a in args.slice(1):
		ks.append(float(a))
	if ks.is_empty():
		ks = [1.0, EngineArgs.DEFAULT_VISUAL_GRADE]
	for k in ks:
		_run(args[0], k)
	print("test_terrain_coherence : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _run(wd: String, k: float) -> void:
	var route = RouteDataScript.new()
	if not route.load_world_dir(wd):
		_check(false, "parcours lisible : %s" % wd)
		return
	route.relief_k = k
	var o: float = route.alt_m[0]
	var near_index := TerrainTiles.scan_index(wd, "near")
	var far_index := TerrainTiles.scan_index(wd, "far")
	_check(not near_index.is_empty() and not far_index.is_empty(), "k = %.1f : tuiles proches et lointaines présentes" % k)
	# Tuiles lointaines comme dans _build_job : [hauteurs avant enfoncement, hauteurs affichées]
	var fars := {}
	var covered := 0
	var deep := 0
	var deepest := 0.0
	for ft in far_index:
		var h := TerrainTiles.load_filled(wd, "far", ft.x, ft.y, route)
		h = TerrainTiles.carve_under_route(h, "far", ft.x, ft.y, route)
		var sunk := TerrainTiles.sink_under_near(h, ft.x, ft.y, near_index,
			func(nx: int, nz: int) -> PackedFloat32Array: return TerrainTiles.load_tile(wd, "near", nx, nz), k)
		fars[ft] = [h, sunk]
		for j in range(TerrainTiles.SAMPLES):
			for i in range(TerrainTiles.SAMPLES):
				var p := TerrainTiles.tile_origin("far", ft.x, ft.y) + Vector3(i * 50.0, 0.0, j * 50.0)
				if not near_index.has(TerrainTiles.tile_of("near", p.x, p.z)):
					continue
				covered += 1
				var d: float = (h[j * TerrainTiles.SAMPLES + i] - sunk[j * TerrainTiles.SAMPLES + i]) * k
				deepest = maxf(deepest, d)
				if d > DEEP_SINK_M:
					deep += 1
	# Tuiles proches comme dans _build_job, comparées au lointain affiché à chaque échantillon de 10 m
	var nears := {}
	var poke := -INF
	var poke_at := Vector3.ZERO
	for t in near_index:
		var h := TerrainTiles.load_filled(wd, "near", t.x, t.y, route)
		var c := TerrainTiles.tile_origin("near", t.x, t.y) + Vector3(1.0, 0.0, 1.0)
		var ft := TerrainTiles.tile_of("far", c.x, c.z)
		if not fars.has(ft):
			continue
		h = TerrainTiles.blend_to_far(h, t.x, t.y, near_index, fars[ft][0], ft, k)
		nears[t] = h
		for j in range(TerrainTiles.SAMPLES):
			for i in range(TerrainTiles.SAMPLES):
				var x: float = t.x * 1000.0 + i * 10.0
				var z: float = t.y * 1000.0 + j * 10.0
				var hn := o + (h[j * TerrainTiles.SAMPLES + i] - o) * k
				var hf := o + (TerrainTiles.mesh_height_at(fars[ft][1], "far", ft.x, ft.y, x, z) - o) * k - TerrainTiles.FAR_DROP_M
				if hf - hn > poke:
					poke = hf - hn
					poke_at = Vector3(x, hn, z)
	var seam := 0.0
	for t in nears:
		var e := Vector2i(t.x + 1, t.y)
		var s := Vector2i(t.x, t.y + 1)
		for m in range(TerrainTiles.SAMPLES):
			if nears.has(e):
				seam = maxf(seam, absf(nears[t][m * TerrainTiles.SAMPLES + TerrainTiles.CELLS] - nears[e][m * TerrainTiles.SAMPLES]))
			if nears.has(s):
				seam = maxf(seam, absf(nears[t][TerrainTiles.CELLS * TerrainTiles.SAMPLES + m] - nears[s][m]))
	_check(poke <= MAX_POKE_M, "k = %.1f : lointain au plus %.1f m au-dessus du proche (%.2f m en x = %.0f, z = %.0f)" % [k, MAX_POKE_M, poke, poke_at.x, poke_at.z])
	_check(seam <= MAX_SEAM_M, "k = %.1f : tuiles proches voisines jointives (écart %.5f m)" % [k, seam])
	var share := float(deep) / maxf(covered, 1)
	_check(share <= MAX_DEEP_SHARE, "k = %.1f : %d sommets lointains sur %d enfoncés de plus de %.0f m (%.1f %%, au plus %.0f %%), creux maximal %.1f m" % [k, deep, covered, DEEP_SINK_M, share * 100.0, MAX_DEEP_SHARE * 100.0, deepest])
