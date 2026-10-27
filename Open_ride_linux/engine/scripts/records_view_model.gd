extends RefCounted

## Écran « Records » du parcours choisi (lot T10, série T), sans nœud. Pas de class_name : charger par
## preload("res://scripts/records_view_model.gd").
##
## L'engine lit lui-même `~/OpenRide/records.json` (forme versionnée du lot T5), en lecture seule : le
## core reste le seul à l'écrire. Fichier absent : aucun temps ; illisible ou d'une version inconnue :
## « Aucun record lisible ». Forme :
##     {"version": 1, "routes": {"<route_id>": {"<segment_id>": {"no_bonus": [...], "bonus": [...]}}}}
## chaque temps étant {time_s, date, avg_power_w, avg_wkg}.
## - `segment_items(route_id)` : un élément par segment de la couche `segments` du parcours
##   (`set_segments`), id « seg:<id> », meilleur temps sans bonus et nombre de temps ; segment sans temps
##   désactivé ;
## - `table_items(route_id, segment_id, with_bonus)` : les 10 meilleurs temps de la table « sans bonus »
##   ou « avec bonus » : place, temps au dixième, date, puissance moyenne et W/kg ; premier élément
##   « toggle » (A court ou A long : autre table) ;
## - `table_title(segment_id, with_bonus)`.

const SegmentHudModel := preload("res://scripts/segment_hud_model.gd")
const RoadsideModel := preload("res://scripts/roadside_model.gd")

const FORMAT_VERSION := 1
const TABLES := {false: "no_bonus", true: "bonus"}
const UNREADABLE := "Aucun record lisible"

var routes: Dictionary = {}
var load_error := ""
var segments: Array = []


static func default_path() -> String:
	return OS.get_environment("HOME").path_join("OpenRide/records.json")


func set_segments(p_segments: Array) -> void:
	segments = p_segments.duplicate()


## Relit le fichier (à chaque ouverture de l'écran : les records d'une séance qui vient de finir y sont).
func load_file(path: String = "") -> bool:
	var p := path if not path.is_empty() else default_path()
	if not FileAccess.file_exists(p):
		routes = {}
		load_error = ""
		return true
	return load_text(FileAccess.get_file_as_string(p))


func load_text(text: String) -> bool:
	routes = {}
	load_error = ""
	var json := JSON.new()   # parse() plutôt que parse_string() : un fichier illisible n'écrit pas d'erreur
	if json.parse(text) != OK:
		load_error = UNREADABLE
		return false
	var doc = json.data
	if typeof(doc) != TYPE_DICTIONARY or typeof(doc.get("routes")) != TYPE_DICTIONARY:
		load_error = UNREADABLE
		return false
	var version = doc.get("version")
	if not (typeof(version) in [TYPE_INT, TYPE_FLOAT]) or int(version) != FORMAT_VERSION:
		load_error = UNREADABLE
		return false
	routes = doc["routes"]
	return true


func entries(route_id: String, segment_id: String, with_bonus: bool) -> Array:
	var r = routes.get(route_id, {})
	var seg = r.get(segment_id, {}) if typeof(r) == TYPE_DICTIONARY else {}
	var rows = seg.get(TABLES[with_bonus], []) if typeof(seg) == TYPE_DICTIONARY else []
	var out: Array = []
	if typeof(rows) != TYPE_ARRAY:
		return out
	for e in rows:
		if typeof(e) == TYPE_DICTIONARY and typeof(e.get("time_s")) in [TYPE_INT, TYPE_FLOAT]:
			out.append(e)
	out.sort_custom(func(a, b): return float(a["time_s"]) < float(b["time_s"]))
	return out


func _name(segment_id: String) -> String:
	for s in segments:
		if str(s.get("id", "")) == segment_id:
			return str(s.get("name", segment_id))
	return segment_id


func segment_items(route_id: String) -> Array:
	if load_error != "":
		return [{"id": "none", "label": UNREADABLE, "enabled": false, "detail": "~/OpenRide/records.json"}]
	if segments.is_empty():
		return [{"id": "none", "label": "Ce parcours n'a ni sprint ni montée", "enabled": false}]
	var out: Array = []
	for s in segments:
		var sid := str(s.get("id", ""))
		var plain := entries(route_id, sid, false)
		var bonus := entries(route_id, sid, true)
		var label := _name(sid)
		var detail := "aucun temps"
		if not plain.is_empty():
			label += " · " + SegmentHudModel.time_text(float(plain[0]["time_s"]), true)
		var parts: Array[String] = []
		if not plain.is_empty():
			parts.append("%d temps sans bonus" % plain.size())
		if not bonus.is_empty():
			parts.append("avec bonus " + SegmentHudModel.time_text(float(bonus[0]["time_s"]), true))
		if not parts.is_empty():
			detail = ", ".join(parts)
		out.append({"id": "seg:" + sid, "label": label, "detail": detail,
			"enabled": not (plain.is_empty() and bonus.is_empty())})
	return out


## « 2026-10-27 18:05 » (format du core) affiché « 27/10/2026 18:05 » ; autre forme : telle quelle.
static func date_text(date: String) -> String:
	var parts := date.split(" ")
	var ymd := parts[0].split("-")
	if ymd.size() != 3:
		return date
	return "%s/%s/%s" % [ymd[2], ymd[1], ymd[0]] + (" " + parts[1] if parts.size() > 1 else "")


static func table_name(with_bonus: bool) -> String:
	return "avec bonus" if with_bonus else "sans bonus"


func table_title(segment_id: String, with_bonus: bool) -> String:
	return "%s : %s" % [_name(segment_id), table_name(with_bonus)]


func table_items(route_id: String, segment_id: String, with_bonus: bool) -> Array:
	var rows := entries(route_id, segment_id, with_bonus)
	var out: Array = [{"id": "toggle", "label": "A : voir les temps " + table_name(not with_bonus),
		"enabled": true}]
	if rows.is_empty():
		out.append({"id": "none", "label": "Aucun temps " + table_name(with_bonus), "enabled": false})
		return out
	for i in range(rows.size()):
		var e: Dictionary = rows[i]
		var detail: Array[String] = []
		if typeof(e.get("avg_power_w")) in [TYPE_INT, TYPE_FLOAT]:
			detail.append("%d W" % int(round(float(e["avg_power_w"]))))
		if typeof(e.get("avg_wkg")) in [TYPE_INT, TYPE_FLOAT]:
			detail.append(RoadsideModel.format_dec(float(e["avg_wkg"]), 1) + " W/kg")
		out.append({"id": "row:%d" % i, "label": "%d. %s · %s" % [i + 1,
			SegmentHudModel.time_text(float(e["time_s"]), true), date_text(str(e.get("date", "")))],
			"detail": ", ".join(detail)})
	return out
