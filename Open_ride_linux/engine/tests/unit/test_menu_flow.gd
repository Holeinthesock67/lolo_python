extends SceneTree

## Tests sans écran du déroulé des menus `menu_flow.gd` et de leur affichage (Lot N6).
## Lancement : godot --headless --path engine --script res://tests/unit/test_menu_flow.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuView := preload("res://scripts/menu_view.gd")
const MenuModel := preload("res://scripts/menu_model.gd")

const ROUTES := [
	{"id": "demo", "name": "Démo", "length_m": 4000.0, "is_loop": true, "status": "ready"},
	{"id": "vosges", "name": "Vosges", "length_m": 32000.0, "is_loop": false, "status": "ready"},
	{"id": "nouveau", "name": "Nouveau GPX", "length_m": 12000.0, "status": "to_compile"},
]
const WORKOUTS := [{"id": "sweet", "name": "Sweet spot", "duration_s": 3600, "selectable": true}]

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _ids(f) -> Array:
	return f.state()["items"].map(func(it): return it["id"])


func _focus_id(f) -> String:
	var st: Dictionary = f.state()
	return "" if st["focus"] < 0 else str(st["items"][st["focus"]]["id"])


func _test_full_session() -> void:
	var f = MenuFlow.new()
	f.connect_done = true   # écran de connexion : _test_connect_screen
	_check(not f.is_visible(), "menu caché avant le premier état")
	_check(f.handle("A_LONG").is_empty(), "aucune action sans état")
	var acts: Array = f.on_state({"session_state": "IDLE"})
	_check(acts == [{"action": "list"}], "listes demandées au premier état visible")
	_check(f.on_state({"session_state": "IDLE"}).is_empty(), "listes demandées une seule fois")
	f.set_routes(ROUTES)
	f.set_workouts(WORKOUTS)
	_check(f.is_visible() and f.state()["screen"] == "home", "accueil affiché en IDLE")
	_check(f.state()["items"][0]["label"] == "Parcours : à choisir", "accueil : parcours à choisir")
	f.handle("A_LONG")   # Parcours
	_check(f.state()["screen"] == "routes", "liste des parcours")
	var routes: Array = f.state()["items"]
	var to_compile: Array = routes.filter(func(it): return it["id"] == "nouveau")
	_check(to_compile.size() == 1 and not to_compile[0]["enabled"] and to_compile[0]["detail"] != "",
			"parcours à compiler désactivé avec sa raison (critère 3)")
	f.handle("PLUS_SHORT")   # 2ᵉ parcours
	var sel: Dictionary = f.handle("A_LONG")
	_check(sel.get("action") == "select_route" and sel.get("route_id") == _ids_route(routes, 1),
			"2ᵉ parcours choisi : select_route %s" % str(sel))
	_check(f.state()["screen"] == "home" and f.state()["items"][0]["label"] == "Parcours : Vosges",
			"retour à l'accueil, monde affiché : %s" % f.state()["items"][0]["label"])
	f.on_state({"session_state": "READY", "route_id": "vosges"})
	f.handle("PLUS_SHORT")
	f.handle("PLUS_SHORT")   # Session ERG
	f.handle("A_LONG")
	_check(f.state()["screen"] == "workouts", "Session ERG : liste des entraînements")
	f.handle("PLUS_SHORT")
	var wk: Dictionary = f.handle("A_LONG")
	_check(wk == {"action": "select_workout", "workout_id": "sweet"}, "entraînement choisi : %s" % str(wk))
	_check(f.state()["screen"] == "ready" and "ERG" in f.state()["title"] and "Vosges" in f.state()["title"],
			"écran Prêt : %s" % f.state()["title"])
	_check(f.handle("A_LONG") == {"action": "start"}, "Démarrer")
	f.on_state({"session_state": "RUNNING"})
	_check(not f.is_visible(), "menu caché en RUNNING")
	_check(f.handle("A_LONG").is_empty(), "en RUNNING, les appuis ne naviguent pas")
	f.on_state({"session_state": "PAUSED"})
	_check(f.is_visible() and f.state()["screen"] == "pause" and _focus_id(f) == "resume",
			"pause : écran de pause, focus sur Reprendre")
	_check(f.handle("A_LONG") == {"action": "resume"}, "Reprendre")
	f.on_state({"session_state": "RUNNING"})
	f.on_state({"session_state": "PAUSED"})
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "end_session", "save": true}, "Terminer et enregistrer")
	f.on_state({"session_state": "FINISHED", "summary": {"duration_s": 300.0, "distance_m": 2500.0}})
	_check(f.state()["screen"] == "summary" and f.summary.get("distance_m") == 2500.0, "bilan affiché en FINISHED")
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG").is_empty() and f.show_details, "Voir le bilan détaillé")
	f.handle("MINUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "list", "route_id": "vosges"} and f.state()["screen"] == "home",
			"Nouvelle séance : accueil, listes redemandées et monde rechargé")
	_check(f.state()["items"][0]["label"] == "Parcours : Vosges", "le parcours reste choisi après la séance")
	f.on_state({"session_state": "FINISHED"})
	f.handle("MINUS_SHORT")   # Quitter (dernier élément de l'accueil)
	f.handle("A_LONG")
	_check(f.state()["screen"] == "confirm" and _focus_id(f) == "no", "Quitter demande confirmation, focus sur Non")
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "quit"}, "Oui : quitter")


func _ids_route(items: Array, index: int) -> String:
	return str(items[index]["id"])


func _test_abandon_and_summary_quit() -> void:
	var f = MenuFlow.new()
	f.connect_done = true   # écran de connexion : _test_connect_screen
	_check(f.on_state({"session_state": "RUNNING"}) == [{"action": "list"}],
			"listes demandées même en RUNNING (profils des blocs ERG avec --autostart)")
	f.on_state({"session_state": "PAUSED"})
	f.handle("PLUS_SHORT")   # Terminer et enregistrer
	f.handle("PLUS_SHORT")   # Abandonner (avant les lignes modifiables de la pause, lot O18)
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "end_session", "save": false}, "Abandonner après confirmation")
	f.on_state({"session_state": "IDLE"})
	_check(f.state()["screen"] == "home", "séance abandonnée sans bilan : accueil")
	f.on_state({"session_state": "RUNNING"})
	f.on_state({"session_state": "FINISHED", "summary": {}})
	f.handle("MINUS_SHORT")   # Quitter depuis le bilan
	f.handle("A_LONG")
	_check(f.state()["screen"] == "confirm", "Quitter depuis le bilan : confirmation")
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "quit"}, "Quitter depuis le bilan")
	f.list_failed("routes")
	var g = MenuFlow.new()
	g.connect_done = true
	g.on_state({"session_state": "IDLE"})
	g.list_failed("routes")
	g.handle("A_LONG")
	var items: Array = g.state()["items"]
	_check(items.size() == 3 and not items[0]["enabled"] and items[1]["id"] == "_add_route",
		"liste indisponible : élément désactivé, aide de fin de liste gardée")
	g.lists_needed()
	_check(g.on_state({"session_state": "IDLE"}) == [{"action": "list"}], "core relancé : listes redemandées")


func _test_view() -> void:
	var f = MenuFlow.new()
	f.connect_done = true   # écran de connexion : _test_connect_screen
	f.on_state({"session_state": "IDLE"})
	var many: Array = []
	for i in range(9):
		many.append({"id": "r%d" % i, "name": "Parcours %d" % i, "length_m": 1000.0 * (i + 1), "status": "ready"})
	for extra in ["9b", "9c"]:   # la liste dépasse la fenêtre de MAX_VISIBLE_ITEMS éléments
		many.append({"id": "r" + extra, "name": "Parcours " + extra, "length_m": 20000.0, "status": "ready"})
	f.set_routes(many)
	var v = MenuView.new()
	var state := {"session_state": "IDLE", "trainer_status": "MOCK", "input_status": "KEYBOARD"}
	v.update_display(f.state(), state, {}, false)
	_check(v.title_label.text == "OpenRide" and v.items_text().begins_with("[Parcours : "), "accueil : %s" % v.items_text())
	_check(v.devices.visible and v.devices.text().contains("Trainer"), "état des appareils : %s" % v.devices.text())
	f.handle("A_LONG")
	for i in range(7):
		f.handle("PLUS_SHORT")
	v.update_display(f.state(), state, {}, false)
	var shown := v.items_text().split(" | ")
	_check(shown.size() == MenuView.MAX_VISIBLE_ITEMS and v.items_text().contains("[Parcours 7"),
			"longue liste : fenêtre autour du focus (%s)" % v.items_text())
	_check(v.more_label.text == "8 / 14", "position dans la liste (tri puis aide en dernier) : %s" % v.more_label.text)
	f.on_state({"session_state": "RUNNING"})
	f.on_state({"session_state": "FINISHED", "summary": {"duration_s": 1800.0, "distance_m": 15000.0,
			"avg_power_w": 210.0, "fit_path": "/x/y/seance.fit", "blocks": [[1, 200.0, 200.0], [2, 260.0, 230.0]]}})
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")   # détails
	v.update_display(f.state(), state, f.summary, f.show_details)
	_check(v.summary.visible and not v.devices.visible and v.summary.text().contains("Distance : 15,00 km"),
			"bilan : %s" % v.summary.text())
	_check(v.summary.fit_label.text.contains("seance.fit"), "fichier FIT : %s" % v.summary.fit_label.text)
	_check(v.summary.blocks_box.get_child_count() == 2, "bilan détaillé : un bloc par ligne")
	v.free()


const DEV_ALL := {"trainer": {"status": "CONNECTED", "name": "HomeTrainer 0001", "address": null},
	"click": [{"side": "plus", "status": "CONNECTED", "battery_pct": 80},
		{"side": "minus", "status": "CONNECTED", "battery_pct": 70}],
	"hr": {"status": "NONE", "source": null, "battery_pct": null}}


func _dev(minus_status: String, trainer_status := "CONNECTED") -> Dictionary:
	var d: Dictionary = DEV_ALL.duplicate(true)
	d["click"][1]["status"] = minus_status
	d["trainer"]["status"] = trainer_status
	return d


func _test_connect_screen() -> void:
	var f = MenuFlow.new()
	f.on_state({"session_state": "IDLE", "trainer_status": "SEARCHING", "devices": _dev("SEARCHING", "SEARCHING")}, 10.0)
	_check(f.state()["screen"] == "connect", "écran de connexion des appareils au premier état")
	_check(_focus_id(f) == "continue" and f.state()["items"][0]["label"] == "Passer"
			and "trainer" in f.state()["items"][0]["detail"], "« Passer » nomme ce qui manque : %s" % str(f.state()["items"][0]))
	# Trainer relié, un seul boîtier : passage unilatéral proposé, pas d'attente.
	f.on_state({"session_state": "IDLE", "trainer_status": "CONNECTED", "devices": _dev("SEARCHING")}, 11.0)
	_check(f.state()["items"][0]["detail"] == "un seul boîtier du Click", "Passer : un seul boîtier du Click")
	f.on_state({"session_state": "IDLE", "trainer_status": "CONNECTED"}, 30.0)   # trame sans `devices`
	_check(f.state()["screen"] == "connect", "trame sans devices : dernier objet gardé, on attend toujours")
	_check(f.with_devices({"session_state": "IDLE"}).has("devices"), "with_devices complète la trame")
	f.handle("A_LONG")   # Passer
	_check(f.state()["screen"] == "home" and f.connect_done, "Passer : accueil")
	# Tout relié : accueil seul après CONNECT_HOLD_S.
	var g = MenuFlow.new()
	g.on_state({"session_state": "IDLE", "trainer_status": "CONNECTED", "devices": DEV_ALL}, 5.0)
	_check(g.state()["screen"] == "connect" and g.state()["items"][0]["label"] == "Continuer", "tout relié : « Continuer », écran encore visible")
	g.on_state({"session_state": "IDLE", "trainer_status": "CONNECTED"}, 5.0 + MenuFlow.CONNECT_HOLD_S + 0.1)
	_check(g.state()["screen"] == "home", "tout relié depuis %.0f s : accueil" % MenuFlow.CONNECT_HOLD_S)
	_check(g.on_state({"session_state": "IDLE"}, 100.0).is_empty() and g.state()["screen"] == "home", "plus d'écran de connexion ensuite")
	# Séance déjà en cours au premier état (--autostart, reprise) : pas d'écran de connexion.
	var h = MenuFlow.new()
	h.on_state({"session_state": "RUNNING"}, 1.0)
	h.on_state({"session_state": "PAUSED"}, 2.0)
	_check(h.connect_done and h.state()["screen"] == "pause", "autostart : pas d'écran de connexion")
	# Rechercher et appairer depuis la connexion, puis retour.
	var k = MenuFlow.new()
	k.on_state({"session_state": "IDLE", "trainer_status": "SEARCHING", "devices": _dev("SEARCHING", "SEARCHING")}, 1.0)
	k.handle("PLUS_SHORT")
	var act: Dictionary = k.handle("A_LONG")
	_check(act.get("action") == "scan_devices" and k.state()["screen"] == "pairing", "Rechercher et appairer : écran Appareils et recherche")
	k.handle("Y_SHORT")
	_check(k.state()["screen"] == "connect", "retour à la connexion")
	k.handle("PLUS_SHORT")   # Quitter
	k.handle("A_LONG")
	_check(k.state()["screen"] == "confirm", "Quitter passe par la confirmation")


func _test_pairing_screen() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	f.handle("MINUS_SHORT")
	f.handle("MINUS_SHORT")   # Réglages (avant Quitter)
	f.handle("A_LONG")
	_check(f.state()["screen"] == "settings" and _focus_id(f) == "devices", "Réglages : Appareils")
	var act: Dictionary = f.handle("A_LONG")
	_check(act.get("action") == "scan_devices" and f.state()["screen"] == "pairing", "Réglages → Appareils : recherche lancée")
	_check(_focus_id(f) == "back", "recherche en cours : seul Retour est actif (%s)" % _focus_id(f))
	f.on_scan_results({"type": "scan_results", "request_cmd_id": 3, "done": true, "plus_address": null, "items": [
		{"role": "trainer", "name": "HomeTrainer 0001", "address": "AA:00:00:00:00:01", "rssi": -50, "configured": false},
		{"role": "click", "name": "Zwift Click", "address": "C1:1C:00:00:00:01", "rssi": -40, "configured": false},
		{"role": "click", "name": "Zwift Click", "address": "C1:1C:00:00:00:02", "rssi": -45, "configured": false}]})
	var labels: Array = f.state()["items"].map(func(it): return it["label"])
	_check("Trainer" in labels and f.state()["items"][labels.find("Trainer")]["detail"] == "HomeTrainer 0001",
		"trainer trouvé choisi : %s" % str(labels))
	f.menu.handle("PLUS_SHORT")
	while _focus_id(f) != "identify":
		f.handle("PLUS_SHORT")
	act = f.handle("A_LONG")
	_check(act.get("action") == "identify_click_plus", "identification du +")
	f.pairing.identify_cmd_id = 7
	f.on_scan_results({"type": "scan_results", "request_cmd_id": 7, "done": true, "plus_address": "C1:1C:00:00:00:02",
		"items": f.pairing.items})
	_check(f.pairing.choice["click_plus"] == "C1:1C:00:00:00:02" and f.pairing.choice["click_minus"] == "C1:1C:00:00:00:01",
			"+ reconnu, l'autre boîtier devient −")
	while _focus_id(f) != "save":
		f.handle("PLUS_SHORT")
	f.handle("A_LONG")
	_check(f.state()["screen"] == "confirm" and "trainer HomeTrainer 0001" in f.state()["title"], "confirmation avec les changements : %s" % f.state()["title"])
	f.handle("PLUS_SHORT")   # Oui
	act = f.handle("A_LONG")
	_check(act.get("action") == "pair_devices" and act["args"]["trainer"] == "AA:00:00:00:00:01"
			and act["args"]["click_plus"] == "C1:1C:00:00:00:02" and act["args"]["hr"] == null, "pair_devices : %s" % str(act))
	_check(f.state()["screen"] == "pairing", "retour à l'écran Appareils après Oui")
	f.on_command_acked("pair_devices")
	_check(f.state()["items"].any(func(it): return it["id"] == "relaunch"), "enregistré : Relancer OpenRide proposé")
	while _focus_id(f) != "relaunch":
		f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG").get("action") == "relaunch", "Relancer : action relaunch")
	f.on_error("pairing_failed", "adresse mal formée")
	_check(not f.pairing.saved and "refusé" in f.pairing.message, "pairing_failed affiché")


func _test_settings_screen() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE", "difficulty_pct": 50})
	f.on_settings({"type": "settings", "request_cmd_id": 2, "items": [
		{"key": "rider.ftp_w", "label": "FTP", "group": "rider", "type": "int", "value": 250, "min": 50, "max": 600,
			"step": 5, "unit": "W", "applies": "next_session"},
		{"key": "trainer.difficulty_pct", "label": "Difficulté en SIM", "group": "ride", "type": "int", "value": 50,
			"min": 0, "max": 100, "step": 10, "unit": "%", "applies": "next_session"},
		{"key": "render.quality", "label": "Qualité graphique", "group": "graphics", "type": "choice", "value": "high",
			"choices": ["low", "medium", "high"], "applies": "now"},
		{"key": "wind.from_deg", "label": "Direction du vent", "group": "wind", "type": "int", "value": 270, "min": 0,
			"max": 360, "step": 45, "unit": "°", "applies": "next_session"},
		{"key": "futur.reglage", "label": "Réglage futur", "type": "int", "value": 1, "min": 0, "max": 2, "step": 1,
			"unit": "", "applies": "next_session"}]})
	f.handle("MINUS_SHORT")
	f.handle("MINUS_SHORT")
	f.handle("A_LONG")   # Réglages
	var labels: Array = f.state()["items"].map(func(it): return it["label"])
	_check(labels == ["Appareils : rechercher et appairer", "Cycliste", "Séance", "Graphisme", "Vent",
			"Autres réglages", "OpenRide " + f.engine_version], "réglages rangés en sous-écrans : %s" % str(labels))
	_check(f.state()["items"][1]["detail"] == "FTP", "détail d'un sous-écran : ses réglages")
	_check(f.state()["items"][-1]["enabled"] == false, "ligne de version non sélectionnable")
	# Version du core différente : alerte discrète dans le détail de la ligne (lots O2 et O4).
	f.set_versions("0.9.0", "0.9.0")
	_check(f.state()["items"][-1]["label"] == "OpenRide 0.9.0" and f.state()["items"][-1]["detail"] == "",
			"même version : « OpenRide 0.9.0 », sans alerte")
	f.set_versions("0.9.0", "0.8.0")
	_check(str(f.state()["items"][-1]["detail"]).begins_with("core 0.8.0 : versions différentes"),
			"versions différentes : %s" % str(f.state()["items"][-1]["detail"]))
	f.set_versions("0.9.0", "")
	_check(f.state()["items"][-1]["detail"] == "", "core pas encore connu : pas d'alerte")
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")   # Cycliste
	_check(f.state()["screen"] == "settings_group" and f.state()["title"] == "Réglages › Cycliste"
			and f.state()["items"].map(func(it): return it["label"]) == ["FTP"] and f.state()["items"][0]["detail"] == "250 W",
			"sous-écran Cycliste : libellé à gauche, valeur à droite")
	_check(f.state()["card"]["name"] == "FTP" and f.state()["card"]["lines"] == ["S'applique à la séance suivante"],
			"carte du réglage sous le focus (%s)" % str(f.state()["card"]))
	f.handle("A_LONG")   # FTP : modification en place, pas d'autre écran
	_check(f.state()["screen"] == "settings_group" and f.state()["editing"] and f.state()["items"][0]["detail"] == "◀ 250 W ▶"
			and f.state()["items"][0]["editing"], "modification de la FTP dans la liste")
	for i in range(3):
		f.handle("PLUS_SHORT")
	_check(f.state()["items"][0]["detail"] == "◀ 265 W ▶", "+ trois fois : 265 W (%s)" % f.state()["items"][0]["detail"])
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "set_setting", "key": "rider.ftp_w", "value": 265} and f.state()["screen"] == "settings_group"
			and not f.state()["editing"] and f.state()["items"][0]["detail"] == "265 W",
			"A maintenu : set_setting une fois, valeur affichée tout de suite (%s)" % str(act))
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")
	_check(f.handle("Y_SHORT").is_empty() and f.state()["items"][0]["detail"] == "265 W" and f.state()["screen"] == "settings_group",
			"Y annule et rend la valeur d'avant")
	f.handle("Y_SHORT")   # retour aux Réglages, focus sur Cycliste
	_check(f.state()["screen"] == "settings" and _focus_id(f) == "group:rider", "retour aux Réglages sur Cycliste")
	f.handle("PLUS_SHORT")
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")   # Graphisme
	f.handle("A_LONG")   # Qualité
	f.handle("PLUS_SHORT")
	_check(f.state()["items"][0]["detail"] == "◀ low ▶", "choix en boucle : high → low")
	_check(f.handle("Y_SHORT").is_empty() and f.state()["screen"] == "settings_group", "Y : annulé")
	f.handle("Y_SHORT")
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")   # Vent
	_check(f.state()["items"][0]["label"] == "Direction du vent" and f.state()["items"][0]["detail"] == "270° (ouest)",
			"direction avec le point cardinal (%s)" % f.state()["items"][0]["detail"])
	f.handle("Y_SHORT")
	# Curseur de difficulté sur l'écran de pause : set_difficulty, sans config.toml.
	f.on_state({"session_state": "RUNNING", "difficulty_pct": 50})
	f.on_state({"session_state": "PAUSED", "difficulty_pct": 50})
	f.handle("MINUS_SHORT")   # dernière ligne : mode de la session libre (lot O18)
	f.handle("MINUS_SHORT")
	_check(_focus_id(f) == "difficulty" and f.state()["items"][3]["detail"] == "50 %" and f.state()["items"][3]["bar"] == 50,
			"pause : curseur de difficulté")
	f.handle("A_LONG")
	f.handle("MINUS_SHORT")
	f.handle("MINUS_SHORT")
	act = f.handle("A_LONG")
	_check(act == {"action": "set_difficulty", "pct": 30} and f.state()["screen"] == "pause"
			and f.state()["items"][3]["detail"] == "30 %" and not f.state()["items"][3]["editing"], "pause : set_difficulty à 30 (%s)" % str(act))


func _test_erg_submenu() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE", "route_id": "vosges"})
	f.set_workouts([{"id": "seuil", "name": "Seuil", "duration_s": 3600}])
	f.handle("PLUS_SHORT")
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")   # Session ERG
	_check(_ids(f) == ["_sim", "seuil", "_create", "_import"], "sous-menu ERG : liste puis Créer et Importer (%s)" % str(_ids(f)))
	f.handle("MINUS_SHORT")
	f.handle("MINUS_SHORT")
	_check(_focus_id(f) == "_create", "focus sur Créer un entraînement")
	_check(f.handle("A_LONG").is_empty() and f.state()["screen"] == "workout_create", "écran Créer un entraînement")
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")   # Répétitions
	_check(f.state()["screen"] == "workout_create" and f.state()["items"][1]["detail"] == "◀ 5 ▶",
		"modification des répétitions en place")
	f.handle("PLUS_SHORT")
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG").is_empty() and f.state()["screen"] == "workout_create" and not f.state()["editing"],
		"A long : valeur gardée dans l'écran Créer")
	_check(f.state()["items"][1]["detail"] == "7", "7 répétitions (%s)" % f.state()["items"][1]["detail"])
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")   # Effort
	f.handle("PLUS_SHORT")
	_check(f.state()["items"][2]["detail"] == "◀ 4 min 15 s ▶", "effort par pas de 15 s (%s)" % f.state()["items"][2]["detail"])
	f.handle("Y_SHORT")  # annulé
	f.handle("MINUS_SHORT")
	f.handle("MINUS_SHORT")
	f.handle("MINUS_SHORT")
	_check(_focus_id(f) == "save", "focus sur Enregistrer")
	var act: Dictionary = f.handle("A_LONG")
	_check(act.get("action", "") == "create_workout" and act["args"]["reps"] == 7 and act["args"]["on_s"] == 240,
		"create_workout avec les sept paramètres : %s" % str(act.get("args", {})))
	f.on_error("bad_args", "reps hors bornes")
	_check(f.state()["screen"] == "workout_create" and f.state()["status"] == "Échec : reps hors bornes",
		"erreur du core sur l'écran Créer")
	var saved := {"type": "workout_saved", "request_cmd_id": 9, "workout_id": "intervalles_7x240s_105",
		"name": "Intervalles 7 × 4 min à 105 %", "created": true}
	_check(f.on_workout_saved(saved) and not f.on_workout_saved(saved), "réponse en double (copie renvoyée) ignorée")
	_check(f.state()["screen"] == "workouts" and f.state()["status"] == "Créé : Intervalles 7 × 4 min à 105 %",
		"retour à la liste, ligne d'état (%s)" % f.state()["status"])
	f.set_workouts([{"id": "intervalles_7x240s_105", "name": "Intervalles", "duration_s": 3540},
		{"id": "seuil", "name": "Seuil", "duration_s": 3600}])
	_check(_focus_id(f) == "intervalles_7x240s_105", "focus sur l'entraînement créé à l'arrivée de la liste")
	act = f.handle("A_LONG")
	_check(act == {"action": "select_workout", "workout_id": "intervalles_7x240s_105"} and f.state()["screen"] == "ready",
		"entraînement créé choisi : écran Prêt")
	# Import.
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")   # Changer d'entraînement
	_check(_focus_id(f) == "intervalles_7x240s_105", "liste ouverte sur le dernier entraînement choisi (lot O32)")
	f.menu.focus_item("_import")
	_check(_focus_id(f) == "_import", "focus sur Importer")
	_check(f.handle("A_LONG") == {"action": "list_imports"} and f.state()["screen"] == "workout_import", "list_imports")
	f.set_import_candidates([])
	_check(f.state()["focus"] == -1 and f.state()["items"][0]["label"] == "Aucun fichier .zwo, .erg ou .mrc", "aucun fichier")
	f.set_import_candidates([{"path": "/x/Téléchargements/vo2.zwo", "file": "vo2.zwo", "source": "Téléchargements",
		"imported": false}, {"path": "/x/b.erg", "file": "b.erg", "source": "Bureau", "imported": true}])
	_check(f.state()["items"][1]["detail"] == "Bureau, déjà importé", "fichier déjà importé signalé")
	_check(f.handle("A_LONG") == {"action": "import_workout", "path": "/x/Téléchargements/vo2.zwo"}, "import_workout")
	f.on_error("workout_invalid", "vo2.zwo : aucun bloc reconnu")
	_check(f.state()["status"] == "Échec : vo2.zwo : aucun bloc reconnu" and f.state()["screen"] == "workout_import",
		"échec affiché")
	f.list_failed("imports")
	_check(f.state()["items"][0]["label"] == "Fichiers à importer indisponibles", "imports sans réponse")
	f.on_workout_saved({"request_cmd_id": 12, "workout_id": "vo2", "name": "VO2", "created": false})
	_check(f.state()["status"] == "Importé : VO2 (déjà présent)", "import : ligne d'état (%s)" % f.state()["status"])
	f.set_workouts([{"id": "vo2", "name": "VO2", "duration_s": 0, "selectable": false, "error": "aucun bloc reconnu"}])
	_check(f.state()["screen"] == "workouts" and _focus_id(f) != "vo2", "import invalide : désactivé, pas de focus")

const DAY := {"week": 1, "day": "jour1", "date": "2026-10-27", "workout": "ss", "name": "Sweet spot",
	"duration_s": 2700.0, "tss": 60.8, "done": false}
const NEXT := {"week": 1, "day": "jour3", "date": "2026-10-29", "workout": "ftp_test:ramp",
	"name": "Test de FTP : rampe", "duration_s": 1500.0, "tss": 30.0, "done": false}
const PLAN_ITEMS := [{"id": "casse", "name": "casse", "weeks": 0, "sessions": 0, "active": false, "error": "TOML illisible"},
	{"id": "essai", "name": "Essai", "weeks": 4, "sessions": 8, "active": false, "error": null}]


func _plans_msg(active) -> Dictionary:
	var items: Array = PLAN_ITEMS.duplicate(true)
	items[1]["active"] = active != null
	return {"type": "plans", "v": 1, "request_cmd_id": 1, "items": items, "truncated": false, "active": active}


## Plans d'entraînement depuis le menu (lot O12, critère 2) : choisir, démarrer, séance du jour, arrêter.
func _test_plans() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE", "route_id": "vosges"})
	f.set_routes(ROUTES)
	_check(f.state()["items"][3]["label"] == "Choisir un plan", "accueil sans plan : Choisir un plan")
	for i in range(3):
		f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "list_plans"} and f.state()["screen"] == "plans", "écran Plans, list_plans")
	_check(f.state()["items"][0]["label"] == "Recherche des plans…", "en attendant la réponse")
	f.on_plans(_plans_msg(null))
	_check(_ids(f) == ["plan:casse", "plan:essai"] and _focus_id(f) == "plan:essai",
		"liste des plans, plan invalide désactivé (%s)" % str(_ids(f)))
	_check(f.state()["items"][1]["detail"] == "4 semaines, 8 séances", "plan : semaines et séances")
	f.handle("A_LONG")
	_check(f.state()["screen"] == "plan" and f.state()["title"] == "Essai" and _focus_id(f) == "start", "écran du plan")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "start_plan", "id": "essai", "start_date": null} and f.state()["screen"] == "plans",
		"start_plan, retour à la liste (%s)" % str(act))
	_check(f.state()["status"] == "Démarrage du plan…", "ligne d'état pendant la demande")
	var active := {"id": "essai", "name": "Essai", "start": "2026-10-27", "week": 1, "weeks": 4, "finished": false,
		"done": 0, "total": 8, "done_pct": 0.0, "today": [DAY], "late": [], "next": NEXT, "plan_day": "ss"}
	f.on_plans(_plans_msg(active))
	_check(f.state()["status"] == "Plan démarré : Essai", "plan démarré (%s)" % f.state()["status"])
	_check(_ids(f) == ["today", "progress", "next", "stop", "plan:casse", "plan:essai"], "suivi du plan actif (%s)" % str(_ids(f)))
	_check(f.state()["items"][1]["detail"] == "semaine 1 / 4, 0 % fait (0 / 8)", "progression : %s" % f.state()["items"][1]["detail"])
	f.menu.focus_item("today")
	_check(f.state()["card"]["title"] == "Séance du jour" and f.state()["card"]["name"] == "Sweet spot"
		and f.state()["card"]["tiles"][0]["value"] == "45 min", "plans : carte de la séance du jour (%s)" % str(f.state()["card"].get("tiles")))
	f.menu.focus_item("stop")
	_check(f.state()["card"]["title"] == "Plan en cours" and f.state()["card"]["tiles"][0]["value"] == "1 / 4",
		"plans : carte du plan en cours")
	f.menu.focus_item("plan:essai")
	_check(f.state()["card"]["name"] == "Essai" and f.state()["card"]["tiles"][2]["label"] == "Fait", "plans : carte d'un plan")
	f.handle("Y_SHORT")
	var home: Dictionary = f.state()["items"][3]
	_check(home["label"] == "Séance du jour : Sweet spot" and home["detail"] == "45 min, TSS 61",
		"accueil : séance du jour, durée et TSS (%s, %s)" % [home["label"], home["detail"]])
	_check(f.handle("A_LONG").is_empty() and f.state()["screen"] == "ready"
		and f.state()["title"] == "Prêt : séance du jour (Sweet spot) — Vosges", "séance du jour : écran Prêt (%s)" % f.state()["title"])
	_check(f.handle("A_LONG") == {"action": "start", "args": {"plan_day": true}}, "start avec plan_day")
	f.on_state({"session_state": "RUNNING", "route_id": "vosges"})
	f.on_state({"session_state": "FINISHED", "route_id": "vosges", "summary": {"duration_s": 2700.0}})
	_check(f.handle("A_LONG") == {"action": "list", "route_id": "vosges"}, "nouvelle séance : listes (plans compris) redemandées")
	var done: Dictionary = active.duplicate(true)
	done["today"][0]["done"] = true
	done["done"] = 1
	done["done_pct"] = 12.5
	done["plan_day"] = null
	f.on_plans(_plans_msg(done))
	_check(f.state()["items"][3]["label"] == "Plan : Essai" and f.state()["items"][3]["detail"] == "semaine 1 / 4, 13 % fait (1 / 8)",
		"séance comptée : %s" % f.state()["items"][3]["detail"])
	for i in range(3):
		f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "list_plans"} and _focus_id(f) == "stop", "sans séance du jour : écran Plans")
	f.handle("A_LONG")
	_check(f.state()["screen"] == "confirm" and f.state()["title"] == "Arrêter le plan Essai ?", "arrêt confirmé")
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "stop_plan"} and f.state()["screen"] == "plans", "stop_plan")
	f.on_error("busy", "séance en cours")
	_check(f.state()["status"] == "Échec : séance en cours", "erreur du core sur la ligne d'état")
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")
	f.on_plans(_plans_msg(null))
	_check(f.state()["status"] == "Plan arrêté" and _ids(f)[0] == "plan:casse", "plan arrêté")


## Test de FTP depuis le menu et acceptation au bilan (lot O12, critère 2).
func _test_ftp_flow() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE", "route_id": "demo"})
	f.set_routes(ROUTES)
	f.on_settings({"items": [{"key": "rider.ftp_w", "value": 250}]})
	for i in range(4):
		f.handle("PLUS_SHORT")
	f.handle("A_LONG")
	_check(f.state()["screen"] == "ftp_test" and _ids(f) == ["ramp"] and f.state()["status"] != "",
		"écran Test de FTP : la rampe seule (lot O19), conseil (%s)" % f.state()["status"])
	_check(f.state()["items"][0]["detail"] == "≈ 22 min"
		and f.state()["card"]["name"] == "Rampe" and f.state()["card"]["tiles"][1]["value"] == "250",
		"test de FTP : durées calculées et carte (%s)" % str(f.state()["items"].map(func(it): return it["detail"])))
	f.handle("A_LONG")
	_check(f.state()["screen"] == "ready" and f.state()["title"].begins_with("Prêt : test de FTP (rampe)"), "rampe : écran Prêt")
	_check(f.handle("A_LONG") == {"action": "start", "args": {"ftp_test": "ramp"}}, "start avec ftp_test")
	f.on_state({"session_state": "RUNNING"})
	var ftp := {"test": "ramp", "ftp_w": 262, "previous_ftp_w": 250, "warnings": ["trainer_dropout"], "reliable": false}
	f.on_state({"session_state": "FINISHED", "summary": {"duration_s": 1500.0, "ftp_test": ftp}})
	_check(f.state()["status"] == "Nouvelle FTP : 262 W (avant 250 W) ; coupure du trainer pendant l'effort",
		"bilan : nouvelle FTP et avertissement (%s)" % f.state()["status"])
	_check(_ids(f) == ["accept_ftp", "keep_ftp", "new_session", "details", "quit"] and _focus_id(f) == "accept_ftp",
		"Accepter / Garder en tête du bilan")
	_check(f.handle("A_LONG") == {"action": "accept_ftp", "force": false}, "accept_ftp")
	f.on_error("ftp_result_doubtful", "résultat douteux")
	_check(f.state()["screen"] == "confirm" and f.state()["title"] == "Résultat douteux : enregistrer 262 W quand même ?",
		"résultat douteux : confirmation")
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "accept_ftp", "force": true} and f.state()["screen"] == "summary",
		"Oui : accept_ftp avec force")
	f.on_settings({"items": [{"key": "rider.ftp_w", "value": 262}]})
	_check(f.state()["status"] == "FTP enregistrée : 262 W" and _ids(f) == ["new_session", "details", "quit"],
		"FTP enregistrée, choix retirés (%s)" % f.state()["status"])
	_check(f.settings.item("rider.ftp_w")["value"] == 262, "nouvelle FTP dans les réglages (O4)")
	# Garder l'ancienne FTP ; test sans FTP calculable.
	f.on_state({"session_state": "RUNNING"})
	f.on_state({"session_state": "FINISHED", "summary": {"ftp_test": ftp}})
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG").is_empty() and f.state()["status"] == "FTP gardée : 250 W" and _ids(f)[0] == "new_session",
		"Garder : FTP inchangée")
	f.on_state({"session_state": "RUNNING"})
	f.on_state({"session_state": "FINISHED", "summary": {"ftp_test": {"test": "ramp", "ftp_w": null,
		"previous_ftp_w": 250, "warnings": ["too_short"], "reliable": false}}})
	_check(f.state()["status"] == "Test de FTP : aucune FTP calculable ; test trop court" and _ids(f)[0] == "new_session",
		"sans FTP calculable : rien à accepter")


## Bibliothèque de parcours (lot O12, critère 3) : filtrer « col », trier par dénivelé, lancer le premier.
func _test_library() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	var lib := [
		{"id": "plat", "name": "Plat", "length_m": 20000.0, "status": "ready", "stats": {"distance_m": 20000.0,
			"gain_m": 40.0, "max_grade_pct": 2.0, "duration_s": 2400.0, "difficulty": 1, "main_climb": null},
			"library": {"description": "", "region": "Alsace", "tags": ["plat"]}},
		{"id": "grand_col", "name": "Grand col", "length_m": 30000.0, "status": "ready", "stats": {"distance_m": 30000.0,
			"gain_m": 900.0, "max_grade_pct": 9.5, "duration_s": 5400.0, "difficulty": 4, "main_climb": {"length_m": 12000.0,
			"gain_m": 850.0, "avg_grade_pct": 7.1, "category": "1"}},
			"library": {"description": "Long col régulier.", "region": "Vosges", "tags": ["col", "montagne"]}},
		{"id": "petit_col", "name": "Petit col", "length_m": 10000.0, "status": "ready", "stats": {"distance_m": 10000.0,
			"gain_m": 300.0, "max_grade_pct": 8.0, "duration_s": 1800.0, "difficulty": 2, "main_climb": {"length_m": 4000.0,
			"gain_m": 280.0, "avg_grade_pct": 7.0, "category": "3"}},
			"library": {"description": "", "region": "Vosges", "tags": ["col"]}},
		{"id": "brut", "name": "Brut", "length_m": 5000.0, "status": "ready"},
	]
	f.set_routes(lib)
	f.handle("A_LONG")   # Parcours
	_check(_ids(f) == ["brut", "grand_col", "petit_col", "plat", "_sort", "_filter", "_add_route", "_route_help"],
		"par nom, puis tri, filtre et aide (%s)" % str(_ids(f)))
	_check(f.state()["items"][1]["label"] == "Grand col (30,0 km, ↑ 900 m)" and f.state()["items"][1]["detail"] == "col, montagne",
		"libellé avec dénivelé, étiquettes (%s — %s)" % [f.state()["items"][1]["label"], f.state()["items"][1]["detail"]])
	f.handle("MINUS_SHORT")   # Comment ça marche ?
	f.handle("MINUS_SHORT")   # Ajouter un parcours
	f.handle("MINUS_SHORT")   # Étiquette
	f.handle("A_LONG")
	_check(_ids(f) == ["grand_col", "petit_col", "_sort", "_filter", "_add_route", "_route_help"]
		and f.state()["items"][3]["label"] == "Étiquette : col"
		and _focus_id(f) == "_filter", "filtre « col », focus gardé (%s)" % str(_ids(f)))
	f.handle("MINUS_SHORT")   # Tri
	f.handle("A_LONG")        # distance
	f.handle("A_LONG")        # dénivelé
	_check(f.state()["items"][2]["label"] == "Trier par : dénivelé" and _ids(f).slice(0, 2) == ["petit_col", "grand_col"],
		"triés par dénivelé (%s)" % str(_ids(f)))
	f.handle("PLUS_SHORT")
	f.handle("PLUS_SHORT")    # Ajouter un parcours
	# Aide des parcours (lot O22) : la carte de la ligne dit où déposer la trace, A maintenu ouvre l'aide.
	_check(_focus_id(f) == "_add_route" and f.state()["card"].get("name") == "Ajouter une trace"
		and str(f.state()["card"]["lines"][0]).contains("~/OpenRide/GPX/"), "« Ajouter un parcours » : carte du dépôt de trace")
	_check(f.handle("A_LONG") == {} and f.state()["screen"] == "route_help" and _focus_id(f) == "help:add",
		"« Ajouter un parcours » ouvre l'aide sur son sujet")
	f.handle("PLUS_SHORT")
	_check(f.state()["card"].get("name") == "Fiche d'un parcours (.toml)" and f.handle("A_LONG") == {}
		and f.state()["screen"] == "route_help", "aide : carte du sujet suivant, A maintenu ne fait rien")
	f.handle("Y_SHORT")
	_check(f.state()["screen"] == "routes", "Y : retour à la liste")
	f.menu.focus_item("_route_help")
	_check(f.state()["card"].get("name") == "Choisir un parcours" and f.handle("A_LONG") == {}
		and _ids(f) == ["help:choose", "help:add", "help:sheet", "help:open_world"], "« Comment ça marche ? » : écran Aide parcours")
	f.handle("Y_SHORT")
	f.menu.focus_item("_route_help")
	f.handle("PLUS_SHORT")    # boucle : premier parcours
	_check(_focus_id(f) == "petit_col", "focus sur le premier")
	_check(f.handle("A_LONG") == {"action": "select_route", "route_id": "petit_col"}, "premier parcours lancé")
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")   # Session libre
	var st: Dictionary = f.state()
	var tiles: Array = st["card"].get("tiles", []).map(func(t): return "%s %s %s" % [t["label"], t["value"], t["unit"]])
	_check(st["screen"] == "ready" and st["card"].get("id") == "petit_col" and st["card"]["title"] == "Parcours",
		"fiche sur l'écran Prêt (%s)" % str(st["card"]))
	_check(tiles == ["Distance 10,0 km", "Dénivelé ↑ 300 m", "Pente max 8,0 %"], "fiche : chiffres clés %s" % str(tiles))
	_check(st["card"]["lines"] == ["Montée principale : 4,0 km à 7,0 %, ↑ 280 m (cat. 3)", "Difficulté 2 / 5 · durée ≈ 30 min",
		"Vosges, col"], "fiche : lignes %s" % str(st["card"]["lines"]))
	f.set_workouts([{"id": "w", "name": "Watts", "duration_s": 600, "unit": "watts", "profile": [[600.0, 0.8, 1.2]]},
		{"id": "r", "name": "Relatif", "duration_s": 900, "profile": [[900.0, 0.8, 0.8]]}])
	f.on_settings({"items": [{"key": "rider.ftp_w", "value": 250}]})
	var w: Array = f.menu._screens["workouts"]["items"].filter(func(it): return it["id"] in ["w", "r"])
	_check(w[0]["detail"] == "watts fixes, jusqu'à 300 W" and w[1]["detail"] == "",
		"entraînement en watts : aperçu en watts (%s)" % w[0]["detail"])
	var v = MenuView.new()
	v.update_display(st, {"session_state": "IDLE"}, {}, false)
	_check(v.card.visible and v.card.text().contains("Distance 10,0 km"), "vue : fiche affichée (%s)" % v.card.text())
	v.free()

## Bots choisis sur l'écran Prêt (lot O7) : `start` avec l'argument `bots`.
func _test_bots_menu() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE", "route_id": "vosges"})
	f.set_routes(ROUTES)
	f.handle("PLUS_SHORT")   # Session libre
	f.handle("A_LONG")
	_check(f.state()["screen"] == "ready" and _ids(f) == ["start", "workout", "change_route", "bot", "ghost", "records"],
		"écran Prêt : bot et fantôme avant les records (%s)" % str(_ids(f)))
	_check(f.state()["items"][3]["label"] == "Bot : aucun" and f.state()["items"][4]["label"] == "Fantôme de la dernière séance : non",
		"par défaut : aucun bot, pas de fantôme")
	_check(f.handle("A_LONG") == {"action": "start"}, "sans bot : start sans argument (les bots de la ligne de commande restent)")
	f.handle("MINUS_SHORT")   # Records (boucle depuis Démarrer)
	f.handle("MINUS_SHORT")   # Fantôme
	_check(_focus_id(f) == "ghost", "focus sur le fantôme")
	f.handle("MINUS_SHORT")   # Bot
	for i in range(4):
		f.handle("A_LONG")
	_check(f.state()["items"][3]["label"] == "Bot : 90 % de la FTP" and f.state()["screen"] == "ready", "A long : bot suivant (%s)" % f.state()["items"][3]["label"])
	f.handle("PLUS_SHORT")
	f.handle("A_LONG")
	_check(f.state()["items"][4]["label"] == "Fantôme de la dernière séance : oui", "fantôme demandé")
	f.handle("MINUS_SHORT")
	f.handle("MINUS_SHORT")
	f.handle("MINUS_SHORT")
	f.handle("MINUS_SHORT")
	_check(_focus_id(f) == "start", "retour sur Démarrer")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "start", "args": {"bots": [{"kind": "constant", "ftp_pct": 90}, {"kind": "ghost"}]}},
		"start avec bot à 90 %% de la FTP et fantôme (%s)" % str(act))
	f.on_error("bot_invalid", "aucune séance passée sur le parcours « vosges » pour le fantôme")
	_check(f.state()["status"].begins_with("Échec : aucune séance passée"), "refus du core sur la ligne d'état")
	f.handle("PLUS_SHORT")
	_check(f.state()["status"] == "", "ligne d'état effacée à l'appui suivant")
	# Un bot de 250 W seul, avec un test de FTP préparé : les deux arguments partent ensemble.
	var g = MenuFlow.new()
	g.connect_done = true
	g.on_state({"session_state": "IDLE", "route_id": "vosges"})
	g.set_routes(ROUTES)
	g.menu.prepare_start("test de FTP (rampe)", {"ftp_test": "ramp"})
	g.menu.bot_choice = 2
	g.menu._refresh_home()
	_check(g.handle("A_LONG") == {"action": "start", "args": {"ftp_test": "ramp", "bots": [{"kind": "constant", "power_w": 250}]}},
		"test de FTP et bot : arguments réunis")
	g.menu.reset()
	_check(g.menu.bot_choice == 2 and not g.menu.ghost, "nouvelle séance : le bot de la séance lancée reste choisi (lot O32)")
	# Bots à profil (lot T13) : après les bots constants, chaque profil à 90, 100 et 110 % de la FTP.
	var labels: Array = []
	for c in MenuModel.BOT_CHOICES:
		labels.append(c[0])
	_check(labels.slice(7) == ["Grimpeur 90 %", "Grimpeur 100 %", "Grimpeur 110 %", "Rouleur 90 %", "Rouleur 100 %",
		"Rouleur 110 %", "Sprinteur 90 %", "Sprinteur 100 %", "Sprinteur 110 %", "Diesel 90 %", "Diesel 100 %", "Diesel 110 %"],
		"profils et niveaux au menu (%s)" % str(labels))
	g.menu.bot_choice = 9
	_check(g.menu._start_args() == {"bots": [{"kind": "profile", "profile": "climber", "level_pct": 110}]},
		"start avec un grimpeur à 110 %% (%s)" % str(g.menu._start_args()))


func _init() -> void:
	_test_bots_menu()
	_test_plans()
	_test_ftp_flow()
	_test_library()
	_test_erg_submenu()
	_test_settings_screen()
	_test_connect_screen()
	_test_pairing_screen()
	_test_full_session()
	_test_abandon_and_summary_quit()
	_test_view()
	print("test_menu_flow : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
