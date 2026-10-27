extends RefCounted

## Consignes d'essai affichées pendant la séance (essais sur le HomeTrainer), selon la distance parcourue
## ou le temps de séance.
##
## Fichier facultatif `~/OpenRide/Essais/<route_id>.consignes.json`, lu au chargement du parcours :
##   {"cues": [{"at_m": 3500, "text": "Changer de braquet à chaque bosse", "duration_s": 25, "beep": true},
##             {"at_s": 660, "text": "Retire la ceinture 30 s", "prepare": "la ceinture", "warn_s": 60}, …]}
## `at_m` : distance depuis le départ ; `at_s` : temps de séance du core (`t` de la trame d'état, arrêté en
## pause) ; une consigne a l'un ou l'autre. `duration_s` : durée d'affichage (défaut 20 s) ; `beep` : bip
## d'annonce (défaut vrai). `prepare` : ce qu'il faut préparer, annoncé à l'avance (« Dans 1 min, prépare
## … ») `warn_s` secondes (défaut 60) avant une consigne `at_s`, ou `warn_m` mètres (défaut 500) avant une
## consigne `at_m`. Sans fichier, rien ne s'affiche. Chaque consigne n'est donnée qu'une fois, quand `s` ou
## `t` la dépasse ; un retour en arrière de plus de 50 m ou de 5 s (nouveau départ) réarme celles qui sont
## derrière. Sans nœud. Pas de class_name : charger par preload("res://scripts/cue_model.gd").

const DEFAULT_DURATION_S := 20.0
const DEFAULT_WARN_S := 60.0
const DEFAULT_WARN_M := 500.0
const WARN_DURATION_S := 15.0
const REWIND_M := 50.0
const REWIND_S := 5.0

var cues: Array = []          # [{at_m ou at_s, text, duration_s, beep, prepare}] : distance, puis temps
var load_error := ""
# Événements à déclencher, par axe : {at, cue (indice dans cues), warn (préavis)}, triés.
var _events := {"m": [], "s": []}
var _next := {"m": 0, "s": 0}
var _last := {"m": -INF, "s": -INF}


static func path_for(route_id: String) -> String:
	return OS.get_environment("HOME").path_join("OpenRide/Essais").path_join(route_id + ".consignes.json")


## Lit le fichier de consignes du parcours ; faux (et `cues` vide) s'il manque ou s'il est invalide.
func load_for_route(route_id: String) -> bool:
	var path := path_for(route_id)
	_clear()
	if not FileAccess.file_exists(path):
		load_error = ""
		return false
	return from_text(FileAccess.get_file_as_string(path))


static func _num(v) -> bool:
	return v is float or v is int


func _clear() -> void:
	cues = []
	_events = {"m": [], "s": []}
	reset()


func from_text(text: String) -> bool:
	_clear()
	var json := JSON.new()
	if json.parse(text) != OK:   # JSON.parse_string écrirait une erreur Godot dans le journal
		load_error = "JSON invalide ligne %d : %s" % [json.get_error_line(), json.get_error_message()]
		return false
	var data = json.data
	if not (data is Dictionary) or not (data.get("cues") is Array):
		load_error = "attendu : {\"cues\": [ … ]}"
		return false
	var by_m: Array = []
	var by_s: Array = []
	for c in data["cues"]:
		if not (c is Dictionary) or str(c.get("text", "")).strip_edges() == "":
			continue
		var axis := "m" if _num(c.get("at_m")) else ("s" if _num(c.get("at_s")) else "")
		if axis == "":
			continue
		var dur = c.get("duration_s", DEFAULT_DURATION_S)
		var cue := {
			"text": str(c["text"]).strip_edges(),
			"duration_s": float(dur) if _num(dur) and float(dur) > 0.0 else DEFAULT_DURATION_S,
			"beep": bool(c.get("beep", true)),
			"prepare": str(c.get("prepare", "")).strip_edges(),
		}
		var warn_key := "warn_" + axis
		var warn = c.get(warn_key, DEFAULT_WARN_M if axis == "m" else DEFAULT_WARN_S)
		cue["at_" + axis] = float(c["at_" + axis])
		cue[warn_key] = float(warn) if _num(warn) and float(warn) > 0.0 else 0.0
		(by_m if axis == "m" else by_s).append(cue)
	by_m.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a["at_m"] < b["at_m"])
	by_s.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a["at_s"] < b["at_s"])
	cues = by_m + by_s
	for i in cues.size():
		var axis := "m" if cues[i].has("at_m") else "s"
		var at: float = cues[i]["at_" + axis]
		_events[axis].append({"at": at, "cue": i, "warn": false})
		var lead: float = cues[i]["warn_" + axis]
		if cues[i]["prepare"] != "" and lead > 0.0:
			_events[axis].append({"at": maxf(0.0, at - lead), "cue": i, "warn": true})
	for axis in _events:
		# À égalité, le préavis d'une consigne suivante passe après la consigne en cours.
		_events[axis].sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
			return a["at"] < b["at"] or (a["at"] == b["at"] and not a["warn"] and b["warn"]))
	load_error = ""
	return not cues.is_empty()


func reset() -> void:
	_next = {"m": 0, "s": 0}
	_last = {"m": -INF, "s": -INF}


## Consignes et préavis à donner maintenant, dans l'ordre. `s` : distance ; `t` : temps de séance (négatif :
## inconnu, consignes au temps ignorées). Plusieurs franchis d'un coup sur un même axe (reprise en cours de
## parcours) : seul le dernier est rendu. Chaque élément : copie de la consigne avec `index`, `count`,
## `warn` (vrai pour un préavis) et, pour un préavis, `warn_text` (« Dans 1 min, prépare … »).
func update(s: float, t: float = -1.0) -> Array:
	var out: Array = _advance("m", s, REWIND_M)
	if t >= 0.0:
		out += _advance("s", t, REWIND_S)
	return out


func _advance(axis: String, value: float, rewind: float) -> Array:
	var events: Array = _events[axis]
	if value < _last[axis] - rewind:
		_next[axis] = 0
		while _next[axis] < events.size() and events[_next[axis]]["at"] < value - rewind:
			_next[axis] += 1
	_last[axis] = value
	var crossed: Array = []
	while _next[axis] < events.size() and events[_next[axis]]["at"] <= value:
		crossed.append(events[_next[axis]])
		_next[axis] += 1
	if crossed.size() > 1:
		crossed = [crossed[-1]]
	var out: Array = []
	for e in crossed:
		var c: Dictionary = cues[e["cue"]].duplicate()
		c["index"] = e["cue"] + 1
		c["count"] = cues.size()
		c["warn"] = e["warn"]
		if e["warn"]:
			c["warn_text"] = "Dans %s, prépare %s" % [_lead_text(c, axis), c["prepare"]]
			c["duration_s"] = WARN_DURATION_S
		out.append(c)
	return out


static func _lead_text(c: Dictionary, axis: String) -> String:
	if axis == "m":
		return "%d m" % int(round(c["warn_m"]))
	var lead := int(round(c["warn_s"]))
	if lead >= 60 and lead % 60 == 0:
		return "%d min" % (lead / 60)
	return "%d s" % lead


## Distance jusqu'à la prochaine consigne au mètre, ou -1 s'il n'y en a plus.
func distance_to_next(s: float) -> float:
	var events: Array = _events["m"]
	var i: int = _next["m"]
	while i < events.size() and events[i]["warn"]:
		i += 1
	return events[i]["at"] - s if i < events.size() else -1.0
