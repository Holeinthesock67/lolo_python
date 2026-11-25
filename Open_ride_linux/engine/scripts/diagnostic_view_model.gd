extends RefCounted

## Écran « Réglages › Diagnostic » (lot DG1 ; contrat IPC révision 1.35, commande `create_diagnostic`, message
## `diagnostic`). Modèle sans nœud, relié par menu_flow.gd : le cycliste choisit le dossier où déposer le fichier
## (Téléchargements, Bureau ou dossier OpenRide), le core l'écrit sans donnée privée et répond par le chemin. Rien
## n'est envoyé : le fichier se joint à la main à un signalement. La ligne d'état dit ce qui se passe, en mots.

const SCREEN := "diagnostic"
## Choix du dossier : [valeur de `dest`, libellé de la ligne, nom du dossier dans les messages].
const DESTS := [["telechargements", "Enregistrer dans Téléchargements", "Téléchargements"],
	["bureau", "Enregistrer sur le Bureau", "Bureau"],
	["openride", "Enregistrer dans le dossier OpenRide", "dossier OpenRide"]]
const PREFIX := "dest:"

## Dossier demandé, en attente de la réponse du core ("" sinon).
var busy := ""
## Ligne d'état : attente, chemin du fichier écrit ou échec.
var message := ""
## Dernier fichier écrit (chemin tel que le core le donne, « ~ » pour le dossier personnel).
var last_path := ""


func menu_items() -> Array:
	var out: Array = []
	for d in DESTS:
		out.append({"id": PREFIX + str(d[0]), "label": str(d[1]), "enabled": busy == ""})
	return out


## Choix d'une ligne : {"action": "create_diagnostic", "dest": …} ; {} pendant une écriture ou hors ligne.
func handle(item_id: String) -> Dictionary:
	if not item_id.begins_with(PREFIX) or busy != "":
		return {}
	var dest := item_id.substr(PREFIX.length())
	if _label(dest) == "":
		return {}
	busy = dest
	message = "Création du fichier de diagnostic…"
	return {"action": "create_diagnostic", "dest": dest}


## Réponse `diagnostic` du core.
func on_diagnostic(msg: Dictionary) -> void:
	busy = ""
	if bool(msg.get("ok", false)):
		last_path = str(msg.get("path", ""))
		message = "Fichier créé (%d ko) : %s. Rien n'a été envoyé." % [int(msg.get("size_kb", 0)), last_path]
	else:
		message = "Échec : " + str(msg.get("reason", "fichier non créé"))


## Refus du core (`bad_args`) pendant une écriture : la ligne d'état le dit ; faux si l'erreur n'est pas pour cet écran.
func on_error(code: String, text: String) -> bool:
	if busy == "" or code != "bad_args":
		return false
	busy = ""
	message = "Échec : " + text
	return true


## Carte de détail sous le focus : ce que contient le fichier, ce qui est masqué, ce qui n'est pas fait.
func sheet(item_id: String) -> Dictionary:
	if not item_id.begins_with(PREFIX):
		return {}
	var where := _label(item_id.substr(PREFIX.length()))
	return {"title": "Diagnostic", "name": "Fichier pour signaler un problème", "lines": [
		"Objectif : un seul fichier à joindre quand quelque chose ne marche pas.",
		"Contenu : versions, qualité graphique, état des capteurs, réglages, erreurs récentes.",
		"Masqué : noms, adresses Bluetooth, appareils, poids, FTP, positions, Wi-Fi.",
		"Rien n'est envoyé : le fichier reste sur cet ordinateur (" + where + "), à vous de le joindre.",
		"A maintenu (Entrée au clavier) : créer le fichier."]}


static func _label(dest: String) -> String:
	for d in DESTS:
		if str(d[0]) == dest:
			return str(d[2])
	return ""
