extends RefCounted

## Comportement des animaux placés par fauna_placer.gd (Lot P11), sans aucun nœud.
## Pas de class_name : charger par preload("res://scripts/fauna_behaviour.gd").
##
## - Oiseaux : cercles lents autour du centre de la bande (`omega` rad/s), ondulés de ± BIRD_WAVE_M ;
##   quand le cycliste passe à moins de BIRD_DODGE_M du centre de la bande (à l'horizontale), toute la
##   bande s'écarte de lui (jusqu'à BIRD_DODGE_SHIFT_M de côté et BIRD_DODGE_RISE_M plus haut), puis
##   revient ; lissage du premier ordre de constante BIRD_DODGE_TAU_S.
## - Bétail : immobile, il tourne lentement sur place (± HERD_YAW_SWING rad), jamais vers la route.
## - Chevreuil : `idle`, puis `flee` dès que le cycliste est à moins de DEER_ALERT_M, à DEER_SPEED_MPS
##   le long de `flee_dir` (vers la forêt, loin de la route), puis `gone` après DEER_FLEE_S.
## Le travail par image est fait par groupe (bande, troupeau, site), pas par bête : `update` coûte
## quelques microsecondes pour 200 animaux ; les positions des oiseaux se calculent à la demande.

const FaunaPlacer := preload("res://scripts/fauna_placer.gd")

const BIRD_WAVE_M := FaunaPlacer.BIRD_WAVE_M
const BIRD_DODGE_M := 40.0
const BIRD_DODGE_SHIFT_M := 25.0
const BIRD_DODGE_RISE_M := 8.0
const BIRD_DODGE_TAU_S := 1.5
const HERD_YAW_SWING := 0.6
const HERD_YAW_PERIOD_S := 40.0
const DEER_ALERT_M := 60.0
const DEER_SPEED_MPS := 9.0
const DEER_FLEE_S := 5.0

var groups: Array = []
var _last_s: float = NAN


## Groupes suivis ; un groupe déjà suivi garde son état (chevreuil en fuite, écart des oiseaux).
func setup(new_groups: Array) -> void:
	groups = new_groups
	for g in groups:
		match str(g.get("type", "")):
			"birds":
				if not g.has("dodge"):
					g["dodge"] = Vector3.ZERO
			"deer":
				if not g.has("state"):
					g["state"] = "idle"
					g["flee_at"] = NAN


## Une fois par image : réactions au cycliste en `rider_pos` à l'instant `now_s`.
func update(rider_pos: Vector3, now_s: float) -> void:
	var dt := 0.0 if is_nan(_last_s) else clampf(now_s - _last_s, 0.0, 0.5)
	_last_s = now_s
	var k := 1.0 - exp(-dt / BIRD_DODGE_TAU_S)
	var r2 := Vector2(rider_pos.x, rider_pos.z)
	for g in groups:
		var t: String = g["type"]
		if t == "birds":
			var c: Vector3 = g["center"]
			var away := Vector2(c.x, c.z) - r2
			var d := away.length()
			var target := Vector3.ZERO
			if d < BIRD_DODGE_M:
				var dir := away / d if d > 1e-3 else Vector2(1.0, 0.0)
				var push := 1.0 - d / BIRD_DODGE_M
				target = Vector3(dir.x * BIRD_DODGE_SHIFT_M * push, BIRD_DODGE_RISE_M * push, dir.y * BIRD_DODGE_SHIFT_M * push)
			var cur: Vector3 = g["dodge"]
			g["dodge"] = cur + (target - cur) * k
		elif t == "deer":
			var st: String = g["state"]
			if st == "idle":
				var p: Vector3 = g["pos"]
				if Vector2(p.x, p.z).distance_to(r2) < DEER_ALERT_M:
					g["state"] = "flee"
					g["flee_at"] = now_s
			elif st == "flee" and now_s - float(g["flee_at"]) >= DEER_FLEE_S:
				g["state"] = "gone"


## Position du `i`-ième oiseau de la bande `g` à l'instant `now_s`.
static func bird_position(g: Dictionary, i: int, now_s: float) -> Vector3:
	var m: Dictionary = g["members"][i]
	var a := float(m["angle"]) + float(m["omega"]) * now_s
	var r := float(m["r"]) * (1.0 + 0.08 * sin(0.37 * now_s + float(m["phase"])))
	var c: Vector3 = g["center"]
	var dodge: Vector3 = g.get("dodge", Vector3.ZERO)
	return c + dodge + Vector3(cos(a) * r, float(m["h"]) + BIRD_WAVE_M * sin(0.9 * now_s + float(m["phase"])), sin(a) * r)


## Cap de vol (rad, autour de y) du `i`-ième oiseau : tangent au cercle.
static func bird_yaw(g: Dictionary, i: int, now_s: float) -> float:
	var m: Dictionary = g["members"][i]
	var a := float(m["angle"]) + float(m["omega"]) * now_s
	return -a


## Cap d'une bête du troupeau à l'instant `now_s` (oscillation lente autour de son cap initial).
static func herd_yaw(member: Dictionary, now_s: float) -> float:
	var y0 := float(member["yaw"])
	return y0 + HERD_YAW_SWING * sin(TAU * now_s / HERD_YAW_PERIOD_S + y0 * 3.0)


## Position du chevreuil (son site tant qu'il ne fuit pas) ; `gone` : il a disparu.
static func deer_position(g: Dictionary, now_s: float) -> Vector3:
	var p: Vector3 = g["pos"]
	if str(g.get("state", "idle")) == "idle":
		return p
	var t := clampf(now_s - float(g["flee_at"]), 0.0, DEER_FLEE_S)
	return p + (g["flee_dir"] as Vector3) * DEER_SPEED_MPS * t


## Visibilité du chevreuil : 1 au repos, s'efface pendant la dernière seconde de fuite, 0 ensuite.
static func deer_alpha(g: Dictionary, now_s: float) -> float:
	match str(g.get("state", "idle")):
		"idle":
			return 1.0
		"gone":
			return 0.0
	return clampf(DEER_FLEE_S - (now_s - float(g["flee_at"])), 0.0, 1.0)
