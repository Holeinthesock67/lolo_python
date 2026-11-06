extends RefCounted

## Sons du mode « What the fuck » (série WTF, lot WTF7), sans nœud : compare l'objet `wtf` de la trame
## `state` (contrat 1.5) à celui de la trame d'avant et rend les jingles à jouer (palette commune
## event_sounds_model.gd JINGLES, noms `wtf_*`, joués par main.gd sur le bus « Events » comme les autres).
## - début d'un gag : un son par gag (`wtf_moon` ou `wtf_jupiter` selon la planète, `wtf_flip`,
##   `wtf_collapse`, `wtf_cheese`, `wtf_micro`, `wtf_eggs`, `wtf_tiny`, `wtf_storm`, `wtf_camera`, `wtf_chef`) ;
## - pendant le gag : cloche du chef qui soulève la cloche (`wtf_cloche`), œuf cassé (`wtf_crack`), écrasé par
##   le fromage (`wtf_splat`), manche d'un micro-défi gagnée ou perdue (`wtf_round_ok`, `wtf_round_fail`) ;
## - fin du gag : points gagnés pendant le gag, arpège (`wtf_win`) ; aucun, trombone triste (`wtf_fail`) ;
## - règles permanentes : objet ramassé par le Katamari (`wtf_pop`), objet trop gros (`wtf_boing`), mamie qui
##   attaque (`wtf_horn`), début d'une pluie de poissons (`wtf_fish`).
## Rien à la première trame du mode (pas de rafale à l'entrée), ni sans mode WTF ; au plus MAX_PER_FRAME sons
## par trame, la fin d'un gag d'abord, puis son début, puis le reste. Pas de class_name :
## preload("res://scripts/wtf/wtf_sound_model.gd").

const MAX_PER_FRAME := 2
const STARTS := {"upside_down": "wtf_flip", "collapse": "wtf_collapse", "cheese": "wtf_cheese",
	"micro": "wtf_micro", "eggs": "wtf_eggs", "tiny": "wtf_tiny", "storm": "wtf_storm", "camera": "wtf_camera",
	"chef": "wtf_chef"}

var _prev: Variant = null     # objet `wtf` de la trame d'avant (null : hors mode)
var _points_at_start := 0     # points au début du gag en cours


func reset() -> void:
	_prev = null


## Une fois par trame `state` ; `wtf` : champ `wtf` de la trame (absent : null). Rend les jingles à jouer.
func on_state(wtf: Variant) -> Array:
	if typeof(wtf) != TYPE_DICTIONARY:
		_prev = null
		return []
	var prev = _prev
	_prev = wtf.duplicate(true)
	var points := int(wtf.get("points", 0))
	if typeof(prev) != TYPE_DICTIONARY:
		_points_at_start = points
		return []
	var out := []
	var ev = wtf.get("event", null)
	var pev = prev.get("event", null)
	var id := str(ev.get("id", "")) if typeof(ev) == TYPE_DICTIONARY else ""
	var pid := str(pev.get("id", "")) if typeof(pev) == TYPE_DICTIONARY else ""
	if pid != "" and id != pid:
		out.append("wtf_win" if points > _points_at_start else "wtf_fail")
	if id != "" and id != pid:
		_points_at_start = points
		out.append(_start(ev))
	elif id != "" and id == pid:
		var during := _during(ev, pev)
		if during != "":
			out.append(during)
	out.append_array(_ambient(wtf, prev))
	return out.slice(0, MAX_PER_FRAME)


static func _start(ev: Dictionary) -> String:
	var id := str(ev.get("id", ""))
	if id == "gravity":
		return "wtf_moon" if str(ev.get("planet", "moon")) == "moon" else "wtf_jupiter"
	return str(STARTS.get(id, "wtf_micro"))


static func _during(ev: Dictionary, pev: Dictionary) -> String:
	match str(ev.get("id", "")):
		"chef":
			if str(ev.get("phase", "")) == "reveal" and str(pev.get("phase", "")) == "arrive":
				return "wtf_cloche"
		"eggs":
			if int(ev.get("eggs", 0)) < int(pev.get("eggs", 0)):
				return "wtf_crack"
		"cheese":
			if bool(ev.get("squashed", false)) and not bool(pev.get("squashed", false)):
				return "wtf_splat"
		"micro":
			var res = ev.get("results", [])
			var pres = pev.get("results", [])
			if typeof(res) == TYPE_ARRAY and typeof(pres) == TYPE_ARRAY and res.size() > pres.size():
				return "wtf_round_ok" if bool(res[-1]) else "wtf_round_fail"
	return ""


static func _ambient(wtf: Dictionary, prev: Dictionary) -> Array:
	var out := []
	var k = wtf.get("kata", null)
	var pk = prev.get("kata", null)
	if typeof(k) == TYPE_DICTIONARY and typeof(pk) == TYPE_DICTIONARY:
		if int(k.get("bonks", 0)) > int(pk.get("bonks", 0)):
			out.append("wtf_boing")
		elif int(k.get("count", 0)) > int(pk.get("count", 0)):
			out.append("wtf_pop")
	var attack = wtf.get("attack", null)
	var pattack = prev.get("attack", null)
	if attack != null and str(attack) != "" and (pattack == null or str(pattack) == ""):
		out.append("wtf_horn")
	if bool(wtf.get("fish", false)) and not bool(prev.get("fish", false)):
		out.append("wtf_fish")
	return out
