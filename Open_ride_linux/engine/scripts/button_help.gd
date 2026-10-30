extends RefCounted

## Aide des boutons des menus (lot « présentation des menus », étape 1), sans nœud : ce que fait chaque
## bouton du Click sur l'écran affiché, d'après le plan des boutons de la spécification générale §7.1
## (seule référence) et menu_model.gd. Une seule table : un changement du plan, ou du clavier avec le
## lot O17 (décision D6), ne touche que les constantes ci-dessous. Affichée par button_bar.gd.
## Pas de class_name : charger par preload("res://scripts/button_help.gd").

## Rôle de Y selon l'écran (menu_model._back) : rien sur l'accueil, reprendre en pause, « Non » sur
## l'écran de confirmation ; ailleurs, écran précédent.
const Y_LABELS := {"home": "", "pause": "Reprendre", "confirm": "Annuler", "edit": "Annuler"}
## Écran de réglage d'une valeur (en place dans la liste, ou écran de la difficulté de la pause) : « edit »,
## clé d'aide donnée par menu_view.gd ; A maintenu enregistre, + et B règlent (menu_flow._handle_edit).
const EDIT := "edit"
const Y_DEFAULT := "Retour"
## Double légende : une ligne pour les boutons du Click, une pour les touches du clavier (key_map.gd :
## chaque touche double un bouton du Click). Titres des deux lignes.
const CLICK_TITLE := "Click"
const KEYBOARD_TITLE := "Clavier"
## Touche du clavier de chaque bouton du Click (key_map.gd) : A maintenu = Entrée, B = « − », Y = Échap.
const KEYBOARD_KEYS := {"A": ["A"], "A_HOLD": ["Entrée"], "+": ["+"], "B": ["−"], "Y": ["Échap"]}


## Entrées de l'aide de l'écran `screen`, dans l'ordre d'affichage :
## [{keys: [boutons du Click], hold: appui long, kb: [touches du clavier], text: action, main: action principale}].
static func entries(screen: String) -> Array:
	var out: Array = [
		{"keys": ["A"], "hold": true, "text": "Valider", "main": true},
		{"keys": ["+", "A"], "hold": false, "text": "Suivant", "main": false},
		{"keys": ["B"], "hold": false, "text": "Précédent", "main": false},
	]
	if screen == EDIT:
		out = [
			{"keys": ["A"], "hold": true, "text": "Enregistrer", "main": true},
			{"keys": ["+", "A"], "hold": false, "text": "Augmenter", "main": false},
			{"keys": ["B"], "hold": false, "text": "Diminuer", "main": false},
		]
	var y := str(Y_LABELS.get(screen, Y_DEFAULT))
	if y != "":
		out.append({"keys": ["Y"], "hold": false, "text": y, "main": false})
	for e in out:
		e["kb"] = keyboard_keys(e["keys"], bool(e["hold"]))
	return out


## Touches du clavier qui doublent `keys` (boutons du Click) : A maintenu = Entrée, B = « − », Y = Échap.
static func keyboard_keys(keys: Array, hold: bool) -> Array:
	var out: Array = []
	for k in keys:
		out.append_array(KEYBOARD_KEYS["A_HOLD"] if (k == "A" and hold) else KEYBOARD_KEYS.get(k, [k]))
	return out


## Aide en une ligne (tests et journal) : « A maintenir : Valider · + A : Suivant · … · Clavier — Entrée :
## Valider · + A : Suivant · − : Précédent · Échap : Retour ».
static func text(screen: String) -> String:
	var click: Array[String] = []
	var keyboard: Array[String] = []
	for e in entries(screen):
		click.append("%s%s : %s" % [" ".join(PackedStringArray(e["keys"])), " maintenir" if e["hold"] else "", e["text"]])
		keyboard.append("%s : %s" % [" ".join(PackedStringArray(e["kb"])), e["text"]])
	return " · ".join(click) + " · " + KEYBOARD_TITLE + " — " + " · ".join(keyboard)
