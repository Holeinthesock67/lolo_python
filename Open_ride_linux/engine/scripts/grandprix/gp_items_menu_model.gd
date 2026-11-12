extends RefCounted

## Écran « Objets » du Grand Prix des objets (série GP, lot GP9), sans nœud : une case par objet, comme l'écran
## des règles du Mode WTF (wtf_rules_model.gd). Les treize objets viennent du core (message `mode_options` avec
## `mode` « grandprix », réponse à `list_mode_options` et `set_mode_option`, contrat 1.7) ; A maintenu (ou
## Entrée) sur une ligne active ou coupe l'objet (`set_mode_option`, section `[items]` de
## `~/OpenRide/grandprix.toml`, repris à la séance suivante) ; « Tout activer » rallume les objets coupés.
## Tant que le core n'a pas répondu, la liste par défaut (tous activés) est affichée. Retour : écran Prêt.
## Noms et familles : grandprix/gp_items.gd (maquettes GP6).
## Pas de class_name : preload("res://scripts/grandprix/gp_items_menu_model.gd").

const GpItems := preload("res://scripts/grandprix/gp_items.gd")

const SCREEN := "gp_items"
const MODE := "grandprix"
const ITEM_PREFIX := "item:"
const ALL_ON_ID := "all_on"
## Famille d'un objet en clair (détail de sa ligne), dans les mots des maquettes GP6.
const FAMILY_TEXTS := {"self": "pour soi", "attack": "attaque", "trap": "piège derrière soi",
	"leader": "contre la tête", "guard": "défense"}

## {id, label, family, on}, dans l'ordre du core.
var options: Array = []
var received := false


func _init() -> void:
	for id in GpItems.IDS:
		options.append({"id": id, "label": GpItems.label(id), "family": GpItems.family(id), "on": true})


## Message `mode_options` du core ; un autre mode, une liste vide ou mal formée est ignoré.
func on_options(msg: Dictionary) -> void:
	if str(msg.get("mode", "")) != MODE:
		return
	var raw = msg.get("options", [])
	if typeof(raw) != TYPE_ARRAY:
		return
	var out: Array = []
	for o in raw:
		if typeof(o) == TYPE_DICTIONARY and o.has("id"):
			out.append({"id": str(o["id"]), "label": str(o.get("label", o["id"])), "family": str(o.get("family", "")),
				"on": bool(o.get("on", true))})
	if not out.is_empty():
		options = out
		received = true


func active_count() -> int:
	var n := 0
	for o in options:
		if o["on"]:
			n += 1
	return n


func title() -> String:
	return "Grand Prix : %d objets sur %d" % [active_count(), options.size()]


## Libellé de la ligne « Objets » de l'écran Prêt.
func ready_label() -> String:
	if active_count() == options.size():
		return "Objets : tous"
	return "Objets : %d sur %d" % [active_count(), options.size()]


func items() -> Array:
	var out: Array = []
	for o in options:
		out.append({"id": ITEM_PREFIX + str(o["id"]), "label": "%s : %s" % [o["label"], "oui" if o["on"] else "non"],
			"enabled": true, "detail": str(FAMILY_TEXTS.get(o["family"], ""))})
	out.append({"id": ALL_ON_ID, "label": "Tout activer", "enabled": active_count() < options.size(), "detail": ""})
	return out


## Élément validé : action du menu ({} si rien à faire). L'objet basculé change tout de suite à l'écran ; la
## réponse `mode_options` du core fait foi ensuite.
func handle(item_id: String) -> Dictionary:
	if item_id == ALL_ON_ID:
		var cmds: Array = []
		for o in options:
			if not o["on"]:
				o["on"] = true
				cmds.append({"id": o["id"], "on": true})
		return {"action": "set_mode_options", "mode": MODE, "list": cmds} if not cmds.is_empty() else {}
	if item_id.begins_with(ITEM_PREFIX):
		var id := item_id.substr(ITEM_PREFIX.length())
		for o in options:
			if o["id"] == id:
				o["on"] = not o["on"]
				return {"action": "set_mode_options", "mode": MODE, "list": [{"id": id, "on": o["on"]}]}
	return {}
