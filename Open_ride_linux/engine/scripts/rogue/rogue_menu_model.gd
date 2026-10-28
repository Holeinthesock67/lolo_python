extends RefCounted

## Menu de départ du Cyber-Rogue (lot R13), sans nœud : choix de l'objectif, de la durée, de W' et du châssis
## à partir de `hello_ack.config.rogue`, avertissement du premier lancement et arguments de la commande
## `start_run`. menu_flow.gd en fait l'écran SCREEN du menu ; les écrans « Prêt » et « Composition de la run »
## sont décrits ici pour le texte seulement. Pas de class_name :
## preload("res://scripts/rogue/rogue_menu_model.gd").
##
## Les derniers choix sont gardés pour la durée du programme ; leur conservation d'une fois sur l'autre
## demandera un réglage du core (hors de ce lot).

const SCREEN := "rogue_start"
const LOADING := "rogue_loading"
const OBJECTIVE_LABELS := {"endurance": "Endurance", "threshold": "Seuil", "vo2max": "VO2max"}
const DEFAULT_OBJECTIVES := ["endurance", "threshold", "vo2max"]
const DEFAULT_DURATIONS := [30, 45, 60, 90]
const WARNING := "Cyber-Rogue : en VO2max, des efforts au-delà de 140 % de la FTP sont possibles. Sortie sans pénalité à tout moment. Lancer ?"
const FTP_HINT := "FTP jamais mesurée : un test de FTP est conseillé"

var objectives: Array = DEFAULT_OBJECTIVES.duplicate()
var durations: Array = DEFAULT_DURATIONS.duplicate()
var w_prime_j := 0.0
var w_estimate_j := 0.0                 # 0 : pas d'estimation (lot R16)
var chassis: Array = []                 # châssis débloqués ; vide : champ `chassis` jamais envoyé
var objective_idx := 0
var duration_idx := 0
var chassis_idx := 0
var use_estimate := false
var warned := false
var message := ""
var _configured := false


## `hello_ack.config.rogue` ; null ou absent : valeurs par défaut du contrat.
func configure(cfg: Variant) -> void:
	_configured = typeof(cfg) == TYPE_DICTIONARY
	if not _configured:
		return
	var objs: Array = cfg.get("objectives", [])
	objectives = objs.duplicate() if not objs.is_empty() else DEFAULT_OBJECTIVES.duplicate()
	var durs: Array = cfg.get("durations_min", [])
	durations = durs.duplicate() if not durs.is_empty() else DEFAULT_DURATIONS.duplicate()
	w_prime_j = float(cfg.get("w_prime_j", 0.0))
	var est = cfg.get("w_prime_estimate_j", null)
	w_estimate_j = float(est) if est != null else 0.0
	var ch = cfg.get("chassis", null)
	chassis = []
	var selected := ""
	if typeof(ch) == TYPE_DICTIONARY:
		chassis = (ch.get("unlocked", []) as Array).duplicate()
		selected = String(ch.get("selected", ""))
	objective_idx = clampi(objective_idx, 0, objectives.size() - 1)
	duration_idx = clampi(duration_idx, 0, durations.size() - 1)
	chassis_idx = chassis.find(selected) if chassis.find(selected) >= 0 else clampi(chassis_idx, 0, maxi(chassis.size() - 1, 0))
	if w_estimate_j <= 0.0:
		use_estimate = false


func objective() -> String:
	return String(objectives[objective_idx])


func duration_min() -> int:
	return int(durations[duration_idx])


func _kj(joules: float) -> String:
	return ("%.1f kJ" % (joules / 1000.0)).replace(".", ",")


func w_prime_text() -> String:
	if w_estimate_j > 0.0:
		return ("estimé " + _kj(w_estimate_j)) if use_estimate else (_kj(w_prime_j) + " (estimé " + _kj(w_estimate_j) + ")")
	return _kj(w_prime_j)


func chassis_name() -> String:
	return "" if chassis.is_empty() else String(chassis[chassis_idx]).capitalize()


## Éléments de l'écran de départ [{id, label, enabled, detail}].
func items() -> Array:
	var out: Array = [
		{"id": "objective", "label": "Objectif : " + OBJECTIVE_LABELS.get(objective(), objective()), "enabled": objectives.size() > 1, "detail": ""},
		{"id": "duration", "label": "Durée : %d min" % duration_min(), "enabled": durations.size() > 1, "detail": ""},
		{"id": "wprime", "label": "W' : " + w_prime_text(), "enabled": w_estimate_j > 0.0,
			"detail": "Utiliser l'estimation de W' ?" if w_estimate_j > 0.0 else ""}]
	if not chassis.is_empty():
		out.append({"id": "chassis", "label": "Châssis : " + chassis_name(), "enabled": chassis.size() > 1, "detail": ""})
	out.append({"id": "launch", "label": "Lancer", "enabled": true, "detail": message})
	return out


## Valider un élément : les trois premiers font défiler leur valeur ; `launch` est traité par l'appelant.
func cycle(item_id: String) -> void:
	match item_id:
		"objective":
			objective_idx = (objective_idx + 1) % objectives.size()
		"duration":
			duration_idx = (duration_idx + 1) % durations.size()
		"wprime":
			if w_estimate_j > 0.0:
				use_estimate = not use_estimate
		"chassis":
			if not chassis.is_empty():
				chassis_idx = (chassis_idx + 1) % chassis.size()
	message = ""


## Arguments de `start_run` : `seed` nul (tirée par le core), `w_prime_j` nul sauf estimation choisie.
func start_args() -> Dictionary:
	var args := {"objective": objective(), "duration_min": duration_min(), "seed": null,
		"w_prime_j": w_estimate_j if use_estimate and w_estimate_j > 0.0 else null}
	if not chassis.is_empty():
		args["chassis"] = String(chassis[chassis_idx])
	return args


func needs_warning() -> bool:
	return not warned


func mark_warned() -> void:
	warned = true


## Texte de rappel de l'écran « Prêt » : objectif, durée, W', châssis.
func ready_text() -> String:
	var t := "%s · %d min · W' %s" % [OBJECTIVE_LABELS.get(objective(), objective()), duration_min(), w_prime_text()]
	if not chassis.is_empty():
		t += " · " + chassis_name()
	return t
