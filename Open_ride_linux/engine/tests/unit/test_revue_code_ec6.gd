extends SceneTree

## Lot EC6, menu du monde ouvert (revue de code, vague 3, E3-01 à E3-03), sans écran : plus de 8 lieux
## trouvés (le choix reste visible, « n / total »), carte d'un lieu quitté pendant le chargement (réponse
## jetée), noms longs d'OpenStreetMap sur une ligne, liste qui reste au-dessus du bandeau des boutons.
## Lancement : godot --headless --path engine --script res://tests/unit/test_revue_code_ec6.gd

const Model := preload("res://scripts/world_menu_model.gd")
const View := preload("res://scripts/world_menu_view.gd")
const UiTheme := preload("res://scripts/ui_theme.gd")

## Fenêtre de référence (project.godot).
const SCREEN_H := 720.0

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
	call_deferred("_run")


func _places(n: int, long_names: bool = false) -> Array:
	var out: Array = []
	for i in range(n):
		var name := "Lieu %02d" % (i + 1)
		if long_names:
			name = "Lieu %02d de la Grande Montagne du Haut-Pays, Annecy, Haute-Savoie, Auvergne-Rhône-Alpes, France" % (i + 1)
		out.append({"name": name, "kind": "village", "lat": 45.0 + i * 0.1, "lon": 6.0 + i * 0.1,
			"cached": false, "source": "nominatim"})
	return out


func _run() -> void:
	_e3_01_results_window()
	_e3_02_stale_map()
	_e3_03_long_names()
	print("test_revue_code_ec6 : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


## E3-01 : 20 lieux reçus, le choix descend au 13e : il reste écrit avec le repère, « 13 / 20 » le dit,
## et A ouvre la carte du lieu affiché.
func _e3_01_results_window() -> void:
	var v = View.new()
	root.add_child(v)
	v.open()
	v.vm.type_text("li")
	v.vm.on_places(_places(20))
	v.update_display()
	_check(v.body_label.text.contains("▶ Lieu 01") and v.body_label.text.contains("1 / 20")
		and not v.body_label.text.contains("Lieu 09"), "20 lieux : 8 lignes et « 1 / 20 »")
	for i in range(12):
		v.vm.handle("PLUS_SHORT")
	v.update_display()
	var w: Vector2i = v.results_window()
	_check(w.y - w.x == View.MAX_RESULTS and w.x <= 12 and 12 < w.y, "fenêtre de 8 lignes qui contient le choix")
	_check(v.body_label.text.contains("▶ Lieu 13") and v.body_label.text.contains("13 / 20")
		and not v.body_label.text.contains("Lieu 01"), "13e lieu choisi : écrit avec le repère et « 13 / 20 »")
	for i in range(30):
		v.vm.handle("PLUS_SHORT")
	v.update_display()
	_check(v.body_label.text.contains("▶ Lieu 20") and v.body_label.text.contains("20 / 20"), "dernier lieu : visible")
	v.vm.place_index = 12
	v.vm.handle("A_SHORT")
	_check(v.vm.state == Model.MAP and is_equal_approx(v.vm.map_lat, 46.2), "A : carte du lieu affiché")
	# Saisie à la grille : quatre lieux et le nombre total ; huit lieux ou moins sans compteur.
	v.vm.reset()
	v.vm.handle("Z_SHORT")
	v.vm.on_places(_places(20))
	v.update_display()
	_check(v.vm.typing and v.body_label.text.contains("Lieu 03") and not v.body_label.text.contains("Lieu 04")
		and v.body_label.text.contains("20 lieux en tout"), "saisie : 3 lieux et « 20 lieux en tout »")
	v.vm.on_places(_places(3))
	v.update_display()
	_check(not v.body_label.text.contains("en tout"), "3 lieux en saisie : pas de compteur")
	v.vm.handle("A_LONG")
	v.update_display()
	_check(not v.vm.typing and not v.body_label.text.contains(" / "), "3 lieux en liste : pas de compteur")
	v.queue_free()


## E3-02 : Y pendant « Chargement de la carte… », autre lieu, la réponse du premier arrive en dernier.
func _e3_02_stale_map() -> void:
	var m = Model.new()
	m.reset()
	var a1: Dictionary = m.handle("A_SHORT")
	_check(a1.get("action") == "world_map" and m.map_request == -1, "carte demandée : identifiant remis à inconnu")
	m.map_request = 10                       # posé par main.gd (send_command)
	var lat1: float = m.map_lat
	var lon1: float = m.map_lon
	m.handle("Y_SHORT")
	m.handle("RIGHT_SHORT")                  # globe tourné de 10°
	m.handle("A_SHORT")
	m.map_request = 11
	var road1 := [{"c": "t", "xz": [3000, 3000, 3500, 3000]}]
	m.on_map({"lat": lat1, "lon": lon1, "roads": road1}, 10)
	_check(not m.map_ready and m.roads.is_empty(), "réponse de la carte quittée : jetée")
	m.on_map({"lat": lat1, "lon": lon1, "roads": road1}, -1)
	_check(not m.map_ready, "sans identifiant, centre d'un autre lieu : jetée")
	var road2 := [{"c": "t", "xz": [0, 0, 500, 0]}]
	m.on_map({"lat": m.map_lat, "lon": m.map_lon, "roads": road2}, 11)
	_check(m.map_ready and m.roads == road2 and m.cursor.length() < 1.0, "réponse de la carte affichée : prise")
	m.handle("A_SHORT")
	var start: Dictionary = m.handle("A_SHORT")
	var args: Dictionary = start.get("args", {})
	_check(start.get("action") == "start_open_world" and absf(float(args["lon"]) - m.map_lon) < 1e-3
		and absf(float(args["lat"]) - m.map_lat) < 1e-3, "départ au lieu choisi, pas décalé par les routes du premier")
	# Core ou essai sans identifiant ni centre : réponse prise (comportement d'avant).
	var m2 = Model.new()
	m2.reset()
	m2.handle("A_SHORT")
	m2.on_map({"roads": road2})
	_check(m2.map_ready, "réponse sans identifiant ni centre : prise")


## E3-03 : noms complets d'OpenStreetMap ramenés à une ligne ; liste et explication au-dessus du bandeau.
func _e3_03_long_names() -> void:
	var long := "Sevrier, Annecy, Haute-Savoie, Auvergne-Rhône-Alpes, France métropolitaine, 74320, France"
	_check(View.short_name(long) == "Sevrier, Annecy", "nom complet : jusqu'à la deuxième virgule")
	_check(View.short_name("Mont Ventoux") == "Mont Ventoux", "nom court : gardé")
	var one := View.short_name("Saint-Jean-de-Maurienne-sur-Arvan-les-Hauts-du-Col, Savoie, France")
	_check(one.length() <= View.RESULT_NAME_MAX and one.ends_with("…"), "premier morceau trop long : coupé par « … »")
	var v = View.new()
	root.add_child(v)
	v.open()
	v.vm.type_text("li")
	var many := _places(50, true)
	for p in many:
		p["cached"] = true                   # « (en cache) » en plus : la ligne la plus longue
	v.vm.on_places(many)
	for typing in [false, true]:
		v.vm.typing = typing
		v.update_display()
		var lines: PackedStringArray = v.body_label.text.split("\n")
		var longest := 0
		var grid: Array = v.grid_lines() if typing else []
		for l in lines:
			if not grid.has(l):
				longest = maxi(longest, l.length())
		var rows := 1 + (v.grid_lines().size() if typing else 0) + (View.MAX_RESULTS_TYPING if typing else View.MAX_RESULTS) + 1
		_check(lines.size() == rows and longest <= 48, "%s : %d lignes courtes (%d caractères au plus)"
			% ["saisie" if typing else "liste", lines.size(), longest])
		_check(v.body_label.get_line_count() == lines.size(), "%s : aucune ligne coupée en deux (%d lignes dessinées)"
			% ["saisie" if typing else "liste", v.body_label.get_line_count()])
		# Hauteur réelle des libellés (police du thème) : explication au-dessus du bandeau des boutons.
		var body_h: float = v.body_label.get_line_height() * v.body_label.get_line_count()
		var help_lines := ceilf(v.help_label.get_theme_font("font").get_string_size(v.help_label.text,
			HORIZONTAL_ALIGNMENT_LEFT, -1, UiTheme.HELP_SIZE).x / 440.0) + 1.0
		var bottom: float = 90.0 + body_h + 18.0 + help_lines * v.help_label.get_line_height()
		_check(bottom <= SCREEN_H - UiTheme.HELP_H, "%s : bas de l'explication à %d px, bandeau à %d px"
			% ["saisie" if typing else "liste", int(bottom), int(SCREEN_H - UiTheme.HELP_H)])
	v.queue_free()
