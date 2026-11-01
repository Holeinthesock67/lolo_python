extends SceneTree

## Tests sans écran des profils de joueurs dans les menus (série MJ, lot MJ8) : modèle
## (profiles_view_model.gd) et déroulé (menu_flow.gd : « Qui roule ? », grille du nom, gestion).
## Lancement : godot --headless --path engine --script res://tests/unit/test_profiles_view_model.gd

const ProfilesViewModel := preload("res://scripts/profiles_view_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
const ButtonHelp := preload("res://scripts/button_help.gd")

const PROFILES := {"type": "profiles", "v": 1, "request_cmd_id": 3, "active": "cycliste-a", "items": [
	{"id": "cycliste-a", "name": "Cycliste A", "type": "joueur", "level": 7, "last_ride": "2026-10-29", "kit_primary": 3},
	{"id": "cycliste-b", "name": "Cycliste B", "type": "joueur", "level": 1, "last_ride": null, "kit_primary": 11}]}
const HELLO_A := {"id": "cycliste-a", "name": "Cycliste A", "type": "joueur", "count": 2}

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _ids(items: Array) -> Array:
	return items.map(func(it): return str(it["id"]))


func _test_model() -> void:
	var m = ProfilesViewModel.new()
	_check(not m.enabled() and m.home_title() == "OpenRide" and m.home_label() == "", "core sans profils : rien d'affiché")
	_check(m.on_hello(HELLO_A), "premier profil : changement")
	_check(m.home_title() == "OpenRide — Cycliste A" and m.home_label() == "Profil : Cycliste A", "titre et ligne de l'accueil")
	_check(m.should_ask(), "deux profils joueur : « Qui roule ? » au démarrage")
	m.on_profiles(PROFILES)
	var who: Array = m.who_items()
	_check(_ids(who) == ["p:cycliste-a", "p:cycliste-b", "new", "manage"], "profil en cours d'abord, puis création et gestion")
	_check(str(who[0]["detail"]).contains("niveau 7") and str(who[0]["detail"]).contains("29/10"), "niveau et dernière séance")
	_check(str(who[1]["detail"]).contains("aucune séance"), "profil sans séance")
	m.on_hello({"id": "_essai", "name": "Profil d'essai", "type": "essai", "count": 2})
	_check(m.is_trial() and m.home_title() == "OpenRide — PROFIL D'ESSAI" and not m.should_ask(), "profil d'essai signalé, jamais proposé")
	# huit profils joueur : plus de création
	var many: Array = []
	for i in range(8):
		many.append({"id": "j%d" % i, "name": "J%d" % i, "type": "joueur", "level": 1, "last_ride": null, "kit_primary": 0})
	m.on_profiles({"active": "j0", "items": many})
	_check(not _ids(m.who_items()).has("new"), "huit profils : pas de « Nouveau profil »")


func _test_name_entry() -> void:
	var m = ProfilesViewModel.new()
	m.on_profiles(PROFILES)
	m.begin_create()
	_check(m.name_text == "Cycliste 3", "nom proposé : Cycliste 3")
	_check(m.validate() == {"action": "create_profile", "name": "Cycliste 3"}, "A maintenu garde le nom proposé")
	m.name_text = ""
	_check(m.validate().is_empty() and m.message.begins_with("Nom vide"), "nom vide refusé")
	for id in ["c:19", "c:7", "c:14", "c:12", "c:0", "c:18"]:   # T H O M A S
		m.press_cell(id)
	_check(m.name_text == "Thomas", "majuscule en début de mot, minuscules ensuite : %s" % m.name_text)
	m.press_cell("c:35")   # espace
	m.press_cell("c:35")   # pas deux espaces
	m.press_cell("c:26")   # é en début de mot : É
	_check(m.name_text == "Thomas É", "espace unique, accent en majuscule : %s" % m.name_text)
	m.press_cell(ProfilesViewModel.ERASE)
	m.press_cell(ProfilesViewModel.ERASE)
	_check(m.name_text == "Thomas", "Effacer retire la dernière lettre")
	_check(m.type_text("-") and m.type_text("2") and not m.type_text("!") and not m.type_text("_"), "clavier : tiret et chiffres, pas de ponctuation")
	for i in range(20):
		m.type_text("x")
	_check(m.name_text.length() == ProfilesViewModel.NAME_MAX, "16 caractères au plus")
	m.begin_rename("cycliste-b")
	_check(m.name_text == "Cycliste B", "renommer : nom actuel déjà écrit")
	_check(m.press_cell(ProfilesViewModel.VALIDATE) == {"action": "rename_profile", "id": "cycliste-b", "name": "Cycliste B"},
		"« Valider » à la souris")
	_check(m.on_error("name_invalid", "le nom « X » est déjà pris") and m.message.begins_with("Nom refusé"), "nom refusé par le core")
	_check(not m.on_error("route_invalid", "x"), "autres erreurs ignorées")


func _flow() -> Variant:
	var f = MenuFlow.new()
	f.on_state({"session_state": "IDLE"})
	f.on_hello_profile(HELLO_A)
	f.on_profiles(PROFILES)
	return f


func _test_flow() -> void:
	var f = _flow()
	f._leave_connect()   # écran de connexion quitté (« Passer » ou tout relié)
	_check(f.menu.current_screen() == ProfilesViewModel.SCREEN, "deux profils : « Qui roule ? » après la connexion")
	_check(f.state()["focus"] == 0 and f.state()["items"][0]["id"] == "p:cycliste-a", "dernier profil présélectionné")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == MenuModel.HOME, "un seul A maintenu : accueil du profil en cours")
	_check(f.state()["title"] == "OpenRide — Cycliste A" and f.state()["items"][0]["label"] == "Profil : Cycliste A",
		"titre et ligne « Profil » de l'accueil")
	_check(f.handle("A_LONG") == {"action": "list_profiles"}, "ligne « Profil » : liste demandée")
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "select_profile", "id": "cycliste-b"}, "A maintenu sur un autre profil : select_profile")
	_check(f.state()["status"] == "Changement de profil…", "attente du core affichée")
	f.on_hello_profile({"id": "cycliste-b", "name": "Cycliste B", "type": "joueur", "count": 2})
	_check(f.menu.current_screen() == MenuModel.HOME and f.state()["title"] == "OpenRide — Cycliste B", "nouveau profil : accueil")
	# création au Click
	f.handle("A_LONG")
	f.on_profiles(PROFILES)
	f.menu.focus_item("new")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == ProfilesViewModel.NAME and f.state().has("grid"), "« Nouveau profil » : grille du nom")
	f.handle("Y_SHORT")
	_check(f.profiles.name_text == "Cycliste ", "Y efface la dernière lettre : %s" % f.profiles.name_text)
	f.handle("PLUS_LONG")
	_check(f.state()["focus"] == ProfilesViewModel.GRID_COLUMNS, "+ maintenu : une ligne plus bas")
	f.handle("PLUS_SHORT")
	f.handle("Z_SHORT")
	_check(f.profiles.name_text == "Cycliste L", "Z écrit la lettre de la case (L, début de mot)")
	_check(f.click_event() == "Z_SHORT", "clic sur la grille : écrire")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "create_profile", "name": "Cycliste L"}, "A maintenu valide le nom")
	f.on_error("name_invalid", "déjà pris")
	_check(f.state()["status_error"] and f.menu.current_screen() == ProfilesViewModel.NAME, "nom refusé : on reste sur la grille")
	_check(f.name_key("x", false, false)["used"] and f.profiles.name_text == "Cycliste Lx", "clavier : la lettre s'écrit")
	_check(f.name_key("", true, false)["action"]["action"] == "create_profile", "Entrée valide")
	for i in range(20):
		if f.menu.current_screen() == ProfilesViewModel.NAME:
			f.handle("Y_SHORT")
	_check(f.menu.current_screen() == ProfilesViewModel.SCREEN, "nom vide puis Y : retour")
	_check(not f.name_key("x", false, false)["used"], "hors de la grille, le clavier reste le Click")
	# gestion : suppression confirmée, « Non » par défaut
	f.menu.focus_item("manage")
	f.handle("A_LONG")
	f.menu.focus_item("p:cycliste-b")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == ProfilesViewModel.MANAGE, "gestion du profil")
	f.on_profiles({"active": "cycliste-b", "items": PROFILES["items"]})
	_check(not f.state()["items"][1]["enabled"], "le profil en cours ne se supprime pas")
	f.on_profiles(PROFILES)
	f.menu.focus_item("delete")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == MenuModel.CONFIRM and f.state()["focus"] == 0, "confirmation, « Non » par défaut")
	_check(f.state()["title"] == "Supprimer « Cycliste B » ? (va à la corbeille)", "question courte, corbeille lisible : %s" % f.state()["title"])
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "delete_profile", "id": "cycliste-b"}, "« Oui » : delete_profile")
	f.on_profiles({"active": "cycliste-a", "items": [PROFILES["items"][0]]})
	_check(f.menu.current_screen() == ProfilesViewModel.SCREEN, "profil supprimé : retour à la liste")
	_check(ButtonHelp.text(ProfilesViewModel.NAME).contains("Z : Écrire"), "aide des boutons de la grille")
	_test_trash_and_trial(f)


## Lot O33 : « Restaurer un profil supprimé » et « Vider le profil d'essai » à la fin de « Gérer un profil ».
func _test_trash_and_trial(f) -> void:
	var trashed := {"id": "cycliste-b_20261030-210500", "name": "Cycliste B", "deleted": "2026-10-30"}
	f.on_profiles({"active": "cycliste-a", "items": [PROFILES["items"][0]], "trash": [trashed]})
	f.menu.focus_item("manage")
	f.handle("A_LONG")
	_check(_ids(f.state()["items"]).slice(-2) == ["restore", "clear_trial"], "gestion : restaurer et vider l'essai en fin de liste")
	f.menu.focus_item("restore")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == ProfilesViewModel.RESTORE and f.state()["items"][0]["detail"] == "supprimé le 30/10",
		"corbeille : nom et date de la suppression")
	_check(f.handle("A_LONG") == {"action": "restore_profile", "id": trashed["id"]}, "A maintenu : restore_profile")
	f.on_profiles(PROFILES.merged({"trash": []}, true))
	_check(f.menu.current_screen() == ProfilesViewModel.MANAGE_LIST and f.state()["status"] == "Profil restauré : Cycliste B",
		"restauré : retour à la gestion, message")
	_check(not f.state()["items"][_ids(f.state()["items"]).find("restore")]["enabled"], "corbeille vide : ligne grisée")
	f.menu.focus_item("clear_trial")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == MenuModel.CONFIRM and f.state()["focus"] == 0, "vider l'essai : confirmation, « Non » d'abord")
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "clear_trial_profile"}, "« Oui » : clear_trial_profile")
	f.on_profiles(PROFILES)
	_check(f.state()["status"] == "Profil d'essai vidé", "réponse du core : profil d'essai vidé")
	f.menu.focus_item("restore")
	f.on_error("profile_invalid", "le nom « Cycliste B » est déjà pris")
	_check(f.state()["status"].contains("déjà pris"), "refus du core sur la ligne d'état")


func _init() -> void:
	_test_model()
	_test_name_entry()
	_test_flow()
	print("test_profiles_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
