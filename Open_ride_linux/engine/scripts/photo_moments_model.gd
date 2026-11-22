extends RefCounted

## Photos automatiques de la séance (idée M9 de l'audit du 22 novembre) : à l'arrivée et à chaque record de
## montée ou de sprint, l'engine garde une image de l'écran dans `~/OpenRide/Captures/<date>_<heure>/`,
## et le bilan dit en mots combien de photos ont été prises et où. Les photos restent sur le PC.
## Modèle pur, sans aucun nœud : il décide quand prendre une photo et comment la nommer ; main.gd lit
## l'image et l'écrit dans un fil de travail. Aucun champ IPC nouveau : tout vient de ce que l'engine
## reçoit déjà, avec les mêmes règles que les jingles (event_sounds_model.gd) :
## - arrivée : passage de `RUNNING` ou `PAUSED` à `FINISHED` ; la photo est l'image déjà rendue, celle du
##   passage de la ligne, avant que le bilan ne la couvre ;
## - record : message `segment_result` de `kind` « climb » ou « sprint » avec `pr` vrai, photo prise
##   `RECORD_DELAY_S` plus tard (le résultat est alors affiché au HUD), seulement si la séance roule encore ;
## - jamais en Cyber-Rogue (`mode` ROGUE, sa propre scène) ; au plus `MAX_PHOTOS` par séance, la dernière place gardée pour l'arrivée ; nouvelle
##   série à chaque nouveau départ (`READY` ou `RUNNING` après `IDLE` ou `FINISHED`).
## Réglage `render.auto_photos` (`on` par défaut, `off` : aucune photo).
## Pas de class_name : charger par preload("res://scripts/photo_moments_model.gd").

const SETTING_KEY := "render.auto_photos"
const MAX_PHOTOS := 6
const RECORD_DELAY_S := 1.2
const KIND_FINISH := "arrivee"
const KIND_RECORD := "record"
## Dossier des photos sous le dossier personnel (affiché tel quel dans le bilan).
const BASE_DIR := "OpenRide/Captures"

var enabled := true
## Photos prises de la séance en cours : [{kind, label, file}], `file` relatif au dossier de la séance.
var photos: Array = []
## Dossier de la séance (`AAAA-MM-JJ_HHMM`), fixé à la première photo ; vide sinon.
var folder := ""
var _pending: Array = []   # [{due_s, kind, label}]
var _prev_session := ""


## Une fois par trame `state`. Rend les photos à prendre tout de suite : [{kind, label}].
func on_state(state: Dictionary, now_s: float) -> Array:
	var session := str(state.get("session_state", ""))
	var out := []
	if session in ["READY", "RUNNING"] and _prev_session in ["", "IDLE", "FINISHED"]:
		reset()
	var rogue := str(state.get("mode", "")) == "ROGUE"
	if enabled and not rogue and session == "FINISHED" and _prev_session in ["RUNNING", "PAUSED"]:
		_pending.clear()
		out.append({"kind": KIND_FINISH, "label": "arrivée"})
	elif session == "RUNNING" and not rogue:
		var keep := []
		for p in _pending:
			if now_s >= float(p["due_s"]):
				out.append({"kind": p["kind"], "label": p["label"]})
			else:
				keep.append(p)
		_pending = keep
	elif session != "PAUSED":
		_pending.clear()
	_prev_session = session
	return _limit(out)


## Message `segment_result` (déjà dédoublonné) : un record prépare une photo `RECORD_DELAY_S` plus tard.
func on_segment_result(msg: Dictionary, now_s: float) -> void:
	if not enabled or not bool(msg.get("pr", false)) or not str(msg.get("kind", "")) in ["climb", "sprint"]:
		return
	var name := str(msg.get("name", "")).strip_edges()
	var what := "montée" if str(msg.get("kind", "")) == "climb" else "sprint"
	var label := "record « %s »" % name if name != "" else "record de %s" % what
	_pending.append({"due_s": now_s + RECORD_DELAY_S, "kind": KIND_RECORD, "label": label})


## Nouvelle séance : liste et dossier vidés.
func reset() -> void:
	photos.clear()
	_pending.clear()
	folder = ""


## Note une photo prise ; rend son chemin relatif au dossier de la séance (`folder` fixé au besoin depuis
## `now`, dictionnaire de Time.get_datetime_dict_from_system()).
func add_photo(req: Dictionary, now: Dictionary) -> String:
	if folder == "":
		folder = folder_name(now)
	var file := file_name(photos.size() + 1, str(req.get("kind", KIND_FINISH)), str(req.get("label", "")))
	photos.append({"kind": req.get("kind", KIND_FINISH), "label": req.get("label", ""), "file": file})
	return file


## Plafond de la séance ; la dernière place reste à l'arrivée.
func _limit(reqs: Array) -> Array:
	var out := []
	for r in reqs:
		var cap := MAX_PHOTOS if r["kind"] == KIND_FINISH else MAX_PHOTOS - 1
		if photos.size() + out.size() < cap:
			out.append(r)
	return out


## « 2026-11-28_1012 ».
static func folder_name(now: Dictionary) -> String:
	return "%04d-%02d-%02d_%02d%02d" % [int(now.get("year", 0)), int(now.get("month", 0)), int(now.get("day", 0)),
		int(now.get("hour", 0)), int(now.get("minute", 0))]


## « 1_arrivee.jpg », « 2_record_cote-du-village.jpg » : lettres ASCII minuscules, chiffres et tirets.
static func file_name(index: int, kind: String, label: String) -> String:
	var base := kind
	if kind == KIND_RECORD:
		var slug := slugify(label.replace("record", ""))
		base = kind + ("_" + slug if slug != "" else "")
	return "%d_%s.jpg" % [index, base]


static func slugify(text: String) -> String:
	const FROM := "àâäáãåçéèêëíìîïñóòôöõúùûüýÿœæ"
	const TO := ["a", "a", "a", "a", "a", "a", "c", "e", "e", "e", "e", "i", "i", "i", "i", "n", "o", "o", "o", "o",
		"o", "u", "u", "u", "u", "y", "y", "oe", "ae"]
	var out := ""
	var dash := false
	for ch in text.to_lower():
		var i := FROM.find(ch)
		var c: String = TO[i] if i >= 0 else ch
		if (c >= "a" and c <= "z") or (c >= "0" and c <= "9") or c.length() > 1:
			out += c
			dash = false
		elif not dash and out != "":
			out += "-"
			dash = true
	return out.trim_suffix("-").left(40).trim_suffix("-")


## Lignes du bilan, en mots : [] sans photo, sinon deux lignes courtes (une ligne longue rapetissait l'encart
## du résultat en high) : « Photos de la séance : 2 (record « Côte du village », arrivée) » et
## « Dossier : ~/OpenRide/Captures/2026-11-28_1012 ».
static func photo_lines(list: Array, dir: String) -> Array:
	if list.is_empty() or dir == "":
		return []
	var labels := []
	for p in list:
		labels.append(str(p.get("label", "")))
	var what := ", ".join(labels)
	var head := "Photo de la séance" if list.size() == 1 else "Photos de la séance : %d" % list.size()
	return ["%s (%s)" % [head, what], "Dossier : ~/%s/%s" % [BASE_DIR, dir]]
