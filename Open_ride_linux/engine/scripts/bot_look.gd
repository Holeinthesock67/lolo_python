extends RefCounted

## Apparence des bots sur la route (lot Y18) : le même cycliste que l'avatar du joueur (avatar_view.gd,
## lots V6, V7 et Y16), habillé et équipé d'après le bot. Sans nœud : des réglages d'avatar
## (avatar_model.gd DEFAULTS) et des `look` d'équipement (equipment_meshes.gd LOOKS), tirés de façon stable
## de l'indice d'affichage du bot, de son rôle (`role_of`) et du maillot qu'il porte.
##
## - Maillot : couleur principale de la palette du Garage selon le rôle du bot (KIT_BY_ROLE : la teinte de
##   son nom dans l'encart du HUD), couleur secondaire et motif selon l'indice ; deux bots de même rôle ne
##   se ressemblent donc pas.
## - Maillot distinctif de la séance (lot T14, champ `jersey` de la révision 1.4) : `sprint` = maillot vert
##   uni, `kom` = blanc à pois rouges (motif `kit_polka`).
## - Corps : taille, silhouette, peau, coupe et couleur des cheveux varient avec l'indice.
## - Équipement : cadre, roues, casque, chaussettes et lunettes varient avec l'indice (jamais le cadre de
##   contre-la-montre, dont les prolongateurs ne vont pas à un peloton).
## - Numéro de dossard : indice + 1 ; le fantôme n'en a pas.
## Pas de class_name : charger par preload("res://scripts/bot_look.gd").

const AvatarModel := preload("res://scripts/avatar_model.gd")

const KIT_GREEN := 3        # AvatarModel.KIT_COLORS : maillot vert des sprints
const KIT_WHITE := 10
const KIT_RED := 0
const KIT_DARK := 13
const KIT_OTHER := 12
## Couleur principale du maillot par rôle, dans la teinte du nom du bot dans l'encart du HUD (ui_theme.gd
## BOT_CONSTANT orange, BOT_PROFILE jaune, BOT_GHOST bleu pâle) ; autre : gris.
const KIT_BY_ROLE := {"constant": 1, "profile": 2, "ghost": 6}
const SECONDARIES := [13, 10, 7, 0, 11, 12]
const KIT_LOOKS := ["kit_stripes", "kit_plain", "kit_club", "kit_milestones"]
const FRAMES := ["frame_round", "frame_aero", "frame_light", "frame_round_light"]
const WHEELS := ["wheels_spoked", "wheels_deep", "wheels_spoked_light", "wheels_deep"]
const HELMETS := ["helmet_road", "helmet_aero", "helmet_road", "helmet_summit"]
const SOCKS := ["socks_white", "socks_striped", "socks_tall", "socks_white", "socks_long_distance"]
const GLASSES := ["glasses_clear", "glasses_mirror", "glasses_metronome"]


## Rôle d'un bot affiché (bots_view_model.view()) : `ghost`, `profile` (bot à profil, lot T12) ou `kind`.
static func role_of(b: Dictionary) -> String:
	if str(b.get("kind", "")) == "ghost":
		return "ghost"
	var profile = b.get("profile")
	return "profile" if profile != null and str(profile) != "" else str(b.get("kind", ""))


## Réglages d'avatar (avatar_model.gd parse_settings) du bot affiché à l'indice `index`.
static func settings_for(index: int, role: String, jersey = null) -> Dictionary:
	var s: Dictionary = AvatarModel.DEFAULTS.duplicate()
	var i := absi(index)
	s["height"] = AvatarModel.HEIGHTS[(i * 3 + 1) % AvatarModel.HEIGHTS.size()]
	s["build"] = AvatarModel.BUILDS[(i + 1) % AvatarModel.BUILDS.size()]
	s["skin"] = (i * 5 + 1) % AvatarModel.SKIN_COLORS.size()
	s["hair"] = (i * 2 + 1) % 6
	s["hair_color"] = (i * 3 + 2) % AvatarModel.HAIR_COLORS.size()
	var primary: int = KIT_BY_ROLE.get(role, KIT_OTHER)
	var secondary: int = SECONDARIES[i % SECONDARIES.size()]
	if secondary == primary:
		secondary = SECONDARIES[(i + 1) % SECONDARIES.size()]
	match str(jersey) if jersey != null else "":
		"sprint":
			primary = KIT_GREEN
			secondary = KIT_DARK
		"kom":
			primary = KIT_WHITE
			secondary = KIT_RED
	s["kit_primary"] = primary
	s["kit_secondary"] = secondary
	s["number"] = 0 if role == "ghost" else (i % AvatarModel.NUMBER_MAX) + 1
	return s


## `look` d'équipement par emplacement (equipment_meshes.gd LOOKS) du bot affiché à l'indice `index`.
static func looks_for(index: int, jersey = null) -> Dictionary:
	var i := absi(index)
	var kit: String = KIT_LOOKS[i % KIT_LOOKS.size()]
	match str(jersey) if jersey != null else "":
		"sprint": kit = "kit_plain"
		"kom": kit = "kit_polka"
	return {
		"frame": FRAMES[i % FRAMES.size()],
		"wheels": WHEELS[(i * 3 + 1) % WHEELS.size()],
		"helmet": HELMETS[(i + 2) % HELMETS.size()],
		"kit": kit,
		"socks": SOCKS[(i * 2) % SOCKS.size()],
		"glasses": GLASSES[(i + 1) % GLASSES.size()],
	}
