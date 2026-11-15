extends RefCounted

## Consigne en direct du guide des essais physiques (série EP, lot EP3) : bandeau affiché dans le jeu.
##
## Le guide (`core/src/openride_core/tools/essai_physique.py`) écrit `~/OpenRide/Essais/consigne_directe.json`
## à chaque consigne : {"id": n, "texte": "...", "sorte": "consigne" | "vu" | "rappel" | ..., "duree_s": 8}.
## `poll` relit ce petit fichier au plus une fois par seconde et renvoie la consigne quand son `id` est nouveau (un dictionnaire vide sinon). Un fichier déjà là au lancement est
## ignoré (consigne d'un essai précédent). Sans nœud. Pas de class_name : preload("res://scripts/live_cue.gd").

const POLL_MS := 1000
const DEFAULT_DURATION_S := 8.0

var path := ""
var _next_ms := 0
var _last_id := -1
var _primed := false


func _init(p: String = "") -> void:
	path = p if p != "" else OS.get_environment("HOME").path_join("OpenRide/Essais/consigne_directe.json")


func poll(now_ms: int) -> Dictionary:
	if now_ms < _next_ms:
		return {}
	_next_ms = now_ms + POLL_MS
	if not FileAccess.file_exists(path):
		_primed = true
		return {}
	var json := JSON.new()   # `parse` sans message d'erreur au journal pour un fichier illisible
	if json.parse(FileAccess.get_file_as_string(path)) != OK:
		return {}
	var data = json.data
	if typeof(data) != TYPE_DICTIONARY or not data.has("id") or str(data.get("texte", "")) == "":
		return {}
	var id := int(data["id"])
	if not _primed:   # fichier laissé par un essai précédent : on retient son id sans l'afficher
		_primed = true
		_last_id = id
		return {}
	if id == _last_id:
		return {}
	_last_id = id
	return {"text": str(data["texte"]), "kind": str(data.get("sorte", "consigne")),
			"duration_s": float(data.get("duree_s", DEFAULT_DURATION_S))}
