extends RefCounted

## Modèle de vue des blocs « segment » et « bonus » du HUD (lot T9, série T), sans aucun nœud. Pas de
## class_name : charger par preload("res://scripts/segment_hud_model.gd").
##
## Entrées (contrat IPC 1.4) : champs `segment` et `powerup` de la trame `state`, message
## `segment_result` ; noms des segments lus dans la couche `segments` du parcours (`set_segments`), le
## champ `segment` ne donnant que l'`id`.
## `view(state, now_s)` rend `{segment: {...}, powerup: {...}}` :
## - segment, `mode` :
##   - `approach` quand `d_to_start_m` est sous APPROACH_M : « Montée 2 · cat. 3 dans 1,2 km » ;
##   - `active` dans le segment : nom, chrono `elapsed_s` (« 1:23 ») et écart au record
##     (« −3,2 s », ton `good` ; « +1,8 s », ton `bad` ; rien sans record) ;
##   - `result` pendant RESULT_S après un `segment_result` (répété 3 fois par le core : doublons ignorés
##     par segment et temps) : temps, « Record ! » et ancien record, place, points ;
##   - `""` (bloc caché) sinon ;
## - powerup : bloc caché sans champ `powerup` (ERG, option « Bonus » coupée) ; « Z : Aéro » pour le
##   bonus en réserve ; bonus actif, secondes restantes et `fraction` de la barre de temps (durée prise
##   au premier `remaining_s` vu pour ce bonus).
## Textes en français, nombres au format français.

const RoadsideModel := preload("res://scripts/roadside_model.gd")

const APPROACH_M := 2000.0
const RESULT_S := 8.0
const MINUS := "−"
const POWERUP_NAMES := {"light": "Légèreté", "aero": "Aéro", "power": "Puissance"}
const KIND_NAMES := {"climb": "Montée", "sprint": "Sprint"}

var names: Dictionary = {}          # id -> {name, type, category}
var result: Dictionary = {}         # dernier `segment_result` accepté
var result_until_s := -INF
var _result_key := ""
var _active_kind := ""
var _active_total_s := 0.0


func set_segments(segments: Array) -> void:
	names = {}
	for seg in segments:
		names[str(seg["id"])] = {"name": str(seg.get("name", seg["id"])), "type": str(seg.get("type", "")),
			"category": seg.get("category")}
	result = {}
	result_until_s = -INF
	_result_key = ""


## Message `segment_result` ; renvoie vrai s'il est nouveau (affiché), faux pour une répétition.
func on_result(msg: Dictionary, now_s: float) -> bool:
	var key := "%s|%s" % [str(msg.get("segment_id", "")), str(msg.get("time_s", ""))]
	if key == _result_key:
		return false
	_result_key = key
	result = msg.duplicate()
	result_until_s = now_s + RESULT_S
	return true


static func distance_text(d_m: float) -> String:
	if d_m >= 1000.0:
		return RoadsideModel.format_dec(d_m / 1000.0, 1) + " km"
	return "%d m" % int(round(d_m / 10.0) * 10.0)


## « 1:23 » (chrono en cours) ou « 4:08,1 » (avec dixièmes).
static func time_text(t_s: float, tenths: bool = false) -> String:
	var t := maxf(t_s, 0.0)
	if tenths:
		var d := int(round(t * 10.0))
		return "%d:%02d,%d" % [d / 600, (d / 10) % 60, d % 10]
	var whole := int(floor(t))
	return "%d:%02d" % [whole / 60, whole % 60]


## « −3,2 s » ou « +1,8 s ».
static func gap_text(gap_s: float) -> String:
	var txt := RoadsideModel.format_dec(absf(gap_s), 1) + " s"
	return (MINUS if gap_s < 0.0 else "+") + txt


static func category_short(category) -> String:
	if category == null:
		return ""
	return "cat. HC" if str(category) == "HC" else "cat. " + str(category)


func _title(seg_id: String, kind: String, category) -> String:
	var info: Dictionary = names.get(seg_id, {})
	var title := str(info.get("name", KIND_NAMES.get(kind, seg_id)))
	var cat := category_short(category if category != null else info.get("category"))
	return title + (" · " + cat if cat != "" else "")


func view(state: Dictionary, now_s: float) -> Dictionary:
	return {"segment": _segment_view(state, now_s), "powerup": _powerup_view(state)}


func _segment_view(state: Dictionary, now_s: float) -> Dictionary:
	var hidden := {"mode": "", "title": "", "main": "", "detail": "", "tone": ""}
	if not result.is_empty() and now_s < result_until_s:
		var r := result
		var detail := []
		if bool(r.get("pr", false)):
			var prev = r.get("pr_time_s")
			detail.append("Record !" + (" Ancien : " + time_text(float(prev), true) if prev != null else ""))
		if int(r.get("rank_total", 0)) > 1:
			detail.append("%d / %d" % [int(r.get("rank", 0)), int(r.get("rank_total", 0))])
		if int(r.get("points", 0)) > 0:
			detail.append("+%d pts" % int(r["points"]))
		var main := time_text(float(r.get("time_s", 0.0)), true)
		if bool(r.get("with_powerup", false)):
			main += " (bonus)"
		return {"mode": "result", "title": _title(str(r.get("segment_id", "")), str(r.get("kind", "")), null),
			"main": main, "detail": " · ".join(detail), "tone": "good" if bool(r.get("pr", false)) else ""}
	var seg = state.get("segment")
	if typeof(seg) != TYPE_DICTIONARY:
		return hidden
	var sid := str(seg.get("id", ""))
	var kind := str(seg.get("kind", ""))
	var title := _title(sid, kind, seg.get("category"))
	var elapsed = seg.get("elapsed_s")
	if elapsed != null:
		var gap = seg.get("gap_to_pr_s")
		var out := {"mode": "active", "title": title, "main": time_text(float(elapsed)), "detail": "", "tone": ""}
		if gap != null:
			out["detail"] = gap_text(float(gap))
			out["tone"] = "good" if float(gap) < 0.0 else "bad"
		return out
	var d := float(seg.get("d_to_start_m", INF))
	if d >= APPROACH_M:
		return hidden
	return {"mode": "approach", "title": title + " dans " + distance_text(d), "main": "", "detail": "", "tone": ""}


func _powerup_view(state: Dictionary) -> Dictionary:
	var pu = state.get("powerup")
	if typeof(pu) != TYPE_DICTIONARY:
		_active_kind = ""
		return {"visible": false, "held_text": "", "active_text": "", "fraction": 0.0}
	var held = pu.get("held")
	var active = pu.get("active")
	var held_text := "Z : " + str(POWERUP_NAMES.get(str(held), str(held))) if held != null else ""
	if active == null:
		_active_kind = ""
		return {"visible": held != null, "held_text": held_text, "active_text": "", "fraction": 0.0}
	var remaining := maxf(float(pu.get("remaining_s", 0.0)), 0.0)
	if str(active) != _active_kind:
		_active_kind = str(active)
		_active_total_s = maxf(remaining, 0.1)
	_active_total_s = maxf(_active_total_s, remaining)
	return {"visible": true, "held_text": held_text,
		"active_text": "%s · %d s" % [POWERUP_NAMES.get(str(active), str(active)), int(ceil(remaining))],
		"fraction": clampf(remaining / _active_total_s, 0.0, 1.0)}
