extends SceneTree

## Tests sans écran de la règle commune des Réglages (lot NI2, audit des éléments inutiles du 21 novembre) :
## réglages de leur propre écran (groupe `screen`) absents de « Réglages » mais lus par leur écran, lignes
## dépendantes (`when`) cachées quand elles sont sans effet et revenues tout de suite, choix à une seule valeur
## cachés, sous-écran vide omis.
## Lancement : godot --headless --path engine --script res://tests/unit/test_settings_rules.gd

const SettingsViewModel := preload("res://scripts/settings_view_model.gd")

const WIND_SET := [{"key": "wind.mode", "in": ["fixed", "gusty"]}]
const ITEMS := [
	{"key": "depart.mode", "label": "Départ", "group": "ride", "type": "choice", "value": "pedalage",
		"choices": ["pedalage", "immediat"], "applies": "next_session"},
	{"key": "depart.cadence_rpm", "label": "Cadence de départ", "group": "ride", "type": "int", "value": 30,
		"min": 10, "max": 90, "step": 5, "unit": "tr/min", "applies": "next_session",
		"when": [{"key": "depart.mode", "in": ["pedalage"]}]},
	{"key": "render.theme", "label": "Thème", "group": "graphics", "type": "choice", "value": "default",
		"choices": ["default"], "applies": "now"},
	{"key": "render.seasons", "label": "Saisons", "group": "graphics", "type": "choice", "value": "off",
		"choices": ["off", "date"], "applies": "now"},
	{"key": "render.day_night", "label": "Jour et nuit", "group": "graphics", "type": "choice", "value": "off",
		"choices": ["off", "real"], "applies": "now"},
	{"key": "render.month", "label": "Mois", "group": "graphics", "type": "choice", "value": "pc",
		"choices": ["pc", "may"], "applies": "now",
		"when": [{"key": "render.seasons", "in": ["date"]}, {"key": "render.day_night", "in": ["theme", "real", "accelerated"]}]},
	{"key": "wind.mode", "label": "Vent", "group": "wind", "type": "choice", "value": "off",
		"choices": ["off", "fixed", "gusty", "theme"], "applies": "next_session"},
	{"key": "wind.speed_kmh", "label": "Force du vent", "group": "wind", "type": "int", "value": 15,
		"min": 0, "max": 60, "step": 5, "unit": "km/h", "applies": "next_session", "when": WIND_SET},
	{"key": "wind.gust_pct", "label": "Rafales", "group": "wind", "type": "int", "value": 30,
		"min": 0, "max": 100, "step": 10, "unit": "%", "applies": "next_session",
		"when": [{"key": "wind.mode", "in": ["gusty"]}]},
	{"key": "trainer.control", "label": "Pilotage du trainer", "group": "advanced", "type": "choice", "value": "sim",
		"choices": ["resistance", "sim"], "applies": "next_session"},
	{"key": "survivor.opponents", "label": "Survivant : adversaires", "group": "screen", "type": "int", "value": 4,
		"min": 2, "max": 11, "step": 1, "unit": "", "applies": "next_session"},
	{"key": "coach.objectif", "label": "Conseil : objectif", "group": "screen", "type": "choice", "value": "endurance",
		"choices": ["endurance", "courses"], "applies": "next_session"},
	{"key": "x.future", "label": "Futur", "group": "ride", "type": "int", "value": 1, "min": 0, "max": 2, "step": 1,
		"unit": "", "applies": "next_session", "when": [{"key": "x.inconnu", "in": ["on"]}]},
]

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _ids(vm, group: String) -> Array:
	return vm.menu_items(group).map(func(it): return str(it["id"]))


func _model():
	var vm = SettingsViewModel.new()
	vm.on_settings({"items": ITEMS.duplicate(true)})
	return vm


func _test_screen_group() -> void:
	var vm = _model()
	var groups: Array = vm.group_items().map(func(it): return str(it["id"]))
	_check(groups == ["group:ride", "group:graphics", "group:wind", "group:advanced"],
		"réglages des écrans de mode absents de « Réglages », pas d'« Autres réglages » (%s)" % str(groups))
	_check(SettingsViewModel.group_of(vm.item("survivor.opponents")) == "screen", "groupe screen reconnu")
	_check(int(vm.item("survivor.opponents")["value"]) == 4 and vm.begin("survivor.opponents"),
		"réglage d'un écran de mode toujours lu et modifiable par son écran")
	vm.cancel()
	var detail := ""
	for it in vm.group_items():
		if it["id"] == "group:ride":
			detail = str(it["detail"])
	_check(detail == "Départ, Cadence de départ, Futur", "détail du sous-écran : lignes montrées seulement (%s)" % detail)


func _test_when_rule() -> void:
	var vm = _model()
	_check(_ids(vm, "wind") == ["set:wind.mode"], "vent coupé : force et rafales cachées (%s)" % str(_ids(vm, "wind")))
	_check(not _ids(vm, "graphics").has("set:render.month"), "saisons et jour-nuit coupés : mois caché")
	_check(not _ids(vm, "graphics").has("set:render.theme"), "un seul thème : ligne cachée")
	_check(_ids(vm, "ride").has("set:depart.cadence_rpm"), "départ au pédalage : cadence de départ montrée")
	_check(_ids(vm, "ride").has("set:x.future"), "dépendance d'un réglage inconnu : ligne gardée")
	# Modification en cours : la liste suit la valeur choisie avant même l'enregistrement.
	vm.begin("wind.mode")
	vm.step(1)   # off → fixed
	_check(_ids(vm, "wind") == ["set:wind.mode", "set:wind.speed_kmh"], "vent constant : force montrée, rafales cachées")
	vm.step(1)   # fixed → gusty
	_check(_ids(vm, "wind") == ["set:wind.mode", "set:wind.speed_kmh", "set:wind.gust_pct"], "vent en rafales : tout montré")
	var act: Dictionary = vm.commit()
	_check(act == {"action": "set_setting", "key": "wind.mode", "value": "gusty"}, "enregistré (%s)" % str(act))
	_check(_ids(vm, "wind").size() == 3, "après l'enregistrement : lignes toujours montrées")
	vm.begin("wind.mode")
	vm.step(1)   # gusty → theme
	vm.cancel()
	_check(_ids(vm, "wind").size() == 3, "Y : valeur d'avant, lignes d'avant")
	vm.item("depart.mode")["value"] = "immediat"
	_check(not _ids(vm, "ride").has("set:depart.cadence_rpm"), "départ immédiat : cadence de départ cachée")
	vm.item("render.day_night")["value"] = "real"
	_check(_ids(vm, "graphics").has("set:render.month"), "jour et nuit à l'heure du PC : mois montré (une condition suffit)")
	_check(int(vm.item("depart.cadence_rpm")["value"]) == 30, "valeur d'une ligne cachée gardée")


func _init() -> void:
	_test_screen_group()
	_test_when_rule()
	print("test_settings_rules : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
