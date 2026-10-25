extends SceneTree

## Tests d'intégration sans écran du client IPC des listes et de la navigation des menus (Lot N3).
## Lancement : godot --headless --path engine --script res://tests/test_menu_ipc.gd -- --ipc-state-port=N --ipc-cmd-port=M

const IpcClientScript := preload("res://scripts/ipc_client.gd")
const CatalogModel := preload("res://scripts/catalog_model.gd")
const MenuModel := preload("res://scripts/menu_model.gd")

var _checked := 0
var _failures := 0

var _client: Node = null
var _catalog = null
var _menu = null

var _routes_data: Array = []
var _workouts_data: Array = []
var _got_routes := false
var _got_workouts := false
var _last_cmd_acked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	_catalog = CatalogModel.new()
	_menu = MenuModel.new()

	# 1. Test unitaire des relances et de l'abandon après 3 pertes
	_test_retry_and_failure_logic()

	# 2. Test avec le faux core via UDP
	call_deferred("_start_ipc_test")


func _test_retry_and_failure_logic() -> void:
	# Simulation d'un client IPC pour tester les relances et l'échec après 3 pertes
	var dummy_client = IpcClientScript.new()
	dummy_client._bound = true

	var failed := {"name": "", "msg": ""}
	dummy_client.list_failed.connect(func(lname: String, msg: String):
		failed["name"] = lname
		failed["msg"] = msg
	)

	# Simule list_routes
	dummy_client._pending_list_routes = {"cmd_id": 1, "retries": 0, "timer": 0.0}

	# 1 s s'écoule -> retries passe à 1 (redemande 1/3)
	dummy_client._process(1.1)
	_check(int(dummy_client._pending_list_routes.get("retries", 0)) == 1, "1ère perte : 1ère redemande après 1 s")

	# 1 s s'écoule -> retries passe à 2 (redemande 2/3)
	dummy_client._process(1.1)
	_check(int(dummy_client._pending_list_routes.get("retries", 0)) == 2, "2e perte : 2e redemande après 2 s")

	# 1 s s'écoule -> retries passe à 3 (redemande 3/3)
	dummy_client._process(1.1)
	_check(int(dummy_client._pending_list_routes.get("retries", 0)) == 3, "3e perte : 3e redemande après 3 s")

	# 1 s supplémentaire -> abandon (retries > 3) : signal list_failed émis avec erreur lisible
	dummy_client._process(1.1)
	_check(failed["name"] == "routes", "échec notifié pour la liste des routes")
	_check("Aucune réponse" in failed["msg"], "erreur lisible : " + str(failed["msg"]))

	# Assemblage des parties (contrat v1.1 §4) : réponse en 2 datagrammes, dans le désordre
	var got := {"n": 0, "items": [], "msg": {}}
	dummy_client.routes_received.connect(func(items: Array, msg: Dictionary):
		got["n"] += 1
		got["items"] = items
		got["msg"] = msg
	)
	dummy_client._reset_list_request(dummy_client._pending_list_routes, 10)
	dummy_client._on_list_part(dummy_client._pending_list_routes, "routes",
		{"type": "routes", "request_cmd_id": 10, "part": 2, "parts": 2, "items": [{"id": "c"}], "truncated": false})
	_check(got["n"] == 0, "parties : rien n'est émis tant qu'il manque la partie 1")
	dummy_client._on_list_part(dummy_client._pending_list_routes, "routes",
		{"type": "routes", "request_cmd_id": 99, "part": 1, "parts": 2, "items": [{"id": "x"}], "truncated": false})
	_check(got["n"] == 0, "parties : une réponse à une autre demande (request_cmd_id 99) est ignorée")
	dummy_client._on_list_part(dummy_client._pending_list_routes, "routes",
		{"type": "routes", "request_cmd_id": 10, "part": 1, "parts": 2, "items": [{"id": "a"}, {"id": "b"}], "truncated": true})
	_check(got["n"] == 1 and got["items"].size() == 3, "parties : liste émise une fois, 3 éléments assemblés")
	_check(str(got["items"][0]["id"]) == "a" and str(got["items"][2]["id"]) == "c", "parties : ordre des parties respecté")
	_check(got["msg"].get("truncated") == true, "parties : truncated repris d'une des parties")
	_check(dummy_client._pending_list_routes.is_empty(), "parties : demande terminée")
	dummy_client._on_list_part(dummy_client._pending_list_routes, "routes",
		{"type": "routes", "request_cmd_id": 10, "part": 1, "parts": 2, "items": [{"id": "a"}], "truncated": false})
	_check(got["n"] == 1, "parties : un doublon tardif après la fin est ignoré")

	# Partie manquante : une seconde après la première partie, nouvelle demande avec un nouveau cmd_id
	dummy_client._reset_list_request(dummy_client._pending_list_routes, 20)
	dummy_client._process(0.6)
	dummy_client._on_list_part(dummy_client._pending_list_routes, "routes",
		{"type": "routes", "request_cmd_id": 20, "part": 1, "parts": 2, "items": [{"id": "a"}], "truncated": false})
	dummy_client._process(0.6)
	_check(int(dummy_client._pending_list_routes.get("retries", 0)) == 0, "partie manquante : délai compté depuis la première partie reçue")
	dummy_client._process(0.5)
	var resent_ids: Array = dummy_client._pending_list_routes.get("cmd_ids", [])
	_check(int(dummy_client._pending_list_routes.get("retries", 0)) == 1 and resent_ids.size() == 2 and int(resent_ids[1]) != 20,
		"partie manquante : redemande avec un nouveau cmd_id après 1 s")
	dummy_client._pending_list_routes.clear()

	# En cas d'erreur de liste, le menu reçoit une liste vide et affiche « Aucun parcours »
	var fallback_menu = MenuModel.new()
	fallback_menu.set_items("routes", [])
	fallback_menu._open("routes")
	_check(fallback_menu.state()["items"][0]["label"] == "Aucun parcours", "liste vide : affiche « Aucun parcours »")
	_check(fallback_menu.state()["items"][0]["enabled"] == false, "« Aucun parcours » est désactivé")
	# Le retour reste possible
	fallback_menu.handle("MINUS_LONG")
	_check(fallback_menu.state()["screen"] == "home", "retour vers home possible depuis la liste vide")

	


func _start_ipc_test() -> void:
	_client = IpcClientScript.new()
	root.add_child(_client)

	_client.routes_received.connect(func(items: Array, _msg: Dictionary):
		_routes_data = items
		_got_routes = true
	)
	_client.workouts_received.connect(func(items: Array, _msg: Dictionary):
		_workouts_data = items
		_got_workouts = true
	)
	_client.state_received.connect(func(st: Dictionary):
		_last_cmd_acked = int(st.get("last_cmd_id", 0))
	)

	# Attend le hello_ack
	var timeout_s := 0.0
	while not _client.is_hello_acked() and timeout_s < 5.0:
		await create_timer(0.05).timeout
		timeout_s += 0.05

	_check(_client.is_hello_acked(), "hello_ack reçu du faux core")

	# Demande des deux listes
	var cmd_routes_id: int = _client.list_routes()
	var cmd_workouts_id: int = _client.list_workouts()
	_check(cmd_routes_id > 0 and cmd_workouts_id > cmd_routes_id, "commandes list_routes et list_workouts envoyées avec cmd_id croissants")

	# Attend les réponses
	timeout_s = 0.0
	while (not _got_routes or not _got_workouts) and timeout_s < 5.0:
		await create_timer(0.05).timeout
		timeout_s += 0.05

	_check(_got_routes, "réponse 'routes' reçue du faux core")
	_check(_got_workouts, "réponse 'workouts' reçue du faux core")
	_check(_routes_data.size() == 4 and _workouts_data.size() == 3, "listes complètes : 4 parcours et 3 entraînements (%d, %d)" % [_routes_data.size(), _workouts_data.size()])

	# Injection dans le modèle de menu
	var r_items: Array = _catalog.route_items(_routes_data)
	var w_items: Array = _catalog.workout_items(_workouts_data)
	_menu.set_items("routes", r_items)
	_menu.set_items("workouts", w_items)

	# Scénario complet au Click :
	# 1. Accueil -> valide "Rouler"
	_check(_menu.state()["screen"] == "home", "menu initial sur home")
	var st1: Dictionary = _menu.handle("PLUS_LONG") # valide 'Rouler' (focus 0)
	_check(_menu.state()["screen"] == "routes", "passage sur l'écran routes")

	# 2. Choix du 2e parcours (focus 1 : galibier)
	_menu.handle("PLUS_SHORT")
	_check(_menu.state()["focus"] == 1, "focus sur le 2e parcours")
	var st2: Dictionary = _menu.handle("PLUS_LONG")
	var act_sel_route: Dictionary = st2.get("action", {})
	_check(act_sel_route.get("action") == "select_route", "action select_route générée")
	var route_id: String = str(act_sel_route.get("route_id", ""))
	_check(route_id != "", "route_id fourni dans select_route")
	var cmd_route_id: int = _client.send_command("select_route", {"route_id": route_id})
	_check(_menu.state()["screen"] == "ready", "passage sur l'écran ready")

	# 3. Choix d'un entraînement depuis l'écran ready
	_menu.handle("PLUS_SHORT") # focus sur 1 ("Choisir un entraînement")
	_check(_menu.state()["focus"] == 1, "focus sur 'Choisir un entraînement'")
	_menu.handle("PLUS_LONG")
	_check(_menu.state()["screen"] == "workouts", "passage sur l'écran workouts")

	# En workouts, focus 0 = Sans entraînement, focus 1 = cassé (désactivé, sauté), focus 2 = Récupération
	_menu.handle("PLUS_SHORT")
	var st3: Dictionary = _menu.handle("PLUS_LONG")
	var act_sel_wo: Dictionary = st3.get("action", {})
	_check(act_sel_wo.get("action") == "select_workout", "action select_workout générée")
	var wo_id = act_sel_wo.get("workout_id")
	_check(wo_id != null, "workout_id choisi non nul")
	var cmd_wo_id: int = _client.send_command("select_workout", {"workout_id": wo_id})
	_check(_menu.state()["screen"] == "ready", "retour sur l'écran ready après sélection entraînement")

	# 4. Démarrage : retour sur 'Démarrer'
	_menu.handle("MINUS_SHORT")
	_check(_menu.state()["focus"] == 0, "focus sur 'Démarrer'")
	var st4: Dictionary = _menu.handle("PLUS_LONG")
	var act_start: Dictionary = st4.get("action", {})
	_check(act_start.get("action") == "start", "action start générée")
	var cmd_start_id: int = _client.send_command("start", {})

	# 5. Vérification des cmd_id croissants
	_check(cmd_route_id < cmd_wo_id and cmd_wo_id < cmd_start_id, "cmd_id strictement croissants (route=%d, wo=%d, start=%d)" % [cmd_route_id, cmd_wo_id, cmd_start_id])

	# Attend que fake_core acquitte les commandes dans state.last_cmd_id
	timeout_s = 0.0
	while _last_cmd_acked < cmd_start_id and timeout_s < 3.0:
		await create_timer(0.05).timeout
		timeout_s += 0.05

	_check(_last_cmd_acked >= cmd_start_id, "toutes les commandes acquittées par le faux core (last_cmd_id=%d >= %d)" % [_last_cmd_acked, cmd_start_id])

	print("test_menu_ipc : %d vérifications, %d échecs" % [_checked, _failures])
	_client.queue_free()
	quit(0 if _failures == 0 else 1)
