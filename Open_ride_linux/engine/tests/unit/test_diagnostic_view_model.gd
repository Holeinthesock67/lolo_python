extends SceneTree

## Tests sans écran de « Réglages › Diagnostic » (lot DG1, contrat 1.32) : modèle (diagnostic_view_model.gd) et
## déroulé (menu_flow.gd : ouverture, choix du dossier, réponse du core, échec).
## Lancement : godot --headless --path engine --script res://tests/unit/test_diagnostic_view_model.gd

const DiagnosticViewModel := preload("res://scripts/diagnostic_view_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _test_model() -> void:
	var m = DiagnosticViewModel.new()
	var items: Array = m.menu_items()
	_check(items.size() == 3 and items[0]["id"] == "dest:telechargements" and items[0]["enabled"],
		"trois dossiers au choix, Téléchargements d'abord")
	_check(m.handle("dest:nuage").is_empty() and m.handle("autre").is_empty(), "ligne inconnue : rien")
	var act: Dictionary = m.handle("dest:bureau")
	_check(act == {"action": "create_diagnostic", "dest": "bureau"}, "choix du Bureau : commande au core")
	_check(not m.menu_items()[0]["enabled"] and m.handle("dest:openride").is_empty(), "pendant l'écriture : lignes grisées")
	_check(m.message == "Création du fichier de diagnostic…", "ligne d'état d'attente")
	m.on_diagnostic({"type": "diagnostic", "ok": true, "dest": "bureau", "path": "~/Bureau/openride_diagnostic.zip",
		"size_kb": 12, "masked": 4})
	_check(m.message == "Fichier créé (12 ko) : ~/Bureau/openride_diagnostic.zip. Rien n'a été envoyé.",
		"réponse : chemin et taille, en mots (%s)" % m.message)
	_check(m.menu_items()[0]["enabled"], "après la réponse : choix rendus")
	m.handle("dest:openride")
	m.on_diagnostic({"type": "diagnostic", "ok": false, "dest": "openride", "reason": "disque plein"})
	_check(m.message == "Échec : disque plein", "échec : cause écrite")
	var text := "\n".join(PackedStringArray(m.sheet("dest:bureau")["lines"]))
	_check(text.contains("Rien n'est envoyé") and text.contains("Masqué") and text.contains("(Bureau)"),
		"carte : rien n'est envoyé, ce qui est masqué, dossier choisi")
	_check(m.sheet("autre").is_empty(), "pas de carte hors des lignes")


func _test_flow() -> void:
	var f = MenuFlow.new()
	f.on_state({"session_state": "IDLE"})
	f.connect_done = true
	f.menu.open_screen(MenuModel.SETTINGS)
	_check(f.menu.focus_item("diagnostic"), "Réglages : ligne Diagnostic")
	var act: Dictionary = f.handle("A_LONG")
	_check(act.is_empty() and f.menu.current_screen() == DiagnosticViewModel.SCREEN, "ouverture de l'écran Diagnostic")
	_check(f.menu.focus_item("dest:openride"), "ligne du dossier OpenRide")
	act = f.handle("A_LONG")
	_check(act.get("action", "") == "create_diagnostic" and act.get("dest", "") == "openride"
		and act.has("engine_version"), "A maintenu : create_diagnostic avec la version de l'engine")
	_check(f.state()["status"] == "Création du fichier de diagnostic…", "ligne d'état en attendant le core")
	f.on_error("bad_args", "Diagnostic : destination inconnue")
	_check(f.state()["status"].begins_with("Échec") and f.state()["status_error"], "refus du core en rouge")
	f.menu.focus_item("dest:openride")
	f.handle("A_LONG")
	f.on_diagnostic({"type": "diagnostic", "ok": true, "dest": "openride",
		"path": "~/OpenRide/Diagnostics/openride_diagnostic.zip", "size_kb": 9, "masked": 2})
	_check(str(f.state()["status"]).begins_with("Fichier créé (9 ko)") and not f.state()["status_error"],
		"fichier créé : chemin sur la ligne d'état")
	f.handle("Y_SHORT")
	_check(f.menu.current_screen() == MenuModel.SETTINGS, "Y : retour aux Réglages")


func _init() -> void:
	_test_model()
	_test_flow()
	print("test_diagnostic_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
