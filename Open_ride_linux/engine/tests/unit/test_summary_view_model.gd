extends SceneTree

## Tests unitaires sans écran du modèle de fin de séance (Lot N4).
## Lancement : godot --headless --path engine --script res://tests/unit/test_summary_view_model.gd

const SummaryViewModel := preload("res://scripts/summary_view_model.gd")
const MenuModel := preload("res://scripts/menu_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	var nodes_before := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	var vm = SummaryViewModel.new()

	# 1. Bilan v1 seul (4 champs) : 3 lignes et ligne FIT, aucune ligne vide ni « null »
	var v1_summary := {
		"duration_s": 1800,
		"distance_m": 15000,
		"avg_power_w": 200,
		"fit_path": "/home/user/OpenRide/session.fit"
	}
	var v1_lines: Array = vm.lines(v1_summary, "SIM", 250)
	_check(v1_lines.size() == 3, "bilan v1 seul : exactement 3 lignes retournées")
	var labels_v1 := []
	var has_null_v1 := false
	for l in v1_lines:
		labels_v1.append(l["label"])
		if str(l["value"]).to_lower() == "null" or str(l["value"]).strip_edges() == "":
			has_null_v1 = true
	_check(labels_v1 == ["Durée", "Distance", "Puissance moyenne"], "bilan v1 : ordre et libellés corrects")
	_check(not has_null_v1, "bilan v1 : aucune valeur null ou vide")

	# 2. Bilan enrichi complet : 10 lignes dans l'ordre fixé, 3 723 s -> « 1:02:03 », 12 345 m -> « 12,35 km »
	var full_summary := {
		"duration_s": 3723,
		"distance_m": 12345,
		"avg_power_w": 220,
		"np_w": 235,
		"intensity_factor": 0.85,
		"tss": 75,
		"elevation_gain_m": 350,
		"avg_cadence_rpm": 88,
		"avg_hr_bpm": 142,
		"max_power_w": 520,
		"fit_path": "/home/user/OpenRide/2026-10-25_test.fit"
	}
	var full_lines: Array = vm.lines(full_summary, "ERG", 280)
	_check(full_lines.size() == 10, "bilan complet : exactement 10 lignes")
	var expected_labels := [
		"Durée", "Distance", "Puissance moyenne", "Puissance normalisée",
		"IF", "TSS", "Dénivelé", "Cadence", "FC moyenne", "Puissance max"
	]
	var got_labels := []
	for l in full_lines:
		got_labels.append(l["label"])
	_check(got_labels == expected_labels, "bilan complet : 10 libellés dans l'ordre fixé")
	_check(full_lines[0]["value"] == "1:02:03", "durée de 3 723 s affichée « 1:02:03 »")
	_check(full_lines[1]["value"] == "12,35" and full_lines[1]["unit"] == "km", "distance de 12 345 m affichée « 12,35 km »")
	_check(full_lines[4]["value"] == "0,85", "IF affiché avec virgule française « 0,85 »")

	# 3. ERG avec 3 blocs à +2 %, −7 % et +12 % de la cible : couleurs vert, orange, rouge
	var erg_summary := {
		"blocks": [
			# Bloc 1 : cible 200 W, moy 204 W (+2.0 %) -> vert
			[1, 204.0, 200.0],
			# Bloc 2 : cible 200 W, moy 186 W (-7.0 %) -> orange
			[2, 186.0, 200.0],
			# Bloc 3 : cible 200 W, moy 224 W (+12.0 %) -> rouge
			[3, 224.0, 200.0]
		]
	}
	var blks: Array = vm.blocks(erg_summary)
	_check(blks.size() == 3, "ERG : 3 blocs traités")
	_check(blks[0]["color"] == "vert", "bloc +2 % : couleur vert")
	_check(blks[1]["color"] == "orange", "bloc −7 % : couleur orange")
	_check(blks[2]["color"] == "rouge", "bloc +12 % : couleur rouge")
	# Bloc sans cible connue (ancien journal) : cible null autorisée par le contrat v1.1 (§3, blocks)
	var free_blks: Array = vm.blocks({"blocks": [[1, 150.0, null], [2, 250.0, 250.0]]})
	_check(free_blks.size() == 2, "ERG : bloc à cible null gardé, les autres aussi")
	_check(free_blks[0]["color"] == "neutre" and free_blks[0]["delta_w"] == null, "bloc à cible null : couleur neutre, pas d'écart")
	_check(free_blks[1]["color"] == "vert", "bloc suivant le bloc à cible null : traité normalement")

	# 4. fit_path à null / vide : « Séance non enregistrée » ; chemin absolu : nom seul
	_check(vm.fit_line({}) == "Séance non enregistrée", "fit_line sans fit_path : « Séance non enregistrée »")
	_check(vm.fit_line({"fit_path": null}) == "Séance non enregistrée", "fit_line avec fit_path null : « Séance non enregistrée »")
	_check(vm.fit_line({"fit_path": ""}) == "Séance non enregistrée", "fit_line avec fit_path vide : « Séance non enregistrée »")
	_check(vm.fit_line({"fit_path": "/var/data/openride/ma_sortie.fit"}) == "Séance enregistrée : ma_sortie.fit", "fit_line Unix absolu : seul le nom de fichier apparaît")
	_check(vm.fit_line({"fit_path": "C:\\Users\\cycliste\\OpenRide\\autre_sortie.fit"}) == "Séance enregistrée : autre_sortie.fit", "fit_line Windows absolu : seul le nom de fichier apparaît")

	# 5. Écran de menu et intégration avec menu_model.gd (« Quitter » demande confirmation)
	var scr: Dictionary = vm.menu_screen()
	_check(scr.get("id") == "summary", "écran menu : identifiant 'summary'")
	_check(scr.has("items") and scr["items"].size() == 3, "écran menu : 3 entrées (nouvelle séance, bilan détaillé, quitter)")

	var menu = MenuModel.new()
	vm.attach_to_menu(menu)
	_check(menu._screens.has("summary"), "écran attaché dans menu_model")
	menu._open("summary")
	_check(menu.state()["screen"] == "summary", "ouverture de l'écran summary dans menu_model")

	# Valider 'quit' depuis summary déclenche la confirmation (règle K5)
	var act_quit := vm.handle_action("quit", menu)
	_check(act_quit.is_empty(), "validation de quitter : aucune action immédiate")
	_check(menu.state()["screen"] == "confirm", "quitter passe par l'écran de confirmation")
	_check(menu.state()["focus"] == 0, "écran de confirmation : focus sur 'Non'")

	# Refus de confirmation : retour à summary
	menu.handle("A_LONG") # valider 'Non'
	_check(menu.state()["screen"] == "summary", "refus confirmation : retour sur l'écran summary")

	# Acceptation de confirmation : produit l'action quit
	vm.handle_action("quit", menu) # ouvre à nouveau confirm
	menu.handle("PLUS_SHORT") # déplacement sur 'Oui'
	var confirmed_act := menu.handle("A_LONG") # valider 'Oui'
	_check(confirmed_act.get("action") == {"action": "quit"}, "acceptation confirmation : action 'quit' émise")

	# 6. Performance : aucun nœud créé
	var nodes_after := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	_check(nodes_after == nodes_before, "aucun nœud créé (Performance.OBJECT_NODE_COUNT constant)")

	print("test_summary_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
