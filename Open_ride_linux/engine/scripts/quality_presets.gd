extends RefCounted

## Table des préréglages de qualité graphique (Lot L4, SRS §8 « Performance » et §11 `[render]`),
## sans aucun nœud ni affichage. Pas de class_name : charger par preload("res://scripts/quality_presets.gd").
##
## Valeurs retenues :
## - `low` (GPU intégré ou objectif ≥ 30 FPS garanti) : portée 3 km (3 tronçons devant, 1 derrière),
##   densité de végétation 0,3, sans SSAO ni brouillard volumétrique, MSAA désactivé (0), moteur `mobile`.
## - `medium` (GPU dédié milieu de gamme type GTX 1060) : portée 5 km (5 tronçons devant, 1 derrière),
##   densité de végétation 0,6, SSAO activé, sans brouillard volumétrique, MSAA 2×, moteur `forward_plus`.
## - `high` (GPU dédié récent) : portée 8 km (8 tronçons devant, 2 derrière), densité de végétation 1,0,
##   SSAO et brouillard volumétrique activés, MSAA 4×, moteur `forward_plus`.

const DEFAULT_PRESET := "low"

const PRESETS := {
	"low": {
		"view_distance_m": 3000.0,
		"chunks_ahead": 3,
		"chunks_behind": 1,
		"vegetation_density_factor": 0.3,
		"ssao": false,
		"fog_volumetric": false,
		"msaa": 0,
		"renderer_hint": "mobile",
	},
	"medium": {
		"view_distance_m": 5000.0,
		"chunks_ahead": 5,
		"chunks_behind": 1,
		"vegetation_density_factor": 0.6,
		"ssao": true,
		"fog_volumetric": false,
		"msaa": 2,
		"renderer_hint": "forward_plus",
	},
	"high": {
		"view_distance_m": 8000.0,
		"chunks_ahead": 8,
		"chunks_behind": 2,
		"vegetation_density_factor": 1.0,
		"ssao": true,
		"fog_volumetric": true,
		"msaa": 4,
		"renderer_hint": "forward_plus",
	},
}


## Renvoie le dictionnaire du préréglage demandé (`low`, `medium`, `high`), ou `low` si le nom est inconnu.
static func preset(name: String) -> Dictionary:
	var key := name.strip_edges()
	if PRESETS.has(key):
		return (PRESETS[key] as Dictionary).duplicate(true)
	return (PRESETS[DEFAULT_PRESET] as Dictionary).duplicate(true)
