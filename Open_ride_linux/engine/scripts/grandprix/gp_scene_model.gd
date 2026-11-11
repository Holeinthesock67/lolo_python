extends RefCounted

## Objets du « Grand Prix des objets » dans la scène (série GP, lot GP7), sans aucun nœud : ce que gp_scene.gd
## pose sur la route d'après l'objet `gp` de la trame `state` (contrat 1.7) et les messages `gp_hit`, selon les
## maquettes GP6 validées le 7 novembre 2026 (scènes 2 à 5) :
## - `boxes(gp)` : boîtes de ravitaillement, une par voie et par rangée (`gp.boxes`, deux rangées au plus,
##   six boîtes au plus : un MultiMesh) ;
## - `objects(gp)` : bidons posés et musettes, musettes guidées et nuages d'orage lancés (`gp.obj`, douze au
##   plus), à leur voie (centres des voies du core, `mode.LANE_CENTRES_M`) ou au milieu pour toute la route ;
## - `assign(objects)` : place de chaque objet dans la réserve d'instances de sa sorte (POOL instances par
##   sorte, créées une fois : aucune création en course) ; un objet garde sa place d'une trame à l'autre, un
##   objet sorti de la trame libère la sienne ;
## - `looks(fx)` : effets à dessiner sur un coureur d'après ses objets en cours (glissade, averse, super-forme,
##   voiture d'équipe, rafales, coup de fouet), et `particles(quality, look)` : `low` sans particules (sprites
##   seulement), `medium` limité, `high` complet (plan §8.3) ;
## - `on_hit(msg, now_s)` : onomatopée au-dessus du coureur touché (« ZIOUF ! », « SPLASH ! », « BOING ! »),
##   les messages répétés trois fois par le core ne comptant qu'une fois.
## Pas de class_name : preload("res://scripts/grandprix/gp_scene_model.gd").

const Items := preload("res://scripts/grandprix/gp_items.gd")

const LANE_CENTRES_M := [0.68, 1.45, 2.22]     # core grandprix/mode.py LANE_CENTRES_M (gauche, centre, droite)
const WHOLE_ROAD_M := 1.45                     # objet sur toute la route (voie -1) : au milieu des trois voies
const MAX_ROWS := 2
const MAX_OBJECTS := 12
const POOL := 12                               # instances par sorte d'objet dessiné (trame : 12 objets au plus)
const SHOT_KINDS := ["bottle", "musette", "homing", "storm"]   # objets posés ou lancés (`shot` du core)
## Effet dessiné sur un coureur pour chaque objet en cours (`gp.fx`, `bots[].fx`).
const FX_LOOK := {"bottle": "slip", "bottle_x3": "slip", "musette": "slip", "musette_x3": "slip", "homing": "slip",
	"storm": "rain", "star": "halo", "team_car": "car", "headwind": "gust", "gel": "kick", "gel_x3": "kick"}
const LOOKS := ["slip", "rain", "halo", "car", "gust", "kick"]
## Particules par effet et par préréglage (0 : sprites seulement).
const PARTICLES := {
	"low": {},
	"medium": {"rain": 48, "halo": 0},
	"high": {"rain": 140, "halo": 24},
}
## Effets dessinés en `low` (sprites) ; `medium` et `high` les dessinent tous.
const LOW_LOOKS := ["slip", "rain", "halo", "car"]
const WORDS := {"bottle": "ZIOUF !", "bottle_x3": "ZIOUF !", "musette": "ZIOUF !", "musette_x3": "ZIOUF !",
	"homing": "ZIOUF !", "storm": "SPLASH !", "star": "BOING !"}
const WORD_S := 1.2
const HIT_REPEAT_S := 3.5                      # le core répète `gp_hit` 3 fois à 1 s : doublons ignorés
const MAX_WORDS := 4

var _slots := {}                               # sorte -> [id ou -1 par place]
var _words: Array = []                         # [{text, target, until}]
var _seen_hits := {}                           # clé du message -> instant de la première réception


func reset() -> void:
	_slots.clear()
	_words.clear()
	_seen_hits.clear()


static func lane_lateral(lane: int) -> float:
	if lane >= 0 and lane < LANE_CENTRES_M.size():
		return float(LANE_CENTRES_M[lane])
	return WHOLE_ROAD_M


## Boîtes à poser : [{s, lateral, row}], trois par rangée, MAX_ROWS rangées au plus.
static func boxes(gp) -> Array:
	var out: Array = []
	if not gp is Dictionary or not gp.get("boxes", null) is Array:
		return out
	var row := 0
	for s in gp["boxes"]:
		if not (s is float or s is int) or row >= MAX_ROWS:
			continue
		for lane in range(LANE_CENTRES_M.size()):
			out.append({"s": float(s), "lateral": lane_lateral(lane), "row": row})
		row += 1
	return out


## Objets à poser : [{id, kind, s, lateral, whole}], MAX_OBJECTS au plus, sortes connues seulement.
static func objects(gp) -> Array:
	var out: Array = []
	if not gp is Dictionary or not gp.get("obj", null) is Array:
		return out
	for o in gp["obj"]:
		if not o is Array or o.size() < 4 or not str(o[1]) in SHOT_KINDS or not (o[2] is float or o[2] is int):
			continue
		var lane := int(o[3]) if (o[3] is float or o[3] is int) else -1
		out.append({"id": int(o[0]) if (o[0] is float or o[0] is int) else -1, "kind": str(o[1]), "s": float(o[2]),
			"lateral": lane_lateral(lane), "whole": lane < 0})
		if out.size() >= MAX_OBJECTS:
			break
	return out


## Place de chaque objet dans la réserve de sa sorte : {sorte: [objet ou null, ...]} (POOL places par sorte).
func assign(objs: Array) -> Dictionary:
	var want := {}
	for o in objs:
		if not want.has(o["kind"]):
			want[o["kind"]] = []
		want[o["kind"]].append(o)
	var out := {}
	for kind in SHOT_KINDS:
		var slots: Array = _slots.get(kind, [])
		if slots.size() != POOL:
			slots = []
			slots.resize(POOL)
			slots.fill(-1)
		var list: Array = want.get(kind, [])
		var ids := {}
		for o in list:
			ids[o["id"]] = o
		for i in range(POOL):   # place libérée : objet sorti de la trame
			if not ids.has(slots[i]):
				slots[i] = -1
		var placed: Array = []
		placed.resize(POOL)
		for o in list:
			var at := slots.find(o["id"])
			if at < 0:
				at = slots.find(-1)
			if at < 0:
				continue   # réserve pleine : jamais avec MAX_OBJECTS = POOL
			slots[at] = o["id"]
			placed[at] = o
		_slots[kind] = slots
		out[kind] = placed
	return out


## Effets à dessiner pour des objets en cours (`fx` : sortes, ou paires [sorte, reste] de `gp.fx`).
static func looks(fx) -> Array:
	var out: Array = []
	if not fx is Array:
		return out
	for e in fx:
		var kind := str(e[0]) if (e is Array and e.size() > 0) else str(e)
		var look := str(FX_LOOK.get(kind, ""))
		if look != "" and not look in out:
			out.append(look)
	return out


## Effets dessinés au préréglage `quality` parmi `wanted`.
static func shown_looks(quality: String, wanted: Array) -> Array:
	if quality != "low":
		return wanted
	return wanted.filter(func(l) -> bool: return l in LOW_LOOKS)


## Particules d'un effet au préréglage `quality` (0 : sprites seulement).
static func particles(quality: String, look: String) -> int:
	return int(PARTICLES.get(quality, {}).get(look, 0))


## Message `gp_hit` : onomatopée au-dessus du coureur touché ; vrai si le message est nouveau.
func on_hit(msg: Dictionary, now_s: float) -> bool:
	var key := "%s|%s|%s|%s" % [msg.get("item", ""), msg.get("by", ""), msg.get("target", ""), msg.get("loss_s", "")]
	for k in _seen_hits.keys():
		if now_s - float(_seen_hits[k]) > HIT_REPEAT_S:
			_seen_hits.erase(k)
	if _seen_hits.has(key):
		return false
	_seen_hits[key] = now_s
	var word := str(WORDS.get(str(msg.get("item", "")), ""))
	if word != "" and str(msg.get("target", "")) != "":
		_words.append({"text": word, "target": str(msg["target"]), "until": now_s + WORD_S, "born": now_s})
		while _words.size() > MAX_WORDS:
			_words.pop_front()
	return true


## Onomatopées en cours : [{text, target, age (0 à 1)}].
func words(now_s: float) -> Array:
	_words = _words.filter(func(w) -> bool: return now_s < float(w["until"]))
	var out: Array = []
	for w in _words:
		out.append({"text": w["text"], "target": w["target"], "age": clampf((now_s - float(w["born"])) / WORD_S, 0.0, 1.0)})
	return out
