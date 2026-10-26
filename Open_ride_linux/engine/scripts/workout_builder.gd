extends RefCounted

## Création d'un entraînement par intervalles depuis le menu ERG (lot N16), sans nœud.
##
## Sept paramètres réglés au Click (échauffement, répétitions, effort et récupération en durée et en
## % de la FTP, retour au calme) ; `to_zwo()` écrit le fichier `.zwo` (blocs Warmup, IntervalsT,
## Cooldown) que main.gd enregistre dans ~/OpenRide/Workouts/ sous `workout_id()` + « .zwo ».
## Les puissances sont en % de la FTP : l'entraînement suit la FTP des réglages (lot O4).
## Pas de class_name : charger par preload("res://scripts/workout_builder.gd").

const SCREEN := "workout_create"
## Préfixe des clés de paramètre dans l'écran de modification (settings_view_model.gd).
const KEY_PREFIX := "workout."

## {key, label, value, min, max, step, format} ; format « min » (minutes), « s » (durée en secondes)
## ou « pct » (% de la FTP), « n » (nombre).
const PARAMS := [
	{"key": "warmup_min", "label": "Échauffement", "value": 10, "min": 0, "max": 30, "step": 1, "format": "min"},
	{"key": "reps", "label": "Répétitions", "value": 5, "min": 1, "max": 20, "step": 1, "format": "n"},
	{"key": "on_s", "label": "Effort", "value": 240, "min": 15, "max": 1200, "step": 15, "format": "s"},
	{"key": "on_pct", "label": "Puissance de l'effort", "value": 105, "min": 50, "max": 200, "step": 5, "format": "pct"},
	{"key": "off_s", "label": "Récupération", "value": 180, "min": 15, "max": 1200, "step": 15, "format": "s"},
	{"key": "off_pct", "label": "Puissance de la récupération", "value": 55, "min": 30, "max": 100, "step": 5, "format": "pct"},
	{"key": "cooldown_min", "label": "Retour au calme", "value": 10, "min": 0, "max": 30, "step": 1, "format": "min"},
]

var values := {}


func _init() -> void:
	reset()


func reset() -> void:
	values = {}
	for p in PARAMS:
		values[p["key"]] = p["value"]


static func param(key: String) -> Dictionary:
	for p in PARAMS:
		if p["key"] == key:
			return p
	return {}


## Durée lisible : « 4 min », « 4 min 30 s », « 45 s ».
static func format_duration(seconds: int) -> String:
	var m := seconds / 60
	var s := seconds % 60
	if m == 0:
		return "%d s" % s
	return "%d min" % m if s == 0 else "%d min %d s" % [m, s]


static func format_param(p: Dictionary, value) -> String:
	match str(p.get("format", "")):
		"min":
			return "%d min" % int(value) if int(value) > 0 else "aucun"
		"s":
			return format_duration(int(value))
		"pct":
			return "%d %% de la FTP" % int(value)
	return str(int(value))


## Fixe un paramètre (borné) ; faux si la clé est inconnue.
func set_value(key: String, value) -> bool:
	var p := param(key)
	if p.is_empty():
		return false
	values[key] = clampi(int(value), int(p["min"]), int(p["max"]))
	return true


func duration_s() -> int:
	return int(values["warmup_min"]) * 60 + int(values["reps"]) * (int(values["on_s"]) + int(values["off_s"])) \
		+ int(values["cooldown_min"]) * 60


## Nom affiché : « Intervalles 5 × 4 min à 105 % ».
func workout_name() -> String:
	return "Intervalles %d × %s à %d %%" % [int(values["reps"]), format_duration(int(values["on_s"])),
		int(values["on_pct"])]


## Identifiant (nom du fichier sans extension) : « intervalles_5x240s_105 » ; mêmes réglages, même fichier.
func workout_id() -> String:
	return "intervalles_%dx%ds_%d" % [int(values["reps"]), int(values["on_s"]), int(values["on_pct"])]


## Éléments de l'écran « Créer un entraînement » : les paramètres (id « param:clé ») puis « Enregistrer ».
func menu_items() -> Array:
	var out: Array = []
	for p in PARAMS:
		out.append({"id": "param:" + str(p["key"]), "label": "%s : %s" % [p["label"],
			format_param(p, values[p["key"]])]})
	out.append({"id": "save", "label": "Enregistrer et choisir",
		"detail": "%s, %d min" % [workout_name(), int(round(duration_s() / 60.0))]})
	return out


## Paramètre prêt pour l'écran de modification de settings_view_model.gd (clé préfixée).
func edit_item(key: String) -> Dictionary:
	var p := param(key)
	if p.is_empty():
		return {}
	return {"key": KEY_PREFIX + key, "label": p["label"], "type": "int", "value": values[key],
		"min": p["min"], "max": p["max"], "step": p["step"], "unit": "", "format": p["format"]}


static func _f(x: float) -> String:
	return "%.2f" % x


## Contenu du fichier `.zwo` (XML de Zwift, lu par workout.py du core).
func to_zwo() -> String:
	var lines := PackedStringArray([
		"<workout_file>",
		"  <author>OpenRide</author>",
		"  <name>%s</name>" % workout_name(),
		"  <description>Créé dans le menu d'OpenRide.</description>",
		"  <sportType>bike</sportType>",
		"  <workout>"])
	if int(values["warmup_min"]) > 0:
		lines.append("    <Warmup Duration=\"%d\" PowerLow=\"0.50\" PowerHigh=\"0.75\"/>" % (int(values["warmup_min"]) * 60))
	lines.append("    <IntervalsT Repeat=\"%d\" OnDuration=\"%d\" OffDuration=\"%d\" OnPower=\"%s\" OffPower=\"%s\"/>" % [
		int(values["reps"]), int(values["on_s"]), int(values["off_s"]), _f(values["on_pct"] / 100.0),
		_f(values["off_pct"] / 100.0)])
	if int(values["cooldown_min"]) > 0:
		lines.append("    <Cooldown Duration=\"%d\" PowerLow=\"0.65\" PowerHigh=\"0.45\"/>" % (int(values["cooldown_min"]) * 60))
	lines.append_array(["  </workout>", "</workout_file>", ""])
	return "\n".join(lines)
