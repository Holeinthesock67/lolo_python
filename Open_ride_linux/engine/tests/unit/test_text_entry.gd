extends SceneTree

## Saisie de texte (text_entry.gd, lots O31, MJ8, W11 ; audit du 22/11, R12) : grille et ses deux actions,
## majuscule en début de mot, espaces refusés en tête ou doublés, longueur maximale, effacement, saisie au
## clavier filtrée, signes en plus (`extra`), déplacement de la case en focus sans boucler.
## Lancement : godot --headless --path engine --script res://tests/unit/test_text_entry.gd

const TextEntry := preload("res://scripts/text_entry.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_text_entry : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _cell_of(t, ch: String) -> String:
	return TextEntry.CELL_PREFIX + str(t.cells().find(ch))


func _run() -> void:
	_grid()
	_writing()
	_keyboard()
	_move()


func _grid() -> void:
	var t = TextEntry.new()
	var items: Array = t.grid_items()
	_check(items.size() == TextEntry.GRID.size() + 2, "grille : une case par signe, puis Effacer et Valider")
	_check(items[-2]["id"] == TextEntry.ERASE and items[-2]["label"] == "Effacer", "avant-dernière case : Effacer")
	_check(items[-1]["id"] == TextEntry.VALIDATE and items[-1]["label"] == "Valider", "dernière case : Valider")
	var space: int = TextEntry.GRID.find(" ")
	_check(items[space]["label"] == "␣", "l'espace est dessiné ␣")
	_check(items.all(func(it): return it["enabled"] == true), "toutes les cases sont actives")
	var t2 = TextEntry.new(16, ["'"])
	_check(t2.cells().size() == TextEntry.GRID.size() + 1 and t2.cells()[-1] == "'", "signe en plus ajouté en fin de grille")
	_check(t2.grid_items().size() == TextEntry.GRID.size() + 3, "signe en plus : une case de plus avant les actions")


func _writing() -> void:
	var t = TextEntry.new(8)
	_check(t.press_cell(_cell_of(t, "M")) == "changed" and t.text == "M", "première lettre en majuscule")
	t.press_cell(_cell_of(t, "A"))
	_check(t.text == "Ma", "lettre suivante en minuscule")
	_check(t.press_cell(_cell_of(t, " ")) == "changed" and t.text == "Ma ", "espace après un mot")
	_check(t.press_cell(_cell_of(t, " ")) == "" and t.text == "Ma ", "deux espaces de suite refusés")
	t.press_cell(_cell_of(t, "R"))
	_check(t.text == "Ma R", "majuscule après un espace")
	t.press_cell(_cell_of(t, "-"))
	t.press_cell(_cell_of(t, "E"))
	_check(t.text == "Ma R-E", "majuscule après un tiret")
	t.press_cell(_cell_of(t, "7"))
	_check(t.text == "Ma R-E7", "chiffre écrit tel quel")
	t.press_cell(_cell_of(t, "é"))
	_check(t.text.length() == 8 and t.text.ends_with("é"), "accent écrit, longueur maximale atteinte")
	_check(t.press_cell(_cell_of(t, "B")) == "" and t.text.length() == 8, "au-delà de la longueur maximale : rien n'est écrit")
	_check(t.press_cell(TextEntry.ERASE) == "changed" and t.text == "Ma R-E7", "Effacer retire la dernière lettre")
	_check(t.press_cell(TextEntry.VALIDATE) == "validate", "Valider renvoie « validate »")
	_check(t.press_cell("c:999") == "" and t.press_cell("autre") == "", "case inconnue : rien")
	var e = TextEntry.new()
	_check(e.press_cell(_cell_of(e, " ")) == "" and e.text == "", "pas d'espace en tête")
	_check(e.press_cell(TextEntry.ERASE) == "" and not e.backspace(), "effacer un texte vide : rien (l'écran revient en arrière)")


func _keyboard() -> void:
	var t = TextEntry.new(16, ["'"])
	for ch in ["l", "'", "É", "t", "a", "n", "g", " ", "2"]:
		_check(t.type_text(ch), "clavier : « %s » accepté" % ch)
	_check(t.text == "l'Étang 2", "clavier : texte tapé tel quel, sans majuscule ajoutée")
	for ch in ["!", "/", "ab", ""]:
		_check(not t.type_text(ch), "clavier : « %s » ignoré" % ch)
	_check(t.text == "l'Étang 2", "clavier : texte inchangé par les signes ignorés")
	var n = TextEntry.new()
	_check(not n.type_text("'"), "sans signe en plus, l'apostrophe est ignorée")


func _move() -> void:
	var t = TextEntry.new()
	var last: int = t.grid_items().size() - 1
	_check(t.cell == 0 and t.cell_id() == TextEntry.CELL_PREFIX + "0", "focus de départ sur la première case")
	t.move(-1)
	_check(t.cell == 0, "pas de retour à la fin depuis la première case")
	t.move(TextEntry.GRID_COLUMNS)
	_check(t.cell == TextEntry.GRID_COLUMNS, "un saut d'une ligne : GRID_COLUMNS cases")
	t.move(1000)
	_check(t.cell == last and t.cell_id() == TextEntry.VALIDATE, "pas de boucle au-delà de Valider")
