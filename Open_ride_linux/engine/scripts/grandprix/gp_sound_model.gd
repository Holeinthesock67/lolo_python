extends RefCounted

## Sons du « Grand Prix des objets » (série GP, lot GP7), sans aucun nœud : bruitages à jouer d'après l'objet
## `gp` de chaque trame et les messages `gp_hit` (contrat 1.7), dans la famille des jingles existants
## (event_sounds_model.gd JINGLES, synthèse de sound_player.gd, remplaçables par ~/OpenRide/Sounds/<nom>.ogg) :
## - `gp_roulette` : début d'un tirage après une boîte ;
## - `gp_lancer` : objet utilisé par le cycliste (une charge de moins, ou réserve vidée), sauf la sonnette
##   (`gp_sonnette`) et la voiture d'équipe (`gp_klaxon`) ;
## - `gp_glissade` : cycliste touché par un bidon ou une musette ; `gp_averse` : par le nuage d'orage.
## Ne décide rien : le core arbitre tout. Pas de class_name : preload("res://scripts/grandprix/gp_sound_model.gd").

const ME := "me"
const USE_SOUND := {"bell": "gp_sonnette", "team_car": "gp_klaxon"}
const HIT_SOUND := {"bottle": "gp_glissade", "bottle_x3": "gp_glissade", "musette": "gp_glissade",
	"musette_x3": "gp_glissade", "homing": "gp_glissade", "storm": "gp_averse"}

var _rolling := false
var _held := ""
var _n := 0


func reset() -> void:
	_rolling = false
	_held = ""
	_n = 0


## Sons à jouer pour la trame `gp` (null : rien, et l'état est remis à zéro).
func on_state(gp) -> Array:
	if not gp is Dictionary:
		reset()
		return []
	var out: Array = []
	var roll_s = gp.get("roll_s", 0.0)
	var rolling := (roll_s is float or roll_s is int) and float(roll_s) > 0.0
	var held := "" if gp.get("held", null) == null else str(gp["held"])
	var n_raw = gp.get("n", 0)
	var n := int(n_raw) if (n_raw is float or n_raw is int) else 0
	if rolling and not _rolling:
		out.append("gp_roulette")
	elif not rolling and not _rolling and _held != "" and (held == "" or (held == _held and n < _n)):
		out.append(str(USE_SOUND.get(_held, "gp_lancer")))
	_rolling = rolling
	_held = held
	_n = n
	return out


## Son du message `gp_hit` nouveau (gp_scene_model.gd on_hit l'a déjà dédoublonné) : seulement si le cycliste
## est touché ; "" sinon.
static func on_hit(msg: Dictionary) -> String:
	if str(msg.get("target", "")) != ME:
		return ""
	return str(HIT_SOUND.get(str(msg.get("item", "")), ""))
