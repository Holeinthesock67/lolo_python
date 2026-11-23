extends RefCounted

## Réglages de l'`Environment` Godot du mode Cyber-Rogue (lot R17 §4.3) : fond `void`, brume `night`, glow
## et correction de couleur par préréglage de qualité. Pas de class_name :
## preload("res://scripts/rogue/rogue_environment.gd").

const Palette := preload("res://scripts/rogue/neon_palette.gd")

## Glow par niveau (niveaux allumés sur 7), intensité, bloom, fin de la brume, part des particules, aberration.
## Une seule règle de brume pour les trois préréglages (lot R27) : linéaire, du joueur à `fog_end_m`. La brume
## exponentielle du high grisait tout le ciel (voile signalé en run le 21/11) ; le glow du high reprend celui
## du medium pour la même raison (halo de la route jaune sur tout l'écran).
const PRESETS := {
	"low": {"glow_levels": 3, "glow_intensity": 0.8, "glow_bloom": 0.05,
		"fog_end_m": 400.0, "particles_share": 0.25, "chromatic": false, "sun": false},
	"medium": {"glow_levels": 5, "glow_intensity": 1.0, "glow_bloom": 0.10,
		"fog_end_m": 600.0, "particles_share": 0.60, "chromatic": false, "sun": true},
	"high": {"glow_levels": 5, "glow_intensity": 1.0, "glow_bloom": 0.10,
		"fog_end_m": 900.0, "particles_share": 1.0, "chromatic": true, "sun": true},
}
const GLOW_LEVEL_COUNT := 7
const GLOW_HDR_THRESHOLD := 1.0


static func settings(preset: String) -> Dictionary:
	return PRESETS.get(preset, PRESETS["low"])


## Applique les réglages à un `Environment`.
static func apply(env: Environment, preset: String) -> void:
	var s := settings(preset)
	env.background_mode = Environment.BG_COLOR
	env.background_color = Palette.color("void")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Palette.color("night")
	env.ambient_light_energy = 0.4
	env.glow_enabled = true
	for i in GLOW_LEVEL_COUNT:
		env.set_glow_level(i, 1.0 if i < int(s["glow_levels"]) else 0.0)
	env.glow_intensity = s["glow_intensity"]
	env.glow_bloom = s["glow_bloom"]
	env.glow_hdr_threshold = GLOW_HDR_THRESHOLD
	env.fog_enabled = true
	env.fog_light_color = Palette.color("night")
	# Brume linéaire (mode « profondeur ») partout. Le mode d'abord : Godot remet la
	# densité à sa valeur par défaut quand le mode change.
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_density = 1.0
	env.fog_depth_begin = 0.0
	env.fog_depth_end = s["fog_end_m"]
