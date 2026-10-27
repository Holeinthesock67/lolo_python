extends SceneTree

## Tests sans écran du déroulé des menus `menu_flow.gd` et de leur affichage (Lot N6).
## Lancement : godot --headless --path engine --script res://tests/unit/test_menu_flow.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuView := preload("res://scripts/menu_view.gd")

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
	f.handle("A_LONG")   # Rouler
	_check(f.state()["screen"] == "routes", "liste des parcours")
	var routes: Array = f.state()["items"]
	var to_compile: Array = routes.filter(func(it): return it["id"] == "nouveau")
	_check(to_compile.size() == 1 and not to_compile[0]["enabled"] and to_compile[0]["detail"] != "",
			"parcours à compiler désactivé avec sa raison (critère 3)")
	f.handle("PLUS_SHORT")   # 2ᵉ parcours
	var sel: Dictionary = f.handle("A_LONG")
	_check(sel.get("action") == "select_route" and sel.get("route_id") == _ids_route(routes, 1),
			"2ᵉ parcours choisi : select_route %s" % str(sel))
	_check(f.state()["screen"] == "ready", "écran Prêt")
	f.on_state({"session_state": "READY"})
	f.handle("PLUS_SHORT")   # Choisir un entraînement
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")
	var wk: Dictionary = f.handle("A_LONG")
	_check(wk == {"action": "select_workout", "workout_id": "sweet"}, "entraînement choisi : %s" % str(wk))
	_check(f.state()["screen"] == "ready", "retour à l'écran Prêt")
	f.handle("MINUS_SHORT")   # le focus revient sur « Choisir un entraînement » : Démarrer est au-dessus
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
	_check(f.handle("A_LONG") == {"action": "list"} and f.state()["screen"] == "home",
			"Nouvelle séance : accueil et listes redemandées")
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
	f.handle("MINUS_SHORT")   # Abandonner (boucle depuis Reprendre)
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
	_check(items.size() == 1 and not items[0]["enabled"], "liste indisponible : élément désactivé")
	g.lists_needed()
	_check(g.on_state({"session_state": "IDLE"}) == [{"action": "list"}], "core relancé : listes redemandées")


func _test_view() -> void:
	var f = MenuFlow.new()
	f.connect_done = true   # écran de connexion : _test_connect_screen
	f.on_state({"session_state": "IDLE"})
	var many: Array = []
	for i in range(9):
		many.append({"id": "r%d" % i, "name": "Parcours %d" % i, "length_m": 1000.0 * (i + 1), "status": "ready"})
	f.set_routes(many)
	var v = MenuView.new()
	var state := {"session_state": "IDLE", "trainer_status": "MOCK", "input_status": "KEYBOARD"}
	v.update_display(f.state(), state, {}, false)
	_check(v.title_label.text == "OpenRide" and v.items_text().begins_with("[Rouler]"), "accueil : %s" % v.items_text())
	_check(v.devices.visible and v.devices.text().contains("Trainer"), "état des appareils : %s" % v.devices.text())
	f.handle("A_LONG")
	for i in range(7):
		f.handle("PLUS_SHORT")
	v.update_display(f.state(), state, {}, false)
	var shown := v.items_text().split(" | ")
	_check(shown.size() == MenuView.MAX_VISIBLE_ITEMS and v.items_text().contains("[Parcours 7"),
			"longue liste : fenêtre autour du focus (%s)" % v.items_text())
	_check(v.more_label.text == "8 / 9", "position dans la liste : %s" % v.more_label.text)
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
	f.handle("PLUS_SHORT")
	f.handle("PLUS_SHORT")   # Réglages
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
	_check("Trainer : HomeTrainer 0001" in labels, "trainer trouvé choisi : %s" % str(labels))
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


func _init() -> void:
	_test_connect_screen()
	_test_pairing_screen()
	_test_full_session()
	_test_abandon_and_summary_quit()
	_test_view()
	print("test_menu_flow : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
