extends SceneTree

## Séance interrompue d'un lancement précédent (lot O34) dans les menus : ligne en tête de l'accueil, écran
## « Enregistrer la séance » / « Ne pas l'enregistrer » (confirmé), commande recover_session, réponse `interrupted`.
## Lancement : godot --headless --path engine --script res://tests/unit/test_interrupted_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")

const ITEM_A := {"id": "2026-10-30_18-05-12.jsonl", "start": "2026-10-30T18:05", "route_id": "vosges",
	"distance_m": 12345, "duration_s": 1920}
const ITEM_B := {"id": "2026-10-29_07-00-00.jsonl", "start": "2026-10-29T07:00", "route_id": null,
	"distance_m": 800, "duration_s": 90}

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _ids(st: Dictionary) -> Array:
	return st["items"].map(func(it): return str(it["id"]))


func _focused(f) -> String:
	var st: Dictionary = f.state()
	return str(st["items"][st["focus"]]["id"]) if st["focus"] >= 0 else ""


func _init() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	f.set_routes([{"id": "vosges", "name": "Vosges", "status": "ready", "length_m": 30000}])
	_check(not "interrupted" in _ids(f.state()), "aucune séance interrompue : accueil inchangé")
	f.on_hello_interrupted([ITEM_A, ITEM_B])
	var home: Dictionary = f.state()
	_check(_ids(home)[0] == "interrupted" and home["items"][0]["label"] == "Séance interrompue à enregistrer (+1)",
		"ligne en tête de l'accueil, avec le nombre d'autres séances")
	_check(home["items"][0]["detail"] == "30/10 à 18:05 · Vosges · 12,3 km · 32 min", "date, parcours, distance, durée")
	_check(MenuFlow.interrupted_detail(ITEM_B, {}) == "29/10 à 07:00 · 0,8 km · 2 min", "sans parcours connu")
	f.menu.focus_item("interrupted")
	f.handle("A_LONG")
	_check(f.state()["screen"] == MenuFlow.INTERRUPTED and _ids(f.state()) == ["save", "discard"],
		"écran : enregistrer ou non")
	_check(f.handle("A_LONG") == {"action": "recover_session", "id": ITEM_A["id"], "save": true},
		"Enregistrer : recover_session avec save")
	f.on_interrupted({"type": "interrupted", "id": ITEM_A["id"], "saved": true, "fit_path": "/x.fit", "items": [ITEM_B]})
	_check(f.state()["screen"] == MenuFlow.INTERRUPTED and f.state()["status"] == "Séance enregistrée dans tes séances"
		and f.state()["items"][0]["detail"].begins_with("29/10"), "séance suivante proposée, résultat sur la ligne d'état")
	f.menu.focus_item("discard")
	f.handle("A_LONG")
	_check(f.state()["screen"] == MenuModel.CONFIRM and _focused(f) == "no", "Ne pas l'enregistrer : confirmation, « Non » d'abord")
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "recover_session", "id": ITEM_B["id"], "save": false}, "« Oui » : save faux")
	f.on_interrupted({"type": "interrupted", "id": ITEM_B["id"], "saved": false, "fit_path": null, "items": []})
	_check(f.state()["screen"] == MenuModel.HOME and not "interrupted" in _ids(f.state())
		and f.state()["status"] == "Séance non enregistrée", "plus rien à rattraper : accueil, ligne retirée")
	f.handle("PLUS_SHORT")
	_check(f.state()["status"] == "", "ligne d'état effacée à l'appui suivant")
	f.on_hello_interrupted([ITEM_A])
	f.menu.focus_item("interrupted")
	f.handle("A_LONG")
	f.on_error("recording_failed", "disque plein")
	_check(f.state()["status"] == "Échec : disque plein", "échec du core sur la ligne d'état")
	f.on_hello_interrupted(null)
	_check(not "interrupted" in _ids(f.menu.state()) or f.menu.current_screen() != MenuModel.HOME,
		"nouveau profil sans séance interrompue : ligne retirée")
	print("test_interrupted_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
