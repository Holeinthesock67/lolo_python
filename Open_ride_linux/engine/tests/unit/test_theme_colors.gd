extends SceneTree

## Couleurs du thème (lot X38) : aucune couleur écrite en dur dans les scripts d'interface, hors de
## `ui_theme.gd`. Scripts lus : tout script qui charge `ui_theme.gd`, plus `EXTRA` (vues sans couleur
## propre ou qui prennent leurs couleurs du thème sans le charger directement). Refusés : `Color(` suivi
## d'un nombre, `Color8(`, `Color.html(`, `Color.from_hsv(`…, constantes nommées `Color.RED`…
## Permis : `Color(UiTheme.X, alpha)` (couleur du thème, opacité changée) et `ALLOWED` ci-dessous.
## Le message donne le fichier, la ligne et la couleur du thème la plus proche.
## Lancement : godot --headless --path engine --script res://tests/unit/test_theme_colors.gd


const SCRIPTS_DIR := "res://scripts"
const EXTRA := ["banner.gd", "bots_view_model.gd", "ui_icons.gd"]
## Seule exception : le transparent, qui n'est la couleur d'aucun rôle.
const ALLOWED := ["Color.TRANSPARENT"]
const PATTERN := "Color\\(\\s*-?[0-9.]|Color8\\(|Color\\.(html|from_hsv|from_ok_hsl|from_rgbe9995|from_string)\\(|Color\\.[A-Z][A-Z_]+\\b"

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		push_error("[ÉCHEC] " + msg)
		print("[ÉCHEC] ", msg)


func _init() -> void:
	_test_scanner()
	_test_ui_scripts()
	print("test_theme_colors : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


## Scripts d'interface : ceux qui chargent ui_theme.gd, plus EXTRA.
static func ui_scripts() -> Array:
	var out: Array = []
	for f in DirAccess.get_files_at(SCRIPTS_DIR):
		if not f.ends_with(".gd") or f == "ui_theme.gd":
			continue
		var src := FileAccess.get_file_as_string(SCRIPTS_DIR + "/" + f)
		if src.contains("res://scripts/ui_theme.gd") or f in EXTRA:
			out.append(f)
	out.sort()
	return out


## Code d'une ligne sans son commentaire (un `#` hors d'une chaîne).
static func _code(line: String) -> String:
	var quote := ""
	for i in line.length():
		var c := line[i]
		if quote != "":
			if c == quote:
				quote = ""
		elif c == "\"" or c == "'":
			quote = c
		elif c == "#":
			return line.substr(0, i)
	return line


## Couleurs littérales d'une source : [{"file", "line", "text", "nearest"}].
static func scan(src: String, file: String) -> Array:
	var re := RegEx.create_from_string(PATTERN)
	var found: Array = []
	var lines := src.split("\n")
	for n in lines.size():
		var code := _code(lines[n])
		for m in re.search_all(code):
			var text := m.get_string()
			if text in ALLOWED:
				continue
			found.append({"file": file, "line": n + 1, "text": code.strip_edges(),
				"nearest": nearest(_literal_value(code.substr(m.get_start())))})
	return found


## Valeur de la couleur littérale au début de `s`, si elle se lit ; null sinon.
static func _literal_value(s: String) -> Variant:
	var named := RegEx.create_from_string("^Color\\.([A-Z][A-Z_]+)\\b(?!\\()").search(s)
	if named:
		return Color.from_string(named.get_string(1).to_lower(), Color(0, 0, 0, 0))
	var args := RegEx.create_from_string("^(Color8?)\\(([-0-9.,\\s]+)\\)").search(s)
	if args:
		var v: Array = []
		for part in args.get_string(2).split(","):
			v.append(float(part.strip_edges()) / (255.0 if args.get_string(1) == "Color8" else 1.0))
		if v.size() == 3:
			return Color(v[0], v[1], v[2])
		if v.size() == 4:
			return Color(v[0], v[1], v[2], v[3])
	var html := RegEx.create_from_string("^Color\\.html\\(\\s*\"(#?[0-9a-fA-F]+)\"").search(s)
	if html and Color.html_is_valid(html.get_string(1)):
		return Color.html(html.get_string(1))
	return null


## Nom de la couleur du thème la plus proche (distance RVBA), ou « ? » si la valeur ne se lit pas.
static func nearest(value: Variant) -> String:
	if not value is Color:
		return "?"
	var best := "?"
	var best_d := INF
	var consts: Dictionary = (load("res://scripts/ui_theme.gd") as Script).get_script_constant_map()
	for k in consts:
		if consts[k] is Color:
			var c: Color = consts[k]
			var d := Vector4(c.r - value.r, c.g - value.g, c.b - value.b, c.a - value.a).length()
			if d < best_d:
				best_d = d
				best = "UiTheme." + k
	return best


func _test_scanner() -> void:
	var src := "func _draw() -> void:\n\tdraw_line(a, b, UiTheme.INK, 2.0)\n\tvar c := Color(1, 0, 0)  # rouge\n" \
		+ "\tvar d := Color.BLACK\n\tvar e := Color(UiTheme.OK, 0.5)\n\tvar f := Color.TRANSPARENT\n" \
		+ "\t# Color(0.5, 0.5, 0.5) en commentaire\n\tvar g := Color8(255, 210, 60)\n\tvar h := \"#Color(1, 1, 1)\"\n"
	var found := scan(src, "hud_view.gd")
	var lines: Array = []
	for f in found:
		lines.append(f["line"])
	_check(lines == [3, 4, 8, 9], "détecteur : Color(1, 0, 0), Color.BLACK, Color8 et la chaîne trouvés ; thème, transparent, commentaire permis %s" % str(lines))
	_check(found.size() == 4 and found[0]["nearest"] == "UiTheme.KOM_DOT" and found[1]["nearest"] == "UiTheme.INK_EDGE"
		and found[2]["nearest"] == "UiTheme.GOLD", "couleur du thème la plus proche : %s" % str(found.map(func(f): return f["nearest"])))
	_check(scan("var c := Color.html(\"#ff2e4c\")\n", "x.gd")[0]["nearest"] == "UiTheme.DANGER", "Color.html lu et rapproché du thème")


func _test_ui_scripts() -> void:
	var files := ui_scripts()
	var expected := ["hud_view.gd", "menu_view.gd", "world_menu_view.gd", "erg_view.gd", "summary_view.gd",
		"devices_view.gd", "workout_chart_view.gd", "junction_view.gd", "banner.gd", "bots_view_model.gd"]
	var missing: Array = []
	for f in expected:
		if not f in files:
			missing.append(f)
	_check(missing.is_empty() and files.size() >= 13, "%d scripts d'interface lus, dont HUD, menus, globe et adversaires %s" % [files.size(), str(missing)])
	var found: Array = []
	for f in files:
		found.append_array(scan(FileAccess.get_file_as_string(SCRIPTS_DIR + "/" + f), f))
	var report: Array = []
	for f in found:
		report.append("%s:%d « %s » (thème le plus proche : %s)" % [f["file"], f["line"], f["text"], f["nearest"]])
	_check(found.is_empty(), "aucune couleur écrite en dur hors de ui_theme.gd" + ("" if found.is_empty() else " :\n  " + "\n  ".join(report)))
