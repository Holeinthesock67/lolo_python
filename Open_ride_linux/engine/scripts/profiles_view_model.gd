extends RefCounted

## Profils de joueurs dans les menus (série MJ, lot MJ8 ; contrat IPC révision 1.5, maquettes A à F
## validées le 29 octobre). Modèle sans nœud, relié par menu_flow.gd :
##
## - « Qui roule ? » (SCREEN) : un profil par ligne (nom, niveau, dernière séance), le profil en cours en
##   premier focus ; A maintenu sur un profil le choisit (`select_profile`) ; puis « Nouveau profil »
##   (moins de huit profils) et « Gérer un profil ». Ouvert au démarrage avec au moins deux profils joueur,
##   et depuis la ligne « Profil : … » de l'accueil.
## - « Nom du profil » (NAME) : saisie de texte partagée (text_entry.gd, lot O31) ; A maintenu valide
##   (`create_profile` ou `rename_profile`). Nom proposé à la création : « Cycliste N ».
## - « Gérer » (MANAGE_LIST puis MANAGE) : Renommer, Supprimer (confirmation, « Non » par défaut ; le
##   profil en cours et le dernier profil joueur ne se suppriment pas).
## - Profil d'essai : titre « OpenRide — PROFIL D'ESSAI » et bandeau « ESSAI » au HUD (`is_trial()`).
##
## Le core contrôle les noms (`name_invalid`) ; le modèle n'empêche que ce que la grille ne sait pas écrire.

const SCREEN := "profiles"
const NAME := "profile_name"
const MANAGE_LIST := "profile_manage_list"
const MANAGE := "profile_manage"
const SCREENS := [SCREEN, NAME, MANAGE_LIST, MANAGE]
const MAX_PROFILES := 8
const NAME_MAX := 16
const TextEntry := preload("res://scripts/text_entry.gd")
const GRID_COLUMNS := TextEntry.GRID_COLUMNS
const ERASE := TextEntry.ERASE
const VALIDATE := TextEntry.VALIDATE
const TRIAL_TITLE := "PROFIL D'ESSAI"

## Dernier message `profiles` : profil en cours et éléments {id, name, type, level, last_ride, kit_primary}.
var items: Array = []
var active := ""
## `hello_ack.config.profile` : {id, name, type, count} ({} : core sans profils, rien n'est affiché).
var profile: Dictionary = {}
## Saisie du nom en cours : texte, « create » ou « rename » et profil renommé.
var entry = TextEntry.new(NAME_MAX)
var name_text: String:
	get:
		return entry.text
	set(value):
		entry.text = value
var name_mode := ""
var rename_id := ""
## Profil ouvert dans « Gérer ».
var manage_id := ""
## Ligne d'état des écrans des profils (nom refusé, profil indisponible, attente du core).
var message := ""
## « Qui roule ? » déjà proposé depuis le démarrage.
var asked := false


func enabled() -> bool:
	return not profile.is_empty()


func is_trial() -> bool:
	return str(profile.get("type", "")) == "essai"


func player_count() -> int:
	return int(profile.get("count", 0))


## Titre de l'accueil : « OpenRide — Cycliste A » ; « OpenRide — PROFIL D'ESSAI » ; « OpenRide » sans profil.
func home_title() -> String:
	if not enabled():
		return "OpenRide"
	return "OpenRide — " + (TRIAL_TITLE if is_trial() else str(profile.get("name", "")))


## Ligne « Profil : … » de l'accueil ("" sans profil).
func home_label() -> String:
	if not enabled():
		return ""
	return "Profil : " + ("essai" if is_trial() else str(profile.get("name", "")))


## « Qui roule ? » au démarrage : au moins deux profils joueur, une seule fois, jamais sur le profil d'essai.
func should_ask() -> bool:
	return enabled() and not asked and not is_trial() and player_count() >= 2


## `hello_ack` (premier ou après un changement de profil) ; vrai si le profil en cours a changé.
func on_hello(block) -> bool:
	var old := str(profile.get("id", ""))
	profile = block if block is Dictionary else {}
	message = ""
	return str(profile.get("id", "")) != old


func on_profiles(msg: Dictionary) -> void:
	var raw = msg.get("items", [])
	items = raw if raw is Array else []
	active = str(msg.get("active", "")) if msg.get("active") != null else ""
	if message == "Enregistrement…":
		message = ""


func on_error(code: String, text: String) -> bool:
	if code not in ["name_invalid", "profile_invalid", "busy"]:
		return false
	message = ("Nom refusé : " if code == "name_invalid" else "") + text
	return true


func _players() -> Array:
	return items.filter(func(it): return str(it.get("type", "")) == "joueur")


func _find(id: String) -> Dictionary:
	for it in items:
		if str(it.get("id", "")) == id:
			return it
	return {}


static func ride_text(it: Dictionary) -> String:
	var lr = it.get("last_ride")
	var last := "aucune séance"
	if lr is String and lr.length() == 10:
		last = "dernière séance " + lr.substr(8, 2) + "/" + lr.substr(5, 2)
	return "niveau %d · %s" % [int(it.get("level", 1)), last]


## Éléments de « Qui roule ? » : profil en cours d'abord, puis les autres par nom ; création et gestion.
func who_items() -> Array:
	var out: Array = []
	var rest: Array = []
	for it in items:
		var row := {"id": "p:" + str(it["id"]), "label": str(it.get("name", it["id"])), "enabled": true,
			"detail": ride_text(it) + (" · en cours" if str(it["id"]) == active else "")}
		if str(it["id"]) == active:
			out.append(row)
		else:
			rest.append(row)
	out.append_array(rest)
	if _players().size() < MAX_PROFILES:
		out.append({"id": "new", "label": "Nouveau profil", "enabled": true, "detail": ""})
	if _players().size() > 0:
		out.append({"id": "manage", "label": "Gérer un profil", "enabled": true, "detail": "renommer, supprimer"})
	return out


func manage_list_items() -> Array:
	var out: Array = []
	for it in _players():
		out.append({"id": "p:" + str(it["id"]), "label": str(it.get("name", it["id"])), "enabled": true,
			"detail": ride_text(it)})
	return out


func manage_items() -> Array:
	var it := _find(manage_id)
	var can_delete := manage_id != active and _players().size() > 1
	var why := "profil en cours" if manage_id == active else ("dernier profil" if not can_delete else "")
	return [{"id": "rename", "label": "Renommer", "enabled": true, "detail": str(it.get("name", ""))},
		{"id": "delete", "label": "Supprimer", "enabled": can_delete, "detail": why}]


func manage_title() -> String:
	return "Gérer : " + str(_find(manage_id).get("name", manage_id))


## Question de la confirmation de suppression, sur une ligne : courte, pour que la corbeille se lise en entier
## (séances, pièces et équipement y partent avec le profil).
func delete_question() -> String:
	return "Supprimer « %s » ? (va à la corbeille)" % str(
		_find(manage_id).get("name", manage_id))


# --- saisie du nom ---------------------------------------------------------------------------

## Nom proposé à la création : « Cycliste N », le premier libre.
func default_name() -> String:
	var taken := {}
	for it in items:
		taken[str(it.get("name", "")).to_lower()] = true
	var n := _players().size() + 1
	while taken.has(("cycliste %d" % n)):
		n += 1
	return "Cycliste %d" % n


func begin_create() -> void:
	name_mode = "create"
	rename_id = ""
	name_text = default_name()
	message = ""


func begin_rename(id: String) -> void:
	name_mode = "rename"
	rename_id = id
	name_text = str(_find(id).get("name", ""))
	message = ""


func name_title() -> String:
	return ("Nouveau profil" if name_mode == "create" else "Renommer") + " : " + name_text + "_"


func grid_items() -> Array:
	return entry.grid_items()


func backspace() -> bool:
	if not entry.backspace():
		return false
	message = ""
	return true


## Case de la grille activée (Z, ou clic) ; renvoie une action pour le core ou {}.
func press_cell(item_id: String) -> Dictionary:
	message = ""
	return validate() if entry.press_cell(item_id) == TextEntry.VALIDATE else {}


## Saisie au clavier : lettres (accents compris), chiffres, espace et tiret ; le reste est ignoré.
func type_text(ch: String) -> bool:
	message = ""
	return entry.type_text(ch)


func validate() -> Dictionary:
	var clean := name_text.strip_edges()
	if clean == "":
		message = "Nom vide : écris au moins une lettre"
		return {}
	message = "Enregistrement…"
	if name_mode == "rename":
		return {"action": "rename_profile", "id": rename_id, "name": clean}
	return {"action": "create_profile", "name": clean}
