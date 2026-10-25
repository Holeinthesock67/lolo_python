extends SceneTree

## Décor OSM et route (défauts vus au banc simulé le 25 octobre) : aucun arbre dans un bâtiment
## (tree_renderer.gd, exclude_buildings) et cours d'eau coupés là où ils croisent la chaussée
## (osm_streamer.gd, cut_lines_at_road).

const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_osm_decor_route : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _run() -> void:
	# --- arbres et bâtiments : maison de 10 × 8 m tournée de 30°.
	var c := Vector2(100.0, 200.0)
	var ring := []
	for corner in [Vector2(-5, -4), Vector2(5, -4), Vector2(5, 4), Vector2(-5, 4)]:
		var p: Vector2 = c + (corner as Vector2).rotated(deg_to_rad(30.0))
		ring.append([p.x, p.y])
	var buildings := [{"id": "b1", "outer": ring}, {"id": "bad", "outer": [[0, 0]]}, "pas un dict"]
	var trees := PackedVector4Array([
		Vector4(c.x, 400.0, c.y, 1.0),                       # au centre
		Vector4(c.x + 4.0, 400.0, c.y + 1.0, 1.0),           # dans l'emprise
		Vector4(c.x + 7.0, 400.0, c.y, 1.0),                 # à ~1,5 m du mur
		Vector4(c.x + 20.0, 400.0, c.y, 1.0),                # loin
		Vector4(-50.0, 400.0, -50.0, 1.0),                   # loin
	])
	var kept := TreeRenderer.exclude_buildings(trees, buildings)
	_check(kept.size() == 2, "arbres gardés hors des bâtiments et à plus de %.0f m des murs : %d/5 (attendu 2)"
		% [TreeRenderer.BUILDING_CLEARANCE_M, kept.size()])
	_check(TreeRenderer.exclude_buildings(trees, []).size() == 5, "sans bâtiment, aucun arbre retiré")

	# --- eau et route : route nord-sud (x = 0), rivière est-ouest qui la croise à z = 500.
	var road := PackedVector2Array()
	for i in range(101):
		road.append(Vector2(0.0, i * 10.0))
	var river := {"id": "r", "kind": "river", "width_m": 9.0, "points": []}
	for i in range(-6, 7):
		river["points"].append([i * 25.0, 500.0, 400.0])
	var lines := OsmStreamer.cut_lines_at_road([river], road)
	_check(lines.size() == 2, "rivière coupée en deux au passage de la route : %d morceaux" % lines.size())
	var min_gap := INF
	for l in lines:
		for p in l["points"]:
			min_gap = minf(min_gap, absf(float(p[0])))
	_check(min_gap >= 20.0, "aucun point d'eau à moins de 20 m de l'axe (relevé %.1f m)" % min_gap)
	_check(lines.size() == 2 and lines[0]["kind"] == "river" and lines[0]["width_m"] == 9.0, "attributs gardés")
	# Ruisseau parallèle à la route, à 15 m : intact. Puis le même à 4 m : retiré en entier.
	var stream := {"id": "s", "kind": "stream", "width_m": 2.0, "points": []}
	for i in range(10):
		stream["points"].append([15.0, 100.0 + i * 20.0, 400.0])
	var kept_s := OsmStreamer.cut_lines_at_road([stream], road)
	_check(kept_s.size() == 1 and (kept_s[0]["points"] as Array).size() == 10, "ruisseau à 15 m de la route intact")
	var close := stream.duplicate(true)
	for p in close["points"]:
		p[0] = 4.0
	_check(OsmStreamer.cut_lines_at_road([close], road).is_empty(), "ruisseau sur le bas-côté (4 m de l'axe) retiré")
	_check(OsmStreamer.cut_lines_at_road([river], PackedVector2Array()).size() == 1, "sans route connue, rien n'est coupé")
