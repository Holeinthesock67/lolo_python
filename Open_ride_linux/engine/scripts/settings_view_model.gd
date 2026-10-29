extends RefCounted

## Réglages du menu (Lot O4, contrat IPC révision 1.3), sans nœud : éléments de l'écran « Réglages »
## et écran de modification d'une valeur au Click.
##
## Le core envoie la liste (`settings` : {key, label, type, value, min, max, step, unit, choices,
## applies}) ; ce modèle la met en forme et garde la valeur en cours de modification. Écran de
## modification (menu_flow._handle_edit, spécification générale §7.1) : + / − changent la valeur (long :
## cinq pas), A long enregistre, Y annule ; la rangée du réglage passe en mode édition dans sa liste
## (row(), lot « présentation des menus »). Tout réglage en % de 0 à 100 (difficulté, volumes) s'affiche en curseur ; le curseur de la
## difficulté sert aussi sur l'écran de pause, où il envoie `set_difficulty` (lot Q1) sans toucher à
## config.toml. Les autres lignes de la pause (lot O18, session libre) : mode SIM / ERG / ERG cadence,
## puissance cible et cadence cible, qui envoient `set_ride_mode` ; clés « pause.… » (pause_item()).
## Le même écran sert aux paramètres de « Créer un entraînement » (lot N16, clés « workout.… ») :
## commit() renvoie alors l'action interne `builder_set`.
## Pas de class_name : charger par preload("res://scripts/settings_view_model.gd").

const WorkoutBuilder := preload("res://scripts/workout_builder.gd")
const GarageViewModel := preload("res://scripts/garage_view_model.gd")

## Écran de modification des champs de l'avatar du Garage (V8) : seul réglage qui garde son écran
## (aperçu 3D à côté), les autres se modifient en place dans leur liste.
const EDIT_SCREEN := "setting_edit"
## Clés des lignes modifiables de l'écran de pause : « pause. » + identifiant de la ligne (menu_model.gd).
const PAUSE_PREFIX := "pause."
const PAUSE_DIFFICULTY := "pause.difficulty"   # difficulté de la séance en cours
const PAUSE_RIDE_MODE := "pause.ride_mode"     # session libre : SIM, ERG ou ERG cadence (lot O18)
const PAUSE_TARGET_W := "pause.target_w"       # ERG libre : puissance cible
const PAUSE_CADENCE := "pause.cadence_rpm"     # ERG cadence : cadence cible
const RIDE_MODES := ["sim", "erg", "cadence"]
## Textes des choix envoyés par le core sous une forme technique : {clé: {valeur: texte}}.
## Option « Bonus » du mode classique (série T, lot T10) : `on` / `off` affichés « oui » / « non ».
## Courbes de la séance (lot O14) : `render.chart` prend `hidden` / `reduced` / `full`.
## Compteur d'images/s du HUD (fps_counter.gd) : `render.fps` prend `off` / `on` / `detail` ; jauge d'abri
## des bots (draft_gauge.gd) : `render.draft_gauge` prend `off` / `on`.
## Mode d'affichage (display_mode.gd) : valeurs de config.toml affichées en français.
const CHOICE_TEXTS := {
	"powerups.mode": {"on": "oui", "off": "non"},
	"render.chart": {"hidden": "masquées", "reduced": "réduites (cible et puissance)", "full": "complètes"},
	"render.camera": {"subjective": "subjective", "follow_near": "suivi proche", "follow_far": "suivi éloigné", "side": "latérale"},
	"render.fps": {"off": "non", "on": "oui", "detail": "détaillé"},
	"render.draft_gauge": {"off": "non", "on": "oui"},
	"render.display": {"windowed": "fenêtré", "borderless": "plein écran sans bordure", "fullscreen": "plein écran"},
	PAUSE_RIDE_MODE: {"sim": "SIM", "erg": "ERG", "cadence": "ERG cadence"},
}

## Sous-écrans de « Réglages » (champ `group` du message `settings`), dans l'ordre d'affichage :
## [groupe, titre]. Un élément sans groupe connu va dans « Autres réglages », montré seulement s'il
## n'est pas vide.
const GROUPS := [["rider", "Cycliste"], ["ride", "Séance"], ["graphics", "Graphisme"], ["sound", "Son"],
	["wind", "Vent"]]
const OTHER_GROUP := ["other", "Autres réglages"]
## Points cardinaux d'une direction en degrés (unité « ° »), de 45 en 45 depuis le nord.
const COMPASS := ["nord", "nord-est", "est", "sud-est", "sud", "sud-ouest", "ouest", "nord-ouest"]

var items: Array = []
## Modification en cours : {key, label, type, value, min, max, step, unit, choices} ; vide sinon.
var editing: Dictionary = {}


func on_settings(msg: Dictionary) -> void:
	var raw = msg.get("items", [])
	items = raw if raw is Array else []


func item(key: String) -> Dictionary:
	for it in items:
		if it is Dictionary and str(it.get("key", "")) == key:
			return it
	return {}


## Curseur texte : dix cases, pleines jusqu'à la valeur (« ■■■■■□□□□□ 50 % »).
static func slider(pct: int) -> String:
	var n := clampi(int(round(pct / 10.0)), 0, 10)
	return "■".repeat(n) + "□".repeat(10 - n) + " %d %%" % pct



## Réglage affiché en curseur : entier en %, de 0 à 100 (difficulté, volumes).
static func is_slider(it: Dictionary) -> bool:
	return str(it.get("type", "")) == "int" and str(it.get("unit", "")) == "%" \
		and int(it.get("min", -1)) == 0 and int(it.get("max", -1)) == 100


static func format_value(it: Dictionary, value) -> String:
	if is_slider(it):
		return slider(int(value))
	if str(it.get("key", "")).begins_with(GarageViewModel.KEY_PREFIX):
		return GarageViewModel.format_edit(str(it["key"]), int(value))
	if it.has("format"):
		return WorkoutBuilder.format_param(it, value)
	var texts: Dictionary = CHOICE_TEXTS.get(str(it.get("key", "")), {})
	if texts.has(str(value)):
		return str(texts[str(value)])
	var unit := str(it.get("unit", ""))
	if unit == "°":
		return "%d° (%s)" % [int(value), COMPASS[posmod(int(round(int(value) / 45.0)), 8)]]
	return str(value) + ((" " + unit) if unit != "" else "")


## Groupe d'un élément : son `group` s'il est connu, sinon « other ».
static func group_of(it: Dictionary) -> String:
	var g := str(it.get("group", ""))
	for known in GROUPS:
		if known[0] == g:
			return g
	return str(OTHER_GROUP[0])


## Titre d'un sous-écran.
static func group_title(group: String) -> String:
	for g in GROUPS + [OTHER_GROUP]:
		if g[0] == group:
			return str(g[1])
	return str(OTHER_GROUP[1])


## Titre d'un sous-écran avec le fil d'Ariane : « Réglages › Son ».
static func crumb(group: String) -> String:
	return "Réglages › " + group_title(group)


## Entrées des sous-écrans pour l'écran « Réglages » (id « group:groupe ») : titre, et en détail les
## réglages qu'il contient. Groupes vides omis.
func group_items() -> Array:
	var out: Array = []
	for g in GROUPS + [OTHER_GROUP]:
		var labels := PackedStringArray()
		for it in items:
			if it is Dictionary and group_of(it) == g[0]:
				labels.append(str(it.get("label", it.get("key", ""))))
		if not labels.is_empty():
			out.append({"id": "group:" + str(g[0]), "label": g[1], "detail": ", ".join(labels)})
	return out


## Valeur d'une rangée de la liste : le curseur est dessiné à part (`bar`), la valeur s'écrit « 75 % ».
static func value_text(it: Dictionary, value) -> String:
	return "%d %%" % int(value) if is_slider(it) else format_value(it, value)


## Rangée d'un réglage dans une liste (id donné) : libellé à gauche, valeur à droite (détail), curseur
## (`bar`) pour un réglage en %. En cours de modification (`editing_it` vide : non), la valeur en cours
## s'écrit entre deux flèches et la rangée porte `editing`.
static func row(id: String, it: Dictionary, editing_it := {}) -> Dictionary:
	var shown: Dictionary = editing_it if not editing_it.is_empty() else it
	var value = shown.get("value")
	var out := {"id": id, "label": str(it.get("label", it.get("key", ""))), "detail": value_text(shown, value)}
	if is_slider(shown):
		out["bar"] = int(value)
	if not editing_it.is_empty():
		out["detail"] = "◀ %s ▶" % out["detail"]
		out["editing"] = true
	return out


## Éléments des réglages d'un sous-écran (id « set:clé »), le réglage en cours de modification en place.
func menu_items(group: String) -> Array:
	var out: Array = []
	for it in items:
		if not it is Dictionary or group_of(it) != group:
			continue
		out.append(row("set:" + str(it["key"]), it, editing if str(editing.get("key", "")) == str(it["key"]) else {}))
	return out


## Carte de détail d'un réglage (clé sans « set: ») : valeur, plage ou choix, moment où il s'applique.
func sheet(key: String) -> Dictionary:
	var it := item(key)
	if it.is_empty():
		return {}
	var tiles: Array = [{"label": "Valeur", "value": value_text(it, it.get("value")), "unit": ""}]
	var lines: Array = []
	if str(it.get("type", "")) == "choice":
		var texts: Array = []
		for c in it.get("choices", []):
			texts.append(format_value({"key": it["key"]}, c))
		lines.append("Choix : " + ", ".join(PackedStringArray(texts)))
	elif it.has("min") and it.has("max"):
		var unit := str(it.get("unit", ""))
		tiles.append({"label": "Plage", "value": "%d à %d" % [int(it["min"]), int(it["max"])], "unit": unit})
		tiles.append({"label": "Pas", "value": str(int(it.get("step", 1))), "unit": unit})
	lines.append("S'applique tout de suite" if str(it.get("applies", "")) == "now" else "S'applique à la séance suivante")
	return {"title": "Réglage", "name": str(it.get("label", key)), "tiles": tiles, "lines": lines}


## Ligne de version en bas de l'écran « Réglages » (lot O4, numéro unique du lot O2) : version de
## l'engine, et celle du core (`hello_ack.core_version`) quand elle diffère ; non sélectionnable.
static func version_item(engine_version: String, core_version: String) -> Dictionary:
	var detail := ""
	if core_version != "" and core_version != engine_version:
		detail = "core %s : versions différentes, mettre à jour OpenRide" % core_version
	return {"id": "version", "label": "OpenRide " + engine_version, "enabled": false, "detail": detail}


## Ouvre la modification d'un réglage (id « set:clé ») ; faux si la clé est inconnue.
func begin(key: String) -> bool:
	var it := item(key)
	if it.is_empty():
		return false
	editing = it.duplicate(true)
	return true


## Modification d'une valeur fournie par l'appelant (paramètre de workout_builder.gd, lot N16).
func begin_with(it: Dictionary) -> void:
	editing = it.duplicate(true)


## Ligne modifiable de l'écran de pause (clé « pause.… ») avec sa valeur ; {} pour une clé inconnue.
## Bornes de la puissance et de la cadence : celles du core (free_erg.py, contrat 1.5 `set_ride_mode`).
static func pause_item(key: String, value) -> Dictionary:
	match key:
		PAUSE_DIFFICULTY:
			return {"key": key, "label": "Difficulté", "type": "int", "value": value, "min": 0, "max": 100,
				"step": 10, "unit": "%"}
		PAUSE_RIDE_MODE:
			return {"key": key, "label": "Mode", "type": "choice", "value": value, "choices": RIDE_MODES.duplicate()}
		PAUSE_TARGET_W:
			return {"key": key, "label": "Puissance cible", "type": "int", "value": value, "min": 50, "max": 1000,
				"step": 5, "unit": "W"}
		PAUSE_CADENCE:
			return {"key": key, "label": "Cadence cible", "type": "int", "value": value, "min": 50, "max": 120,
				"step": 1, "unit": "tr/min"}
	return {}


## Modification d'une ligne de l'écran de pause, à partir de la valeur de la séance.
func begin_pause(key: String, value) -> void:
	editing = pause_item(key, value)


func step(direction: int) -> void:
	if editing.is_empty():
		return
	if str(editing.get("type", "")) == "choice":
		var ch: Array = editing.get("choices", [])
		if ch.is_empty():
			return
		var i := maxi(ch.find(editing["value"]), 0)
		editing["value"] = ch[posmod(i + (1 if direction > 0 else -1), ch.size())]
		return
	var stp := int(editing.get("step", 1))
	var v := int(editing.get("value", 0)) + (stp if direction > 0 else -stp)
	editing["value"] = clampi(v, int(editing.get("min", v)), int(editing.get("max", v)))


## Écran de modification d'un champ de l'avatar : titre et un élément, la valeur.
func edit_items() -> Array:
	return [{"id": "value", "label": format_value(editing, editing.get("value")),
		"detail": "+ / − : changer, A long : enregistrer, Y : annuler"}]


## Fin de la modification (A long) : action pour main.gd.
func commit() -> Dictionary:
	var e := editing
	editing = {}
	if e.is_empty():
		return {}
	match str(e["key"]):
		PAUSE_DIFFICULTY:
			return {"action": "set_difficulty", "pct": int(e["value"])}
		PAUSE_RIDE_MODE:
			return {"action": "set_ride_mode", "args": {"mode": str(e["value"])}}
		PAUSE_TARGET_W:
			return {"action": "set_ride_mode", "args": {"mode": "erg", "target_w": int(e["value"])}}
		PAUSE_CADENCE:
			return {"action": "set_ride_mode", "args": {"mode": "cadence", "cadence_rpm": int(e["value"])}}
	if str(e["key"]).begins_with(GarageViewModel.KEY_PREFIX):
		return {"action": "garage_set", "key": str(e["key"]).substr(GarageViewModel.KEY_PREFIX.length()),
			"value": int(e["value"])}
	if str(e["key"]).begins_with(WorkoutBuilder.KEY_PREFIX):
		return {"action": "builder_set", "key": str(e["key"]).substr(WorkoutBuilder.KEY_PREFIX.length()),
			"value": int(e["value"])}
	item(str(e["key"]))["value"] = e["value"]   # affiché tout de suite, le core confirme ensuite
	return {"action": "set_setting", "key": e["key"], "value": e["value"]}


func cancel() -> void:
	editing = {}
