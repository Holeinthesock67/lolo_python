extends RefCounted

## Écran des règles du mode « What the fuck » (série WTF, lot WTF3), sans nœud : les treize règles reçues
## du core (message `wtf_rules`, contrat 1.5), chacune allumée ou coupée par A ou Entrée (commande
## `set_wtf_rule`), « Tout allumer » et « Lancer une séance WTF ». menu_flow.gd en fait l'écran SCREEN.
## Tant que le core n'a pas répondu, la liste par défaut (toutes les règles allumées) est affichée.
## Maquette validée par le propriétaire le 30 octobre (planche « Menu »).
## Pas de class_name : preload("res://scripts/wtf/wtf_rules_model.gd").

const SCREEN := "wtf_rules"
const RULE_PREFIX := "rule:"
const ALL_ON_ID := "all_on"
const LAUNCH_ID := "launch"
## Règles dans l'ordre du core (core/src/openride_core/wtf/rules.py) : identifiant et nom.
const DEFAULT_RULES := [
	["gravity", "Gravité au choix"], ["upside_down", "Monde à l'envers"], ["collapse", "La route s'effondre"],
	["katamari", "Katamari à vélo"], ["peloton", "Peloton délirant"], ["cheese", "Fromage géant"],
	["micro", "Micro-défis"], ["eggs", "Livraison d'œufs"], ["clock", "La cadence pilote le monde"],
	["tiny", "Vélo minuscule"], ["storm", "Météo folle"], ["camera", "Caméras improbables"],
	["chef", "Surprise du chef"]]

## {id, label, family, pitch, on}, dans l'ordre d'affichage.
var rules: Array = []
var received := false


func _init() -> void:
	for r in DEFAULT_RULES:
		rules.append({"id": r[0], "label": r[1], "family": "", "pitch": "", "on": true})


## Message `wtf_rules` du core ; une liste vide ou mal formée est ignorée.
func on_rules(msg: Dictionary) -> void:
	var raw = msg.get("rules", [])
	if typeof(raw) != TYPE_ARRAY:
		return
	var out: Array = []
	for r in raw:
		if typeof(r) == TYPE_DICTIONARY and r.has("id"):
			out.append({"id": str(r["id"]), "label": str(r.get("label", r["id"])), "family": str(r.get("family", "")),
				"pitch": str(r.get("pitch", "")), "on": bool(r.get("on", true))})
	if not out.is_empty():
		rules = out
		received = true


func active_count() -> int:
	var n := 0
	for r in rules:
		if r["on"]:
			n += 1
	return n


func title() -> String:
	return "Mode WTF : %d règles sur %d" % [active_count(), rules.size()]


func items() -> Array:
	var out: Array = []
	for r in rules:
		out.append({"id": RULE_PREFIX + str(r["id"]), "label": "%s : %s" % [r["label"], "oui" if r["on"] else "non"],
			"enabled": true, "detail": str(r["pitch"])})
	out.append({"id": ALL_ON_ID, "label": "Tout allumer", "enabled": active_count() < rules.size(), "detail": ""})
	out.append({"id": LAUNCH_ID, "label": "Lancer une séance WTF", "enabled": true,
		"detail": "SIM seulement : la puissance du FIT reste ta puissance mesurée"})
	return out


## Élément validé : action du menu ({} si rien à faire). La règle basculée change tout de suite à l'écran ;
## la réponse `wtf_rules` du core fait foi ensuite.
func handle(item_id: String) -> Dictionary:
	if item_id == LAUNCH_ID:
		return {"action": "launch"}
	if item_id == ALL_ON_ID:
		var cmds: Array = []
		for r in rules:
			if not r["on"]:
				r["on"] = true
				cmds.append({"id": r["id"], "on": true})
		return {"action": "set_wtf_rules", "list": cmds} if not cmds.is_empty() else {}
	if item_id.begins_with(RULE_PREFIX):
		var id := item_id.substr(RULE_PREFIX.length())
		for r in rules:
			if r["id"] == id:
				r["on"] = not r["on"]
				return {"action": "set_wtf_rules", "list": [{"id": id, "on": r["on"]}]}
	return {}
