extends RefCounted

## Table des préréglages de qualité graphique (Lots L4 et E3, SRS §8 « Performance » et §11 `[render]`),
## sans aucun nœud ni affichage. Pas de class_name : charger par preload("res://scripts/quality_presets.gd").
##
## Valeurs retenues :
## - `low` (GPU intégré ou objectif ≥ 30 FPS garanti) : portée 3 km (3 tronçons devant, 1 derrière),
##   densité de végétation 0,3, sans SSAO ni brouillard volumétrique, MSAA désactivé (0),
##   brouillard opaque à 4 km, ombres 150 m, budget arbres 20 000.
## - `medium` (GPU dédié milieu de gamme type GTX 1060) : portée 5 km (5 tronçons devant, 1 derrière),
##   densité de végétation 0,6, SSAO activé, sans brouillard volumétrique, MSAA 2×,
##   brouillard opaque à 6 km, ombres 300 m, budget arbres 50 000.
## - `high` (GPU dédié récent) : portée 8 km (8 tronçons devant, 2 derrière), densité de végétation 1,0,
##   SSAO et brouillard volumétrique activés, MSAA 4×,
##   brouillard opaque à 9 km, ombres 600 m, budget arbres 100 000.
## `fog_end_m` (lot Y1) : distance où le brouillard devient opaque ; la caméra (`camera.far`) et le
## rayon des tuiles lointaines du terrain la suivent (render_quality.gd, world_streamer.gd).
## Le moteur de rendu ne fait pas partie des préréglages : Forward+ partout (essai Mobile : lot Y7).

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
		"fog_end_m": 4000.0,
	},
	"medium": {
		"view_distance_m": 5000.0,
		"chunks_ahead": 5,
		"chunks_behind": 1,
		"vegetation_density_factor": 0.6,
		"ssao": true,
		"fog_volumetric": false,
		"msaa": 2,
		"fog_end_m": 6000.0,
	},
	"high": {
		"view_distance_m": 8000.0,
		"chunks_ahead": 8,
		"chunks_behind": 2,
		"vegetation_density_factor": 1.0,
		"ssao": true,
		"fog_volumetric": true,
		"msaa": 4,
		"fog_end_m": 9000.0,
	},
}

## Distance des ombres portées selon le préréglage (Lots E1 et E3)
const SHADOW_DISTANCES := {
	"low": 150.0,
	"medium": 300.0,
	"high": 600.0,
}

## Budget d'arbres affichés selon le préréglage (Lot E3 / SRS §8)
const TREE_BUDGETS := {
	"low": 20000,
	"medium": 50000,
	"high": 100000,
}

## Distance d'affichage des bâtiments (Lot E4)
const BUILDING_VISIBILITY_END := {
	"low": 1500.0,
	"medium": 2500.0,
	"high": 4000.0,
}


## Renvoie le dictionnaire du préréglage demandé (`low`, `medium`, `high`), ou `low` si le nom est inconnu.
static func preset(name: String) -> Dictionary:
	var key := name.strip_edges()
	if PRESETS.has(key):
		return (PRESETS[key] as Dictionary).duplicate(true)
	return (PRESETS[DEFAULT_PRESET] as Dictionary).duplicate(true)


## Distance où le brouillard de profondeur devient opaque (lot Y1), `low` si le nom est inconnu.
static func fog_end_m(name: String) -> float:
	return float(preset(name)["fog_end_m"])


static func shadow_distance_m(name: String) -> float:
	var key := name.strip_edges()
	return SHADOW_DISTANCES.get(key, SHADOW_DISTANCES[DEFAULT_PRESET])


static func tree_budget(name: String) -> int:
	var key := name.strip_edges()
	return TREE_BUDGETS.get(key, TREE_BUDGETS[DEFAULT_PRESET])


static func building_visibility_end_m(name: String) -> float:
	var key := name.strip_edges()
	return BUILDING_VISIBILITY_END.get(key, BUILDING_VISIBILITY_END[DEFAULT_PRESET])


## Budgets du décor vivant de la série P selon le préréglage (Lot P4), lus par les lots P5 à P15 et P21.
## `low` vise ≥ 55 images/s et un temps d'image p99 sous 25 ms sur la GTX 1060 du PC cible, toute la
## série activée. `passersby` est le budget des passants des villages (P21).
const LIVING := {
	"low": {
		"tree_sway": true,
		"grass_tufts": 1500,
		"clouds": "flat",
		"weather_particles": 600,
		"birds": 12,
		"animals": 20,
		"vehicles": 3,
		"spectators": 40,
		"passersby": 24,
		"ambience_voices": 4,
		"water_shimmer": true,
	},
	"medium": {
		"tree_sway": true,
		"grass_tufts": 8000,
		"clouds": "flat",
		"weather_particles": 1500,
		"birds": 24,
		"animals": 40,
		"vehicles": 5,
		"spectators": 80,
		"passersby": 48,
		"ambience_voices": 6,
		"water_shimmer": true,
	},
	"high": {
		"tree_sway": true,
		"grass_tufts": 20000,
		"clouds": "layered",
		"weather_particles": 4000,
		"birds": 40,
		"animals": 80,
		"vehicles": 8,
		"spectators": 160,
		"passersby": 80,
		"ambience_voices": 8,
		"water_shimmer": true,
	},
}


## Budgets du décor vivant du préréglage (`low` si le nom est inconnu) ; `enabled = false`
## (`[render] living = false`) coupe tout : booléens faux, nombres à zéro, nuages `off`.
static func living(name: String, enabled: bool = true) -> Dictionary:
	var key := name.strip_edges()
	var out: Dictionary = (LIVING[key] if LIVING.has(key) else LIVING[DEFAULT_PRESET]).duplicate(true)
	if not enabled:
		for k in out.keys():
			match typeof(out[k]):
				TYPE_BOOL:
					out[k] = false
				TYPE_INT, TYPE_FLOAT:
					out[k] = 0
				TYPE_STRING:
					out[k] = "off"
	return out
