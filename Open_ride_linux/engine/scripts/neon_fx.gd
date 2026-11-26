extends Node3D

## Ambiance des paysages en ville néon (lot NV2, parcours « Avenue de la Lagune »). Règle unique de biome_model.gd
## (`neon_at`) : une tuile dont le paysage a une section `neon` dans le thème est en ville néon ; aujourd'hui seul
## `ville_neon` en a une. Ce nœud ne dessine rien : il tient l'état lu par main.gd pour le ciel, la lumière et la
## brume (atmosphere_view.gd `set_neon`), et pose les globaux des néons des façades (lot NV3, `apply_globals`).
##
## - `neon_level` (0 à 1, lissé) : part de l'ambiance autour de la caméra, comme `fire_level` du volcan ;
## - `night` (0 à 1) : coucher du soleil au départ, puis la nuit tombe (`night_at`) ; le paysage impose sa lumière,
##   quelle que soit l'heure choisie par le joueur (sinon les néons ne se voient pas) ;
## - `palette` : section `neon` du thème complétée (couleurs `#RRGGBB`, densité).

const LEVEL_RATE := 0.5       # montée et descente de `neon_level` par seconde
const DUSK_HOLD_S := 120.0    # coucher du soleil tenu au départ
const NIGHT_AT_S := 600.0     # nuit complète

var biome_model = null
var neon_level := 0.0
var night := 0.0
var palette := {}
## Essais et captures : nuit imposée (0 à 1) ; NAN : nuit donnée par le temps roulé dans le paysage.
var night_override := NAN
var _clock := 0.0
var _started := false
static var _glow_set := 0.0     # dernière valeur posée dans le global `neon_glow`
static var _colors_set := ""


## Modèle de biome du parcours (nul : rien) ; remet l'ambiance à zéro.
func configure(model) -> void:
	biome_model = model
	neon_level = 0.0
	night = 0.0
	_clock = 0.0
	_started = false
	palette = {} if model == null else model.any_neon()
	apply_globals(0.0, palette)


func active() -> bool:
	return not palette.is_empty()


## Part de nuit après `t` secondes roulées dans le paysage.
static func night_at(t: float) -> float:
	return smoothstep(DUSK_HOLD_S, NIGHT_AT_S, t)


## Une fois par image : `neon_level` vers 1 dans une tuile en ville néon, vers 0 ailleurs ; la nuit avance tant
## que la caméra y roule (pas en pause : `dt_s` nul).
func update(cam_pos: Vector3, dt_s: float) -> void:
	if not active():
		return
	var here: Dictionary = biome_model.neon_at(cam_pos.x, cam_pos.z)
	var target := 0.0 if here.is_empty() else 1.0
	if not here.is_empty():
		palette = here
	# Scène figée (captures, pas nul) ou première image : l'ambiance prend tout de suite sa valeur
	neon_level = target if dt_s <= 0.0 or not _started else move_toward(neon_level, target, LEVEL_RATE * dt_s)
	_started = true
	if neon_level > 0.0:
		_clock += maxf(dt_s, 0.0)
	night = night_at(_clock) if is_nan(night_override) else clampf(night_override, 0.0, 1.0)
	apply_globals(neon_level, palette)


## Néons des façades (lot NV3, building.gdshader) : globaux `neon_glow` (ambiance × densité du thème, 0 : rien
## n'est dessiné) et couleurs `neon_color_a`, `neon_color_b` (rose et cyan du thème). Posés seulement quand ils
## changent (pas d'appel au serveur de rendu à chaque image).
static func apply_globals(level: float, neon_palette: Dictionary) -> void:
	var glow := clampf(level, 0.0, 1.0) * clampf(float(neon_palette.get("density", 1.0)), 0.0, 2.0)
	if neon_palette.is_empty():
		glow = 0.0
	if glow > 0.0:
		var key := str(neon_palette.get("pink", "")) + str(neon_palette.get("cyan", ""))
		if key != _colors_set:
			_colors_set = key
			RenderingServer.global_shader_parameter_set("neon_color_a", Color(str(neon_palette["pink"])))
			RenderingServer.global_shader_parameter_set("neon_color_b", Color(str(neon_palette["cyan"])))
	if glow != _glow_set:
		_glow_set = glow
		RenderingServer.global_shader_parameter_set("neon_glow", glow)
