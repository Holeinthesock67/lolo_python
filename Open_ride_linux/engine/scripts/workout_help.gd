extends RefCounted

## Aide du sous-menu ERG (demande du propriétaire du 30 octobre : « Faudra expliquer cela dans le menu
## erg »), sans nœud. « Comment ça marche ? » en fin de liste des entraînements ouvre l'écran
## « Aide ERG » : un sujet par ligne, son explication dans la carte de détail à droite (même carte que
## les fiches, menu_flow.card()). Les lignes « Créer » et « Importer » de la liste montrent aussi
## l'explication de leur sujet. Textes alignés sur docs/GUIDE_UTILISATION.md §5 et sur le core
## (workout.py : ERG_MIN_W, biais 80–120 % ; workout_menu.py : IMPORT_SOURCES ; workout_formats.py :
## syntaxe QWKcode, lot O20).
## Pas de class_name : charger par preload("res://scripts/workout_help.gd").

const SCREEN := "workout_help"
const TITLE := "Aide ERG"

## Sujets dans l'ordre de l'écran : id, libellé (ligne du menu et nom de la carte), lignes de la carte.
const TOPICS := [
	["choose", "Choisir un entraînement", [
		"La liste montre les entraînements de ~/OpenRide/Workouts/, du plus court au plus long.",
		"A maintenu (Entrée au clavier) choisit l'entraînement ; Démarrer, sur l'écran Prêt, lance la séance.",
		"Un fichier invalide reste grisé, avec son erreur.",
		"Quatre façons d'en ajouter : Créer, QWKcode, Importer, ou écrire un fichier à la main.",
	]],
	["create", "Créer des intervalles", [
		"Échauffement, répétitions effort et récupération (durée et % de la FTP), retour au calme.",
		"A maintenu ouvre une ligne, + et − règlent, A maintenu garde la valeur, Y annule.",
		"« Enregistrer et choisir » écrit le fichier .zwo et le choisit.",
		"Mêmes réglages : pas de doublon. Aucun entraînement n'est remplacé : un nom déjà pris reçoit _2, _3…",
	]],
	["qwk", "Saisie QWKcode (GoldenCheetah)", [
		"Un fichier texte .qwk, une ligne par segment : [Nx] durée@puissance[-puissance] [rdurée@puissance].",
		"Durée en h, m ou s (1m30s). Puissance en watts, ou en % de la FTP avec % (50-75%).",
		"10m@130-220 : rampe de 130 à 220 W.   4x 5m@280 r3m@140 : 4 × (5 min à 280 W, 3 min à 140 W).",
		"Une ligne # en tête donne le nom. Enregistre-le dans Téléchargements, puis Importer un fichier.",
	]],
	["import", "Importer un fichier", [
		"Fichiers .zwo, .erg, .mrc et .qwk trouvés dans Téléchargements, sur le Bureau ou dans ~/OpenRide/Import.",
		"Le fichier est vérifié, puis copié dans ~/OpenRide/Workouts/ ; s'il est invalide, l'erreur s'affiche.",
		"Déjà importé : rien n'est recopié. Même nom, autre contenu : _2, _3…",
	]],
	["write", "Écrire un fichier à la main", [
		"Un fichier posé directement dans ~/OpenRide/Workouts/ apparaît dans la liste, sans import.",
		".zwo (Zwift) et .mrc : puissances en % de la FTP, elles suivent ta FTP.",
		".erg : watts fixes, quelle que soit ta FTP. .qwk : watts ou %.",
		"Un bloc FreeRide devient un palier à 50 W. Exemples et détails : guide d'utilisation, section 5.",
	]],
	["ride", "Pendant la séance", [
		"Le trainer impose la cible du bloc, jamais sous 50 W ; la pente ne compte plus.",
		"+ et − : intensité de ± 2 % (appui long ± 10 %), entre 80 et 120 %.",
		"Z : bloc suivant. Y : pause.",
		"Le bandeau du bas montre le bloc, le temps restant, la cible et le bloc suivant.",
	]],
]


## Éléments de l'écran « Aide ERG » : un par sujet.
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
