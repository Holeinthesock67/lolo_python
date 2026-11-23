extends RefCounted

## Aide du Grand Prix des objets (lot GPH1, demande du propriétaire du 21 novembre 2026 : « À quoi sert le
## changement de voie en Grand Prix ? » puis « Aucune explication nulle part »), sans nœud. Sur l'écran Prêt du
## mode, la ligne « Comment ça marche ? » montre le résumé dans la carte de droite (sujet `summary`) et ouvre
## l'écran « Aide Grand Prix » : un sujet par ligne, son explication dans la carte de détail, comme l'aide des
## parcours (route_help.gd) et du sous-menu ERG (workout_help.gd). Textes alignés sur le core
## (grandprix/mode.py : trois voies, boîte prise seulement réserve vide, reformée en 2 s, changement de voie en
## 0,6 s, placement automatique repris après 20 s sans objet en vue ; grandprix/items.py, lot GPO1 : durées 5 s
## et 12 s, boîtes de famille par voie ; session.py : en voie choisie, le cycliste
## ne se range plus dans la roue) et sur docs/GUIDE_UTILISATION.md (Grand Prix des objets).
## Pas de class_name : preload("res://scripts/grandprix/gp_help.gd").

const SCREEN := "gp_help"
const TITLE := "Aide Grand Prix"
## Sujet montré sur l'écran Prêt quand le focus est sur « Comment ça marche ? ».
const SUMMARY := "summary"

## Sujets dans l'ordre de l'écran : id, libellé (ligne du menu et nom de la carte), lignes de la carte.
const TOPICS := [
	[SUMMARY, "Le Grand Prix en bref", [
		"Une course en tours contre les bots, sur une boucle à trois voies. Le premier à l'arrivée gagne.",
		"Passe sur une boîte pour gagner un objet, puis Z pour l'utiliser. Chaque effet dure 5 s, ou 12 s pour les plus forts.",
		"Boîte de gauche « + BONUS » : pour toi. Centre « ? SURPRISE » : tout. Droite « ! ATTAQUE » : contre les autres.",
		"Change de voie pour prendre une boîte encore là ou éviter un objet : A ou ← →.",
		"Les objets ne changent que la vitesse à l'écran, jamais la résistance du vélo ni tes watts.",
	]],
	["boxes", "Boîtes et objets", [
		"Une rangée de trois boîtes, une par voie, tous les 500 m (réglage « Écart des boîtes »).",
		"Tu prends la boîte de ta voie, seulement si ta réserve est vide : utilise d'abord ton objet (Z).",
		"Chaque boîte porte son signe écrit : à gauche « + BONUS » (objets pour toi et sonnette), au centre « ? SURPRISE » (tout le tirage), à droite « ! ATTAQUE » (attaques et pièges).",
		"Une boîte prise par un bot disparaît 2 s : passe par une autre voie.",
		"Plus tu es loin du premier, plus l'objet tiré est fort.",
		"Bidon : lâché derrière toi sur ta voie. Musette : lancée tout droit devant sur ta voie. Musette guidée : suit le coureur juste devant, même s'il change de voie.",
	]],
	["lanes", "À quoi servent les voies", [
		"Trois voies : gauche, centre, droite. Les trois traits en bas de l'écran montrent la tienne.",
		"Elles servent à choisir ta boîte (+ BONUS, ? SURPRISE ou ! ATTAQUE), à prendre une boîte encore là, à éviter un bidon ou une musette sur ta voie, et à viser : ta musette part sur ta voie.",
		"Choisis ta voie avant la rangée de boîtes : les bots le font aussi.",
		"Trait gris : placement automatique, tu te ranges dans la roue du coureur devant pour l'abri.",
		"Trait blanc : voie choisie par toi. Tu ne te ranges plus dans la roue : tu peux perdre l'abri.",
		"Après 20 s sans boîte ni objet en vue, le placement automatique revient tout seul.",
	]],
	["buttons", "Boutons", [
		"Z : utiliser l'objet en réserve.",
		"A : voie suivante quand une boîte ou un objet est à moins de 150 m (ou une musette derrière toi) ; sinon vue suivante.",
		"← → : voie à gauche ou à droite, à tout moment. Le changement prend 0,6 s.",
		"A maintenu : retour au placement automatique.",
		"Au clavier : mêmes touches (Z, A, Maj+A, flèches).",
	]],
	["hits", "Coups reçus et défense", [
		"Touché : le bandeau du bas le dit, avec l'objet et le temps restant ; le bord de l'écran prend sa couleur.",
		"Une musette guidée derrière toi : le bandeau prévient. Un bidon ou une musette en réserve la pare tout seul.",
		"Un coup te ralentit 5 s ; au-dessus du coureur touché s'écrit le temps perdu (« ZIOUF ! −7 s »).",
		"Après un coup reçu, 5 s sans nouveau coup.",
		"La super-forme te rend invincible 12 s ; la sonnette détruit bidons et musettes à 15 m autour de toi.",
		"Un objet arrêté (réserve, sonnette, super-forme) fait écrire « PARÉ ! » au-dessus de celui qui l'arrête, bots compris.",
	]],
]


## Éléments de l'écran « Aide Grand Prix » : un par sujet.
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
