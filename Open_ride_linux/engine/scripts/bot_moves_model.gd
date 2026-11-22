extends RefCounted

## Gestes des bots voisins écrits et entendus (lot BA1, essai du propriétaire du 22 novembre en mode Course :
## « rien n'indique quand un bot utilise un boost »). Une seule règle pour tous les modes à bots (session libre
## avec peloton, Course, Grand Prix, Dernier survivant) : quand un bot proche commence un geste (champ `move`
## des éléments de `bots`, révision 1.33 : `attack`, `respond`, `sprint`), une ligne en mots dans le bandeau
## (« Grimpeur attaque, 40 m devant ») et un son court (`bot_attack`). Jamais la couleur seule.
## Pas de class_name : charger par preload("res://scripts/bot_moves_model.gd").

## Bandeau : durée d'une ligne, écart minimal entre deux lignes (pas de rafale), distance des bots annoncés.
const SHOW_S := 3.0
const MIN_GAP_S := 4.0
const NEAR_M := 250.0
const JINGLE := "bot_attack"
## Ordre d'importance quand plusieurs gestes partent dans la même trame.
const ORDER := ["attack", "sprint", "respond"]

var _names: Dictionary = {}   # id → nom (le nom n'est pas dans toutes les trames d'un peloton allégé)
var _moves: Dictionary = {}   # id → geste de la trame précédente ("" : aucun)
var _last_s := -INF           # instant de la dernière ligne


## Texte d'un geste : « Grimpeur attaque, 40 m devant » ; "" pour un geste inconnu.
static func text_of(name: String, move: String, gap_m: float) -> String:
	var where := "à ta hauteur" if absf(gap_m) < 5.0 else ("%d m %s" % [int(round(absf(gap_m))), "devant" if gap_m > 0.0 else "derrière"])
	match move:
		"attack":
			return "%s attaque, %s" % [name, where]
		"sprint":
			return "%s lance le sprint, %s" % [name, where]
		"respond":
			return "%s suit l'attaque, %s" % [name, where]
	return ""


## Une trame `state` ; `now_s` : horloge de l'engine. Rend {text, jingle} d'un geste à annoncer, {} sinon.
func on_state(state: Dictionary, now_s: float) -> Dictionary:
	var bots = state.get("bots", null)
	var running := str(state.get("session_state", "")) == "RUNNING" and str(state.get("mode", "")) != "ROGUE"
	if not bots is Array or not running:
		_moves = {}
		return {}
	var s := float(state.get("s", 0.0))
	var best := {}
	var seen := {}
	for b in bots:
		if not b is Dictionary or str(b.get("kind", "")) == "ghost":
			continue
		var id := str(b.get("id", ""))
		if id == "":
			continue
		if b.get("name") is String:
			_names[id] = str(b["name"])
		var move := str(b.get("move", "")) if b.get("move") is String else ""
		seen[id] = move
		if move == "" or move == str(_moves.get(id, "")) or not ORDER.has(move):
			continue
		var gap := float(b.get("s", s)) - s
		if absf(gap) > NEAR_M:
			continue
		if best.is_empty() or ORDER.find(move) < ORDER.find(str(best["move"])) \
				or (move == best["move"] and absf(gap) < absf(float(best["gap"]))):
			best = {"id": id, "move": move, "gap": gap}
	_moves = seen
	if best.is_empty() or now_s - _last_s < MIN_GAP_S:
		return {}
	_last_s = now_s
	var name := str(_names.get(best["id"], best["id"]))
	return {"text": text_of(name, str(best["move"]), float(best["gap"])), "jingle": JINGLE}
