extends SceneTree

## Bandeau des boutons des menus (button_bar.gd ; audit du 22/11, R12) : deux lignes (Click puis clavier),
## une pastille par touche, anneau d'appui long sur la seule ligne du Click, « maintenir : » devant le texte,
## entrée d'une seule ligne sautée sur l'autre (menu du monde ouvert), rien de refait pour le même écran,
## et l'aide d'une ligne égale à button_help.gd. Fige aussi la grille de saisie telle qu'elle est (Z écrit,
## Y efface : écarts U2 de l'audit, à changer exprès).
## Lancement : godot --headless --path engine --script res://tests/unit/test_button_bar.gd

const ButtonBar := preload("res://scripts/button_bar.gd")
const ButtonHelp := preload("res://scripts/button_help.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_button_bar : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _rows(bar) -> Array:
	return bar.get_child(0).get_children()


## Groupes (entrées) d'une ligne : tout sauf le titre.
func _groups(row: Node) -> Array:
	return row.get_children().slice(1)


func _words(group: Node) -> String:
	return (group.get_child(group.get_child_count() - 1) as Label).text


func _caps(group: Node) -> Array:
	return group.get_children().filter(func(c): return c is PanelContainer).map(func(c): return (c.get_child(0) as Label).text)


func _has_ring(group: Node) -> bool:
	return group.get_children().any(func(c): return c.get_class() == "Control")


func _run() -> void:
	_menu("routes")
	_menu(ButtonHelp.NAME_GRID)
	_world()
	_same_screen()
	_grid_rule()


func _menu(screen: String) -> void:
	var bar = ButtonBar.new()
	bar.update_display(screen)
	var rows := _rows(bar)
	_check(rows.size() == 2, "%s : deux lignes" % screen)
	_check((rows[0].get_child(0) as Label).text == ButtonHelp.CLICK_TITLE
		and (rows[1].get_child(0) as Label).text == ButtonHelp.KEYBOARD_TITLE, "%s : ligne du Click puis du clavier" % screen)
	var entries := ButtonHelp.entries(screen)
	var click := _groups(rows[0])
	var kb := _groups(rows[1])
	_check(click.size() == entries.size() and kb.size() == entries.size(), "%s : un groupe par entrée sur chaque ligne" % screen)
	for i in range(mini(click.size(), entries.size())):
		var e: Dictionary = entries[i]
		_check(_caps(click[i]) == e["keys"], "%s : pastilles du Click « %s »" % [screen, e["text"]])
		_check(_caps(kb[i]) == e["kb"], "%s : touches du clavier « %s »" % [screen, e["text"]])
		_check(_has_ring(click[i]) == bool(e["hold"]) and not _has_ring(kb[i]),
			"%s : anneau d'appui long sur le Click seul « %s »" % [screen, e["text"]])
		var want := ("maintenir : " if e["hold"] else "") + str(e["text"])
		_check(_words(click[i]) == want and _words(kb[i]) == str(e["text"]), "%s : texte « %s »" % [screen, want])
	_check(bar.text() == ButtonHelp.text(screen), "%s : aide d'une ligne = button_help.gd" % screen)
	bar.free()


func _world() -> void:
	var bar = ButtonBar.new()
	bar.update_display("world_globe")
	var entries := ButtonHelp.entries("world_globe")
	var with_kb := entries.filter(func(e): return not (e["kb"] as Array).is_empty())
	var rows := _rows(bar)
	_check(_groups(rows[0]).size() == entries.size(), "globe : toutes les entrées sur la ligne du Click")
	_check(_groups(rows[1]).size() == with_kb.size() and with_kb.size() < entries.size(),
		"globe : entrée sans touche du clavier sautée sur la ligne du clavier")
	bar.free()


func _same_screen() -> void:
	var bar = ButtonBar.new()
	bar.update_display("routes")
	var first: Node = _rows(bar)[0]
	bar.update_display("routes")
	_check(_rows(bar)[0] == first, "même écran : bandeau non refait")
	bar.update_display(ButtonHelp.EDIT)
	_check(_rows(bar).size() == 2 and _rows(bar)[0] != first, "autre écran : bandeau refait, toujours deux lignes")
	_check(_words(_groups(_rows(bar)[0])[0]) == "maintenir : Enregistrer", "écran de réglage : A maintenu enregistre")
	bar.free()


func _grid_rule() -> void:
	var g := ButtonHelp.entries(ButtonHelp.NAME_GRID)
	var by_key := {}
	for e in g:
		by_key[str(e["keys"][0])] = e
	_check(by_key["A"]["hold"] and by_key["A"]["main"] and by_key["A"]["text"] == "Valider le nom", "grille : A maintenu valide le nom")
	_check(by_key["Z"]["text"] == "Écrire" and by_key["Z"]["kb"] == ["lettres"], "grille : Z écrit (clavier : lettres)")
	_check(by_key["Y"]["text"] == "Effacer" and by_key["Y"]["kb"] == ["Retour arrière"], "grille : Y efface (clavier : Retour arrière)")
	_check(ButtonHelp.entries(ButtonHelp.WORLD_SEARCH_GRID)[0]["text"] == "Voir les résultats", "recherche du monde : A maintenu montre les résultats")
