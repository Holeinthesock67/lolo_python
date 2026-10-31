extends SceneTree

## Tests sans écran de l'écran « Réglages › Contenus » (lot O25) : modèle (contents_view_model.gd) et
## déroulé (menu_flow.gd : ouverture, installation, confirmation d'un téléchargement, listes redemandées).
## Lancement : godot --headless --path engine --script res://tests/unit/test_contents_view_model.gd

const ContentsViewModel := preload("res://scripts/contents_view_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")

const STARTER := {"id": "starter", "kind": "starter", "label": "Contenus de départ",
	"detail": "7 entraînements, 2 plans de départ, 4 parcours de démonstration des biomes", "state": "missing",
	"network": false, "size_mb": null, "progress_pct": null}
const PACK := {"id": "pack", "kind": "route_pack", "label": "Cols célèbres", "detail": "16 cols",
	"state": "missing", "network": true, "size_mb": 12.4, "progress_pct": null}

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _msg(items: Array, busy = null, text := "") -> Dictionary:
	return {"type": "contents", "v": 1, "request_cmd_id": 1, "busy": busy, "message": text, "items": items}


func _test_model() -> void:
	var m = ContentsViewModel.new()
	_check(m.menu_items()[0]["id"] == "wait", "avant la réponse : attente")
	_check(not m.on_contents(_msg([STARTER])), "première liste : rien de terminé")
	var it: Dictionary = m.menu_items()[0]
	_check(it["id"] == "content:starter" and it["enabled"], "contenu à installer : choisissable")
	_check(it["detail"] == "à installer", "état à droite de la ligne")
	var card: Dictionary = m.sheet("content:starter")
	_check(card["name"] == "Contenus de départ" and card["lines"][0].begins_with("7 entraînements")
		and card["lines"][1] == "Rien n'est téléchargé", "carte : contenu et téléchargement")
	_check(m.handle("content:starter") == {"action": "install_content", "id": "starter"}, "A maintenu : install_content")
	var installing := STARTER.duplicate()
	installing["state"] = "installing"
	installing["progress_pct"] = 40
	m.on_contents(_msg([installing], "starter"))
	_check(not m.menu_items()[0]["enabled"] and str(m.menu_items()[0]["detail"]).begins_with("installation : 40 %"),
		"pendant l'installation : avancement, rien de choisissable")
	var done := STARTER.duplicate()
	done["state"] = "installed"
	_check(m.on_contents(_msg([done], null, "Ajouté : 7 entraînement(s).")), "fin de l'installation signalée")
	_check(m.message == "Ajouté : 7 entraînement(s)." and m.menu_items()[0]["detail"] == "installé", "compte rendu, contenu installé")
	_check(m.handle("content:starter").is_empty() and m.message == "Déjà installé : rien à ajouter.",
		"contenu installé : rien à faire, dit sur la ligne d'état")
	m.on_contents(_msg([PACK]))
	var pack: Dictionary = m.menu_items()[0]
	_check(pack["detail"] == "à installer, 12 Mo, téléchargement", "taille et téléchargement annoncés")
	_check(m.sheet("content:pack")["lines"][1] == "Téléchargement nécessaire", "carte : téléchargement")
	var choice: Dictionary = m.handle("content:pack")
	_check(choice.has("confirm") and choice["action"] == {"action": "install_content", "id": "pack"},
		"téléchargement : confirmation d'abord")
	_check(m.on_error("content_failed", "réseau absent") and m.message == "Échec : réseau absent", "échec sur la ligne d'état")
	_check(not m.on_error("plan_invalid", "x"), "autres erreurs ignorées")
	m.on_contents(_msg([]))
	_check(m.menu_items()[0]["id"] == "none", "liste vide : ligne désactivée")


func _test_flow() -> void:
	var f = MenuFlow.new()
	f.on_state({"session_state": "IDLE"})
	f.connect_done = true
	f.menu.open_screen(MenuModel.SETTINGS)
	_check(f.menu.focus_item("contents"), "Réglages : ligne Contenus")
	var act: Dictionary = f.handle("A_LONG")
	_check(act.get("action", "") == "list_contents" and f.menu.current_screen() == ContentsViewModel.SCREEN,
		"ouverture : écran Contenus et list_contents")
	_check(f.on_contents(_msg([STARTER])).is_empty(), "liste reçue")
	act = f.handle("A_LONG")
	_check(act == {"action": "install_content", "id": "starter"}, "A maintenu : installation demandée")
	_check(f.state()["status"] == "Installation demandée…", "ligne d'état en attendant le core")
	var installing := STARTER.duplicate()
	installing["state"] = "installing"
	f.on_contents(_msg([installing], "starter"))
	var done := STARTER.duplicate()
	done["state"] = "installed"
	_check(f.on_contents(_msg([done], null, "Ajouté : 7 entraînement(s).")).get("action", "") == "list",
		"installation terminée : listes redemandées")
	f.on_contents(_msg([PACK]))
	f.handle("A_LONG")
	_check(f.menu.current_screen() == MenuModel.CONFIRM, "pack téléchargé : écran de confirmation")
	f.handle("PLUS_SHORT")
	act = f.handle("A_LONG")
	_check(act == {"action": "install_content", "id": "pack"} and f.menu.current_screen() == ContentsViewModel.SCREEN,
		"« Oui » : installation et retour à l'écran Contenus")
	f.on_error("content_failed", "réseau absent")
	_check(f.state()["status"] == "Échec : réseau absent" and f.state()["status_error"], "échec en rouge sur la ligne d'état")
	f.handle("Y_SHORT")
	_check(f.menu.current_screen() == MenuModel.SETTINGS, "Y : retour aux Réglages")


func _init() -> void:
	_test_model()
	_test_flow()
	print("test_contents_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
