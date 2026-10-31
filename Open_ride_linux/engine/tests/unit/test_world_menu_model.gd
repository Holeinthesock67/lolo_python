extends SceneTree

## Menu du monde ouvert sans affichage (lot W11) : parcours complet globe → recherche → carte → cap →
## `start_open_world`, rotation, curseur accroché aux routes, épinglage, préchargement.
## Lancement : godot --headless --path engine --script res://tests/unit/test_world_menu_model.gd

const Model := preload("res://scripts/world_menu_model.gd")

var _checked := 0
var _failures := 0


func _check(ok: bool, what: String) -> void:
	_checked += 1
	if not ok:
		_failures += 1
		printerr("[ÉCHEC] ", what)
	else:
		print("[OK] ", what)


func _init() -> void:
	var m = Model.new()
	_check(m.state == "globe", "départ sur le globe")
	var lon0: float = m.globe_lon
	m.handle("RIGHT_SHORT")
	_check(absf(m.globe_lon - (lon0 + 10.0)) < 1e-9, "droite : le globe tourne vers l'est")
	m.handle("MINUS_SHORT")
	m.handle("LEFT_SHORT")
	_check(absf(m.globe_lon - (lon0 - 10.0)) < 1e-9, "− et gauche : vers l'ouest")
	m.globe_lon = 175.0
	m.handle("PLUS_SHORT")
	_check(absf(m.globe_lon - (-175.0)) < 1e-9, "tour complet : longitude ramenée à [−180 ; 180[")
	var lat0: float = m.globe_lat
	m.handle("MINUS_LONG")
	_check(absf(m.globe_lat - (lat0 + 10.0)) < 1e-9, "appui long − : incline vers le nord")
	for i in range(20):
		m.handle("PLUS_LONG")
	_check(m.globe_lat == -80.0, "inclinaison bornée à 80°")

	# Suite complète : « Ventoux » → carte → cap 90° → départ.
	m = Model.new()
	var act: Dictionary = m.type_text("V")
	_check(act.is_empty() and m.state == "search", "première lettre : recherche ouverte, rien demandé (moins de 2 lettres)")
	for ch in "entoux":
		act = m.type_text(ch)
	_check(act == {"action": "world_search", "query": "Ventoux"}, "recherche « Ventoux » demandée : %s" % str(act))
	m.on_places([{"name": "Mont Ventoux", "kind": "peak", "lat": 44.174, "lon": 5.2788, "cached": false, "source": "embedded"},
		{"name": "Ventoux, Vaucluse", "kind": "other", "lat": 44.0, "lon": 5.0, "cached": false, "source": "nominatim"}])
	m.handle("PLUS_SHORT")
	_check(m.place_index == 1, "+ : deuxième résultat")
	m.handle("MINUS_SHORT")
	act = m.handle("A_SHORT")
	_check(act["action"] == "world_map" and absf(act["lat"] - 44.174) < 1e-9 and absf(act["lon"] - 5.2788) < 1e-9 and act["radius_m"] == 8000.0,
		"A : carte demandée autour du Ventoux : %s" % str(act))
	_check(m.state == "map" and not m.map_ready, "écran carte, routes pas encore reçues")
	m.on_map({"roads": [{"c": "t", "xz": [-400, 1000, 0, 1000, 500, 1000]}, {"c": "m", "xz": [1500, -300, 1500, 300]}]})
	_check(m.map_ready and m.cursor == Vector2(0, 1000), "curseur accroché à la route la plus proche : %s" % str(m.cursor))
	m.handle("RIGHT_SHORT")
	_check(m.cursor.x == 100.0 and m.cursor.y == 1000.0, "droite : 100 m vers l'est, sur la route")
	m.handle("MINUS_SHORT")
	_check(m.cursor.y == 1000.0, "nord : la route reste la plus proche, curseur toujours dessus")
	m.cursor = Vector2(1490.0, 0.0)
	m.handle("PLUS_SHORT")
	_check(m.cursor.x == 1500.0, "curseur près de la route nord-sud : accroché à x = 1500 (%s)" % str(m.cursor))
	m.cursor = Vector2(0, 1000)
	act = m.handle("A_SHORT")
	_check(act.is_empty() and m.state == "setup", "A : réglage du cap")
	for i in range(6):
		m.handle("RIGHT_SHORT")
	_check(m.heading_deg == 90.0, "six pas de 15° : cap 90°")
	act = m.handle("A_SHORT")
	_check(act["action"] == "start_open_world", "A : départ")
	var a: Dictionary = act["args"]
	var expected_lat := 44.174 - 1000.0 / 111320.0
	_check(absf(a["lat"] - expected_lat) < 2e-6 and absf(a["lon"] - 5.2788) < 2e-6, "lat et lon du point choisi : %s" % str(a))
	_check(a["heading_deg"] == 90 and a["nav"] == "ride" and a["seed"] == 0 and not a.has("loop_km") and not a.has("target"),
		"cap 90°, balade, graine, rien d'autre")
	_check(m.state == "loading" and m.is_loading(), "préchargement")

	# Boucle et destination.
	m = Model.new()
	m.handle("A_SHORT")
	m.on_map({"roads": [{"c": "t", "xz": [0, 0, 100, 0]}]})
	m.handle("A_SHORT")
	m.handle("PLUS_SHORT")                  # ligne navigation
	m.handle("RIGHT_SHORT")
	_check(m.nav == "destination", "navigation : destination")
	act = m.handle("A_SHORT")
	_check(act.is_empty() and m.state == "search" and m.search_for_target, "destination sans cible : recherche de la cible")
	m.type_text("co")
	m.on_places([{"name": "Col de la Bonette", "kind": "pass", "lat": 44.32, "lon": 6.8, "cached": true, "source": "base"}])
	m.handle("A_SHORT")
	_check(m.state == "setup" and m.target == {"lat": 44.32, "lon": 6.8}, "cible choisie, retour au réglage")
	act = m.handle("A_SHORT")
	_check(act["args"]["nav"] == "destination" and act["args"]["target"] == {"lat": 44.32, "lon": 6.8}, "départ vers la destination")
	m = Model.new()
	m.handle("A_SHORT")
	m.on_map({"roads": [{"c": "t", "xz": [0, 0, 100, 0]}]})
	m.handle("A_SHORT")
	m.handle("PLUS_SHORT")
	m.handle("RIGHT_SHORT")
	m.handle("RIGHT_SHORT")
	_check(m.nav == "loop", "navigation : boucle")
	m.handle("PLUS_SHORT")
	m.handle("RIGHT_SHORT")
	m.handle("RIGHT_SHORT")
	_check(m.loop_km == 40.0, "longueur de boucle par pas de 5 km : 40")
	act = m.handle("A_SHORT")
	_check(act["args"]["nav"] == "loop" and act["args"]["loop_km"] == 40.0, "départ en boucle de 40 km")

	# Retours.
	m = Model.new()
	m.handle("A_SHORT")
	_check(m.state == "map" and m.handle("A_SHORT").is_empty() and m.state == "map", "A sans routes reçues : on reste sur la carte")
	m.handle("Y_SHORT")
	_check(m.state == "globe", "Y : retour au globe")
	_check(m.handle("Y_SHORT") == {"action": "close"}, "Y sur le globe : fermeture")
	m.handle("A_SHORT")
	m.on_map({"roads": []})
	m.handle("A_SHORT")
	m.handle("A_SHORT")
	m.on_error("world_unavailable", "aucune route à moins de 200 m")
	_check(m.state == "setup" and m.last_error != "", "départ refusé : retour au réglage avec le message")

	# Régions : épinglage.
	m = Model.new()
	m.on_regions([{"id": "provence", "name": "Provence", "pinned": false, "bbox": [4.2, 42.9, 7.7, 45.2]}])
	m.globe_lat = 44.0
	m.globe_lon = 5.0
	_check(m.region_at(44.0, 5.0)["id"] == "provence" and m.region_at(10.0, 10.0).is_empty(), "région sous le centre")
	_check(m.handle("A_LONG") == {"action": "world_pin", "region_id": "provence", "pinned": true}, "appui long : épingler")
	m.on_regions([{"id": "provence", "name": "Provence", "pinned": true, "bbox": [4.2, 42.9, 7.7, 45.2]}])
	_check(m.handle("A_LONG")["pinned"] == false, "déjà épinglée : libérer")
	m.globe_lat = 10.0
	_check(m.handle("A_LONG").is_empty(), "hors région : rien")

	# Préchargement.
	m = Model.new()
	m.state = "loading"
	_check(m.loading_text() == "Préparation du monde…" and m.loading_fraction() == 0.0, "préchargement : attente")
	m.on_status({"phase": "dem", "done_bytes": 12_000_000, "total_bytes": 48_000_000, "squares_ready": 3, "squares_needed": 9, "message": "relief"})
	_check(m.loading_text() == "12 Mo / 48 Mo — 3 / 9 carrés — relief", "texte : %s" % m.loading_text())
	_check(absf(m.loading_fraction() - 0.25) < 1e-9, "barre à 25 %")
	m.on_status({"phase": "generate", "done_bytes": 0, "total_bytes": null, "squares_ready": 3, "squares_needed": 12, "message": ""})
	_check(absf(m.loading_fraction() - 0.25) < 1e-9 and m.loading_text() == "3 / 12 carrés", "sans total d'octets : carrés prêts")
	_check(m.handle("Y_SHORT") == {"action": "cancel_loading"}, "Y pendant le préchargement : annulation demandée")

	_test_last_start()
	print("test_world_menu_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


## Dernier départ du profil (lot O32) : globe centré dessus, mêmes cap, navigation et boucle ; A, A, A le relance.
func _test_last_start() -> void:
	var m = Model.new()
	m.set_last_start({"lat": 48.9, "lon": 7.05, "heading_deg": 90, "nav": "loop", "loop_km": 40})
	m.reset()
	_check(absf(m.globe_lat - 48.9) < 1e-9 and absf(m.globe_lon - 7.05) < 1e-9, "globe centré sur le dernier départ")
	_check(m.heading_deg == 90.0 and m.nav == "loop" and m.loop_km == 40.0, "cap, navigation et boucle repris")
	m.handle("A_SHORT")   # carte au centre du globe
	m.on_map({"lat": 48.9, "lon": 7.05, "roads": []})
	m.state = "setup"
	var act: Dictionary = m.handle("A_SHORT")
	var args: Dictionary = act.get("args", {})
	_check(act.get("action", "") == "start_open_world" and absf(float(args["lat"]) - 48.9) < 1e-6
		and args["nav"] == "loop" and args["loop_km"] == 40.0, "même départ relancé")
	m.set_last_start({"lat": 10.0, "lon": 20.0, "nav": "destination"})   # destination sans cible : balade
	m.reset()
	_check(m.nav == "ride" and m.target == null, "destination sans cible : retour à la balade")
	m.set_last_start(null)
	m.reset()
	_check(m.nav == "ride", "aucun départ gardé : valeurs par défaut")
