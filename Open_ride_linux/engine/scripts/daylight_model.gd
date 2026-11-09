extends RefCounted

## Jour et nuit, sans nœud ni affichage (lot P7, version 2.0) : position du soleil pour une latitude, une
## date et une heure solaire, lumière de l'heure (aube et crépuscule orangés, heure bleue, nuit au clair
## de lune), étoiles, horloge (heure fixe, heure du PC ou journée accélérée). Appliqué à la scène par P19.
## Pas de class_name : charger par preload("res://scripts/daylight_model.gd").
##
## - `sun_position(lat_deg, day_of_year, solar_hour)` -> `{elevation_deg, azimuth_deg}` (azimut en degrés,
##   sens horaire depuis le nord −z, comme `ThemeRenderParams.SUN_AZIMUTH_DEG`) ; précision d'environ 1° ;
## - `light(elevation_deg, moon_illum, min_ambient)` -> multiplicateurs des valeurs de jour du thème (tous
##   neutres, blanc et 1, dès LIGHT_DAY_DEG) : `sun_color`, `sun_energy`, `ambient_color`, `ambient_energy`,
##   `sky_top`, `sky_horizon`, `fog_color`, plus `moon_energy` (lumière de lune, 0 de jour) ;
## - `stars(elevation_deg)` : 0 au-dessus de l'horizon, 1 sous −18°, pour le ciel de P6 ;
## - `clock(mode, hour, factor, elapsed_s, now, lon_deg)` -> heure solaire ; `days_elapsed` : jours passés
##   en heure accélérée (P19 suit la saison quand la date change) ;
## - `moon_illumination(unix_days)` : part éclairée de la lune (0 nouvelle lune, 1 pleine lune) ;
## - `evaluate(tod, lat, lon, day_of_year, elapsed_s, now, unix_days)` : tout en un ; `tod` vient de
##   `ThemeRenderParams.time_of_day_params` ; `tod.present` faux (thème sans `sky.time_of_day`) : soleil et
##   lumière d'aujourd'hui (hauteur du thème, azimut constant, multiplicateurs neutres).
## La latitude et la longitude ne sont lues qu'à l'exécution (manifeste du parcours) ; NAN : 45° et
## heure locale prise pour l'heure solaire.

const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")

const OBLIQUITY_DEG := 23.44
const DEFAULT_LATITUDE_DEG := 45.0
const LIGHT_DAY_DEG := 30.0          # au-dessus : lumière du thème, inchangée
const NIGHT_DEG := -6.0              # fin du crépuscule civil
const ASTRO_NIGHT_DEG := -18.0       # nuit noire, étoiles pleines
const SYNODIC_DAYS := 29.530588
const NEW_MOON_UNIX_DAYS := 10962.759   # nouvelle lune du 6 janvier 2000, 18 h 14 UTC (jours depuis 1970)
const MOON_ENERGY := 0.18            # énergie de la lune pleine, en part du soleil du thème
const MOON_AMBIENT := 0.08           # lumière ambiante ajoutée par la lune pleine
const MOON_COLOR := Color(0.72, 0.80, 1.0)
const MOON_MIN_ELEVATION_DEG := 25.0    # la lune éclaire toujours d'assez haut pour des ombres lisibles
const MAX_ACCEL_FACTOR := 1440.0     # une journée par minute au plus

## Paliers de lumière, de la nuit noire au plein jour : élévation (°), puis multiplicateurs des valeurs de
## jour du thème. Interpolation linéaire entre deux paliers voisins : aucune marche.
const STOPS := [
	{"el": -18.0, "sun": Color(1.0, 0.55, 0.35), "sun_e": 0.0, "amb": Color(0.32, 0.38, 0.62), "amb_e": 0.0,
		"top": Color(0.03, 0.04, 0.10), "hor": Color(0.06, 0.08, 0.16), "fog": Color(0.06, 0.08, 0.15)},
	{"el": -6.0, "sun": Color(1.0, 0.55, 0.35), "sun_e": 0.0, "amb": Color(0.38, 0.45, 0.75), "amb_e": 0.10,
		"top": Color(0.10, 0.15, 0.36), "hor": Color(0.24, 0.27, 0.50), "fog": Color(0.22, 0.25, 0.42)},
	{"el": -2.0, "sun": Color(1.0, 0.55, 0.35), "sun_e": 0.0, "amb": Color(0.55, 0.58, 0.85), "amb_e": 0.25,
		"top": Color(0.22, 0.32, 0.62), "hor": Color(0.78, 0.52, 0.48), "fog": Color(0.55, 0.46, 0.52)},
	{"el": 0.0, "sun": Color(1.0, 0.58, 0.30), "sun_e": 0.20, "amb": Color(0.80, 0.70, 0.75), "amb_e": 0.40,
		"top": Color(0.38, 0.50, 0.78), "hor": Color(1.0, 0.62, 0.40), "fog": Color(0.90, 0.66, 0.52)},
	{"el": 5.0, "sun": Color(1.0, 0.70, 0.45), "sun_e": 0.50, "amb": Color(0.92, 0.84, 0.82), "amb_e": 0.65,
		"top": Color(0.62, 0.72, 0.90), "hor": Color(1.0, 0.80, 0.62), "fog": Color(1.0, 0.84, 0.72)},
	{"el": 12.0, "sun": Color(1.0, 0.86, 0.70), "sun_e": 0.78, "amb": Color(0.97, 0.94, 0.93), "amb_e": 0.85,
		"top": Color(0.86, 0.90, 0.97), "hor": Color(1.0, 0.92, 0.84), "fog": Color(1.0, 0.94, 0.88)},
	{"el": LIGHT_DAY_DEG, "sun": Color.WHITE, "sun_e": 1.0, "amb": Color.WHITE, "amb_e": 1.0,
		"top": Color.WHITE, "hor": Color.WHITE, "fog": Color.WHITE},
]


## Jour de l'année (1 le 1er janvier) d'une date grégorienne.
static func day_of_year(year: int, month: int, day: int) -> int:
	var lengths := [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
	if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0:
		lengths[1] = 29
	var n := day
	for m in range(clampi(month, 1, 12) - 1):
		n += lengths[m]
	return n


## Déclinaison du soleil (°) : approximation en cosinus, à environ 1° près.
static func declination_deg(day_of_year: float) -> float:
	return -OBLIQUITY_DEG * cos(TAU / 365.0 * (day_of_year + 10.0))


static func sun_position(lat_deg: float, doy: float, solar_hour: float) -> Dictionary:
	var phi := deg_to_rad(lat_deg)
	var dec := deg_to_rad(declination_deg(doy))
	var h := deg_to_rad(15.0 * (solar_hour - 12.0))
	var sin_el := sin(phi) * sin(dec) + cos(phi) * cos(dec) * cos(h)
	var el := asin(clampf(sin_el, -1.0, 1.0))
	# Azimut depuis le nord, sens horaire : 90° à l'est le matin, 180° au sud à midi (hémisphère nord).
	var az := atan2(sin(h), cos(h) * sin(phi) - tan(dec) * cos(phi)) + PI
	return {"elevation_deg": rad_to_deg(el), "azimuth_deg": fposmod(rad_to_deg(az), 360.0)}


static func direction(elevation_deg: float, azimuth_deg: float) -> Vector3:
	var el := deg_to_rad(elevation_deg)
	var az := deg_to_rad(azimuth_deg)
	return Vector3(cos(el) * sin(az), sin(el), -cos(el) * cos(az)).normalized()


## Part éclairée de la lune pour une date en jours depuis le 1er janvier 1970 (UTC).
static func moon_illumination(unix_days: float) -> float:
	var age := fposmod(unix_days - NEW_MOON_UNIX_DAYS, SYNODIC_DAYS) / SYNODIC_DAYS
	return 0.5 * (1.0 - cos(TAU * age))


static func stars(elevation_deg: float) -> float:
	if elevation_deg >= 0.0:
		return 0.0
	return smoothstep(0.0, ASTRO_NIGHT_DEG, elevation_deg)


static func light(elevation_deg: float, moon_illum: float = 0.0, min_ambient: float = 0.12) -> Dictionary:
	var e := clampf(elevation_deg, STOPS[0]["el"], LIGHT_DAY_DEG)
	var i := 0
	while i < STOPS.size() - 2 and e > float(STOPS[i + 1]["el"]):
		i += 1
	var a: Dictionary = STOPS[i]
	var b: Dictionary = STOPS[i + 1]
	var t := clampf((e - float(a["el"])) / (float(b["el"]) - float(a["el"])), 0.0, 1.0)
	# Lune : sa lumière monte avec la nuit (rien au-dessus de l'horizon), selon sa phase.
	var night := clampf(-elevation_deg / -NIGHT_DEG, 0.0, 1.0) if elevation_deg < 0.0 else 0.0
	var moon := clampf(moon_illum, 0.0, 1.0) * night
	var amb_e := lerpf(float(a["amb_e"]), float(b["amb_e"]), t)
	amb_e = maxf(amb_e, clampf(min_ambient, 0.0, 1.0)) + MOON_AMBIENT * moon
	return {
		"sun_color": (a["sun"] as Color).lerp(b["sun"], t),
		"sun_energy": lerpf(float(a["sun_e"]), float(b["sun_e"]), t),
		"ambient_color": (a["amb"] as Color).lerp(b["amb"], t),
		"ambient_energy": amb_e,
		"sky_top": (a["top"] as Color).lerp(b["top"], t),
		"sky_horizon": (a["hor"] as Color).lerp(b["hor"], t),
		"fog_color": (a["fog"] as Color).lerp(b["fog"], t),
		"moon_energy": MOON_ENERGY * moon,
		"moon_color": MOON_COLOR,
	}


## Heure solaire. `now` : heure locale du PC (`hour`, `minute`, `second`) et décalage du fuseau en minutes
## (`bias`, comme `Time.get_time_zone_from_system()`), lus seulement en mode `real`.
static func clock(mode: String, hour: float, factor: float, elapsed_s: float, now: Dictionary = {},
		lon_deg: float = NAN) -> float:
	match mode:
		"real":
			var local := float(now.get("hour", hour)) + float(now.get("minute", 0)) / 60.0 \
					+ float(now.get("second", 0)) / 3600.0
			if is_nan(lon_deg) or not now.has("bias"):
				return fposmod(local, 24.0)
			return fposmod(local - float(now["bias"]) / 60.0 + lon_deg / 15.0, 24.0)
		"accelerated":
			return fposmod(hour + maxf(elapsed_s, 0.0) * clampf(factor, 0.0, MAX_ACCEL_FACTOR) / 3600.0, 24.0)
		_:
			return fposmod(hour, 24.0)


## Jours entiers passés depuis le départ en heure accélérée (0 dans les autres modes).
static func days_elapsed(mode: String, hour: float, factor: float, elapsed_s: float) -> int:
	if mode != "accelerated":
		return 0
	return int(floor((hour + maxf(elapsed_s, 0.0) * clampf(factor, 0.0, MAX_ACCEL_FACTOR) / 3600.0) / 24.0))


static func evaluate(tod: Dictionary, lat_deg: float, lon_deg: float, doy: float, elapsed_s: float,
		now: Dictionary = {}, unix_days: float = NAN) -> Dictionary:
	if not bool(tod.get("present", false)):
		var sky: Dictionary = tod.get("sky", ThemeRenderParams.sky_params({}))
		var neutral := light(LIGHT_DAY_DEG)
		neutral["sun_elevation_deg"] = sky["sun_elevation_deg"]
		neutral["sun_azimuth_deg"] = sky["sun_azimuth_deg"]
		neutral["sun_direction"] = sky["sun_direction"]
		neutral["solar_hour"] = NAN
		neutral["stars"] = 0.0
		neutral["active"] = false
		return neutral
	var lat := DEFAULT_LATITUDE_DEG if is_nan(lat_deg) else clampf(lat_deg, -90.0, 90.0)
	var mode := str(tod.get("mode", "fixed"))
	var hour := float(tod.get("hour", 12.0))
	var factor := float(tod.get("factor", 1.0))
	var solar := clock(mode, hour, factor, elapsed_s, now, lon_deg)
	var day := doy + days_elapsed(mode, hour, factor, elapsed_s)
	var sun := sun_position(lat, day, solar)
	var illum := 0.0 if is_nan(unix_days) else moon_illumination(unix_days + days_elapsed(mode, hour, factor, elapsed_s))
	var out := light(float(sun["elevation_deg"]), illum, float(tod.get("min_ambient", 0.12)))
	out["sun_elevation_deg"] = sun["elevation_deg"]
	out["sun_azimuth_deg"] = sun["azimuth_deg"]
	out["sun_direction"] = direction(sun["elevation_deg"], sun["azimuth_deg"])
	# Lune : à l'opposé du soleil, assez haute pour éclairer la route d'en haut.
	var moon_el := maxf(-float(sun["elevation_deg"]), MOON_MIN_ELEVATION_DEG)
	out["moon_direction"] = direction(moon_el, fposmod(float(sun["azimuth_deg"]) + 180.0, 360.0))
	out["moon_illumination"] = illum
	out["solar_hour"] = solar
	out["day_of_year"] = day
	out["stars"] = stars(float(sun["elevation_deg"]))
	out["active"] = true
	return out
