extends SceneTree

## Maquettes de la séance conseillée (série CO, lot CO4) au rendu réel du menu : la vraie vue des menus
## (menu_view.gd, thème ui_theme.gd, carte de détail, bandeau des boutons) reçoit les écrans prévus pour CO5,
## remplis avec un conseil fabriqué (aucune donnée personnelle). Rien n'est branché au core : ces écrans
## servent à la validation du propriétaire avant tout code d'affichage (plan docs/5.0/PLAN_SERIE_CO.md §6).
##
##   xvfb-run -a -s "-screen 0 1280x720x24" $GODOT --path engine --rendering-driver vulkan \
##     --rendering-method forward_plus --audio-driver Dummy --resolution 1280x720 \
##     --script res://tests/maquette_conseil.gd -- --out DOSSIER
##
## Écrit DOSSIER/<écran>_<largeur>x<hauteur>.png pour chaque écran de SCREENS.

const MenuView := preload("res://scripts/menu_view.gd")

const SETTLE_FRAMES := 8


static func _it(id: String, label: String, detail := "", enabled := true) -> Dictionary:
	return {"id": id, "label": label, "detail": detail, "enabled": enabled}


static func _bar(id: String, label: String, detail: String, pct: int) -> Dictionary:
	return {"id": id, "label": label, "detail": detail, "enabled": true, "bar": pct}


## Écrans de CO5 (menu_flow.gd les produira depuis le message `coach`), dans l'ordre de la planche.
static func screens() -> Array:
	var reason := "9 % de ton temps en aérobie intense sur 4 semaines (cible 16 %), dernière séance de ce type\nil y a 6 jours, forme +4."
	return [
		{"file": "01_accueil", "menu": {"screen": "home", "title": "OpenRide", "focus": 1, "items": [
			_it("profile", "Profil : Cycliste A"),
			_it("coach", "Séance conseillée", "aérobie intense · 60 min"),
			_it("world", "Parcours : Côte des vignes"),
			_it("ride", "Rouler", "parcours libre, bots"),
			_it("erg", "Entraînement ERG", "séances de la bibliothèque"),
			_it("rogue", "Cyber-Rogue"),
			_it("plan", "Plan d'entraînement", "aucun plan actif"),
			_it("history", "Historique", "séances, semaines, tests de FTP"),
			_it("settings", "Réglages"),
			_it("quit", "Quitter")]}},
		{"file": "02_conseil", "menu": {"screen": "coach", "title": "Séance conseillée : aérobie intense",
			"status": "Pourquoi : " + reason, "focus": 0, "items": [
				_it("coach_workout", "Lancer l'entraînement", "60 min"),
				_it("coach_race", "Lancer la course", "60 min"),
				_it("coach_other", "Autre séance", "2 de plus"),
				_it("coach_need", "Autre besoin"),
				_it("coach_watch", "Ma montre", "aucune"),
				_it("coach_race_date", "Prochaine course", "aucune"),
				_it("coach_objective", "Objectif", "Endurance"),
				_it("coach_time", "Temps disponible", "60 min"),
				_it("coach_detail", "Détail du calcul")],
			"card": {"title": "Entraînement conseillé", "name": "Seuil 2 × 20", "tiles": [
				{"label": "Durée", "value": "60", "unit": "min"}, {"label": "TSS estimé", "value": "72"},
				{"label": "Zone", "value": "Z4", "gold": true}],
				"lines": ["Aérobie intense : zones Z3 à Z5,", "75 à 120 % de la FTP.",
					"Règle R6 · objectif Endurance.",
					"À côté : « Lancer la course », 4 bots à 95 %,", "côte de 6 min, 4 tours."]}}},
		{"file": "03_conseil_course", "menu": {"screen": "coach", "title": "Séance conseillée : aérobie intense",
			"status": "Pourquoi : " + reason, "focus": 1, "items": [
				_it("coach_workout", "Lancer l'entraînement", "60 min"),
				_it("coach_race", "Lancer la course", "60 min"),
				_it("coach_other", "Autre séance", "2 de plus"),
				_it("coach_need", "Autre besoin"),
				_it("coach_watch", "Ma montre", "aucune"),
				_it("coach_race_date", "Prochaine course", "aucune"),
				_it("coach_objective", "Objectif", "Endurance"),
				_it("coach_time", "Temps disponible", "60 min"),
				_it("coach_detail", "Détail du calcul")],
			"card": {"title": "Course contre des bots", "name": "Côte des vignes · 4 tours", "tiles": [
				{"label": "Bots", "value": "4"}, {"label": "Niveau", "value": "95", "unit": "%"},
				{"label": "Dans le besoin", "value": "79", "unit": "%", "gold": true}],
				"lines": ["Côte de 6 min au seuil à chaque tour ;", "bots tenus de 90 à 105 % de la FTP en montée.",
					"Simulée à tes valeurs : 79 % du temps", "de l'entraînement dans les zones du besoin.",
					"Difficulté de la pente : la tienne (50 %)."]}}},
		{"file": "04_detail", "menu": {"screen": "coach_detail", "title": "Détail du calcul",
			"status": "Répartition du temps sur 4 semaines, en regard de ta cible (objectif Endurance).", "focus": 1,
			"items": [
				_bar("d_light", "Léger", "85 %", 85),
				_bar("d_intense", "Intense", "9 %", 9),
				_bar("d_anaerobic", "Anaérobie", "6 %", 6),
				_it("d_form", "Forme", "+4"),
				_it("d_hard", "Séance dure", "il y a 6 j"),
				_it("d_profile", "Profil de puissance", "5 min"),
				_it("d_ftp", "FTP", "250 W"),
				_it("d_races", "Dernières courses", "1"),
				_it("d_rule", "Règle", "R6")],
			"card": {"title": "Aérobie intense", "name": "Zones Z3 à Z5", "tiles": [
				{"label": "Part", "value": "9", "unit": "%"}, {"label": "Cible", "value": "16", "unit": "%"},
				{"label": "Retard", "value": "7", "unit": "pts", "gold": true}],
				"lines": ["Le plus grand retard décide (règle R6).", "Dernière séance de ce type il y a 6 jours ;",
					"1 séance dure cette semaine (2 au plus).", "Courses : 05/11 Dernier survivant, 3e,",
					"lâché en montée."]}}},
		{"file": "05_autre_besoin", "menu": {"screen": "coach_need", "title": "Choisir un autre besoin",
			"status": "Le conseil du jour reste proposé en premier ; ton choix ne change rien au calcul.", "focus": 2,
			"items": [
				_it("need_light", "Aérobie léger", "Z1–Z2"),
				_it("need_intense", "Aérobie intense", "conseillé"),
				_it("need_anaerobic", "Anaérobie", "Z6–Z7"),
				_it("need_recovery", "Récupération", "40 min"),
				_it("need_ftp_test", "Test de FTP", "30 min")],
			"card": {"title": "Anaérobie", "name": "Au-dessus de 120 % de la FTP", "tiles": [
				{"label": "Séance", "value": "8 × 30 s"}, {"label": "Durée", "value": "45", "unit": "min"}],
				"lines": ["Ou en jeu : Dernier survivant,", "une arche par kilomètre, 4 adversaires.",
					"Règle CH : le conseil du jour reste", "en première autre idée."]}}},
		{"file": "06_prochaine_course", "menu": {"screen": "coach_race_date", "title": "Ma prochaine course",
			"status": "Deux jours avant : activation courte. Le lendemain : récupération.", "focus": 0,
			"items": [
				_it("race_date", "Date", "sam. 14/11"),
				_it("race_kind", "Type", "Championnat"),
				_it("race_save", "Enregistrer"),
				_it("race_clear", "Effacer", "", false)],
			"card": {"title": "Course annoncée", "name": "Dans 7 jours", "tiles": [
				{"label": "Activation", "value": "12/11"}, {"label": "Récupération", "value": "15/11"}],
				"lines": ["Types : course ou manche de championnat.", "Gardée dans ton profil jusqu'à son jour ;",
					"un futur championnat l'écrira lui-même."]}}},
		{"file": "07_montre", "menu": {"screen": "coach_watch", "title": "Suggestion de ma montre",
			"status": "Recopie l'entraînement du jour de ta montre Garmin. OpenRide ne se connecte pas à Garmin Connect.",
			"focus": 0, "items": [
				_it("watch_type", "Type", "Seuil"),
				_it("watch_time", "Durée", "50 min"),
				_it("watch_target", "Puissance cible", "aucune"),
				_it("watch_save", "Enregistrer"),
				_it("watch_clear", "Effacer", "", false)],
			"card": {"title": "Ce que fera le conseil", "name": "Seuil → aérobie intense", "tiles": [
				{"label": "Règle", "value": "RG"}, {"label": "Zone", "value": "Z4"},
				{"label": "Durée", "value": "50", "unit": "min"}],
				"lines": ["Passe avant les autres règles, pour la journée.", "Une course hier ou dans 2 jours s'affiche",
					"en note, sans l'annuler.", "Types : repos, récupération, fond, tempo,", "seuil, VO2 max, anaérobie, sprint."]}}},
	]


func _out_dir() -> String:
	var args := OS.get_cmdline_user_args()
	var i := args.find("--out")
	return args[i + 1] if i >= 0 and i + 1 < args.size() else "user://maquettes_conseil"


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var out := _out_dir()
	DirAccess.make_dir_recursive_absolute(out)
	var bg := ColorRect.new()
	bg.color = Color(0.09, 0.13, 0.12)   # place de la vue 3D derrière le voile des menus
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_child(bg)
	var view = MenuView.new()
	root.add_child(view)
	view.visible = true
	var win := root.get_window().size
	for s in screens():
		view.update_display(s["menu"], {"trainer_status": "CONNECTED", "input_status": "CONNECTED"}, {}, false)
		for i in SETTLE_FRAMES:
			await process_frame
		await RenderingServer.frame_post_draw
		var img := root.get_texture().get_image()
		var path := "%s/%s_%dx%d.png" % [out, s["file"], win.x, win.y]
		print("maquette : ", path, " -> ", img.save_png(path))
	quit(0)
