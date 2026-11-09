extends RefCounted

## Noms affichés des épreuves de piste et de leurs réglages (série VD, lots VD9 et VD10), communs au HUD de piste
## (track_hud_model.gd) et à l'écran Prêt du vélodrome (menu_model.gd). Les identifiants et les valeurs
## permises viennent du core (`hello_ack.config.track`, `track.menu_options`) ; ce fichier ne donne que les mots.
## Pas de class_name : preload("res://scripts/track/track_names.gd").

const EVENTS := {"free": "Séance libre", "pursuit": "Poursuite individuelle", "kilo": "Kilomètre · départ arrêté",
	"500": "500 m · départ arrêté", "flying_200": "200 m lancé", "hour": "Record de l'heure", "scratch": "Scratch",
	"points": "Course aux points", "tempo": "Tempo", "elimination": "Élimination", "keirin": "Keirin",
	"omnium": "Omnium", "team_sprint": "Vitesse par équipes", "team_pursuit": "Poursuite par équipes",
	"madison": "Américaine"}
const TEAM_EVENTS := ["team_sprint", "team_pursuit", "madison"]
const OPTIONS := {"opponents": "Adversaires", "laps": "Tours", "distance_m": "Distance", "place": "Ta place dans l'équipe",
	"relay_laps": "Relais", "bot_tactics": "Tactique des bots"}
const TACTICS := {"none": "aucune", "simple": "simple", "full": "complète"}


static func event_name(id: String) -> String:
	return str(EVENTS.get(id, id))


## Nom d'un réglage ; « Équipes adverses » pour les adversaires d'une épreuve par équipes.
static func option_name(event_id: String, option_id: String) -> String:
	if option_id == "opponents" and event_id in TEAM_EVENTS:
		return "Équipes adverses"
	return str(OPTIONS.get(option_id, option_id))


## Valeur d'un réglage telle qu'affichée.
static func value_text(option_id: String, value) -> String:
	match option_id:
		"distance_m":
			return ("%d km" % int(round(float(value) / 1000.0))) if float(value) >= 1000.0 else "%d m" % int(value)
		"place":
			return "1er" if int(value) == 1 else "%de" % int(value)
		"relay_laps":
			return "½ tour" if is_equal_approx(float(value), 0.5) else "%s tour%s" % [str(int(value)), "s" if float(value) > 1.0 else ""]
		"bot_tactics":
			return str(TACTICS.get(str(value), str(value)))
		"opponents":
			return "aucun" if int(value) == 0 else str(int(value))
	return str(int(value)) if value is float and is_equal_approx(value, round(value)) else str(value)
