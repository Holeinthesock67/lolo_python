extends RefCounted

## Gags en 3D du mode « What the fuck » (série WTF, lots WTF5 et WTF6), sans nœud : traduit l'objet `wtf` de
## la trame `state` (contrat 1.5) en ce que wtf_scene.gd pose dans la scène, d'après les maquettes validées
## le 30 octobre (style cartoon : formes simples, couleurs vives).
## - `tint` : voile de couleur sur toute l'image (Lune grise, Jupiter rougeâtre, tempête sombre, gelée verte) ;
## - `roll_deg` : roulis visé de la caméra (180 en monde à l'envers ; wtf_scene.gd y va en douceur) ;
## - `camera` : vue imposée ("" ou pigeon, snail, wheel, tiny) ;
## - `hop_m` : bond du vélo sur la Lune ;
## - `sun_hour` : heure du soleil (règle de l'horloge), −1 sans elle ;
## - `props` : objets à poser, {kind, ds (m le long de la route depuis le cycliste), lateral (m à droite),
##   up (m), scale, spin (rad)} ;
## - `skins`, `attack` : costumes des bots et mamie qui attaque (règle du peloton), passés tels quels.
## Le nombre d'objets suit la qualité (`low`, `medium`, `high`). Pas de class_name :
## preload("res://scripts/wtf/wtf_scene_model.gd").

const TINT_MOON := Color(0.75, 0.78, 0.85, 0.22)
const TINT_JUPITER := Color(1.0, 0.45, 0.2, 0.2)
const TINT_STORM := Color(0.25, 0.27, 0.33, 0.3)
const TINT_JELLY := Color(0.48, 0.85, 0.29, 0.14)
const TINT_CHILI := Color(1.0, 0.25, 0.1, 0.16)
## Objets par qualité : vaches de la tornade, poissons, tronçons qui tombent.
const COUNTS := {"low": {"cows": 8, "fish": 6, "chunks": 4}, "medium": {"cows": 16, "fish": 12, "chunks": 6},
	"high": {"cows": 24, "fish": 20, "chunks": 8}}
const CHUNK_M := 6.0
const CHEESE_RADIUS_M := 1.5
const STORM_AHEAD_M := 28.0   # assez près pour voir les vaches (essai PC 7cn : à 45 m, quelques points)
const COW_SCALE := 2.5         # vaches cartoon, plus grosses que nature
const KATA_BALL_M := 0.45     # rayon de la boule à la taille 1
const KATA_SHOW_MAX := 3.0     # la boule affichée cesse de grossir à × 3 (1,35 m) : le décor reste visible
const KATA_LATERAL_M := 1.2    # poussée un peu à droite du cycliste, hors du centre de l'image
const KITCHEN := [["plate", 25.0, -9.0, 30.0], ["fork", 60.0, 10.0, 28.0], ["cup", 110.0, -12.0, 35.0],
	["plate", 160.0, 11.0, 30.0], ["fork", 210.0, -10.0, 28.0]]
const KATA_SCALES := {"apple": 0.3, "sign": 1.0, "cow": 1.4, "car": 1.8, "house": 4.0, "church": 7.0}


## Vue complète ; `wtf` absent ou nul : rien. `t` : horloge de l'engine (s), pour les mouvements continus.
static func view(wtf: Variant, t: float, quality := "medium") -> Dictionary:
	var out := {"active": false, "tint": Color(0, 0, 0, 0), "roll_deg": 0.0, "camera": "", "hop_m": 0.0,
		"sun_hour": -1.0, "props": [], "skins": {}, "attack": ""}
	if typeof(wtf) != TYPE_DICTIONARY:
		return out
	out["active"] = true
	var n: Dictionary = COUNTS.get(quality, COUNTS["medium"])
	var props: Array = out["props"]
	var ev = wtf.get("event", null)
	if typeof(ev) == TYPE_DICTIONARY:
		_event(ev, t, n, out, props)
	var kata = wtf.get("kata", null)
	if typeof(kata) == TYPE_DICTIONARY:
		var size := minf(float(kata.get("size", 1.0)), KATA_SHOW_MAX)
		props.append(_prop("ball", 2.0 + KATA_BALL_M * size, KATA_LATERAL_M + KATA_BALL_M * size,
			KATA_BALL_M * size, size, t * 4.0))
		var nxt = kata.get("next", [])
		if typeof(nxt) == TYPE_ARRAY:
			for o in nxt:
				if typeof(o) == TYPE_ARRAY and o.size() >= 2:
					var kind := str(o[1])
					props.append(_prop("kata_" + kind, float(o[0]), 0.0, 0.0, float(KATA_SCALES.get(kind, 1.0)), 0.0))
	if wtf.has("clock_h"):
		out["sun_hour"] = fposmod(float(wtf["clock_h"]), 24.0)
		if bool(wtf.get("fish", false)):
			for i in int(n["fish"]):
				props.append(_prop("fish", fposmod(i * 7.3, 60.0) - 10.0, fposmod(i * 13.0, 14.0) - 7.0,
					12.0 - fposmod(t * 6.0 + i * 1.7, 12.0), 1.0, t * 3.0 + i))
	var skins = wtf.get("skins", {})
	if typeof(skins) == TYPE_DICTIONARY:
		out["skins"] = skins
	var attack = wtf.get("attack", null)
	out["attack"] = str(attack) if attack != null else ""
	return out


static func _event(ev: Dictionary, t: float, n: Dictionary, out: Dictionary, props: Array) -> void:
	match str(ev.get("id", "")):
		"gravity":
			var moon := str(ev.get("planet", "moon")) == "moon"
			out["tint"] = TINT_MOON if moon else TINT_JUPITER
			out["hop_m"] = float(ev.get("hop_m", 0.0)) if moon else 0.0
		"upside_down":
			out["roll_deg"] = 180.0
		"collapse":
			var gap := float(ev.get("gap_m", 0.0))
			for i in int(n["chunks"]):
				# Le front de l'effondrement à `gap` m derrière, les tronçons plus loin déjà tombés.
				props.append(_prop("chunk", -gap - i * CHUNK_M, 0.0, -0.6 * i * i, 1.0, 0.25 * i))
		"cheese":
			var gap := float(ev.get("gap_m", 0.0))
			var squashed := bool(ev.get("squashed", false))
			props.append(_prop("cheese", 0.0 if squashed else -gap, 0.0, CHEESE_RADIUS_M, 1.0, -t * 3.0))
		"storm":
			out["tint"] = TINT_STORM
			var cows := mini(int(n["cows"]), int(ev.get("cows", n["cows"])))
			for i in cows:
				var a := t * 2.0 + i * TAU / maxf(cows, 1)
				var r := 5.0 + (i % 3) * 3.0
				props.append(_prop("cow", STORM_AHEAD_M + r * sin(a), r * cos(a), fposmod(i * 1.3 + t, 14.0), COW_SCALE, a))
			props.append(_prop("tornado", STORM_AHEAD_M, 0.0, 0.0, 1.0, t * 2.0))
		"tiny":
			out["camera"] = "tiny"
			for k in KITCHEN:
				props.append(_prop(k[0], k[1], k[2], 0.0, k[3], 0.0))
		"camera":
			out["camera"] = str(ev.get("view", ""))
		"chef":
			var phase := str(ev.get("phase", ""))
			if phase in ["arrive", "reveal"]:
				props.append(_prop("chef", 3.0, -1.6, 0.0, 1.0, 0.0))
			if phase == "reveal" or phase == "eat":
				var dish := str(ev.get("dish", ""))
				if dish != "" and dish != "<null>":
					props.append(_prop("dish_" + dish, 1.2 if phase == "eat" else 3.0, -0.6 if phase == "reveal" else 0.0,
						1.3 + 0.3 * float(ev.get("souffle", 0.0)), 1.0, t))
			if phase == "eat":
				match str(ev.get("dish", "")):
					"jelly":
						out["tint"] = TINT_JELLY
					"chili":
						if bool(ev.get("burning", false)):
							out["tint"] = TINT_CHILI


static func _prop(kind: String, ds: float, lateral: float, up: float, scale: float, spin: float) -> Dictionary:
	return {"kind": kind, "ds": ds, "lateral": lateral, "up": up, "scale": scale, "spin": spin}


## Élévation du soleil (degrés) pour une heure : 0 à 6 h et 18 h, 60 à midi, sous l'horizon la nuit.
static func sun_elevation_deg(hour: float) -> float:
	return 60.0 * sin((fposmod(hour, 24.0) - 6.0) / 12.0 * PI)
