extends RefCounted

## Atmosphère par biome, sans nœud ni affichage (lot U10, série U) : brouillard, voile de l'horizon,
## teinte et force de la lumière, brume de chaleur et humidité selon les biomes que traverse la route.
## Pas de class_name : charger par preload("res://scripts/atmosphere_model.gd"). Branché par U17.
##
## - `params_at(model, weights, daylight, weather, quality)` (pur) : paramètres pour des poids de biomes
##   (`biome_model.gd`), une lumière du jour (`daylight_from_theme`, puis P7) et une météo évaluée
##   (`weather_model.gd evaluate`) ;
## - `smoothed_weights(s)` : poids moyennés sur WINDOW_M de route centrés sur `s`, pour qu'un changement
##   de biome se fasse en douceur (au plus 1/51 de l'écart tous les 10 m) ; `at(s, daylight, weather)`
##   enchaîne les deux.
##
## Clés rendues :
## - `fog_density` : densité du biome (brume volumétrique, RenderQuality.volumetric_density) ;
## - `fog_end_factor` (0,6 à 1) : rapproche le brouillard de profondeur dans l'air humide ;
## - `horizon_color` : horizon voilé par `haze` (RenderQuality.HAZE_COLOR) puis teinté par la lumière ;
## - `light_tint`, `light_energy_factor` : teinte du soleil, lumière plus diffuse quand l'air est humide ;
## - `humidity` (0 à 1) : 0 jusqu'à la densité de la prairie, 1 à celle de la jungle ;
## - `heat_haze` (0 à 1) : distorsion de l'horizon (shaders/heat_haze.gdshader) en `sand_desert`,
##   `rock_desert` et `savanna`, l'après-midi, coupée par la pluie, la neige ou la brume (la météo de P8
##   l'emporte) et par le préréglage (`heat_haze` de QualityPresets.IMAGE, faux en `low`) ;
## - `sun_elevation_deg`, `sun_direction` : au-delà de 66° de latitude, soleil rasant (POLAR_MAX_SUN_DEG)
##   et lumière froide (POLAR_TINT).
## Prairie tempérée (`temperate_grassland`) : brouillard, horizon et soleil d'aujourd'hui.

const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")

const WINDOW_M := 500.0
const STEP_M := 10.0
const CACHE_MAX := 600
const HEAT_BIOMES := ["sand_desert", "rock_desert", "savanna"]
## Brume de chaleur : monte de 12 h à 14 h, pleine jusqu'à 17 h, partie à 19 h.
const HEAT_RISE := Vector2(12.0, 14.0)
const HEAT_FALL := Vector2(17.0, 19.0)
## Météo qui l'emporte sur la brume de chaleur : coupée dès 0,3 de pluie, de neige ou de brume.
const WEATHER_WINS_AT := 0.3
const HUMID_REF_DENSITY := 0.0008     # prairie (thème 1.x)
const HUMID_FULL_DENSITY := 0.0018    # jungle
const HUMID_FOG_END := 0.4            # brouillard 40 % plus proche à humidité pleine
const HUMID_LIGHT := 0.25             # soleil 25 % plus faible à humidité pleine
const HAZE_HORIZON := 0.6             # même mélange que main._apply_sky_params
const POLAR_LAT_DEG := 66.0
const POLAR_FULL_LAT_DEG := 70.0
const POLAR_MAX_SUN_DEG := 18.0
const POLAR_TINT := Color(0.86, 0.91, 1.0)

var model
var pos_at: Callable       # s (m) -> Vector2(x, z) du monde
var _cache := {}           # indice de pas -> poids des biomes


func _init(biome_model = null, position_at: Callable = Callable()) -> void:
	model = biome_model
	pos_at = position_at


## Lumière du jour du thème en attendant P7 : heure fixe (`sky.time_of_day.hour`, sinon inconnue),
## hauteur du soleil du thème, latitude du parcours.
static func daylight_from_theme(theme: Dictionary, latitude_deg: float = NAN) -> Dictionary:
	var hour := NAN
	var sky: Variant = theme.get("sky", null) if typeof(theme) == TYPE_DICTIONARY else null
	if typeof(sky) == TYPE_DICTIONARY and typeof(sky.get("time_of_day", null)) == TYPE_DICTIONARY:
		var tod: Dictionary = sky["time_of_day"]
		if str(tod.get("mode", "fixed")) == "fixed" and ThemeRenderParams._is_number(tod.get("hour", null)):
			hour = float(tod["hour"])
	return {
		"solar_hour": hour,
		"sun_elevation_deg": float(ThemeRenderParams.sky_params(theme)["sun_elevation_deg"]),
		"latitude_deg": latitude_deg,
	}


## Part de la brume de chaleur selon l'heure solaire ; heure inconnue : pleine (rendu sans P7).
static func heat_hour_factor(solar_hour: float) -> float:
	if is_nan(solar_hour):
		return 1.0
	var h := fposmod(solar_hour, 24.0)
	return smoothstep(HEAT_RISE.x, HEAT_RISE.y, h) * (1.0 - smoothstep(HEAT_FALL.x, HEAT_FALL.y, h))


static func humidity_of(fog_density: float) -> float:
	return clampf((fog_density - HUMID_REF_DENSITY) / (HUMID_FULL_DENSITY - HUMID_REF_DENSITY), 0.0, 1.0)


static func params_at(biome_model, weights: Dictionary, daylight: Dictionary, weather: Dictionary,
		quality: String) -> Dictionary:
	var by_biome := {}
	var heat_w := 0.0
	for b in weights.keys():
		by_biome[b] = biome_model.params(b)
		if b in HEAT_BIOMES:
			heat_w += float(weights[b])
	var mix: Dictionary = biome_model.blend(weights, by_biome)
	var fog_density := float(mix["fog_density"])
	var humidity := humidity_of(fog_density)
	var tint: Color = mix["light_tint"]

	var elev := float(daylight.get("sun_elevation_deg", ThemeRenderParams.DEFAULT_SUN_ELEVATION_DEG))
	var lat := float(daylight.get("latitude_deg", NAN))
	if not is_nan(lat):
		var polar := smoothstep(POLAR_LAT_DEG, POLAR_FULL_LAT_DEG, absf(lat))
		if polar > 0.0:
			elev = lerpf(elev, minf(elev, POLAR_MAX_SUN_DEG), polar)
			tint = tint * Color.WHITE.lerp(POLAR_TINT, polar)
	var el_rad := deg_to_rad(elev)
	var az_rad := deg_to_rad(ThemeRenderParams.SUN_AZIMUTH_DEG)
	var sun_dir := Vector3(cos(el_rad) * sin(az_rad), sin(el_rad), -cos(el_rad) * cos(az_rad)).normalized()

	var blocked := maxf(float(weather.get("rain", 0.0)), maxf(float(weather.get("snow", 0.0)),
		float(weather.get("fog_boost", 0.0))))
	var heat := 0.0
	if bool(QualityPresets.image(quality).get("heat_haze", false)):
		heat = heat_w * heat_hour_factor(float(daylight.get("solar_hour", NAN))) \
			* (1.0 - smoothstep(0.0, WEATHER_WINS_AT, blocked))

	return {
		"fog_density": fog_density,
		"fog_end_factor": 1.0 - HUMID_FOG_END * humidity,
		"horizon_color": RenderQuality.FOG_COLOR.lerp(RenderQuality.HAZE_COLOR, float(mix["haze"]) * HAZE_HORIZON) * tint,
		"light_tint": tint,
		"light_energy_factor": 1.0 - HUMID_LIGHT * humidity,
		"humidity": humidity,
		"heat_haze": clampf(heat, 0.0, 1.0),
		"sun_elevation_deg": elev,
		"sun_direction": sun_dir,
	}


func _weights_at_step(k: int) -> Dictionary:
	var hit = _cache.get(k, null)
	if hit != null:
		return hit
	if _cache.size() >= CACHE_MAX:
		_cache.clear()
	var p: Vector2 = pos_at.call(k * STEP_M)
	var w: Dictionary = model.weights_at(p.x, p.y)
	_cache[k] = w
	return w


## Poids moyennés sur WINDOW_M (51 pas de 10 m) centrés sur `s`, interpolés entre deux fenêtres voisines :
## continus en `s`, de somme 1.
func smoothed_weights(s: float) -> Dictionary:
	var n := int(WINDOW_M / STEP_M) + 1
	var start := (s - WINDOW_M * 0.5) / STEP_M
	var k0 := floori(start)
	var frac := start - k0
	var out := {}
	for i in range(n + 1):
		var share := 1.0
		if i == 0:
			share = 1.0 - frac
		elif i == n:
			share = frac
		if share <= 0.0:
			continue
		var w := _weights_at_step(k0 + i)
		for b in w.keys():
			out[b] = float(out.get(b, 0.0)) + float(w[b]) * share / n
	return out


func at(s: float, daylight: Dictionary, weather: Dictionary, quality: String) -> Dictionary:
	return params_at(model, smoothed_weights(s), daylight, weather, quality)
