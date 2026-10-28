extends RefCounted

## Aide des boutons des menus (lot « présentation des menus », étape 1), sans nœud : ce que fait chaque
## bouton du Click sur l'écran affiché, d'après le plan des boutons de la spécification générale §7.1
## (seule référence) et menu_model.gd. Une seule table : un changement du plan, ou du clavier avec le
## lot O17 (décision D6), ne touche que les constantes ci-dessous. Affichée par button_bar.gd.
## Pas de class_name : charger par preload("res://scripts/button_help.gd").

## Rôle de Y selon l'écran (menu_model._back) : rien sur l'accueil, reprendre en pause, « Non » sur
## l'écran de confirmation ; ailleurs, écran précédent.
const Y_LABELS := {"home": "", "pause": "Reprendre", "confirm": "Annuler"}
const Y_DEFAULT := "Retour"
## Rappel du clavier (key_map.gd : chaque touche double un bouton du Click), coupé en dernier si la place manque.
const KEYBOARD := "Clavier : Entrée valide, Échap revient"


## Entrées de l'aide de l'écran `screen`, dans l'ordre d'affichage :
## [{keys: [touches], hold: appui long, text: action, main: action principale}].
static func entries(screen: String) -> Array:
	var out: Array = [
		{"keys": ["A"], "hold": true, "text": "Valider", "main": true},
		{"keys": ["+", "A"], "hold": false, "text": "Suivant", "main": false},
		{"keys": ["B"], "hold": false, "text": "Précédent", "main": false},
	]
	var y := str(Y_LABELS.get(screen, Y_DEFAULT))
	if y != "":
		out.append({"keys": ["Y"], "hold": false, "text": y, "main": false})
	return out


## Aide en une ligne (tests et journal) : « A maintenir : Valider · + A : Suivant · … · Clavier : … ».
static func text(screen: String) -> String:
	var parts: Array[String] = []
	for e in entries(screen):
		parts.append("%s%s : %s" % [" ".join(PackedStringArray(e["keys"])), " maintenir" if e["hold"] else "", e["text"]])
	parts.append(KEYBOARD)
	return " · ".join(parts)
