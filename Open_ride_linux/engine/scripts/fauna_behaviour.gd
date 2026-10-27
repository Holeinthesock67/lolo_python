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
## - Rapace (Lot P23) : il plane en cercle lent, ailes tendues ; quand le cycliste est à moins de
##   RAPTOR_CRY_M, il crie une fois par période de RAPTOR_CRY_PERIOD_S (événement `raptor_cry`).
## - Volée en V (Lot P23) : elle file en ligne droite à `speed_mps` le long de sa trajectoire de `span_m`,
##   qu'elle reprend au début une fois au bout ; elle rétrécit jusqu'à rien sur les VEE_FADE_M des deux bouts.
## - Corneilles (Lot P23) : posées au sol (`idle`) ; dès que le cycliste est à moins de CROW_ALERT_M du
##   groupe, elles s'envolent l'une après l'autre (CROW_STAGGER_S d'écart, événement `crow_caw`), montent à
##   CROW_FLIGHT_H_M et se reposent en CROW_FLIGHT_S à leur point `land`, plus loin de la route (`landed`).
## `events` : sons à jouer, rendus par le dernier `update`, `[{sound, pos}]`.
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
const RAPTOR_CRY_M := 250.0
const RAPTOR_CRY_PERIOD_S := 30.0
const VEE_FADE_M := 150.0
const VEE_WAVE_M := 1.0
const CROW_ALERT_M := 35.0
const CROW_STAGGER_S := 0.12
const CROW_FLIGHT_S := 5.0
const CROW_FLIGHT_H_M := 14.0
const CROW_YAW_SWING := 0.8
const CROW_YAW_PERIOD_S := 7.0

var groups: Array = []
var events: Array = []
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
			"crows":
				if not g.has("state"):
					g["state"] = "idle"
					g["flight_at"] = NAN
			"raptor":
				if not g.has("cry_slot"):
					g["cry_slot"] = -1


## Une fois par image : réactions au cycliste en `rider_pos` à l'instant `now_s`.
func update(rider_pos: Vector3, now_s: float) -> void:
	var dt := 0.0 if is_nan(_last_s) else clampf(now_s - _last_s, 0.0, 0.5)
	_last_s = now_s
	var k := 1.0 - exp(-dt / BIRD_DODGE_TAU_S)
	var r2 := Vector2(rider_pos.x, rider_pos.z)
	events.clear()
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
		elif t == "crows":
			var st: String = g["state"]
			if st == "idle":
				var p: Vector3 = g["pos"]
				if Vector2(p.x, p.z).distance_to(r2) < CROW_ALERT_M:
					g["state"] = "flight"
					g["flight_at"] = now_s
					events.append({"sound": "crow_caw", "pos": p})
			elif st == "flight" and now_s - float(g["flight_at"]) >= CROW_FLIGHT_S + CROW_STAGGER_S * ((g["members"] as Array).size() - 1):
				g["state"] = "landed"
		elif t == "raptor":
			# Une période de cri par rapace (décalée par son angle de départ) ; le premier passage ne fait que
			# prendre la période en cours, pour qu'aucun rapace ne crie dès son chargement.
			var slot := int(floor((now_s + float(g["angle"]) * RAPTOR_CRY_PERIOD_S / TAU) / RAPTOR_CRY_PERIOD_S))
			var prev: int = g["cry_slot"]
			g["cry_slot"] = slot
			if prev >= 0 and slot != prev:
				var c: Vector3 = g["center"]
				if Vector2(c.x, c.z).distance_to(r2) < RAPTOR_CRY_M:
					events.append({"sound": "raptor_cry", "pos": raptor_position(g, now_s)})


## Transformée du `i`-ième oiseau de la bande `g` à l'instant `now_s` (position et cap calculés ensemble,
## comme bird_position et bird_yaw, pour la mise à jour par image).
static func bird_transform(g: Dictionary, i: int, now_s: float) -> Transform3D:
	var m: Dictionary = g["members"][i]
	var ph: float = m["phase"]
	var a: float = m["angle"] + m["omega"] * now_s
	var r: float = m["r"] * (1.0 + 0.08 * sin(0.37 * now_s + ph))
	var c: Vector3 = g["center"] + g["dodge"]
	return Transform3D(Basis(Vector3.UP, -a), c + Vector3(cos(a) * r, m["h"] + BIRD_WAVE_M * sin(0.9 * now_s + ph), sin(a) * r))


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


## Position du rapace à l'instant `now_s` : cercle de `radius_m`, légère houle de ± 2 m.
static func raptor_position(g: Dictionary, now_s: float) -> Vector3:
	var a := float(g["angle"]) + float(g["omega"]) * now_s
	var r := float(g["radius_m"])
	var c: Vector3 = g["center"]
	return c + Vector3(cos(a) * r, 2.0 * sin(0.3 * now_s + float(g["angle"])), sin(a) * r)


## Cap du rapace : tangent au cercle, dans le sens de rotation (`omega` négatif : sens inverse).
static func raptor_yaw(g: Dictionary, now_s: float) -> float:
	var a := float(g["angle"]) + float(g["omega"]) * now_s
	return -a if float(g["omega"]) >= 0.0 else PI - a


## Avancée de la volée sur sa trajectoire, de `-span_m / 2` à `span_m / 2` (0 au-dessus de `origin`).
static func vee_along(g: Dictionary, now_s: float) -> float:
	var span := float(g["span_m"])
	return fposmod(float(g["phase_m"]) + float(g["speed_mps"]) * now_s, span) - span * 0.5


## Position du `i`-ième oiseau de la volée : la tête devant, les autres en arrière et de côté.
static func vee_position(g: Dictionary, i: int, now_s: float) -> Vector3:
	var m: Dictionary = g["members"][i]
	var d: Vector3 = g["dir"]
	var side := Vector3(d.z, 0.0, -d.x)
	var o: Vector3 = g["origin"]
	return o + d * (vee_along(g, now_s) - float(m["back"])) + side * float(m["side"]) \
		+ Vector3(0.0, VEE_WAVE_M * sin(0.8 * now_s + float(i)), 0.0)


static func vee_yaw(g: Dictionary) -> float:
	var d: Vector3 = g["dir"]
	return atan2(d.x, d.z)


## Taille de la volée (0 à 1) : elle rétrécit sur les VEE_FADE_M des deux bouts de sa trajectoire.
static func vee_scale(g: Dictionary, now_s: float) -> float:
	return clampf((float(g["span_m"]) * 0.5 - absf(vee_along(g, now_s))) / VEE_FADE_M, 0.0, 1.0)


## Avancée du vol de la `i`-ième corneille, de 0 (au sol, au départ) à 1 (reposée à `land`).
static func crow_flight(g: Dictionary, i: int, now_s: float) -> float:
	match str(g.get("state", "idle")):
		"idle":
			return 0.0
		"landed":
			return 1.0
	return clampf((now_s - float(g["flight_at"]) - CROW_STAGGER_S * i) / CROW_FLIGHT_S, 0.0, 1.0)


## Vrai pendant le vol de la `i`-ième corneille (ailes qui battent).
static func crow_flying(g: Dictionary, i: int, now_s: float) -> bool:
	var u := crow_flight(g, i, now_s)
	return u > 0.0 and u < 1.0


static func crow_position(g: Dictionary, i: int, now_s: float) -> Vector3:
	var m: Dictionary = g["members"][i]
	var u := crow_flight(g, i, now_s)
	var p: Vector3 = (m["pos"] as Vector3).lerp(m["land"], smoothstep(0.0, 1.0, u))
	return p + Vector3(0.0, CROW_FLIGHT_H_M * sin(PI * u), 0.0)


## Cap de la `i`-ième corneille : vers `away` en vol, sinon elle tourne sur place en picorant.
static func crow_yaw(g: Dictionary, i: int, now_s: float) -> float:
	if crow_flying(g, i, now_s):
		var a: Vector3 = g["away"]
		return atan2(a.x, a.z)
	var y0 := float(g["members"][i]["yaw"])
	return y0 + CROW_YAW_SWING * sin(TAU * now_s / CROW_YAW_PERIOD_S + y0 * 5.0)
