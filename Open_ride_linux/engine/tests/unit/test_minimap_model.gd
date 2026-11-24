extends SceneTree

## Mini-carte du monde ouvert (lot W24) : modèle sans affichage (cap en haut, route devant et derrière, nord,
## échelle, carrefour, but épinglé, position géographique du but) et placement du panneau.
## Lancement : godot --headless --path engine --script res://tests/unit/test_minimap_model.gd

const Model := preload("res://scripts/minimap_model.gd")
const MinimapView := preload("res://scripts/minimap_view.gd")
const RouteData := preload("res://scripts/route_data.gd")

const LAT0 := 45.0
const LON0 := 6.0

var _checked := 0
var _failures := 0


func _check(ok: bool, what: String) -> void:
	_checked += 1
	if not ok:
		_failures += 1
		printerr("[ÉCHEC] ", what)
	else:
		print("[OK] ", what)


## Route droite de `length` m au pas de 10 m, de cap `heading_deg` (0 = nord, 90 = est) dans le repère du monde ;
## `grid_deg` : écart entre le nord géographique et le nord de la grille (colonnes lat et lon tournées d'autant).
func _route(length: float, heading_deg: float, grid_deg: float = 0.0):
	var n := int(length / 10.0) + 1
	var h := deg_to_rad(heading_deg)
	var g := deg_to_rad(heading_deg + grid_deg)
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in n:
		var d := i * 10.0
		cols["x"].append(d * sin(h))
		cols["z"].append(-d * cos(h))
		cols["lat"].append(LAT0 + d * cos(g) / 111132.0)
		cols["lon"].append(LON0 + d * sin(g) / (111320.0 * cos(deg_to_rad(LAT0))))
		cols["alt_m"].append(100.0)
		cols["grade_pct"].append(0.0)
		cols["heading_deg"].append(heading_deg)
	var r = RouteData.new()
	var data := {"version": "1.0", "ds_m": 10.0, "n": n, "length_m": (n - 1) * 10.0, "type": "open"}
	data.merge(cols)
	_check(r.load_route_dict(data), "route d'essai lue (%s)" % r.load_error)
	return r


func _init() -> void:
	# Textes et échelle
	_check(Model.distance_text(240.4) == "240 m", "240 m")
	_check(Model.distance_text(3240.0) == "3,2 km", "3,2 km avec une virgule : " + Model.distance_text(3240.0))
	_check(Model.distance_text(12400.0) == "12 km", "12 km sans décimale")
	var sc := Model.scale_bar(600.0)
	_check(sc["m"] == 200 and sc["text"] == "200 m", "échelle de 200 m pour 1 200 m de large : %s" % str(sc))
	_check(is_equal_approx(sc["frac"], 200.0 / 600.0), "longueur de la barre en unités de la carte")
	_check(Model.scale_bar(2000.0)["text"] == "1,0 km" or Model.scale_bar(2000.0)["m"] == 1000, "échelle d'1 km pour 4 km")
	_check(Model.quality("low")["stride"] == 3 and Model.quality("high")["redraw_ms"] < Model.quality("low")["redraw_ms"],
		"low lit un point sur trois et redessine moins souvent")
	_check(Model.quality("inconnue") == Model.QUALITY["medium"], "qualité inconnue : medium")

	_check(not Model.build(null, 0.0, 1)["visible"], "sans route : cachée")

	# Route vers le nord : devant en haut, derrière en bas, nord en haut
	var north = _route(3000.0, 0.0)
	var v: Dictionary = Model.build(north, 1000.0, 1)
	_check(v["visible"], "visible avec une route")
	var ahead: PackedVector2Array = v["ahead"]
	var behind: PackedVector2Array = v["behind"]
	_check(ahead.size() > 50 and behind.size() > 50, "route lue devant et derrière (%d, %d points)" % [ahead.size(), behind.size()])
	_check(ahead[0].distance_to(Model.RIDER) < 0.01, "la route devant part du cycliste")
	_check(ahead[ahead.size() - 1].y < -1.0 and absf(ahead[ahead.size() - 1].x) < 0.01, "devant = en haut : %s" % str(ahead[ahead.size() - 1]))
	_check(behind[0].y > Model.RIDER.y + 0.5, "derrière = en bas : %s" % str(behind[0]))
	_check(v["north"].distance_to(Vector2(0.0, -1.0)) < 0.01, "cap au nord : N en haut %s" % str(v["north"]))

	# Route vers l'est : nord à gauche
	var east = _route(3000.0, 90.0)
	v = Model.build(east, 1000.0, 1)
	_check(v["north"].distance_to(Vector2(-1.0, 0.0)) < 0.01, "cap à l'est : N à gauche %s" % str(v["north"]))
	ahead = v["ahead"]
	_check(ahead[ahead.size() - 1].y < -1.0, "cap à l'est : la route devant reste en haut")

	# Marche arrière (demi-tour) : la route devant est celle des s décroissants, toujours en haut
	v = Model.build(north, 1000.0, -1)
	ahead = v["ahead"]
	_check(ahead[0].y < -1.0 and ahead[ahead.size() - 1].distance_to(Model.RIDER) < 0.01, "à rebours : devant toujours en haut")
	_check(v["north"].distance_to(Vector2(0.0, 1.0)) < 0.01, "à rebours vers le sud : N en bas")

	# Qualité low : moins de points
	var lo: Dictionary = Model.build(north, 1000.0, 1, {"stride": 3})
	_check(lo["ahead"].size() < v["behind"].size() * 0.5, "low : un point sur trois (%d points)" % lo["ahead"].size())

	# Prochain carrefour
	v = Model.build(north, 1000.0, 1, {"next": {"id": "j1", "d_m": 240.4, "default": 0, "chosen": 0, "locked": false, "b": []}})
	_check(v["lines"] == ["Carrefour dans 240 m"], "carrefour écrit sous la carte : %s" % str(v["lines"]))
	_check(absf(v["junction"]["pos"].y - (Model.RIDER.y - 240.4 / Model.RADIUS_M)) < 0.01, "anneau du carrefour 240 m devant")
	v = Model.build(north, 1000.0, 1, {"next": {"id": "j1", "d_m": 2000.0}})
	_check(v["junction"].is_empty() and v["lines"].is_empty(), "carrefour à 2 km : rien")

	# Amorces des branches
	v = Model.build(north, 1000.0, 1, {"previews": [{"xs": [0.0, 100.0], "zs": [-1100.0, -1100.0]}]})
	_check(v["previews"].size() == 1 and v["previews"][0][1].x > 0.1, "amorce vers l'est dessinée à droite")

	# But : destination et boucle
	_check(Model.goal_from_start({"nav": "ride"}).is_empty(), "balade libre : pas de but")
	var dest := Model.goal_from_start({"nav": "destination", "lat": LAT0, "lon": LON0, "target": {"lat": 45.1, "lon": 6.1}})
	_check(dest["label"] == "Arrivée" and dest["kind"] == "destination", "destination : Arrivée")
	var loop := Model.goal_from_start({"nav": "loop", "lat": LAT0, "lon": LON0, "loop_km": 20})
	_check(loop["label"] == "Départ" and is_equal_approx(loop["lat"], LAT0), "boucle : retour au départ")
	_check(Model.goal_from_start(null).is_empty() and Model.goal_from_start({"nav": "destination"}).is_empty(),
		"départ inconnu ou sans cible : pas de but")

	# Position géographique → repère du monde, y compris avec 2,5° d'écart entre nord géographique et grille
	var p := Model.geo_to_world(north, LAT0 + 2500.0 / 111132.0, LON0)
	_check(p.distance_to(Vector2(0.0, -2500.0)) < 5.0, "cible sur la route à 2,5 km : %s" % str(p))
	var tilted = _route(3000.0, 0.0, 2.5)
	var far_geo_lat := LAT0 + 2900.0 * cos(deg_to_rad(2.5)) / 111132.0
	var far_geo_lon := LON0 + 2900.0 * sin(deg_to_rad(2.5)) / (111320.0 * cos(deg_to_rad(LAT0)))
	p = Model.geo_to_world(tilted, far_geo_lat, far_geo_lon)
	_check(p.distance_to(Vector2(0.0, -2900.0)) < 5.0, "écart de grille de 2,5° corrigé : %s" % str(p))
	_check(not is_finite(Model.geo_to_world(null, LAT0, LON0).x), "sans route : position inconnue")

	# But dans la carte, puis épinglé au bord
	v = Model.build(north, 1000.0, 1, {"goal": {"label": "Arrivée", "x": 0.0, "z": -1300.0}})
	_check(v["goal"]["inside"] and v["lines"] == ["Arrivée : 300 m à vol d'oiseau"], "but à 300 m dans la carte : %s" % str(v["lines"]))
	v = Model.build(north, 1000.0, 1, {"goal": {"label": "Arrivée", "x": 0.0, "z": -4200.0}, "aspect": 0.7})
	var g: Dictionary = v["goal"]
	_check(not g["inside"] and absf(g["pos"].y + Model.EDGE * 0.7) < 0.01 and absf(g["pos"].x) < 0.01,
		"but hors carte épinglé au bord haut : %s" % str(g["pos"]))
	_check(v["lines"] == ["Arrivée : 3,2 km à vol d'oiseau"], "distance à vol d'oiseau écrite : %s" % str(v["lines"]))
	v = Model.build(north, 1000.0, 1, {"goal": {"label": "Départ", "x": 0.0, "z": 0.0}, "aspect": 0.7,
		"next": {"d_m": 100.0}})
	_check(v["lines"] == ["Carrefour dans 100 m", "Départ : 1,0 km à vol d'oiseau"], "deux lignes : carrefour puis but")
	_check(v["goal"]["pos"].y > Model.RIDER.y, "départ derrière : épinglé en bas")

	# Panneau : place suffisante ou non
	var view = MinimapView.new()
	_check(view.place(20.0, 300.0, 705.0, 2), "place suffisante en 1 280 × 720")
	_check(is_equal_approx(view.size.x, MinimapView.WIDTH) and is_equal_approx(view.position.y + view.size.y, 705.0),
		"largeur de la colonne, posée sur le bas")
	_check(view.position.y >= 300.0, "sous la colonne gauche")
	_check(not view.place(20.0, 600.0, 705.0, 2), "place insuffisante : cachée")
	view.free()

	print("Mini-carte : %d vérifications, %d échec(s)" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
