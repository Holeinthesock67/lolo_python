extends RefCounted

## Apparence des cyclistes du décor (lot AS7, retour d'essai du 04/11) : le même cycliste que l'avatar du joueur
## et les bots (avatar_view.gd, lot Y18), dans une garde-robe « décor » qui ne se confond ni avec les bots ni
## avec le fantôme. Sans nœud : des réglages d'avatar (avatar_model.gd DEFAULTS) et des `look` d'équipement
## (equipment_meshes.gd LOOKS), tirés du maillot (`jersey`, 0 à 7) et de la tenue (`look`, 16 bits) du
## cycliste de road_cyclists_model.gd, ceux que le core envoie aussi (liste `riders`, `look` sur 20 bits).
##
## - Maillot : couleur principale parmi DECOR_KITS, jamais celle d'un bot (bot_look.gd KIT_BY_ROLE, autre,
##   maillots vert et à pois) ni le vert de l'avatar par défaut ; uni ou de club, sans dossard.
## - VARIANTS apparences (maillot × BODIES corps) : peu de maillages différents à construire et à garder
##   (avatar_view.gd `_parts_cache`), et un avatar caché resservant au cycliste suivant de même apparence.
## - Corps et équipement varient avec l'apparence (jamais le cadre ni les roues de contre-la-montre).
## Pas de class_name : charger par preload("res://scripts/road_cyclist_look.gd").

const AvatarModel := preload("res://scripts/avatar_model.gd")

## Couleurs principales (AvatarModel.KIT_COLORS) : rouge, turquoise, marine, violet, magenta, anthracite,
## brun, sable. Les bots portent 1, 2, 6, 12 (et 3, 10 pour les maillots de la séance), l'avatar par défaut 4.
const DECOR_KITS := [0, 5, 7, 8, 9, 13, 14, 15]
const SECONDARIES := [10, 13, 11, 15]
const BODIES := 2
const VARIANTS := 16                  # DECOR_KITS.size() × BODIES
const KIT_LOOKS := ["kit_plain", "kit_club"]
const FRAMES := ["frame_round", "frame_light", "frame_round_light", "frame_aero"]
const WHEELS := ["wheels_spoked", "wheels_spoked_light", "wheels_deep"]
const HELMETS := ["helmet_road", "helmet_summit", "helmet_road", "helmet_aero"]
const SOCKS := ["socks_white", "socks_tall", "socks_striped", "socks_white"]
const GLASSES := ["glasses_clear", "glasses_mirror", "glasses_metronome"]


## Apparence (0 à VARIANTS − 1) du cycliste au maillot `jersey` et à la tenue `look` (road_cyclists_model.gd).
static func variant_of(jersey: int, look: int) -> int:
	return absi(jersey) % DECOR_KITS.size() + DECOR_KITS.size() * (absi(look) % BODIES)


## Réglages d'avatar (avatar_model.gd parse_settings) de l'apparence `v`.
static func settings_for(v: int) -> Dictionary:
	var i := absi(v) % VARIANTS
	var kit := i % DECOR_KITS.size()
	var s: Dictionary = AvatarModel.DEFAULTS.duplicate()
	s["height"] = AvatarModel.HEIGHTS[(i * 3 + 2) % AvatarModel.HEIGHTS.size()]
	s["build"] = AvatarModel.BUILDS[(i + 2) % AvatarModel.BUILDS.size()]
	s["skin"] = (i * 3 + 2) % AvatarModel.SKIN_COLORS.size()
	s["hair"] = (i * 5 + 3) % 6
	s["hair_color"] = (i * 5 + 1) % AvatarModel.HAIR_COLORS.size()
	var primary: int = DECOR_KITS[kit]
	var secondary: int = SECONDARIES[i % SECONDARIES.size()]
	if secondary == primary:
		secondary = SECONDARIES[(i + 1) % SECONDARIES.size()]
	s["kit_primary"] = primary
	s["kit_secondary"] = secondary
	s["number"] = 0
	return s


## `look` d'équipement par emplacement (equipment_meshes.gd LOOKS) de l'apparence `v`.
static func looks_for(v: int) -> Dictionary:
	var i := absi(v) % VARIANTS
	return {
		"frame": FRAMES[i % FRAMES.size()],
		"wheels": WHEELS[(i * 2 + 1) % WHEELS.size()],
		"helmet": HELMETS[(i + 1) % HELMETS.size()],
		"kit": KIT_LOOKS[(i % DECOR_KITS.size()) % KIT_LOOKS.size()],
		"socks": SOCKS[(i * 3) % SOCKS.size()],
		"glasses": GLASSES[(i + 2) % GLASSES.size()],
	}
