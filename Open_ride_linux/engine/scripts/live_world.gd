extends RefCounted

## Monde vivant côté engine (lot W10, format §13, contrat IPC 1.5) : suit les révisions du monde que le
## générateur prolonge, sans aucun affichage (les tests l'essaient sans écran).
##
## - `open(dossier)` lit le dossier de séance : parties de route, `junctions.json`, `live.json`.
## - `on_open_world(state.open_world)` : quand `rev` dépasse la révision connue, relit en tâche de fond
##   `live.json`, les parties depuis `changed_from_part` et `junctions.json` ; plusieurs demandes
##   pendant une lecture se fondent en une seule (la plus récente).
## - `poll()` (fil principal, à chaque image) échange la route et rend {} ou la révision appliquée ; la
##   route d'avant n'est jamais modifiée (les travaux de maillage en cours la gardent).
## - `previews(s)` : amorces de 500 m des branches non suivies des carrefours à moins de 1 500 m devant.
## - Recentrage : `recenter_target` et `to_render` (positions 64 bits ramenées à l'origine de rendu,
##   multiple de 1 000 m, avant la conversion en 32 bits).
## Pas de class_name (charger par preload).

const RouteData := preload("res://scripts/route_data.gd")

const PREVIEW_AHEAD_M := 1500.0
const RECENTER_STEP_M := 1000.0
const DEFAULT_RECENTER_M := 10000.0

var world_dir := ""
var route = null
var revision := 0
var junctions: Array = []
var recenter_m := DEFAULT_RECENTER_M
var render_offset := Vector2.ZERO
var last_error := ""

var _task := -1
var _result := {}
var _wanted_rev := 0         # plus haute révision annoncée par le core
var _failed_rev := 0         # dernière révision dont la lecture a échoué (pas de nouvelle tentative)
var _running_rev := 0


# --- lecture -----------------------------------------------------------------------------

static func _read_json(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		return null
	return JSON.parse_string(FileAccess.get_file_as_string(path))


static func read_junctions(dir: String) -> Array:
	var doc = _read_json(dir.path_join("junctions.json"))
	if typeof(doc) == TYPE_DICTIONARY and typeof(doc.get("junctions")) == TYPE_ARRAY:
		return doc["junctions"]
	return []


static func read_live(dir: String) -> Dictionary:
	var doc = _read_json(dir.path_join("live.json"))
	return doc if typeof(doc) == TYPE_DICTIONARY else {}


## Ouvre un dossier de séance. Renvoie vrai si la route a pu être lue.
func open(dir: String) -> bool:
	close()
	world_dir = dir
	var new_route = RouteData.new()
	if not new_route.load_live_dir(dir):
		last_error = new_route.load_error
		return false
	route = new_route
	junctions = read_junctions(dir)
	revision = int(read_live(dir).get("revision", 0))
	_wanted_rev = revision
	last_error = ""
	return true


## Reprend une route déjà lue (chargement en tâche de fond de main.gd) au lieu de la relire.
func adopt(dir: String, loaded_route) -> void:
	close()
	world_dir = dir
	route = loaded_route
	junctions = read_junctions(dir)
	revision = int(read_live(dir).get("revision", 0))
	_wanted_rev = revision
	last_error = ""


func close() -> void:
	if _task >= 0:
		WorkerThreadPool.wait_for_task_completion(_task)
		_task = -1
	route = null
	junctions = []
	revision = 0
	_wanted_rev = 0
	_failed_rev = 0
	_running_rev = 0
	_result = {}
	world_dir = ""
	render_offset = Vector2.ZERO


func is_loading() -> bool:
	return _task >= 0


# --- révisions ---------------------------------------------------------------------------

## Champ `open_world` d'une trame `state` : lance la relecture quand `rev` dépasse ce qu'on a.
func on_open_world(ow: Dictionary) -> void:
	if world_dir == "" or typeof(ow) != TYPE_DICTIONARY:
		return
	var rev := int(ow.get("rev", 0))
	if rev > _wanted_rev:
		_wanted_rev = rev
	_maybe_start()


func _maybe_start() -> void:
	if _task >= 0 or _wanted_rev <= revision or _wanted_rev == _failed_rev or route == null:
		return
	var live := read_live(world_dir)
	var live_rev := int(live.get("revision", 0))
	if live_rev <= revision:
		return                       # le core annonce une révision que le disque n'a pas encore : plus tard
	var info = live.get("route", {})
	var from_part := int(info.get("changed_from_part", 0)) if typeof(info) == TYPE_DICTIONARY else 0
	if live_rev > revision + 1 or from_part < 0 or from_part > route.parts.size():
		from_part = 0                # révisions manquées : on ne sait plus ce qui a changé
	_result = {}
	_running_rev = live_rev
	_task = WorkerThreadPool.add_task(_read_job.bind(world_dir, from_part, route, live_rev), false, "monde vivant")


## Exécuté dans un fil de WorkerThreadPool : lit les parties, assemble une nouvelle route, lit les carrefours.
func _read_job(dir: String, from_part: int, base, live_rev: int) -> void:
	var res := RouteData.read_parts(dir, from_part)
	if not res["ok"]:
		_result = {"ok": false, "error": res["error"], "revision": live_rev}
		return
	var fresh = base.revised_from(from_part, res["parts"])
	if fresh == null:
		_result = {"ok": false, "error": base.load_error, "revision": live_rev}
		return
	_result = {"ok": true, "route": fresh, "from_part": from_part, "junctions": read_junctions(dir),
		"revision": live_rev}


## Fil principal : applique une lecture terminée. Renvoie {} s'il n'y a rien de neuf, sinon
## {revision, from_part, route, junctions} (route déjà échangée) ; en cas d'échec {error, revision}.
func poll() -> Dictionary:
	if _task < 0 or not WorkerThreadPool.is_task_completed(_task):
		_maybe_start()
		return {}
	return _finish()


## Attend la fin de la lecture en cours (tests, fermeture) puis applique son résultat.
func wait_poll() -> Dictionary:
	if _task < 0:
		return poll()
	return _finish()


func _finish() -> Dictionary:
	WorkerThreadPool.wait_for_task_completion(_task)
	_task = -1
	var res := _result
	_result = {}
	var out := {}
	if res.get("ok", false):
		route = res["route"]
		junctions = res["junctions"]
		revision = int(res["revision"])
		last_error = ""
		out = {"revision": revision, "from_part": int(res["from_part"]), "route": route, "junctions": junctions}
	else:
		last_error = str(res.get("error", "lecture impossible"))
		_failed_rev = int(res.get("revision", 0))
		out = {"error": last_error, "revision": _failed_rev}
	_maybe_start()
	return out


# --- amorces de branches -----------------------------------------------------------------

## Amorces à dessiner pour la position s : une par branche non suivie des carrefours situés entre s et
## s + 1 500 m ; [{key, junction, branch, xs, ys, zs}]. Un carrefour dépassé n'en a plus.
func previews(s_pos: float) -> Array:
	var out := []
	for j in junctions:
		if typeof(j) != TYPE_DICTIONARY:
			continue
		var d := float(j.get("s_m", 0.0)) - s_pos
		if d < 0.0 or d > PREVIEW_AHEAD_M:
			continue
		var chosen := int(j.get("chosen", j.get("default", 0)))
		var branches = j.get("branches", [])
		if typeof(branches) != TYPE_ARRAY:
			continue
		for b in branches:
			if typeof(b) != TYPE_DICTIONARY or int(b.get("index", -1)) == chosen:
				continue
			var pv = b.get("preview", {})
			if typeof(pv) != TYPE_DICTIONARY or typeof(pv.get("x")) != TYPE_ARRAY:
				continue
			out.append({"key": "%s:%d" % [str(j.get("id", "")), int(b["index"])], "junction": str(j.get("id", "")),
				"branch": int(b["index"]), "xs": pv["x"], "ys": pv.get("y", []), "zs": pv.get("z", [])})
	return out


# --- recentrage de l'origine -------------------------------------------------------------

## Nouvelle origine de rendu pour une caméra en (cam_x, cam_z) : inchangée tant que la caméra reste à
## `recenter_m` ou moins de l'origine courante, sinon le multiple de 1 000 m le plus proche de la caméra.
static func recenter_target(cam_x: float, cam_z: float, offset: Vector2, limit_m: float) -> Vector2:
	if Vector2(cam_x - offset.x, cam_z - offset.y).length() <= limit_m:
		return offset
	return Vector2(roundf(cam_x / RECENTER_STEP_M) * RECENTER_STEP_M, roundf(cam_z / RECENTER_STEP_M) * RECENTER_STEP_M)


## Met à jour `render_offset` ; renvoie le déplacement à appliquer au nœud racine du monde affiché
## (la nouvelle origine moins l'ancienne, multiple de 1 000 m) ou Vector2.ZERO.
func track_camera(cam_x: float, cam_z: float) -> Vector2:
	var target := recenter_target(cam_x, cam_z, render_offset, recenter_m)
	var delta := target - render_offset
	render_offset = target
	return delta


## Position du monde (64 bits) dans le repère de rendu : l'origine est retranchée avant la conversion en
## 32 bits, d'où une erreur sous le millimètre même à des dizaines de kilomètres du départ.
static func to_render(x64: float, z64: float, offset: Vector2) -> Vector2:
	return Vector2(x64 - float(offset.x), z64 - float(offset.y))
