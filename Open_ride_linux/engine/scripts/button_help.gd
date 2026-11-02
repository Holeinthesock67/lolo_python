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
const NAME_GRID := "profile_name"   # grille du nom d'un profil (profiles_view_model.gd, lot MJ8)
## Saisie de texte partagée (text_entry.gd, lot O31) : nom d'un profil et recherche du monde ouvert.
const WORLD_SEARCH_GRID := "world_search"
## Saisie du QWKcode (qwk_editor.gd, lot O21) : au clavier, les touches écrivent (main._qwk_key), donc + A
## et − n'y sont pas des boutons du clavier (boutons du Click : mêmes pastilles que les autres menus) ; les flèches ← → passent d'une ligne à l'autre, Entrée change de ligne
## ou choisit « Enregistrer » / « Tout effacer ». Touches données une à une (`kb`), comme le monde ouvert.
const QWK := "workout_qwk"
const QWK_ENTRIES := [
	{"keys": ["A"], "hold": true, "text": "Valider", "main": true, "kb": []},
	{"keys": NEXT_KEYS, "hold": false, "text": "Suivant", "main": false, "kb": []},
	{"keys": PREV_KEYS, "hold": false, "text": "Précédent", "main": false, "kb": []},
	{"keys": [], "hold": false, "text": "Écrire", "main": true, "kb": ["touches"]},
	{"keys": [], "hold": false, "text": "Ligne, valider", "main": false, "kb": ["Entrée"]},
	{"keys": [], "hold": false, "text": "Déplacer", "main": false, "kb": ["←", "→"]},
	{"keys": [], "hold": false, "text": "Effacer", "main": false, "kb": ["Retour arrière"]},
	{"keys": ["Y"], "hold": false, "text": "Retour", "main": false, "kb": ["Échap"]},
]
const Y_DEFAULT := "Retour"
## Double légende : une ligne pour les boutons du Click, une pour les touches du clavier (key_map.gd :
## chaque touche double un bouton du Click). Titres des deux lignes.
const CLICK_TITLE := "Click"
const KEYBOARD_TITLE := "Clavier"
## Boutons du Click qui avancent et reculent d'un élément (§7.1) : + et A, flèche droite du boîtier gauche ;
## − du boîtier gauche, B du boîtier droit (il double « − ») et flèche gauche.
const NEXT_KEYS := ["+", "A", "→"]
const PREV_KEYS := ["−", "B", "←"]
## Touche du clavier de chaque bouton du Click (key_map.gd) : A maintenu = Entrée, B = « − » (pas de touche
## propre), Y = Échap, flèches = flèches.
const KEYBOARD_KEYS := {"A": ["A"], "A_HOLD": ["Entrée"], "+": ["+"], "−": ["−"], "B": ["−"], "Y": ["Échap"],
	"→": ["→"], "←": ["←"]}
## Menu « Monde ouvert » (world_menu_view.gd, lot O22) : une aide par état de world_menu_model.gd, clé
## WORLD_PREFIX + état. Au clavier, les lettres tapées sur le globe et dans la recherche cherchent un
## lieu (main._world_menu_key) : A et Y n'y sont donc pas des boutons, d'où des touches données une à
## une (`kb`). Une entrée sans bouton du Click (`keys` vide) ou sans touche (`kb` vide) n'est montrée que
## sur l'autre ligne. Mêmes pastilles que les autres menus : flèches ← → du boîtier gauche, − à côté de B.
const WORLD_PREFIX := "world_"
const WORLD := {
	"globe": [
		{"keys": ["A"], "hold": false, "text": "Carte", "main": true, "kb": []},
		{"keys": ["Z"], "hold": false, "text": "Chercher", "main": true, "kb": ["lettres"]},
		{"keys": ["←", "→"], "hold": false, "text": "Tourner", "main": false, "kb": ["←", "→"]},
		{"keys": ["+", "−", "B"], "hold": true, "text": "Incliner", "main": false, "kb": ["Page haut", "Page bas"]},
		{"keys": ["A"], "hold": true, "text": "Épingler", "main": false, "kb": ["Entrée"]},
		{"keys": ["Y"], "hold": false, "text": "Quitter", "main": false, "kb": ["Échap"]},
	],
	"search_results": [
		{"keys": ["A"], "hold": false, "text": "Choisir le lieu", "main": true, "kb": ["Entrée"]},
		{"keys": ["+", "−", "B"], "hold": false, "text": "Lieu suivant, précédent", "main": false, "kb": ["+", "−"]},
		{"keys": ["Z"], "hold": false, "text": "Écrire", "main": false, "kb": ["lettres"]},
		{"keys": [], "hold": false, "text": "Effacer", "main": false, "kb": ["Retour arrière"]},
		{"keys": ["Y"], "hold": false, "text": "Retour", "main": false, "kb": ["Échap"]},
	],
	"map": [
		{"keys": ["A"], "hold": false, "text": "Départ ici", "main": true, "kb": ["Entrée"]},
		{"keys": ["←", "→"], "hold": false, "text": "Ouest, est", "main": false, "kb": ["←", "→"]},
		{"keys": ["−", "B", "+"], "hold": false, "text": "Nord, sud", "main": false, "kb": ["−", "+"]},
		{"keys": ["−", "B", "+"], "hold": true, "text": "Nord, sud 500 m", "main": false, "kb": ["Page bas", "Page haut"]},
		{"keys": ["Y"], "hold": false, "text": "Retour", "main": false, "kb": ["Échap"]},
	],
	"setup": [
		{"keys": ["A"], "hold": false, "text": "Démarrer", "main": true, "kb": ["Entrée"]},
		{"keys": ["+", "−", "B"], "hold": false, "text": "Ligne suivante, précédente", "main": false, "kb": ["+", "−"]},
		{"keys": ["←", "→"], "hold": false, "text": "Changer la valeur", "main": false, "kb": ["←", "→"]},
		{"keys": ["Y"], "hold": false, "text": "Retour", "main": false, "kb": ["Échap"]},
	],
	"loading": [
		{"keys": ["Y"], "hold": false, "text": "Annuler", "main": false, "kb": ["Échap"]},
	],
}


## Entrées de l'aide de l'écran `screen`, dans l'ordre d'affichage :
## [{keys: [boutons du Click], hold: appui long, kb: [touches du clavier], text: action, main: action principale}].
static func entries(screen: String) -> Array:
	if screen == NAME_GRID:
		return text_grid("Valider le nom")
	if screen == WORLD_SEARCH_GRID:
		return text_grid("Voir les résultats")
	if screen.begins_with(WORLD_PREFIX):
		return (WORLD.get(screen.substr(WORLD_PREFIX.length()), []) as Array).duplicate(true)
	if screen == QWK:
		return QWK_ENTRIES.duplicate(true)
	var out: Array = [
		{"keys": ["A"], "hold": true, "text": "Valider", "main": true},
		{"keys": NEXT_KEYS, "hold": false, "text": "Suivant", "main": false},
		{"keys": PREV_KEYS, "hold": false, "text": "Précédent", "main": false},
	]
	if screen == EDIT:
		out = [
			{"keys": ["A"], "hold": true, "text": "Enregistrer", "main": true},
			{"keys": NEXT_KEYS, "hold": false, "text": "Augmenter", "main": false},
			{"keys": PREV_KEYS, "hold": false, "text": "Diminuer", "main": false},
		]
	var y := str(Y_LABELS.get(screen, Y_DEFAULT))
	if y != "":
		out.append({"keys": ["Y"], "hold": false, "text": y, "main": false})
	for e in out:
		e["kb"] = keyboard_keys(e["keys"], bool(e["hold"]))
	return out


## Grille de saisie (text_entry.gd) : Z écrit, Y efface, A maintenu valide ; au clavier, on tape le texte.
static func text_grid(validate_text: String) -> Array:
	var out: Array = [
		{"keys": ["A"], "hold": true, "text": validate_text, "main": true},
		{"keys": NEXT_KEYS, "hold": false, "text": "Lettre suivante", "main": false},
		{"keys": PREV_KEYS, "hold": false, "text": "Précédente", "main": false},
		{"keys": ["Z"], "hold": false, "text": "Écrire", "main": false},
		{"keys": ["Y"], "hold": false, "text": "Effacer", "main": false},
	]
	for e in out:
		e["kb"] = keyboard_keys(e["keys"], bool(e["hold"]))
	out[3]["kb"] = ["lettres"]
	out[4]["kb"] = ["Retour arrière"]
	return out


## Touches du clavier qui doublent `keys` (boutons du Click), chacune une fois : A maintenu = Entrée,
## − et B = « − », Y = Échap.
static func keyboard_keys(keys: Array, hold: bool) -> Array:
	var out: Array = []
	for k in keys:
		for kb in (KEYBOARD_KEYS["A_HOLD"] if (k == "A" and hold) else KEYBOARD_KEYS.get(k, [k])):
			if not kb in out:
				out.append(kb)
	return out


## Aide en une ligne (tests et journal) : « A maintenir : Valider · + A → : Suivant · − B ← : Précédent · … ·
## Clavier — Entrée : Valider · + A → : Suivant · − ← : Précédent · Échap : Retour ».
static func text(screen: String) -> String:
	var click: Array[String] = []
	var keyboard: Array[String] = []
	for e in entries(screen):
		if not (e["keys"] as Array).is_empty():
			click.append("%s%s : %s" % [" ".join(PackedStringArray(e["keys"])), " maintenir" if e["hold"] else "", e["text"]])
		if not (e["kb"] as Array).is_empty():
			keyboard.append("%s : %s" % [" ".join(PackedStringArray(e["kb"])), e["text"]])
	return " · ".join(click) + " · " + KEYBOARD_TITLE + " — " + " · ".join(keyboard)
