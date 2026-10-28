extends RefCounted

## Catalogue graphique du mode Cyber-Rogue (lot R17 §4.4 et §4.5), partie données : les objets à dessiner
## (couleur-rôle, forme de base, lot qui les intègre) et les effets d'événement (durée, nombre maximal de
## clignotements par seconde). Pas de class_name : preload("res://scripts/rogue/neon_catalog.gd").

## Plafond de clignotements par seconde de tout effet de jeu (confort, charte §4.6).
const MAX_FLASHES_PER_S := 3.0

## Un objet : jeton de couleur, forme de base de la planche de démonstration, lot qui l'intègre.
const OBJECTS := {
	"player_bike": {"token": "player", "shape": "wheel", "lot": "R10"},
	"player_trail": {"token": "player", "shape": "ribbon", "lot": "R10"},
	"track_ribbon": {"token": "grade_flat", "shape": "ribbon", "lot": "R10"},
	"perfect_shift_arch": {"token": "gold", "shape": "arch", "lot": "R10"},
	"attack_target": {"token": "energy", "shape": "diamond", "lot": "R10"},
	"parry_zone": {"token": "parry", "shape": "slab", "lot": "R10"},
	"purge_beacon": {"token": "glitch", "shape": "ring", "lot": "R10"},
	"cadence_tunnel": {"token": "player", "shape": "ring", "lot": "R10"},
	"armor_rock": {"token": "energy", "shape": "rock", "lot": "R10"},
	"boost_pad": {"token": "gold", "shape": "slab", "lot": "R10"},
	"firewall": {"token": "danger", "shape": "wall", "lot": "R10"},
	"enemy_diesel": {"token": "energy", "shape": "block", "lot": "R12"},
	"enemy_puncher": {"token": "parry", "shape": "block", "lot": "R12"},
	"enemy_climber": {"token": "gold", "shape": "rock", "lot": "R12"},
	"enemy_sprinter": {"token": "neutral", "shape": "diamond", "lot": "R12"},
	"enemy_saboteur": {"token": "glitch", "shape": "diamond", "lot": "R12"},
	"boss_chimera": {"token": "danger", "shape": "block", "lot": "R12"},
	"corridor_door": {"token": "player", "shape": "gate", "lot": "R13"},
	"card_terraformer": {"token": "gold", "shape": "card", "lot": "R13"},
	"card_gear": {"token": "player", "shape": "card", "lot": "R13"},
	"card_module": {"token": "parry", "shape": "card", "lot": "R13"},
	"card_active": {"token": "energy", "shape": "card", "lot": "R13"},
	"card_relic": {"token": "neutral", "shape": "card", "lot": "R13"},
	"end_chest": {"token": "gold", "shape": "block", "lot": "R13"},
}

## Un effet : événement du jeu (`state.rogue.events`), durée en secondes, jeton principal, clignotements par
## seconde au plus (0 : pas de clignotement), grand flash plein écran (toujours faux : charte §4.6).
const EFFECTS := {
	"perfect_shift": {"duration_s": 0.4, "token": "gold", "flashes_per_s": 2.5, "fullscreen_flash": false},
	"hit": {"duration_s": 0.3, "token": "energy", "flashes_per_s": 3.0, "fullscreen_flash": false},
	"crit": {"duration_s": 0.3, "token": "energy", "flashes_per_s": 3.0, "fullscreen_flash": false},
	"parry": {"duration_s": 0.4, "token": "parry", "flashes_per_s": 2.5, "fullscreen_flash": false},
	"parry_miss": {"duration_s": 0.5, "token": "danger", "flashes_per_s": 2.0, "fullscreen_flash": false},
	"firewall_contact": {"duration_s": 0.0, "token": "glitch", "flashes_per_s": 0.0, "fullscreen_flash": false},
	"hack": {"duration_s": 0.0, "token": "glitch", "flashes_per_s": 0.0, "fullscreen_flash": false},
	"room_won": {"duration_s": 1.5, "token": "gold", "flashes_per_s": 0.0, "fullscreen_flash": false},
	"room_fled": {"duration_s": 1.5, "token": "neutral", "flashes_per_s": 0.0, "fullscreen_flash": false},
	"room_skipped": {"duration_s": 3.0, "token": "danger", "flashes_per_s": 2.0, "fullscreen_flash": false},
	"defeat": {"duration_s": 2.0, "token": "danger", "flashes_per_s": 1.5, "fullscreen_flash": false},
	"boss_phase": {"duration_s": 1.0, "token": "danger", "flashes_per_s": 1.0, "fullscreen_flash": false},
}

## Formes reconnues pour la planche.
const SHAPES := ["wheel", "ribbon", "arch", "diamond", "slab", "ring", "rock", "wall", "block", "gate", "card"]


static func object_ids() -> Array:
	return OBJECTS.keys()


static func effect_ids() -> Array:
	return EFFECTS.keys()
