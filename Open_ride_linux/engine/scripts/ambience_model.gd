extends RefCounted

## Fonds sonores d'ambiance selon le décor (Lot P9, thème 1.2 `ambience`), sans aucun nœud.
## Pas de class_name : charger par preload("res://scripts/ambience_model.gd"). Joué par sound_player.gd ;
## le voisinage et l'heure sont fournis par P16 (main.gd).
##
## - `describe(rider_xz, forests, buildings, waters, radius_m)` : voisinage dans un rayon de 150 m à
##   partir des couches chargées (polygones de forêt et de bâtiments en x, z ; eaux `{kind, points, area}`) :
##   `{forest_share, built_share, water_dist_m, water_kind}`.
## - `evaluate(neigh, now_s)` : volume (dB) de chaque fond de `BEDS`. `neigh` porte aussi `alt_m`,
##   `solar_hour` (P7, version 2.0 ; NAN : heure locale du PC), `rain` (P8, 0 à 1), `wind_strength`
##   (P4, 0 à 1) et `paused`. Au plus `voices` fonds audibles (`living(preset).ambience_voices`) : les
##   plus forts gagnent, avec 3 dB d'avance pour un fond déjà joué (hystérésis). Fondus en dB à
##   `SLEW_DB_PER_S` (4 s de `FADE_FLOOR_DB` au niveau d'un fond), jamais plus de 3 dB en 0,5 s ; un fond
##   ne commence à monter que s'il reste une voix libre. En pause, tout descend vite au silence.
## - Oiseaux réduits la nuit (24 dB) et sous la pluie ; insectes seulement en journée.
## - `bell_strikes(prev_hour, hour)` : coups de cloche quand l'heure pleine est franchie.

const SILENCE_DB := -80.0
const FADE_FLOOR_DB := -36.0     # un fond qui démarre part d'ici (sous les autres sons)
const SLEW_DB_PER_S := 5.5       # 2,75 dB en 0,5 s
const PAUSE_SLEW_DB_PER_S := 40.0
const HYSTERESIS_DB := 3.0
const MIN_GAIN := 0.02           # gain sous lequel un fond est muet
const RADIUS_M := 150.0
const GRID := 9                  # points d'échantillonnage du voisinage par côté
const NIGHT_BIRDS_GAIN := 0.063  # −24 dB la nuit
const DEFAULT_VOICES := 4

const BEDS := ["forest_birds", "field_insects", "water_flow", "village_murmur", "high_wind", "rain"]
## Niveau de chaque fond à plein gain et volume général 1 (dB) : sous les bips du Click.
const BED_MAX_DB := {
	"forest_birds": -14.0,
	"field_insects": -18.0,
	"water_flow": -15.0,
	"village_murmur": -20.0,
	"high_wind": -16.0,
	"rain": -14.0,
}
const WATER_KIND_GAIN := {"river": 1.0, "stream": 0.8, "canal": 0.4, "lake": 0.35, "pond": 0.25}

var volume := 0.6
var birds := 0.6
var insects := 0.4
var voices := DEFAULT_VOICES

var _db := {}
var _last_s := NAN


func _init() -> void:
	reset()


func reset() -> void:
	for b in BEDS:
		_db[b] = SILENCE_DB
	_last_s = NAN


static func _is_number(v: Variant) -> bool:
	return typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT


## Lit `ambience` du thème 1.2 (`volume`, `birds`, `insects`, de 0 à 1) ; absent : valeurs par défaut.
func set_theme(theme: Dictionary) -> void:
	var a: Variant = theme.get("ambience", null) if typeof(theme) == TYPE_DICTIONARY else null
	volume = 0.6
	birds = 0.6
	insects = 0.4
	if typeof(a) != TYPE_DICTIONARY:
		return
	if _is_number(a.get("volume", null)):
		volume = clampf(float(a["volume"]), 0.0, 1.0)
	if _is_number(a.get("birds", null)):
		birds = clampf(float(a["birds"]), 0.0, 1.0)
	if _is_number(a.get("insects", null)):
		insects = clampf(float(a["insects"]), 0.0, 1.0)


## Heure locale du PC (heures décimales), quand l'heure solaire n'est pas simulée.
static func local_hour() -> float:
	var t := Time.get_datetime_dict_from_system()
	return float(t["hour"]) + float(t["minute"]) / 60.0 + float(t["second"]) / 3600.0


## Facteur de jour des oiseaux : 1 de 6 h à 20 h 30, NIGHT_BIRDS_GAIN de 22 h à 4 h 30, rampes d'1 h 30.
static func birds_day_factor(hour: float) -> float:
	var h := fposmod(hour, 24.0)
	var day := 0.0
	if h >= 6.0 and h <= 20.5:
		day = 1.0
	elif h > 4.5 and h < 6.0:
		day = smoothstep(4.5, 6.0, h)
	elif h > 20.5 and h < 22.0:
		day = 1.0 - smoothstep(20.5, 22.0, h)
	return lerpf(NIGHT_BIRDS_GAIN, 1.0, day)


## Insectes : de 9 h à 19 h, rampes de 7 h à 9 h et de 19 h à 21 h, rien la nuit.
static func insects_day_factor(hour: float) -> float:
	var h := fposmod(hour, 24.0)
	if h >= 9.0 and h <= 19.0:
		return 1.0
	if h > 7.0 and h < 9.0:
		return smoothstep(7.0, 9.0, h)
	if h > 19.0 and h < 21.0:
		return 1.0 - smoothstep(19.0, 21.0, h)
	return 0.0


static func _gain_db(gain: float, bed: String, master: float) -> float:
	var g := gain * master
	if g < MIN_GAIN:
		return SILENCE_DB
	return float(BED_MAX_DB[bed]) + 20.0 * log(g) / log(10.0)


## Volumes cibles avant la limite de voix et les fondus.
func targets(neigh: Dictionary) -> Dictionary:
	var out := {}
	var paused: bool = neigh.get("paused", false) == true
	var hour := float(neigh.get("solar_hour", NAN))
	if is_nan(hour):
		hour = local_hour()
	var forest := clampf(float(neigh.get("forest_share", 0.0)), 0.0, 1.0)
	var built := clampf(float(neigh.get("built_share", 0.0)), 0.0, 1.0)
	var rain := clampf(float(neigh.get("rain", 0.0)), 0.0, 1.0)
	var wind := clampf(float(neigh.get("wind_strength", 0.0)), 0.0, 1.0)
	var alt := float(neigh.get("alt_m", 0.0))
	var water_dist := float(neigh.get("water_dist_m", INF))
	var water_kind := str(neigh.get("water_kind", "river"))
	var gains := {
		"forest_birds": pow(forest, 0.7) * birds / 0.6 * birds_day_factor(hour) * (1.0 - 0.8 * rain),
		"field_insects": (1.0 - forest) * (1.0 - built) * insects / 0.4 * insects_day_factor(hour)
			* (1.0 - rain) * (1.0 - 0.5 * wind) * (1.0 - clampf((alt - 1800.0) / 600.0, 0.0, 1.0)),
		"water_flow": clampf(1.0 - (water_dist - 15.0) / 85.0, 0.0, 1.0) * float(WATER_KIND_GAIN.get(water_kind, 0.5)),
		"village_murmur": pow(built, 0.6) * (1.0 if birds_day_factor(hour) > 0.5 else 0.3),
		"high_wind": clampf((alt - 1200.0) / 1300.0, 0.0, 1.0) * (0.4 + 0.6 * wind),
		"rain": rain,
	}
	for b in BEDS:
		out[b] = SILENCE_DB if paused else _gain_db(minf(float(gains[b]), 1.0), b, volume)
	return out


## Volumes (dB) de chaque fond à l'instant `now_s`, fondus et limite de voix compris.
func evaluate(neigh: Dictionary, now_s: float) -> Dictionary:
	var dt := 0.0 if is_nan(_last_s) else clampf(now_s - _last_s, 0.0, 1.0)
	_last_s = now_s
	var paused: bool = neigh.get("paused", false) == true
	var tgt := targets(neigh)
	# Choix des voix : les plus forts, avec une avance pour les fonds déjà joués
	var ranked: Array = []
	for b in BEDS:
		var t: float = tgt[b]
		if t > SILENCE_DB:
			ranked.append([t + (HYSTERESIS_DB if _db[b] > SILENCE_DB else 0.0), b])
	ranked.sort_custom(func(x, y): return x[0] > y[0])
	var chosen := {}
	for i in range(mini(voices, ranked.size())):
		chosen[ranked[i][1]] = true
	var audible := 0
	for b in BEDS:
		if _db[b] > SILENCE_DB:
			audible += 1
	var rate := PAUSE_SLEW_DB_PER_S if paused else SLEW_DB_PER_S
	var step := rate * dt
	for b in BEDS:
		var cur: float = _db[b]
		var target: float = tgt[b] if chosen.has(b) else SILENCE_DB
		if cur <= SILENCE_DB:
			# Un fond muet démarre seulement s'il reste une voix libre
			if target > SILENCE_DB and audible < voices and not paused:
				_db[b] = minf(FADE_FLOOR_DB, target)
				audible += 1
			continue
		if target <= SILENCE_DB:
			var down := cur - step
			_db[b] = SILENCE_DB if down <= FADE_FLOOR_DB else down
		elif cur < target:
			_db[b] = minf(cur + step, target)
		else:
			_db[b] = maxf(cur - step, target)
	return _db.duplicate()


func audible_count() -> int:
	var n := 0
	for b in BEDS:
		if _db[b] > SILENCE_DB:
			n += 1
	return n


## Coups de cloche à sonner quand l'heure passe de `prev_hour` à `hour` (heures décimales, PC ou P7) :
## à l'heure pleine franchie, autant de coups que l'heure sur 12 (12 à midi et minuit), sinon 0.
static func bell_strikes(prev_hour: float, hour: float) -> int:
	if is_nan(prev_hour) or is_nan(hour):
		return 0
	var delta := fposmod(hour - prev_hour, 24.0)
	if delta <= 0.0 or delta > 0.5:
		return 0   # recul de l'horloge ou saut : rien
	var full: float = floorf(prev_hour) + 1.0
	if prev_hour + delta < full:
		return 0
	var h12 := int(fposmod(full, 12.0))
	return 12 if h12 == 0 else h12


static func _point_segment_dist(p: Vector2, a: Vector2, b: Vector2) -> float:
	var ab := b - a
	var len2 := ab.length_squared()
	var t := 0.0 if len2 <= 1e-9 else clampf((p - a).dot(ab) / len2, 0.0, 1.0)
	return p.distance_to(a + ab * t)


## Voisinage du cycliste à partir des couches chargées (osm_streamer.gd), en x, z.
static func describe(rider_xz: Vector2, forests: Array, buildings: Array, waters: Array,
		radius_m: float = RADIUS_M) -> Dictionary:
	var inside := 0
	var forest_n := 0
	var built_n := 0
	var cell := 2.0 * radius_m / float(GRID - 1)
	for i in range(GRID):
		for j in range(GRID):
			var off := Vector2(-radius_m + i * cell, -radius_m + j * cell)
			if off.length() > radius_m:
				continue
			inside += 1
			var p := rider_xz + off
			for poly in forests:
				if Geometry2D.is_point_in_polygon(p, poly):
					forest_n += 1
					break
			for poly in buildings:
				# Un bâtiment occupe peu de place : la case de la grille compte comme bâtie s'il est à
				# moins d'une demi-case du point.
				var hit := Geometry2D.is_point_in_polygon(p, poly)
				if not hit and poly.size() > 0 and (poly[0] as Vector2).distance_to(p) < cell * 0.5:
					hit = true
				if hit:
					built_n += 1
					break
	var best := INF
	var kind := ""
	for w in waters:
		var pts: PackedVector2Array = w.get("points", PackedVector2Array())
		if pts.size() == 0:
			continue
		if w.get("area", false) == true and pts.size() >= 3 and Geometry2D.is_point_in_polygon(rider_xz, pts):
			best = 0.0
			kind = str(w.get("kind", "lake"))
			continue
		var n := pts.size()
		var last := n if w.get("area", false) == true else n - 1
		for k in range(maxi(last, 1)):
			var d := rider_xz.distance_to(pts[0]) if n == 1 else _point_segment_dist(rider_xz, pts[k], pts[(k + 1) % n])
			if d < best:
				best = d
				kind = str(w.get("kind", "river"))
	return {
		"forest_share": float(forest_n) / float(maxi(inside, 1)),
		"built_share": float(built_n) / float(maxi(inside, 1)),
		"water_dist_m": best,
		"water_kind": kind,
	}
