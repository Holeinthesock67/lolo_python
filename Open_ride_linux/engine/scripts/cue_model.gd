extends RefCounted

## Consignes d'essai affichées pendant la séance, selon la distance parcourue (essais sur le HomeTrainer).
##
## Fichier facultatif `~/OpenRide/Essais/<route_id>.consignes.json`, lu au chargement du parcours :
##   {"cues": [{"at_m": 3500, "text": "Changer de braquet à chaque bosse", "duration_s": 25, "beep": true}, …]}
## `at_m` : distance depuis le départ ; `duration_s` : durée d'affichage (défaut 20 s) ; `beep` : bip d'annonce
## (défaut vrai). Sans fichier, rien ne s'affiche. Chaque consigne n'est donnée qu'une fois, quand `s` la
## dépasse ; un retour en arrière de plus de 50 m (nouveau départ) réarme celles qui sont derrière.
## Sans nœud. Pas de class_name : charger par preload("res://scripts/cue_model.gd").

const DEFAULT_DURATION_S := 20.0
const REWIND_M := 50.0

var cues: Array = []          # [{at_m, text, duration_s, beep}] triées par distance
var load_error := ""
var _next := 0                # indice de la prochaine consigne à donner
var _last_s := -INF


static func path_for(route_id: String) -> String:
	return OS.get_environment("HOME").path_join("OpenRide/Essais").path_join(route_id + ".consignes.json")


## Lit le fichier de consignes du parcours ; faux (et `cues` vide) s'il manque ou s'il est invalide.
func load_for_route(route_id: String) -> bool:
	var path := path_for(route_id)
	cues = []
	reset()
	if not FileAccess.file_exists(path):
		load_error = ""
		return false
	return from_text(FileAccess.get_file_as_string(path))


func from_text(text: String) -> bool:
	cues = []
	reset()
	var json := JSON.new()
	if json.parse(text) != OK:   # JSON.parse_string écrirait une erreur Godot dans le journal
		load_error = "JSON invalide ligne %d : %s" % [json.get_error_line(), json.get_error_message()]
		return false
	var data = json.data
	if not (data is Dictionary) or not (data.get("cues") is Array):
		load_error = "attendu : {\"cues\": [ … ]}"
		return false
	for c in data["cues"]:
		if not (c is Dictionary) or not (c.get("at_m") is float or c.get("at_m") is int) \
				or str(c.get("text", "")).strip_edges() == "":
			continue
		var dur = c.get("duration_s", DEFAULT_DURATION_S)
		cues.append({
			"at_m": float(c["at_m"]),
			"text": str(c["text"]).strip_edges(),
			"duration_s": float(dur) if (dur is float or dur is int) and float(dur) > 0.0 else DEFAULT_DURATION_S,
			"beep": bool(c.get("beep", true)),
		})
	cues.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a["at_m"] < b["at_m"])
	load_error = ""
	return not cues.is_empty()


func reset() -> void:
	_next = 0
	_last_s = -INF


## Consignes à donner maintenant (celles dont la distance vient d'être atteinte), dans l'ordre.
## Plusieurs consignes franchies d'un coup (reprise en cours de parcours) : seule la dernière est rendue.
func update(s: float) -> Array:
	if s < _last_s - REWIND_M:
		_next = 0
		while _next < cues.size() and cues[_next]["at_m"] < s - REWIND_M:
			_next += 1
	_last_s = s
	var crossed: Array = []
	while _next < cues.size() and cues[_next]["at_m"] <= s:
		crossed.append(_next)
		_next += 1
	if crossed.size() > 1:
		crossed = [crossed[-1]]
	var out: Array = []
	for i in crossed:
		var c: Dictionary = cues[i].duplicate()
		c["index"] = i + 1
		c["count"] = cues.size()
		out.append(c)
	return out


## Distance jusqu'à la prochaine consigne, ou -1 s'il n'y en a plus.
func distance_to_next(s: float) -> float:
	return cues[_next]["at_m"] - s if _next < cues.size() else -1.0
