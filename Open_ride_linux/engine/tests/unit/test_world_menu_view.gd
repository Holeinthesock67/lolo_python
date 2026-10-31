extends SceneTree

## Affichage du menu « Monde ouvert » et réunion des parties de réponse du core (lot W11), sans écran.
## Lancement : godot --headless --path engine --script res://tests/unit/test_world_menu_view.gd

const View := preload("res://scripts/world_menu_view.gd")
const IpcClientScript := preload("res://scripts/ipc_client.gd")
const MenuModel := preload("res://scripts/menu_model.gd")

var _checked := 0
var _failures := 0
var _received: Array = []


func _check(ok: bool, what: String) -> void:
	_checked += 1
	if not ok:
		_failures += 1
		printerr("[ÉCHEC] ", what)
	else:
		print("[OK] ", what)


func _on_menu(kind: String, msg: Dictionary) -> void:
	_received.append([kind, msg])


func _init() -> void:
	# Géométrie du globe : (lon, lat) → vecteur unitaire ; le centre du globe fait face à la caméra (+z).
	_check(View.lonlat_to_vec(0.0, 0.0).is_equal_approx(Vector3(0, 0, 1)), "lon 0, lat 0 : vers +z")
	_check(View.lonlat_to_vec(90.0, 0.0).is_equal_approx(Vector3(1, 0, 0)), "lon 90 : vers +x")
	_check(View.lonlat_to_vec(10.0, 90.0).is_equal_approx(Vector3(0, 1, 0)), "pôle nord : +y")

	# Entrée « Monde ouvert » de l'accueil, seulement si le core l'annonce.
	var menu = MenuModel.new()
	var ids := func() -> Array:
		var out := []
		for it in menu.state()["items"]:
			out.append(it["id"])
		return out
	_check(not ids.call().has("open_world"), "sans l'annonce du core : pas d'entrée")
	menu.set_modes(["ride", "erg", "open_world"])
	_check(ids.call().has("open_world"), "annoncé : entrée « Monde ouvert »")
	menu.handle("PLUS_SHORT")
	var guard := 0
	while menu.state()["items"][menu.state()["focus"]]["id"] != "open_world" and guard < 20:
		menu.handle("PLUS_SHORT")
		guard += 1
	_check(menu.handle("A_LONG")["action"] == {"action": "open_world_menu"}, "valider l'entrée : ouvre le menu du globe")

	# Affichage de bout en bout.
	var v = View.new()
	root.add_child(v)
	_check(not v.visible, "caché au départ")
	v.open()
	_check(v.visible and v.globe_view.visible and v.body_label.text.contains("Centre"), "globe affiché")
	v.vm.type_text("ve")
	v.vm.on_places([{"name": "Mont Ventoux", "kind": "peak", "lat": 44.17, "lon": 5.27, "cached": true, "source": "base"}])
	v.update_display()
	_check(v.vm.state == "search" and v.body_label.text.contains("Mont Ventoux") and v.body_label.text.contains("en cache"), "résultats de la recherche")
	v.vm.handle("A_SHORT")
	v.update_display()
	_check(v.vm.state == "map" and not v.globe_view.visible and v.body_label.text.contains("Chargement"), "carte : globe caché, attente des routes")
	v.vm.on_map({"roads": [{"c": "t", "xz": [0, 0, 500, 0]}]})
	v.vm.handle("A_SHORT")
	v.vm.handle("A_SHORT")
	v.update_display()
	_check(v.vm.state == "loading" and v.hint_label.text.contains("NASA") and v.hint_label.text.contains("Natural Earth"), "préchargement : attributions")
	v.vm.on_status({"phase": "dem", "done_bytes": 5_000_000, "total_bytes": 10_000_000, "squares_ready": 0, "squares_needed": 0, "message": "relief"})
	v.update_display()
	_check(v.body_label.text.contains("5 Mo / 10 Mo"), "barre et octets")
	v.close()
	_check(not v.visible, "fermé")
	v.queue_free()

	# Réunion des parties de réponse.
	var ipc = IpcClientScript.new()
	ipc.world_menu_received.connect(_on_menu)
	var part := func(i: int, n: int, rid: int, roads: Array) -> Dictionary:
		return {"type": "world_map", "v": 1, "request_cmd_id": rid, "part": i, "parts": n, "lat": 44.0, "lon": 5.0,
			"radius_m": 8000.0, "truncated": false, "roads": roads}
	ipc._on_world_part("world_map", part.call(2, 2, 7, [{"c": "m", "xz": [1, 2, 3, 4]}]))
	_check(_received.is_empty(), "une partie sur deux : rien")
	ipc._on_world_part("world_map", part.call(1, 2, 7, [{"c": "t", "xz": [0, 0, 5, 5]}]))
	_check(_received.size() == 1 and _received[0][1]["roads"].size() == 2 and _received[0][1]["lat"] == 44.0, "parties réunies, en-tête gardé")
	ipc._on_world_part("world_map", part.call(1, 2, 7, []))      # copie renvoyée : pas de seconde livraison
	ipc._on_world_part("world_map", part.call(2, 2, 7, []))
	_check(_received.size() == 1, "réponse déjà livrée : ignorée")
	ipc._on_world_part("places", {"type": "places", "request_cmd_id": 8, "part": 1, "parts": 1, "items": [{"name": "x"}]})
	_check(_received.size() == 2 and _received[1][0] == "places" and _received[1][1]["items"].size() == 1, "places : une partie")
	ipc._on_world_part("world_map", part.call(1, 1, 9, [{"c": "t", "xz": [0, 0, 5, 5]}]))
	_check(_received.size() == 3, "nouvelle demande : livrée")
	var got_settings := []
	ipc.settings_received.connect(func(m: Dictionary) -> void: got_settings.append(m))
	var setting := func(i: int, n: int, key: String) -> Dictionary:
		return {"type": "settings", "v": 1, "request_cmd_id": 11, "part": i, "parts": n, "items": [{"key": key}]}
	ipc._on_settings_part(setting.call(1, 2, "rider.ftp_w"))
	_check(got_settings.is_empty(), "settings : une partie sur deux, rien")
	ipc._on_settings_part(setting.call(2, 2, "progression.enabled"))
	_check(got_settings.size() == 1 and got_settings[0]["items"].size() == 2, "settings en parties réunies (lot O27)")
	ipc._on_settings_part({"type": "settings", "v": 1, "request_cmd_id": 0, "items": [{"key": "render.fps"}]})
	ipc._on_settings_part({"type": "settings", "v": 1, "request_cmd_id": 0, "items": [{"key": "render.fps"}]})
	_check(got_settings.size() == 3, "settings sans parties : chaque message livré")
	ipc._track_open_world({"route_id": "ow:x", "open_world": {"rev": 3}})
	ipc._track_open_world({"route_id": "ow:x"})
	_check(ipc.open_world.get("rev") == 3, "open_world gardé quand une trame l'omet")
	ipc._track_open_world({"route_id": "demo"})
	_check(ipc.open_world.is_empty(), "hors monde ouvert : vidé")

	ipc.free()
	print("test_world_menu_view : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
