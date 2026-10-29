extends RefCounted

## Modèle de vue de l'entraînement ERG côté Godot (Lot I6, SRS §6 et §13, Contrat IPC v1 §3).
##
## Calcule l'état d'affichage du bandeau ERG, le déclenchement unique du bip à T − 3 s
## et la géométrie de l'histogramme des blocs (`profile_bars`), sans aucun nœud Godot.
## ERG d'une session libre (lot O18, `erg.kind` = `free` ou `cadence`) : pas de blocs, donc ni temps
## restant, ni bloc suivant, ni bip ; en cadence verrouillée, le titre donne la cadence cible et sa
## plage, et la ligne suivante dit si la cadence est dans la plage (`cadence_zone`).
## Pas de class_name : charger par preload("res://scripts/erg_view_model.gd").

const BEEP_THRESHOLD_S := 3.0
const MIN_BEEP_BLOCK_TOTAL_S := 4.0
## État de la cadence en ERG cadence (`erg.cadence_zone`, lot O18).
const CADENCE_ZONE_TEXTS := {"in": "Cadence dans la plage", "high": "Trop vite : la puissance monte",
	"low": "Trop lent : la puissance baisse"}

var _has_state: bool = false
var _last_erg: Dictionary = {}
var _frame_time_s: float = 0.0
var _raw_remaining_s: float = 0.0
var _last_block_index: int = -1
var _beeped_block_index: int = -1


static func format_mm_ss(seconds: float) -> String:
	var sec := maxi(0, int(floor(seconds + 1e-6)))
	return "%d:%02d" % [sec / 60, sec % 60]


func reset() -> void:
	_has_state = false
	_last_erg = {}
	_frame_time_s = 0.0
	_raw_remaining_s = 0.0
	_last_block_index = -1
	_beeped_block_index = -1


## Enregistre l'objet `erg` (ou null) reçu dans une trame `state` à l'instant `now_s`.
func on_state(erg: Variant, now_s: float) -> void:
	if erg == null or typeof(erg) != TYPE_DICTIONARY or (erg as Dictionary).is_empty():
		reset()
		return
	var d: Dictionary = erg
	var blk_idx := int(d.get("block_index", 1))
	var raw_rem := maxf(0.0, float(d.get("block_remaining_s", 0.0)))
	if not _has_state or blk_idx != _last_block_index:
		_beeped_block_index = -1
	elif raw_rem > BEEP_THRESHOLD_S + 0.5 and _raw_remaining_s <= BEEP_THRESHOLD_S:
		# Même indice de bloc mais temps restant reparti au-dessus du seuil (ex. redémarrage)
		_beeped_block_index = -1
	_has_state = true
	_last_erg = d.duplicate(true)
	_frame_time_s = now_s
	_raw_remaining_s = raw_rem
	_last_block_index = blk_idx


## Évalue le modèle de vue à l'instant de rendu `now_s` à partir de la dernière trame reçue.
func evaluate(now_s: float) -> Dictionary:
	if not _has_state:
		return {
			"visible": false,
			"title": "",
			"target_text": "",
			"next_text": "",
			"remaining_text": "",
			"remaining_s": 0.0,
			"progress": 0.0,
			"beep": false,
			"paused_text": "",
		}

	var workout_name := str(_last_erg.get("workout_name", ""))
	var block_index := int(_last_erg.get("block_index", 1))
	var block_count := maxi(1, int(_last_erg.get("block_count", 1)))
	var block_total_s := maxf(0.0, float(_last_erg.get("block_total_s", 0.0)))
	var target_w := int(round(float(_last_erg.get("target_w", 0))))
	var next_target_raw: Variant = _last_erg.get("next_target_w", null)
	var bias_pct := int(round(float(_last_erg.get("bias_pct", 100))))
	var paused := bool(_last_erg.get("paused", false))
	var kind := str(_last_erg.get("kind", "workout"))
	if kind == "free" or kind == "cadence":
		return _free_eval(kind, target_w, bias_pct, paused)

	var dt := 0.0 if paused else maxf(0.0, now_s - _frame_time_s)
	var rem_s := maxf(0.0, _raw_remaining_s - dt)

	var title := "%s — Bloc %d / %d" % [workout_name, block_index, block_count]

	var target_text := "%d W" % target_w
	if bias_pct != 100:
		target_text += " (%d %%)" % bias_pct

	var rem_text := format_mm_ss(rem_s)

	var next_text := ""
	if block_index < block_count and next_target_raw != null:
		next_text = "Ensuite : %d W dans %s" % [int(round(float(next_target_raw))), rem_text]

	var progress := 0.0
	if block_total_s > 0.0:
		progress = clampf((block_total_s - rem_s) / block_total_s, 0.0, 1.0)

	var beep := false
	if paused:
		# Si le bloc est en pause pendant les 3 dernières secondes, aucun bip ne doit partir pour ce bloc.
		if rem_s <= BEEP_THRESHOLD_S:
			_beeped_block_index = block_index
	elif block_total_s >= MIN_BEEP_BLOCK_TOTAL_S and rem_s <= BEEP_THRESHOLD_S:
		if _beeped_block_index != block_index:
			beep = true
			_beeped_block_index = block_index

	var paused_text := "ERG en pause" if paused else ""

	return {
		"visible": true,
		"title": title,
		"target_text": target_text,
		"next_text": next_text,
		"remaining_text": rem_text,
		"remaining_s": rem_s,
		"progress": progress,
		"beep": beep,
		"paused_text": paused_text,
	}


## Évaluation de l'ERG d'une session libre : cible seule (`free`) ou cible, cadence et plage (`cadence`).
func _free_eval(kind: String, target_w: int, bias_pct: int, paused: bool) -> Dictionary:
	var title := "ERG libre"
	var target_text := "%d W" % target_w
	var next_text := ""
	if kind == "cadence":
		title = "ERG cadence %d tr/min (%d–%d)" % [int(_last_erg.get("cadence_target_rpm", 0)),
			int(round(float(_last_erg.get("cadence_low_rpm", 0.0)))),
			int(round(float(_last_erg.get("cadence_high_rpm", 0.0))))]
		next_text = str(CADENCE_ZONE_TEXTS.get(str(_last_erg.get("cadence_zone", "in")), ""))
	elif bias_pct != 100:
		target_text += " (%d %%)" % bias_pct
	return {
		"visible": true,
		"kind": kind,
		"title": title,
		"target_text": target_text,
		"next_text": next_text,
		"remaining_text": "",
		"remaining_s": 0.0,
		"progress": 0.0,
		"beep": false,
		"paused_text": "ERG en pause" if paused else "",
	}


## Méthode combinée : met à jour la trame si `erg` a changé, puis évalue à l'heure de rendu `now_s`.
func update(erg: Variant, now_s: float) -> Dictionary:
	if erg == null or typeof(erg) != TYPE_DICTIONARY or (erg as Dictionary).is_empty():
		reset()
		return evaluate(now_s)
	var d: Dictionary = erg
	var is_new_frame: bool = (
		not _has_state
		or int(d.get("block_index", 1)) != _last_block_index
		or absf(float(d.get("block_remaining_s", 0.0)) - _raw_remaining_s) > 1e-6
		or bool(d.get("paused", false)) != bool(_last_erg.get("paused", false))
		or int(round(float(d.get("bias_pct", 100)))) != int(round(float(_last_erg.get("bias_pct", 100))))
		or int(round(float(d.get("target_w", 0)))) != int(round(float(_last_erg.get("target_w", 0))))
		or str(d.get("workout_name", "")) != str(_last_erg.get("workout_name", ""))
		or d.get("cadence_target_rpm") != _last_erg.get("cadence_target_rpm")
		or d.get("cadence_zone") != _last_erg.get("cadence_zone")
	)
	if is_new_frame:
		on_state(d, now_s)
	return evaluate(now_s)


## Transforme une liste de blocs (`type`, `duration_s`, `start_frac`, `end_frac`) en barres
## ou trapèzes normalisés dans un rectangle (`width` × `height`).
static func profile_bars(blocks: Array, ftp_w: float, width: float, height: float) -> Array:
	var out: Array = []
	if blocks.is_empty() or width <= 0.0 or height <= 0.0:
		return out

	var total_dur := 0.0
	var max_frac := 1.0
	for item in blocks:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var b: Dictionary = item
		var dur := maxf(0.0, float(b.get("duration_s", 0.0)))
		total_dur += dur
		if b.get("start_frac", null) != null:
			max_frac = maxf(max_frac, float(b["start_frac"]))
		if b.get("end_frac", null) != null:
			max_frac = maxf(max_frac, float(b["end_frac"]))

	if total_dur <= 0.0:
		return out

	var cum_dur := 0.0
	for i in range(blocks.size()):
		if typeof(blocks[i]) != TYPE_DICTIONARY:
			continue
		var b: Dictionary = blocks[i]
		var dur := maxf(0.0, float(b.get("duration_s", 0.0)))
		if dur <= 0.0:
			continue
		var b_type := str(b.get("type", "steady"))
		var x0 := (cum_dur / total_dur) * width
		var x1 := ((cum_dur + dur) / total_dur) * width
		cum_dur += dur

		var sf_raw: Variant = b.get("start_frac", null)
		var ef_raw: Variant = b.get("end_frac", sf_raw)
		var sf := 0.0
		var ef := 0.0
		var start_w := 0
		var end_w := 0
		if sf_raw != null:
			sf = maxf(0.0, float(sf_raw))
			ef = maxf(0.0, float(ef_raw if ef_raw != null else sf_raw))
			start_w = int(round(ftp_w * sf))
			end_w = int(round(ftp_w * ef))

		var h0 := clampf(sf / max_frac, 0.0, 1.0) * height
		var h1 := clampf(ef / max_frac, 0.0, 1.0) * height
		var poly := PackedVector2Array([
			Vector2(x0, height),
			Vector2(x0, height - h0),
			Vector2(x1, height - h1),
			Vector2(x1, height),
		])
		out.append({
			"index": i + 1,
			"type": b_type,
			"duration_s": dur,
			"x0": x0,
			"x1": x1,
			"width": x1 - x0,
			"h0": h0,
			"h1": h1,
			"start_w": start_w,
			"end_w": end_w,
			"polygon": poly,
		})
	return out
