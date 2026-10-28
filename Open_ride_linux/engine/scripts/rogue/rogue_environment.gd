extends RefCounted

## Réglages de l'`Environment` Godot du mode Cyber-Rogue (lot R17 §4.3) : fond `void`, brume `night`, glow
## et correction de couleur par préréglage de qualité. Pas de class_name :
## preload("res://scripts/rogue/rogue_environment.gd").

const Palette := preload("res://scripts/rogue/neon_palette.gd")

## Glow par niveau (niveaux allumés sur 7), intensité, bloom, brume, part des particules, aberration.
const PRESETS := {
	"low": {"glow_levels": 3, "glow_intensity": 0.8, "glow_bloom": 0.05, "fog_exponential": false,
		"fog_end_m": 400.0, "particles_share": 0.25, "chromatic": false, "sun": false},
	"medium": {"glow_levels": 5, "glow_intensity": 1.0, "glow_bloom": 0.10, "fog_exponential": false,
		"fog_end_m": 600.0, "particles_share": 0.60, "chromatic": false, "sun": true},
	"high": {"glow_levels": 7, "glow_intensity": 1.1, "glow_bloom": 0.15, "fog_exponential": true,
		"fog_end_m": 900.0, "particles_share": 1.0, "chromatic": true, "sun": true},
}
const GLOW_LEVEL_COUNT := 7
const GLOW_HDR_THRESHOLD := 1.0


static func settings(preset: String) -> Dictionary:
	return PRESETS.get(preset, PRESETS["low"])


## Densité de la brume exponentielle qui devient opaque (≈ 95 %) à `fog_end_m`.
static func exponential_density(fog_end_m: float) -> float:
	return 3.0 / maxf(fog_end_m, 1.0)


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
	# Brume linéaire (mode « profondeur ») en low et medium, exponentielle en high ; `set` ignore une
	# propriété absente de la version de Godot, la densité exponentielle sert alors de repli.
	env.fog_density = exponential_density(s["fog_end_m"])
	env.set("fog_mode", 0 if s["fog_exponential"] else 1)    # 0 : exponentielle, 1 : profondeur
	env.set("fog_depth_begin", 0.0)
	env.set("fog_depth_end", s["fog_end_m"])
