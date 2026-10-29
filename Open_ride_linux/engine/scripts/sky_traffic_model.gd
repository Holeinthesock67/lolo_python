extends RefCounted

## Engins du ciel (Lot P26), sans nœud ni effet sur la physique. Pas de class_name : charger par
## preload("res://scripts/sky_traffic_model.gd").
##
## Tout est tiré de la graine et de l'horloge du modèle (figée en pause) :
## - avions de ligne : une case d'horaire tous les AIRLINER_SLOT_S, un vol sur AIRLINER_RATE, cap, écart à la
##   caméra, altitude et traînée (sur CONTRAIL_SHARE des vols) tirés ; le vol traverse le ciel en ligne
##   droite à AIRLINER_MPS, à 8,5 à 11 km au-dessus de la caméra. Il est placé par homothétie autour de la
##   caméra à RENDER_M au plus (même image à l'écran, dans la distance de vue) ; pas d'avion sous une
##   couverture nuageuse du thème de plus d'AIRLINER_MAX_COVERAGE.
## - hélicoptère : une case tous les HELI_SLOT_S, un passage sur HELI_RATE, en ligne droite à HELI_MPS et à
##   HELI_AGL_M au-dessus de la caméra, au plus près de 150 à 700 m d'elle ; rotor qui tourne.
## - parapentes : au-dessus des montées du parcours (climb_detector.gd ou couche `segments`) de
##   PARA_MIN_GAIN_M au moins, selon le biome (BIOME_SKY) : 1 à 6 voiles qui tournent dans une ascendance à côté
##   du sommet, visibles à moins de PARA_RANGE_M ; pas au-delà de PARA_MAX_WIND de vent.
## - montgolfières : une case tous les BALLOON_SLOT_S, un envol (chance du biome) de 1 à 3 ballons, à 0,9 à
##   2,5 km de la caméra ; chacun monte, dérive avec le vent pendant deux cases, puis se pose ; brûleur
##   allumé 3 s toutes les 20 s ; seulement par vent faible (BALLOON_MAX_WIND).
## - paramoteurs (lot P31) : une case tous les PARAMOTOR_SLOT_S, un passage seul ou en duo, en ligne droite
##   qui louvoie à PARAMOTOR_MPS, à PARAMOTOR_AGL_M au-dessus de la caméra, au plus près de 100 à 500 m
##   d'elle : les voiles des pays plats ; pas au-delà de PARAMOTOR_MAX_WIND de vent.
## Lot P31 : le biome (`biome_model`, biome_model.gd actif, sinon le biome par défaut) règle, d'après
## BIOME_SKY, la part des montées qui portent des parapentes et leur nombre (au sommet de la montée), la
## chance d'un envol de montgolfières et d'un passage de paramoteur (à la place de la caméra au début de la
## case) ; chaque montgolfière prend un motif d'enveloppe (`style`, sky_mesh.gd BALLOON_STYLES).
## Rien ne vole sous la pluie (NO_FLY_RAIN) ni dans la brume (NO_FLY_FOG). Un vol est accroché à la place
## de la caméra la première fois qu'il est calculé. `update` garde au plus `budget` engins
## (`living(preset).aircraft`) : hélicoptère, montgolfières, avions, paramoteurs puis parapentes, les plus
## proches d'abord, et remplit `craft` : {id, kind, color, style, xform, contrail_m, rotor, lights, dist}.

const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const TrafficModel := preload("res://scripts/traffic_model.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const BiomeIds := preload("res://scripts/biome_ids.gd")
const FaunaPlacer := preload("res://scripts/fauna_placer.gd")
const SkyMesh := preload("res://scripts/sky_mesh.gd")

const RENDER_M := 2500.0
const PRIORITY := {"helicopter": 0, "balloon": 1, "airliner": 2, "paramotor": 3, "paraglider": 4}
const MAX_AT_ONCE := {"airliner": 4, "helicopter": 2, "paraglider": 8, "paramotor": 2, "balloon": 3}   # nœuds de sky_traffic_renderer.gd
const NO_FLY_RAIN := 0.1
const NO_FLY_FOG := 0.5
const STROBE_PERIOD_S := 1.2
const STROBE_ON_S := 0.1

const AIRLINER_SLOT_S := 75.0
const AIRLINER_RATE := 0.55
const AIRLINER_ALT_M := Vector2(8500.0, 11000.0)
const AIRLINER_MPS := 230.0
const AIRLINER_HALF_PATH_M := 40000.0
const AIRLINER_OFFSET_M := 15000.0
const AIRLINER_MAX_COVERAGE := 0.6
const CONTRAIL_SHARE := 0.75
const CONTRAIL_M := Vector2(2500.0, 9000.0)

const HELI_SLOT_S := 240.0
const HELI_RATE := 0.3
const HELI_AGL_M := Vector2(120.0, 250.0)
const HELI_MPS := 55.0
const HELI_HALF_PATH_M := 3000.0
const HELI_PASS_M := Vector2(150.0, 700.0)
const ROTOR_HZ := 5.5

const PARA_MIN_GAIN_M := 80.0
const PARA_MIN_COUNT := 1
const PARA_SIDE_M := Vector2(250.0, 600.0)
const PARA_ABOVE_M := Vector2(120.0, 400.0)
const PARA_RADIUS_M := Vector2(35.0, 70.0)
const PARA_MPS := 9.0
const PARA_BOB_M := 15.0
const PARA_BOB_S := 120.0
const PARA_BANK_RAD := 0.35
const PARA_RANGE_M := 5000.0
const PARA_MAX_WIND := 0.6

const BALLOON_SLOT_S := 900.0
const BALLOON_COUNT := Vector2i(1, 3)
const BALLOON_DIST_M := Vector2(900.0, 2500.0)
const BALLOON_ABOVE_M := Vector2(250.0, 800.0)
const BALLOON_CLIMB_S := 120.0
const BALLOON_DRIFT_MPS := 3.0
const BALLOON_MAX_WIND := 0.35
const BALLOON_BURN_PERIOD_S := 20.0
const BALLOON_BURN_S := 3.0
const PARAMOTOR_SLOT_S := 300.0
const PARAMOTOR_MPS := 11.0
const PARAMOTOR_HALF_PATH_M := 1500.0
const PARAMOTOR_AGL_M := Vector2(60.0, 250.0)
const PARAMOTOR_PASS_M := Vector2(100.0, 500.0)
const PARAMOTOR_WEAVE_M := 60.0
const PARAMOTOR_WEAVE_S := 40.0
const PARAMOTOR_BANK_RAD := 0.3
const PARAMOTOR_PAIR := 0.3                       # part des passages en duo
const PARAMOTOR_WINGMAN := Vector3(25.0, 12.0, 40.0)   # place du second : à droite, au-dessus, derrière
const PARAMOTOR_MAX_WIND := 0.5

## Ciel de chaque biome (lot P31) : part des montées assez hautes qui portent des parapentes (`para`) et
## nombre de voiles au plus par montée (`para_max`) ; chance par case d'un envol de montgolfières
## (`balloon`) et d'un passage de paramoteur (`paramotor`). Montagnes, volcans et côtes : beaucoup de voiles ;
## savane, volcans (Cappadoce) et campagnes : montgolfières ; plaines, déserts et côtes : paramoteurs ;
## rien dans le ciel polaire. Sans couche biome, le biome par défaut garde les chances d'avant P31.
const BIOME_SKY := {
	"temperate_grassland": {"para": 0.6, "para_max": 4, "balloon": 0.6, "paramotor": 0.35},
	"temperate_forest": {"para": 0.6, "para_max": 4, "balloon": 0.4, "paramotor": 0.15},
	"farmland": {"para": 0.5, "para_max": 3, "balloon": 0.7, "paramotor": 0.45},
	"boreal_forest": {"para": 0.4, "para_max": 3, "balloon": 0.25, "paramotor": 0.1},
	"alpine": {"para": 1.0, "para_max": 6, "balloon": 0.3, "paramotor": 0.0},
	"tundra": {"para": 0.3, "para_max": 2, "balloon": 0.1, "paramotor": 0.05},
	"polar": {"para": 0.0, "para_max": 1, "balloon": 0.0, "paramotor": 0.0},
	"mediterranean": {"para": 0.85, "para_max": 5, "balloon": 0.4, "paramotor": 0.25},
	"steppe": {"para": 0.5, "para_max": 3, "balloon": 0.5, "paramotor": 0.35},
	"savanna": {"para": 0.4, "para_max": 3, "balloon": 0.85, "paramotor": 0.2},
	"sand_desert": {"para": 0.5, "para_max": 3, "balloon": 0.6, "paramotor": 0.45},
	"rock_desert": {"para": 0.6, "para_max": 4, "balloon": 0.7, "paramotor": 0.3},
	"jungle": {"para": 0.2, "para_max": 2, "balloon": 0.1, "paramotor": 0.05},
	"wetland": {"para": 0.0, "para_max": 1, "balloon": 0.35, "paramotor": 0.3},
	"coast": {"para": 0.9, "para_max": 5, "balloon": 0.35, "paramotor": 0.4},
	"volcanic": {"para": 0.9, "para_max": 5, "balloon": 0.9, "paramotor": 0.1},
}

const CAMERA_EYE_M := 1.4          # hauteur de la caméra au-dessus du sol (sol des montgolfières)

var budget: int = 0
var seed: int = 0
var clock_s := 0.0
var coverage := 0.0
var craft: Array = []
var paragliders: Array = []        # {id, centre, radius, phase, dir, color}
var biome_model = null             # biome_model.gd actif, ou null : biome par défaut (lot P31)
var _anchors: Dictionary = {}      # clé du vol -> Vector3 (caméra au premier calcul)
var _anchor_sky: Dictionary = {}   # clé du vol -> ciel du biome à la place de la caméra (BIOME_SKY)


static func _u(h: int) -> float:
	return TrafficModel._u(h)


func _h(k: int, salt: int, i: int = 0) -> float:
	return _u(VegetationPlacer.hash3(seed ^ salt, k, i))


## Ciel du biome au point `pos` (BIOME_SKY) : biome tiré selon les poids de `biome_model` (`u` de 0 à 1).
func sky_at(pos: Vector3, u: float) -> Dictionary:
	var biome := BiomeIds.DEFAULT_BIOME
	if biome_model != null:
		biome = FaunaPlacer._pick_biome(biome_model.weights_at(pos.x, pos.z), u)
	return BIOME_SKY.get(biome, BIOME_SKY[BiomeIds.DEFAULT_BIOME])


## `theme` fusionné (couverture nuageuse), `climbs` : montées {summit_s, gain_m} du parcours ; poser
## `biome_model` avant (lot P31).
func configure(route, theme: Dictionary, climbs: Array, aircraft_budget: int, rng_seed: int = 0) -> void:
	budget = maxi(0, aircraft_budget)
	seed = rng_seed
	coverage = float(ThemeRenderParams.cloud_params(theme)["coverage"])
	clock_s = 0.0
	craft.clear()
	_anchors.clear()
	_anchor_sky.clear()
	paragliders.clear()
	if route == null:
		return
	for i in range(climbs.size()):
		var c: Dictionary = climbs[i]
		if float(c.get("gain_m", 0.0)) < PARA_MIN_GAIN_M:
			continue
		var s := float(c.get("summit_s", 0.0))
		var top: Vector3 = route.sample_point(s)
		var sky := sky_at(top, _h(i, 0x9A49))
		if _h(i, 0x9A4A) >= float(sky["para"]):
			continue
		var hd := deg_to_rad(float(route.sample(s)["heading_deg"]))
		var right := Vector3(cos(hd), 0.0, sin(hd))
		var side := 1.0 if _h(i, 0x9A4B) < 0.5 else -1.0
		var centre := top + right * side * lerpf(PARA_SIDE_M.x, PARA_SIDE_M.y, _h(i, 0x9A4C))
		var most := maxi(PARA_MIN_COUNT, int(sky["para_max"]))
		var n := PARA_MIN_COUNT + int(_h(i, 0x9A4D) * (most - PARA_MIN_COUNT + 1))
		for j in range(mini(n, most)):
			paragliders.append({
				"id": "p%d_%d" % [i, j],
				"centre": centre + Vector3(0.0, lerpf(PARA_ABOVE_M.x, PARA_ABOVE_M.y, _h(i, 0x9B00, j)), 0.0),
				"radius": lerpf(PARA_RADIUS_M.x, PARA_RADIUS_M.y, _h(i, 0x9B01, j)),
				"phase": TAU * _h(i, 0x9B02, j),
				"dir": 1.0 if _h(i, 0x9B03, j) < 0.5 else -1.0,
				"color": int(_h(i, 0x9B04, j) * 16.0),
			})


func set_budget(n: int) -> void:
	budget = maxi(0, n)


## Place affichée d'un engin réel en `real` (cap `basis`) : homothétie autour de la caméra à RENDER_M au plus.
static func far_transform(cam_pos: Vector3, real: Vector3, basis: Basis) -> Transform3D:
	var d := real - cam_pos
	var k := minf(1.0, RENDER_M / maxf(d.length(), 1.0))
	return Transform3D(basis.scaled(Vector3.ONE * k), cam_pos + d * k)


static func _yaw(fwd: Vector3) -> Basis:
	return Basis(Vector3.UP, atan2(-fwd.x, -fwd.z))


func _anchor(key: String, cam_pos: Vector3) -> Vector3:
	if not _anchors.has(key):
		_anchors[key] = cam_pos
	return _anchors[key]


## Ciel du biome à la place de la caméra au début du vol `key` (lot P31), gardé jusqu'à la fin du vol.
func _sky_of(key: String, cam_pos: Vector3) -> Dictionary:
	if not _anchor_sky.has(key):
		_anchor_sky[key] = sky_at(_anchor(key, cam_pos), _u(VegetationPlacer.hash_string(key) ^ seed))
	return _anchor_sky[key]


func _strobe(phase: float) -> float:
	return 1.0 if fposmod(clock_s + phase, STROBE_PERIOD_S) < STROBE_ON_S else 0.0


func update(cam_pos: Vector3, dt_s: float, wind_eval: Dictionary, weather_eval: Dictionary, paused: bool = false) -> void:
	if not paused:
		clock_s += dt_s
	var out := []
	var fly := float(weather_eval.get("rain", 0.0)) < NO_FLY_RAIN and float(weather_eval.get("fog_boost", 0.0)) < NO_FLY_FOG
	var wind := float(wind_eval.get("strength", 0.0))
	if fly and coverage <= AIRLINER_MAX_COVERAGE:
		_airliners(cam_pos, out)
	if fly:
		_helicopter(cam_pos, out)
	if fly and wind <= PARA_MAX_WIND:
		_paragliders(cam_pos, out)
	if fly and wind <= PARAMOTOR_MAX_WIND:
		_paramotors(cam_pos, out)
	if fly and wind <= BALLOON_MAX_WIND:
		_balloons(cam_pos, wind_eval, out)
	out.sort_custom(func(a, b):
		var pa: int = PRIORITY[a["kind"]]
		var pb: int = PRIORITY[b["kind"]]
		return pa < pb if pa != pb else float(a["dist"]) < float(b["dist"]))
	craft = []
	var per := {}
	for c in out:
		if craft.size() >= budget:
			break
		var n: int = per.get(c["kind"], 0)
		if n < MAX_AT_ONCE[c["kind"]]:
			per[c["kind"]] = n + 1
			craft.append(c)
	# Vols terminés oubliés
	for key in _anchors.keys():
		var parts: PackedStringArray = (key as String).split(":")
		var slot_s: float = {"a": AIRLINER_SLOT_S, "h": HELI_SLOT_S, "b": BALLOON_SLOT_S, "m": PARAMOTOR_SLOT_S}[parts[0]]
		var life: float = {"a": 2.0 * AIRLINER_HALF_PATH_M / AIRLINER_MPS + AIRLINER_SLOT_S, "h": HELI_SLOT_S,
			"b": 2.0 * BALLOON_SLOT_S, "m": PARAMOTOR_SLOT_S}[parts[0]]
		if float(parts[1]) * slot_s + life < clock_s - 1.0:
			_anchors.erase(key)
			_anchor_sky.erase(key)


func _airliners(cam_pos: Vector3, out: Array) -> void:
	var dur := 2.0 * AIRLINER_HALF_PATH_M / AIRLINER_MPS
	var k1 := int(floor(clock_s / AIRLINER_SLOT_S))
	for k in range(maxi(0, k1 - int(ceil(dur / AIRLINER_SLOT_S)) - 1), k1 + 1):
		if _h(k, 0xA1) >= AIRLINER_RATE:
			continue
		var t0 := k * AIRLINER_SLOT_S + AIRLINER_SLOT_S * _h(k, 0xA2)
		var t := clock_s - t0
		if t < 0.0 or t > dur:
			continue
		var a := _anchor("a:%d" % k, cam_pos)
		var hd := TAU * _h(k, 0xA3)
		var fwd := Vector3(sin(hd), 0.0, -cos(hd))
		var right := Vector3(cos(hd), 0.0, sin(hd))
		var real := a + right * lerpf(-AIRLINER_OFFSET_M, AIRLINER_OFFSET_M, _h(k, 0xA4)) \
			+ fwd * (-AIRLINER_HALF_PATH_M + AIRLINER_MPS * t) + Vector3.UP * lerpf(AIRLINER_ALT_M.x, AIRLINER_ALT_M.y, _h(k, 0xA5))
		var trail := 0.0
		if _h(k, 0xA6) < CONTRAIL_SHARE:
			trail = minf(lerpf(CONTRAIL_M.x, CONTRAIL_M.y, _h(k, 0xA7)), AIRLINER_MPS * t)
		out.append({"id": "a%d" % k, "kind": "airliner", "color": int(_h(k, 0xA8) * 16.0), "style": 0,
			"xform": far_transform(cam_pos, real, _yaw(fwd)), "contrail_m": trail, "rotor": 0.0,
			"lights": _strobe(_h(k, 0xA9)), "dist": real.distance_to(cam_pos)})


func _helicopter(cam_pos: Vector3, out: Array) -> void:
	var dur := 2.0 * HELI_HALF_PATH_M / HELI_MPS
	var k := int(floor(clock_s / HELI_SLOT_S))
	for kk: int in [k - 1, k]:
		if kk < 0 or _h(kk, 0xB1) >= HELI_RATE:
			continue
		var t0 := kk * HELI_SLOT_S + (HELI_SLOT_S - dur) * _h(kk, 0xB2)
		var t := clock_s - t0
		if t < 0.0 or t > dur:
			continue
		var a := _anchor("h:%d" % kk, cam_pos)
		var hd := TAU * _h(kk, 0xB3)
		var fwd := Vector3(sin(hd), 0.0, -cos(hd))
		var right := Vector3(cos(hd), 0.0, sin(hd))
		var side := 1.0 if _h(kk, 0xB4) < 0.5 else -1.0
		var real := a + right * side * lerpf(HELI_PASS_M.x, HELI_PASS_M.y, _h(kk, 0xB5)) \
			+ fwd * (-HELI_HALF_PATH_M + HELI_MPS * t) + Vector3.UP * lerpf(HELI_AGL_M.x, HELI_AGL_M.y, _h(kk, 0xB6))
		out.append({"id": "h%d" % kk, "kind": "helicopter", "color": int(_h(kk, 0xB7) * 16.0), "style": 0,
			"xform": Transform3D(_yaw(fwd) * Basis(Vector3.RIGHT, -0.08), real), "contrail_m": 0.0,
			"rotor": fposmod(clock_s * TAU * ROTOR_HZ, TAU), "lights": _strobe(_h(kk, 0xB8)),
			"dist": real.distance_to(cam_pos)})


func _paragliders(cam_pos: Vector3, out: Array) -> void:
	for p in paragliders:
		var centre: Vector3 = p["centre"]
		if Vector2(centre.x - cam_pos.x, centre.z - cam_pos.z).length() > PARA_RANGE_M:
			continue
		var r: float = p["radius"]
		var dir: float = p["dir"]
		var ang: float = float(p["phase"]) + dir * clock_s * PARA_MPS / r
		var pos := centre + Vector3(cos(ang), 0.0, sin(ang)) * r \
			+ Vector3.UP * PARA_BOB_M * sin(TAU * clock_s / PARA_BOB_S + float(p["phase"]))
		var fwd := Vector3(-sin(ang), 0.0, cos(ang)) * dir
		out.append({"id": p["id"], "kind": "paraglider", "color": p["color"], "style": 0,
			"xform": Transform3D(_yaw(fwd) * Basis(Vector3.FORWARD, dir * PARA_BANK_RAD), pos), "contrail_m": 0.0,
			"rotor": 0.0, "lights": 0.0, "dist": pos.distance_to(cam_pos)})


func _balloons(cam_pos: Vector3, wind_eval: Dictionary, out: Array) -> void:
	var k1 := int(floor(clock_s / BALLOON_SLOT_S))
	var wdir: Vector3 = wind_eval.get("dir", Vector3.ZERO)
	var drift := wdir * BALLOON_DRIFT_MPS * (0.5 + float(wind_eval.get("strength", 0.0)))
	var life := 2.0 * BALLOON_SLOT_S
	for k: int in [k1 - 1, k1]:
		if k < 0:
			continue
		var key := "b:%d" % k
		if _h(k, 0xC1) >= float(_sky_of(key, cam_pos)["balloon"]):
			continue
		var t := clock_s - k * BALLOON_SLOT_S
		var a := _anchor(key, cam_pos)
		var n := BALLOON_COUNT.x + int(_h(k, 0xC2) * (BALLOON_COUNT.y - BALLOON_COUNT.x + 1))
		for j in range(mini(n, BALLOON_COUNT.y)):
			var ang := TAU * _h(k, 0xC3, j)
			var base := a + Vector3(cos(ang), 0.0, sin(ang)) * lerpf(BALLOON_DIST_M.x, BALLOON_DIST_M.y, _h(k, 0xC4, j))
			var above := lerpf(BALLOON_ABOVE_M.x, BALLOON_ABOVE_M.y, _h(k, 0xC5, j))
			var h := above * smoothstep(0.0, BALLOON_CLIMB_S, t) * (1.0 - smoothstep(life - BALLOON_CLIMB_S, life, t))
			var pos := base + drift * t + Vector3.UP * (h - CAMERA_EYE_M)
			var burn := 1.0 if fposmod(t + BALLOON_BURN_PERIOD_S * _h(k, 0xC6, j), BALLOON_BURN_PERIOD_S) < BALLOON_BURN_S else 0.0
			out.append({"id": "b%d_%d" % [k, j], "kind": "balloon", "color": int(_h(k, 0xC7, j) * 16.0),
				"style": int(_h(k, 0xC8, j) * SkyMesh.BALLOON_STYLES.size()),
				"xform": Transform3D(Basis(Vector3.UP, ang), pos), "contrail_m": 0.0, "rotor": 0.0, "lights": burn,
				"dist": pos.distance_to(cam_pos)})


func _paramotors(cam_pos: Vector3, out: Array) -> void:
	var dur := 2.0 * PARAMOTOR_HALF_PATH_M / PARAMOTOR_MPS
	var k := int(floor(clock_s / PARAMOTOR_SLOT_S))
	for kk: int in [k - 1, k]:
		if kk < 0:
			continue
		var key := "m:%d" % kk
		if _h(kk, 0xD1) >= float(_sky_of(key, cam_pos)["paramotor"]):
			continue
		var t0 := kk * PARAMOTOR_SLOT_S + (PARAMOTOR_SLOT_S - dur) * _h(kk, 0xD2)
		var t := clock_s - t0
		if t < 0.0 or t > dur:
			continue
		var a := _anchor(key, cam_pos)
		var hd := TAU * _h(kk, 0xD3)
		var fwd := Vector3(sin(hd), 0.0, -cos(hd))
		var right := Vector3(cos(hd), 0.0, sin(hd))
		var side := 1.0 if _h(kk, 0xD4) < 0.5 else -1.0
		# Louvoiement : écart latéral en sinus ; le cap suit la pente de la courbe, l'inclinaison son virage
		# (vers la droite quand l'écart latéral se creuse vers la droite)
		var ph := TAU / PARAMOTOR_WEAVE_S * t + TAU * _h(kk, 0xD5)
		var lateral := PARAMOTOR_WEAVE_M * sin(ph)
		var slope := PARAMOTOR_WEAVE_M * TAU / PARAMOTOR_WEAVE_S * cos(ph) / PARAMOTOR_MPS
		var lead := a + right * (side * lerpf(PARAMOTOR_PASS_M.x, PARAMOTOR_PASS_M.y, _h(kk, 0xD6)) + lateral) \
			+ fwd * (-PARAMOTOR_HALF_PATH_M + PARAMOTOR_MPS * t) + Vector3.UP * lerpf(PARAMOTOR_AGL_M.x, PARAMOTOR_AGL_M.y, _h(kk, 0xD7))
		var basis := _yaw((fwd + right * slope).normalized()) * Basis(Vector3.FORWARD, -sin(ph) * PARAMOTOR_BANK_RAD)
		var n := 2 if _h(kk, 0xD8) < PARAMOTOR_PAIR else 1
		for j in range(n):
			var pos := lead if j == 0 else lead + basis * PARAMOTOR_WINGMAN
			out.append({"id": "m%d_%d" % [kk, j], "kind": "paramotor", "color": int(_h(kk, 0xD9, j) * 16.0), "style": 0,
				"xform": Transform3D(basis, pos), "contrail_m": 0.0, "rotor": 0.0, "lights": 0.0,
				"dist": pos.distance_to(cam_pos)})


func count(kind: String) -> int:
	var n := 0
	for c in craft:
		if c["kind"] == kind:
			n += 1
	return n
