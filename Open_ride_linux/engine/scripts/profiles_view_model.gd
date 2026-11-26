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
## - « Gérer un profil » finit par « Vider le profil d'essai » (confirmation, `clear_trial_profile`) et
##   « Restaurer un profil supprimé » (RESTORE : profils de la corbeille, `restore_profile`), lot O33.
## - « Ma puissance » (lot PP3) sous le profil en cours : courbe de puissance et FTP estimée (power_view_model.gd).
## - « Gérer : <profil en cours> » (lot RZ1, révision 1.31) : « Remettre à zéro mes statistiques »
##   (confirmation aux boutons écrits, « Non » par défaut, `reset_profile_stats`) et « Annuler la remise à zéro »
##   (dernière remise de `profiles.resets`, `undo_profile_reset`) ; la sauvegarde est faite par le core avant tout.
## - « Gérer : <profil en cours> » (lot SV1) : « Restaurer une sauvegarde » ouvre BACKUPS, les copies du profil
##   (`list_profile_backups`, message `profile_backups`) en mots écrits ; A maintenu sur une copie demande une
##   confirmation (« Non » par défaut), puis `restore_profile_backup` ; l'état actuel est copié par le core avant.
## - Profil d'essai : titre « OpenRide — PROFIL D'ESSAI » et bandeau « ESSAI » au HUD (`is_trial()`).
##
## Le core contrôle les noms (`name_invalid`) ; le modèle n'empêche que ce que la grille ne sait pas écrire.

const SCREEN := "profiles"
const NAME := "profile_name"
const MANAGE_LIST := "profile_manage_list"
const MANAGE := "profile_manage"
const RESTORE := "profile_restore"
const BACKUPS := "profile_backups"   # lot SV1
const SCREENS := [SCREEN, NAME, MANAGE_LIST, MANAGE, RESTORE, BACKUPS]
const CLEAR_TRIAL_ID := "clear_trial"
## « Ma puissance » (série PP, lot PP3) : courbe de puissance et FTP estimée du profil en cours.
const POWER_ID := "power"
const RESTORE_ID := "restore"
const RESET_ID := "reset_stats"     # lot RZ1
const UNDO_RESET_ID := "undo_reset"
const BACKUPS_ID := "backups"       # lot SV1
const REASON_WORDS := {"semaine": "Copie de la semaine", "mise-a-jour": "Avant la mise à jour",
	"remise-a-zero": "Avant la remise à zéro", "restauration": "Avant une restauration"}
const WEEKDAYS := ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."]
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
## Corbeille (`profiles.trash`, lot O33) : {id, name, deleted}, les plus récents d'abord.
var trash: Array = []
## Remises à zéro du profil en cours (`profiles.resets`, lot RZ1) : {id, date, time}, les plus récentes d'abord.
var resets: Array = []
## Copies du profil en cours (`profile_backups.items`, lot SV1) : {id, reason, date, time, sessions}, les plus
## récentes d'abord ; `backups_loaded` faux tant que la réponse du core n'est pas arrivée.
var backups: Array = []
var backups_loaded := false
## Restauration demandée, en attente de la liste `profile_backups` qui la termine (retour à « Gérer »).
var restoring := false
## Message affiché à la réponse `profiles` de la demande en cours (vider, restaurer) ; "" : aucune.
var done_message := ""
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
	if str(profile.get("id", "")) != "":
		active = str(profile["id"])
	return str(profile.get("id", "")) != old


## Profil en cours : le dernier annoncé, par `hello_ack` (renvoyé dès un changement de profil) ou par `active`
## du message `profiles`. Le message `profiles` arrive après l'ouverture de « Qui roule ? » : avec `active`
## seul, l'écran ouvert juste après un changement de profil mettait le focus sur l'ancien profil (banc des
## menus, scénario `profils`, échecs intermittents du 31 octobre au 2 novembre).
func current_id() -> String:
	return active


## Nom du profil en cours (« » s'il n'est pas encore connu) : titre de « Ma puissance » (lot PP3).
func current_name() -> String:
	var it := _find(current_id())
	if not it.is_empty():
		return str(it.get("name", current_id()))
	return str(profile.get("name", current_id())) if str(profile.get("id", "")) == current_id() else current_id()


func on_profiles(msg: Dictionary) -> void:
	var raw = msg.get("items", [])
	items = raw if raw is Array else []
	active = str(msg.get("active", "")) if msg.get("active") != null else ""
	var t = msg.get("trash", [])
	trash = t if t is Array else []
	var r = msg.get("resets", [])
	resets = r if r is Array else []
	if message == "Enregistrement…":
		message = ""
	if done_message != "":
		message = done_message
		done_message = ""


func on_error(code: String, text: String) -> bool:
	if code not in ["name_invalid", "profile_invalid", "busy"]:
		return false
	done_message = ""
	restoring = false
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
			"detail": ride_text(it) + (" · en cours" if str(it["id"]) == current_id() else "")}
		if str(it["id"]) == current_id():
			out.append(row)
		else:
			rest.append(row)
	if not out.is_empty():   # juste sous le profil en cours, une fois la liste reçue : sa courbe et sa FTP (PP3)
		out.append({"id": POWER_ID, "label": "Ma puissance", "enabled": true,
			"detail": "courbe et FTP estimée de " + current_name()})
	out.append_array(rest)
	if _players().size() < MAX_PROFILES:
		out.append({"id": "new", "label": "Nouveau profil", "enabled": true, "detail": ""})
	if _players().size() > 0:
		out.append({"id": "manage", "label": "Gérer un profil", "enabled": true,
			"detail": "renommer, supprimer, remettre à zéro, restaurer"})
	return out


func manage_list_items() -> Array:
	var out: Array = []
	for it in _players():
		out.append({"id": "p:" + str(it["id"]), "label": str(it.get("name", it["id"])), "enabled": true,
			"detail": ride_text(it)})
	var room := _players().size() < MAX_PROFILES
	out.append({"id": RESTORE_ID, "label": "Restaurer un profil supprimé", "enabled": not trash.is_empty() and room,
		"detail": ("corbeille vide" if trash.is_empty() else ("%d dans la corbeille" % trash.size()
			if room else "8 profils au plus"))})
	out.append({"id": CLEAR_TRIAL_ID, "label": "Vider le profil d'essai", "enabled": true,
		"detail": "séances, pièces et records d'essai"})
	return out


## Profils de la corbeille (écran RESTORE) : nom et date de la suppression.
func restore_items() -> Array:
	var out: Array = []
	for it in trash:
		var d := str(it.get("deleted", ""))
		out.append({"id": "t:" + str(it.get("id", "")), "label": str(it.get("name", "")), "enabled": true,
			"detail": ("supprimé le %s/%s" % [d.substr(8, 2), d.substr(5, 2)]) if d.length() == 10 else ""})
	if out.is_empty():
		out.append({"id": "none", "label": "Corbeille vide", "enabled": false, "detail": ""})
	return out


## Nom d'un profil de la corbeille (message de la restauration).
func trash_name(entry_id: String) -> String:
	for it in trash:
		if str(it.get("id", "")) == entry_id:
			return str(it.get("name", entry_id))
	return entry_id


func manage_items() -> Array:
	var it := _find(manage_id)
	var can_delete := manage_id != current_id() and _players().size() > 1
	var why := "profil en cours" if manage_id == current_id() else ("dernier profil" if not can_delete else "")
	var out := [{"id": "rename", "label": "Renommer", "enabled": true, "detail": str(it.get("name", ""))},
		{"id": "delete", "label": "Supprimer", "enabled": can_delete, "detail": why}]
	var own := manage_id == current_id()
	out.append({"id": RESET_ID, "label": "Remettre à zéro mes statistiques", "enabled": own,
		"detail": "sauvegarde faite avant, annulable" if own else "choisir ce profil d'abord"})
	if own and not resets.is_empty():
		out.append({"id": UNDO_RESET_ID, "label": "Annuler la remise à zéro", "enabled": true,
			"detail": "remise du " + reset_when(resets[0])})
	out.append({"id": BACKUPS_ID, "label": "Restaurer une sauvegarde", "enabled": own,
		"detail": "copie faite chaque semaine" if own else "choisir ce profil d'abord"})
	return out


func on_backups(msg: Dictionary) -> void:
	var raw = msg.get("items", [])
	backups = raw if raw is Array else []
	backups_loaded = true
	if done_message != "":
		message = done_message
		done_message = ""


## « dim. 22/11 à 13:05 » d'une copie {date, time} (jour de la semaine calculé, sans fuseau).
static func backup_when(b: Dictionary) -> String:
	var d := str(b.get("date", ""))
	if d.length() != 10:
		return d + " à " + str(b.get("time", ""))
	var unix := Time.get_unix_time_from_datetime_string(d + "T00:00:00")
	var wd: int = Time.get_datetime_dict_from_unix_time(unix)["weekday"]
	return "%s %s/%s à %s" % [WEEKDAYS[wd], d.substr(8, 2), d.substr(5, 2), str(b.get("time", ""))]


static func backup_label(b: Dictionary) -> String:
	return str(REASON_WORDS.get(str(b.get("reason", "")), "Copie")) + ", " + backup_when(b)


static func sessions_text(n: int) -> String:
	return "aucune séance" if n <= 0 else ("1 séance" if n == 1 else "%d séances" % n)


## Fin de la restauration (lot SV1) : vrai une fois, à la liste qui suit la restauration.
func take_restored() -> bool:
	var was := restoring
	restoring = false
	return was


## Copies du profil en cours (écran BACKUPS) : raison et date en mots, nombre de séances.
func backup_items() -> Array:
	var out: Array = []
	for b in backups:
		out.append({"id": "b:" + str(b.get("id", "")), "label": backup_label(b), "enabled": true,
			"detail": sessions_text(int(b.get("sessions", 0)))})
	if out.is_empty():
		out.append({"id": "none", "label": "Recherche des copies…" if not backups_loaded else "Aucune copie pour l'instant",
			"enabled": false, "detail": "" if not backups_loaded else "la première se fait au prochain lancement"})
	return out


func _backup(entry_id: String) -> Dictionary:
	for b in backups:
		if str(b.get("id", "")) == entry_id:
			return b
	return {}


## Confirmation de la restauration d'une copie (lot SV1) : « Non » par défaut, boutons écrits courts.
func backup_confirm(entry_id: String) -> Dictionary:
	var b := _backup(entry_id)
	return {"title": ("Restaurer la copie du %s ? Ton profil revient à cet état (réglages et FTP compris). "
		+ "Ton profil actuel est sauvegardé avant.") % backup_when(b), "id": entry_id,
		"yes": "Oui, restaurer", "yes_detail": "", "no": "Non, garder mon profil", "no_detail": ""}


## « 28/11 à 09:30 » d'une remise à zéro {id, date, time}.
static func reset_when(r: Dictionary) -> String:
	var d := str(r.get("date", ""))
	var day := (d.substr(8, 2) + "/" + d.substr(5, 2)) if d.length() == 10 else d
	return day + " à " + str(r.get("time", ""))


## Confirmation de la remise à zéro (lot RZ1) : question qui dit ce qui part et ce qui reste, boutons écrits courts
## (la boîte de confirmation coupe les libellés longs : banc des menus du 22 novembre).
func reset_confirm() -> Dictionary:
	var name := str(_find(manage_id).get("name", manage_id))
	return {"title": ("Remettre à zéro les statistiques de « %s » ? Niveau, pièces, cartes et records repartent "
		+ "de zéro. Séances, FTP, réglages et cote Elo gardés. Sauvegarde faite avant.") % name,
		"yes": "Oui, remettre à zéro", "yes_detail": "", "no": "Non, garder mes statistiques", "no_detail": ""}


## Confirmation de l'annulation de la dernière remise à zéro (lot RZ1).
func undo_confirm() -> Dictionary:
	var r: Dictionary = resets[0] if not resets.is_empty() else {}
	return {"title": ("Annuler la remise à zéro du %s ? Les statistiques d'avant reviennent ; "
		+ "les séances courues depuis comptent aussi.") % reset_when(r), "id": str(r.get("id", "")),
		"yes": "Oui, annuler la remise", "yes_detail": "", "no": "Non, garder la remise", "no_detail": ""}


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
