extends RefCounted

## Réglages du menu (Lot O4, contrat IPC révision 1.3), sans nœud : éléments de l'écran « Réglages »
## et écran de modification d'une valeur au Click.
##
## Le core envoie la liste (`settings` : {key, label, type, value, min, max, step, unit, choices,
## applies}) ; ce modèle la met en forme et garde la valeur en cours de modification. Écran de
## modification : + / − (appui court) changent la valeur, appui long + enregistre, appui long −
## annule. Tout réglage en % de 0 à 100 (difficulté, volumes) s'affiche en curseur ; le curseur de la
## difficulté sert aussi sur l'écran de pause, où il envoie `set_difficulty` (lot Q1) sans toucher à
## config.toml.
## Le même écran sert aux paramètres de « Créer un entraînement » (lot N16, clés « workout.… ») :
## commit() renvoie alors l'action interne `builder_set`.
## Pas de class_name : charger par preload("res://scripts/settings_view_model.gd").

const WorkoutBuilder := preload("res://scripts/workout_builder.gd")

const EDIT_SCREEN := "setting_edit"
## Clé de l'écran de modification ouvert depuis la pause (difficulté de la séance en cours).
const PAUSE_DIFFICULTY := "pause.difficulty"
## Textes des choix envoyés par le core sous une forme technique : {clé: {valeur: texte}}.
## Option « Bonus » du mode classique (série T, lot T10) : `on` / `off` affichés « oui » / « non ».
## Courbes de la séance (lot O14) : `render.chart` prend `hidden` / `reduced` / `full`.
## Compteur d'images/s du HUD (fps_counter.gd) : `render.fps` prend `off` / `on`.
const CHOICE_TEXTS := {
	"powerups.mode": {"on": "oui", "off": "non"},
	"render.chart": {"hidden": "masquées", "reduced": "réduites (cible et puissance)", "full": "complètes"},
	"render.fps": {"off": "non", "on": "oui"},
}

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
	if it.has("format"):
		return WorkoutBuilder.format_param(it, value)
	var texts: Dictionary = CHOICE_TEXTS.get(str(it.get("key", "")), {})
	if texts.has(str(value)):
		return str(texts[str(value)])
	var unit := str(it.get("unit", ""))
	return str(value) + ((" " + unit) if unit != "" else "")


## Éléments des réglages pour l'écran « Réglages » (id « set:clé »).
func menu_items() -> Array:
	var out: Array = []
	for it in items:
		if not it is Dictionary:
			continue
		var detail := "tout de suite" if str(it.get("applies", "")) == "now" else ""
		out.append({"id": "set:" + str(it["key"]), "label": "%s : %s" % [it.get("label", it["key"]),
			format_value(it, it.get("value"))], "detail": detail})
	return out


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


## Modification de la difficulté depuis la pause, à partir de la valeur de la séance.
func begin_pause_difficulty(pct: int) -> void:
	editing = {"key": PAUSE_DIFFICULTY, "label": "Difficulté", "type": "int", "value": pct,
		"min": 0, "max": 100, "step": 10, "unit": "%"}


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


## Écran de modification : titre et un élément (la valeur), aide en détail.
func edit_items() -> Array:
	return [{"id": "value", "label": format_value(editing, editing.get("value")),
		"detail": "+ / − : changer, long + : enregistrer, long − : annuler"}]


## Fin de la modification (appui long +) : action pour main.gd.
func commit() -> Dictionary:
	var e := editing
	editing = {}
	if e.is_empty():
		return {}
	if e["key"] == PAUSE_DIFFICULTY:
		return {"action": "set_difficulty", "pct": int(e["value"])}
	if str(e["key"]).begins_with(WorkoutBuilder.KEY_PREFIX):
		return {"action": "builder_set", "key": str(e["key"]).substr(WorkoutBuilder.KEY_PREFIX.length()),
			"value": int(e["value"])}
	return {"action": "set_setting", "key": e["key"], "value": e["value"]}


func cancel() -> void:
	editing = {}
