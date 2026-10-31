extends RefCounted

## Aide de la liste des parcours (lot O22, demande du propriétaire du 31 octobre : « Le menu est
## explicite avec des légendes pour ces fonctions ? »), sans nœud. En fin de liste des parcours,
## « Ajouter un parcours » montre dans la carte de droite comment ajouter une trace, et « Comment ça
## marche ? » ouvre l'écran « Aide parcours » : un sujet par ligne, son explication dans la carte de
## détail (même carte que les fiches, menu_flow.card()). Textes alignés sur docs/GUIDE_UTILISATION.md
## §4 et §4 bis, et sur le core (config.py : GPX_DIR ; route_import.py, lot O23 ; catalog.py : fiche `<trace>.toml` ;
## open_world_save.py : balade enregistrée en GPX au-delà de 500 m).
## Pas de class_name : charger par preload("res://scripts/route_help.gd").

const SCREEN := "route_help"
const TITLE := "Aide parcours"

## Sujets dans l'ordre de l'écran : id, libellé (ligne du menu et nom de la carte), lignes de la carte.
const TOPICS := [
	["choose", "Choisir un parcours", [
		"La liste montre les parcours compilés. La fiche à droite donne distance, dénivelé, montée principale et durée estimée.",
		"A maintenu (Entrée au clavier) choisit le parcours ; Démarrer, sur l'écran Prêt, lance la séance.",
		"En bas de la liste, « Trier par » et « Étiquette » : A maintenu passe au choix suivant.",
		"Un parcours illisible reste grisé, avec son erreur.",
	]],
	["add", "Ajouter une trace", [
		"« Ajouter un parcours » liste les traces de Téléchargements, du Bureau et de ~/OpenRide/Import : un .gpx, ou l'export de Garmin Connect tel quel (.fit, .tcx, .fit.gz, .tcx.gz, .zip).",
		"A maintenu copie la trace dans ~/OpenRide/GPX/ et la compile, sans relancer : quelques secondes, ou plusieurs minutes la première fois dans une région (relief et cartes téléchargés).",
		"Le parcours arrive ensuite dans la liste, sous le focus. Une trace illisible affiche son erreur.",
		"Autre moyen : déposer la trace dans ~/OpenRide/GPX/ puis relancer OpenRide, qui la compile au démarrage.",
	]],
	["sheet", "Fiche d'un parcours (.toml)", [
		"À côté de la trace, un petit fichier du même nom en .toml rend la fiche plus parlante.",
		"Clés : name (nom), description, region, tags (étiquettes).",
		"Les étiquettes servent au filtre « Étiquette » de la liste.",
	]],
	["open_world", "Sans trace : le monde ouvert", [
		"« Monde ouvert », à l'accueil, crée la route en roulant à partir des cartes OpenStreetMap, sans trace.",
		"Tu choisis le départ sur un globe puis sur une carte ; il faut Internet la première fois dans une région.",
		"« Terminer et enregistrer » garde la balade (au-delà de 500 m) : elle devient un parcours de cette liste au démarrage suivant.",
	]],
]


## Éléments de l'écran « Aide parcours » : un par sujet.
static func items() -> Array:
	var out: Array = []
	for t in TOPICS:
		out.append({"id": "help:" + str(t[0]), "label": str(t[1]), "enabled": true, "detail": ""})
	return out


## Carte de détail d'un sujet ({} si l'id est inconnu).
static func sheet(topic: String) -> Dictionary:
	for t in TOPICS:
		if t[0] == topic:
			return {"title": TITLE, "name": str(t[1]), "lines": (t[2] as Array).duplicate()}
	return {}
