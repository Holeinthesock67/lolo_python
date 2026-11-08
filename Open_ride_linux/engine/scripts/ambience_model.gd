extends RefCounted

## Fonds sonores d'ambiance selon le décor (Lot P9, thème 1.2 `ambience`), sans aucun nœud.
## Pas de class_name : charger par preload("res://scripts/ambience_model.gd"). Joué par sound_player.gd ;
## le voisinage et l'heure sont fournis par P16 (main.gd).
##
## - `describe(rider_xz, forests, buildings, waters, radius_m)` : voisinage dans un rayon de 150 m à
##   partir des couches chargées (polygones de forêt et de bâtiments en x, z ; eaux `{kind, points, area}`) :
##   `{forest_share, built_share, water_dist_m, water_kind, sea_dist_m, forest_dist_m}` (mer la plus proche :
##   lot U11 ; distance à la forêt la plus proche, 0 dedans, INF sans forêt dans le rayon : lot P19).
## - `evaluate(neigh, now_s)` : volume (dB) de chaque fond de `BEDS`. `neigh` porte aussi `alt_m`,
##   `solar_hour` (P7, version 2.0 ; NAN : heure locale du PC), `rain` (P8, 0 à 1), `wind_strength`
##   (P4, 0 à 1) et `paused`. Au plus `voices` fonds audibles (`living(preset).ambience_voices`) : les
##   plus forts gagnent, avec 3 dB d'avance pour un fond déjà joué (hystérésis). Fondus en dB à
##   `SLEW_DB_PER_S` (4 s de `FADE_FLOOR_DB` au niveau d'un fond), jamais plus de 3 dB en 0,5 s ; un fond
##   ne commence à monter que s'il reste une voix libre. En pause, tout descend vite au silence.
## - Oiseaux réduits la nuit (24 dB) et sous la pluie ; insectes seulement en journée.
## - Oiseaux par phrases (essai vélo du 2 novembre : « le bruit des oiseaux en continu est pénible ») : une
##   phrase de BIRD_PHRASE_MIN_S à BIRD_PHRASE_MAX_S par tranche de BIRD_SLOT_S, puis silence (BIRD_REST_DB),
##   fondus de BIRD_EDGE_S ; `birds_gate(t)` est déterministe (même tirage d'une partie à l'autre).
## - Saisons (lot P18) : `set_season(p)` (`season_model.params`) multiplie oiseaux et insectes par `birds` et
##   `insects` de la saison (insectes l'été seulement, oiseaux plus rares l'hiver) ; été ou sans appel : 1.
## - `bell_strikes(prev_hour, hour)` : coups de cloche quand l'heure pleine est franchie.
##
## Lot U11 (version 3.0) : dix fonds propres aux biomes (`BIOME_BEDS`), joués comme ceux de P9. `neigh` porte
## aussi `biomes` (poids de chaque biome au cycliste, biome_model.gd `weights_at` ; vide sans couche biome),
## `season` (thème `season` tant que P18 n'est pas là) et `sea_dist_m` (mer la plus proche, `describe`).
## Le gain d'un fond de biome vaut la somme, sur les biomes présents, du poids du biome multiplié par la valeur
## que ce biome déclare dans `biomes.<id>.ambience.layers` du thème (sans biome : `ambience.layers`), puis par les facteurs de saison
## (`SEASON_GAIN`), d'heure (`HOUR_PROFILE`), de pluie, de vent et, pour les vagues, de distance au rivage.
## `volume`, `birds` et `insects` du thème sont eux aussi pondérés par les biomes (`mix`) : un biome qui ne
## déclare rien prend les valeurs 1.x, d'où des volumes identiques à P9 en `temperate_grassland`.
## Tous les fonds suivent la même règle de fondu : au plus SLEW_DB_PER_S et au plus LINEAR_SLEW_PER_S du
## niveau plein par seconde (d'un biome à l'autre, il faut donc au moins 3 s pour passer du plein au silence).

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
const BIRD_SLOT_S := 9.0         # une phrase d'oiseaux par tranche de 9 s
const BIRD_PHRASE_MIN_S := 1.5
const BIRD_PHRASE_MAX_S := 3.5
const BIRD_EDGE_S := 0.3
const BIRD_REST_DB := -40.0      # entre deux phrases : 40 dB sous la phrase (le lecteur ne s'arrête pas)

const LINEAR_SLEW_PER_S := 1.0 / 3.0   # part du niveau plein gagnée ou perdue au plus en une seconde (U11)
const SEA_REACH_M := 400.0       # vagues audibles jusqu'à 400 m de la mer, pleines à 30 m (U11)
const SEA_FULL_M := 30.0

## Fonds des biomes (lot U11, selon `layers` du thème) ; BEDS : les six fonds de P9 (selon le voisinage), puis eux.
const BIOME_BEDS := ["cicadas", "jungle_chorus", "conifer_wind", "cowbells", "waves", "gulls", "frogs",
	"singing_sand", "ice_cracks", "fumaroles"]
const BEDS := ["forest_birds", "field_insects", "water_flow", "village_murmur", "high_wind", "rain",
	"cicadas", "jungle_chorus", "conifer_wind", "cowbells", "waves", "gulls", "frogs",
	"singing_sand", "ice_cracks", "fumaroles"]
## Niveau de chaque fond à plein gain et volume général 1 (dB) : sous les bips du Click.
const BED_MAX_DB := {
	"forest_birds": -14.0,
	"field_insects": -18.0,
	"water_flow": -15.0,
	"village_murmur": -20.0,
	"high_wind": -16.0,
	"rain": -14.0,
	"cicadas": -17.0,
	"jungle_chorus": -15.0,
	"conifer_wind": -17.0,
	"cowbells": -19.0,
	"waves": -13.0,
	"gulls": -18.0,
	"frogs": -17.0,
	"singing_sand": -19.0,
	"ice_cracks": -17.0,
	"fumaroles": -18.0,
}
## Facteur de saison des fonds de biome [printemps, été, automne, hiver] ; saison inconnue : 1.
const SEASONS := ["spring", "summer", "autumn", "winter"]
const SEASON_GAIN := {
	"cicadas": [0.2, 1.0, 0.3, 0.0],
	"jungle_chorus": [1.0, 1.0, 1.0, 1.0],
	"conifer_wind": [1.0, 1.0, 1.0, 1.0],
	"cowbells": [0.6, 1.0, 0.6, 0.0],   # troupeaux à l'étable l'hiver
	"waves": [1.0, 1.0, 1.0, 1.0],
	"gulls": [1.0, 1.0, 0.8, 0.6],
	"frogs": [1.0, 0.8, 0.3, 0.0],
	"singing_sand": [1.0, 1.0, 1.0, 1.0],
	"ice_cracks": [0.6, 0.3, 0.6, 1.0],
	"fumaroles": [1.0, 1.0, 1.0, 1.0],
}
## Profil horaire des fonds de biome : `day` = insects_day_factor, `light` = jour des oiseaux ramené de 0 à 1,
## `dusk` = surtout le soir et la nuit, `always` = toute la journée.
const HOUR_PROFILE := {
	"cicadas": "day", "jungle_chorus": "always", "conifer_wind": "always", "cowbells": "light", "waves": "always",
	"gulls": "light", "frogs": "dusk", "singing_sand": "always", "ice_cracks": "always", "fumaroles": "always",
}
const WATER_KIND_GAIN := {"river": 1.0, "stream": 0.8, "canal": 0.4, "lake": 0.35, "pond": 0.25}

var volume := 0.6
var birds := 0.6
var insects := 0.4
var voices := DEFAULT_VOICES
var season_birds := 1.0
var season_insects := 1.0
var _biome_ambience := {}   # biome -> {volume, birds, insects, layers} (thème 2.0, lot U11)
var _mix_key: Variant = null   # poids du dernier `mix` (cache de `targets`)
var _mix_val := {}
var _root_layers := {}      # `ambience.layers` du thème (lot U11) : repli des biomes qui n'en déclarent pas

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
## Lot U11 : `layers`, gain (0 à 1) de chaque fond de BIOME_BEDS à faire entendre ; thème 2.0 :
## `biomes.<id>.ambience` de chaque biome, mêmes clés, repli sur celles du thème.
func set_theme(theme: Dictionary) -> void:
	var a: Variant = theme.get("ambience", null) if typeof(theme) == TYPE_DICTIONARY else null
	var root := _read_ambience(a, {"volume": 0.6, "birds": 0.6, "insects": 0.4, "layers": {}})
	volume = root["volume"]
	birds = root["birds"]
	insects = root["insects"]
	_root_layers = root["layers"]
	_mix_key = null
	_mix_val = {}
	_biome_ambience = {}
	var biomes: Variant = theme.get("biomes", null) if typeof(theme) == TYPE_DICTIONARY else null
	if typeof(biomes) != TYPE_DICTIONARY:
		return
	for id in biomes:
		var entry: Variant = biomes[id]
		if typeof(entry) == TYPE_DICTIONARY:
			_biome_ambience[str(id)] = _read_ambience(entry.get("ambience", null), root)


## Clés absentes : celles de `fallback` (`layers` compris, pris en entier quand la clé manque).
static func _read_ambience(a: Variant, fallback: Dictionary) -> Dictionary:
	var out := {"volume": fallback["volume"], "birds": fallback["birds"], "insects": fallback["insects"],
		"layers": (fallback.get("layers", {}) as Dictionary).duplicate()}
	if typeof(a) != TYPE_DICTIONARY:
		return out
	for key in ["volume", "birds", "insects"]:
		if _is_number(a.get(key, null)):
			out[key] = clampf(float(a[key]), 0.0, 1.0)
	var layers: Variant = a.get("layers", null)
	if typeof(layers) == TYPE_DICTIONARY:
		out["layers"] = {}
		for bed in BIOME_BEDS:
			if _is_number(layers.get(bed, null)):
				out["layers"][bed] = clampf(float(layers[bed]), 0.0, 1.0)
	return out


## Réglages d'ambiance au point décrit par `biomes` (biome -> poids, somme 1) : `volume`, `birds`, `insects`
## pondérés, et `layers` (fond -> somme des poids × gain déclaré). Sans biome : valeurs du thème.
func mix(biomes: Variant) -> Dictionary:
	var out := {"volume": volume, "birds": birds, "insects": insects, "layers": _root_layers.duplicate()}
	if typeof(biomes) != TYPE_DICTIONARY or (biomes as Dictionary).is_empty():
		return out
	var total := 0.0
	for id in biomes:
		total += maxf(float(biomes[id]), 0.0)
	if total <= 0.0:
		return out
	for key in ["volume", "birds", "insects"]:
		out[key] = 0.0
	out["layers"] = {}
	for id in biomes:
		var w := maxf(float(biomes[id]), 0.0) / total
		var e: Dictionary = _biome_ambience.get(str(id), {"volume": volume, "birds": birds, "insects": insects, "layers": _root_layers})
		for key in ["volume", "birds", "insects"]:
			out[key] += w * float(e[key])
		for bed in e["layers"]:
			out["layers"][bed] = float(out["layers"].get(bed, 0.0)) + w * float(e["layers"][bed])
	return out


## `mix` du dernier mélange demandé : les poids ne changent qu'au recalcul du voisinage (toutes les 0,5 s).
func _mix_cached(biomes: Variant) -> Dictionary:
	if typeof(biomes) == typeof(_mix_key) and biomes == _mix_key and not _mix_val.is_empty():
		return _mix_val
	_mix_key = biomes.duplicate() if typeof(biomes) == TYPE_DICTIONARY else biomes
	_mix_val = mix(biomes)
	return _mix_val


## Facteur de saison d'un fond de biome (1 pour une saison inconnue ou vide).
static func season_factor(bed: String, season: String) -> float:
	var k := SEASONS.find(season)
	return 1.0 if k < 0 else float(SEASON_GAIN[bed][k])


## Facteur d'heure d'un fond de biome selon son profil (HOUR_PROFILE).
static func hour_factor(bed: String, hour: float) -> float:
	var light := (birds_day_factor(hour) - NIGHT_BIRDS_GAIN) / (1.0 - NIGHT_BIRDS_GAIN)
	match str(HOUR_PROFILE.get(bed, "always")):
		"day":
			return insects_day_factor(hour)
		"light":
			return light
		"dusk":
			return 0.35 + 0.65 * (1.0 - light)
	return 1.0


## Gains (0 à 1, avant le volume général) des fonds de biome, sans fondu.
func biome_gains(neigh: Dictionary, settings: Dictionary = {}) -> Dictionary:
	var m: Dictionary = settings if not settings.is_empty() else mix(neigh.get("biomes", {}))
	var hour := float(neigh.get("solar_hour", NAN))
	if is_nan(hour):
		hour = local_hour()
	var season := str(neigh.get("season", ""))
	var rain := clampf(float(neigh.get("rain", 0.0)), 0.0, 1.0)
	var wind := clampf(float(neigh.get("wind_strength", 0.0)), 0.0, 1.0)
	var sea := float(neigh.get("sea_dist_m", INF))
	var shore := clampf(1.0 - (sea - SEA_FULL_M) / (SEA_REACH_M - SEA_FULL_M), 0.0, 1.0)
	var weather := {
		"cicadas": 1.0 - rain,
		"conifer_wind": 0.35 + 0.65 * wind,
		"cowbells": 1.0 - 0.5 * rain,
		"waves": shore * (0.7 + 0.3 * wind),
		"gulls": 1.0 - 0.6 * rain,
		"singing_sand": 0.2 + 0.8 * wind,
	}
	var out := {}
	for bed in BIOME_BEDS:
		out[bed] = minf(float(m["layers"].get(bed, 0.0)) * season_factor(bed, season) * hour_factor(bed, hour)
			* float(weather.get(bed, 1.0)), 1.0)
	return out


## Facteurs de saison des oiseaux et des insectes (season_model.params) ; {} : été (aucun effet).
func set_season(p: Dictionary) -> void:
	season_birds = clampf(float(p.get("birds", 1.0)), 0.0, 1.0)
	season_insects = clampf(float(p.get("insects", 1.0)), 0.0, 1.0)


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
	var m := _mix_cached(neigh.get("biomes", {}))
	var birds_k: float = m["birds"]
	var insects_k: float = m["insects"]
	var gains := {
		"forest_birds": pow(forest, 0.7) * birds_k / 0.6 * season_birds * birds_day_factor(hour) * (1.0 - 0.8 * rain),
		"field_insects": (1.0 - forest) * (1.0 - built) * insects_k / 0.4 * season_insects * insects_day_factor(hour)
			* (1.0 - rain) * (1.0 - 0.5 * wind) * (1.0 - clampf((alt - 1800.0) / 600.0, 0.0, 1.0)),
		"water_flow": clampf(1.0 - (water_dist - 15.0) / 85.0, 0.0, 1.0) * float(WATER_KIND_GAIN.get(water_kind, 0.5)),
		"village_murmur": pow(built, 0.6) * (1.0 if birds_day_factor(hour) > 0.5 else 0.3),
		"high_wind": clampf((alt - 1200.0) / 1300.0, 0.0, 1.0) * (0.4 + 0.6 * wind),
		"rain": rain,
	}
	gains.merge(biome_gains(neigh, m))
	for b in BEDS:
		out[b] = SILENCE_DB if paused else _gain_db(minf(float(gains[b]), 1.0), b, float(m["volume"]))
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
	var lin_step := INF if paused else LINEAR_SLEW_PER_S * dt   # en pause, tout descend vite
	for b in BEDS:
		var cur: float = _db[b]
		var target: float = tgt[b] if chosen.has(b) else SILENCE_DB
		if cur <= SILENCE_DB:
			# Un fond muet démarre seulement s'il reste une voix libre
			if target > SILENCE_DB and audible < voices and not paused:
				_db[b] = minf(FADE_FLOOR_DB, target)
				audible += 1
			continue
		# Niveau relatif au plein du fond (0 à 1) : la variation en est bornée à lin_step
		var lin := pow(10.0, (cur - float(BED_MAX_DB[b])) / 20.0)
		var up_cap := float(BED_MAX_DB[b]) + 20.0 * log(lin + lin_step) / log(10.0)
		var down_cap := SILENCE_DB if lin - lin_step <= 0.0 else float(BED_MAX_DB[b]) + 20.0 * log(lin - lin_step) / log(10.0)
		if target <= SILENCE_DB:
			var down := maxf(cur - step, down_cap)
			_db[b] = SILENCE_DB if down <= FADE_FLOOR_DB else down
		elif cur < target:
			_db[b] = minf(minf(cur + step, up_cap), target)
		else:
			_db[b] = maxf(maxf(cur - step, down_cap), target)
	return _db.duplicate()


## Écart (dB, de BIRD_REST_DB à 0) des chants d'oiseaux à l'instant `t`, appliqué par sound_player.gd au
## niveau du fond `forest_birds` (le choix des voix et les fondus restent sur le niveau du fond).
static func birds_phrase_db(t: float) -> float:
	return maxf(20.0 * log(maxf(birds_gate(t), 1e-6)) / log(10.0), BIRD_REST_DB)


## Enveloppe des chants d'oiseaux (0 à 1) à l'instant `t` (s) : une phrase par tranche de BIRD_SLOT_S.
static func birds_gate(t: float) -> float:
	var slot := int(floor(t / BIRD_SLOT_S))
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(slot * 7919 + 17)
	var length := rng.randf_range(BIRD_PHRASE_MIN_S, BIRD_PHRASE_MAX_S)
	var start := rng.randf_range(0.0, BIRD_SLOT_S - length)
	var u := t - slot * BIRD_SLOT_S - start
	if u <= 0.0 or u >= length:
		return 0.0
	return minf(1.0, minf(u, length - u) / BIRD_EDGE_S)


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
	# Distance à la forêt la plus proche (feuilles qui tombent, lot P19) : 0 dedans
	var forest_dist := INF
	for poly in forests:
		var pts: PackedVector2Array = poly
		if pts.size() >= 3 and Geometry2D.is_point_in_polygon(rider_xz, pts):
			forest_dist = 0.0
			break
		for k in range(pts.size()):
			forest_dist = minf(forest_dist, _point_segment_dist(rider_xz, pts[k], pts[(k + 1) % pts.size()]))
	var best := INF
	var kind := ""
	var sea := INF
	for w in waters:
		var pts: PackedVector2Array = w.get("points", PackedVector2Array())
		if pts.size() == 0:
			continue
		var is_sea := str(w.get("kind", "")) == "sea"
		if w.get("area", false) == true and pts.size() >= 3 and Geometry2D.is_point_in_polygon(rider_xz, pts):
			best = 0.0
			kind = str(w.get("kind", "lake"))
			if is_sea:
				sea = 0.0
			continue
		var n := pts.size()
		var last := n if w.get("area", false) == true else n - 1
		for k in range(maxi(last, 1)):
			var d := rider_xz.distance_to(pts[0]) if n == 1 else _point_segment_dist(rider_xz, pts[k], pts[(k + 1) % n])
			if d < best:
				best = d
				kind = str(w.get("kind", "river"))
			if is_sea and d < sea:
				sea = d
	return {
		"forest_share": float(forest_n) / float(maxi(inside, 1)),
		"built_share": float(built_n) / float(maxi(inside, 1)),
		"water_dist_m": best,
		"forest_dist_m": forest_dist,
		"water_kind": kind,
		"sea_dist_m": sea,
	}
