extends SceneTree

## Tests unitaires sans écran de la consigne en direct des essais physiques (live_cue.gd, lot EP3).
## Lancement : godot --headless --path engine --script res://tests/unit/test_live_cue.gd

const LiveCue := preload("res://scripts/live_cue.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _write(path: String, data) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data) if typeof(data) == TYPE_DICTIONARY else str(data))
	f.close()


func _init() -> void:
	var nodes_before := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	var path := ProjectSettings.globalize_path("user://test_live_cue.json")
	DirAccess.remove_absolute(path)

	var m = LiveCue.new(path)
	_check(m.poll(0).is_empty(), "sans fichier : rien")
	_write(path, {"id": 1, "texte": "Roule à 100 watts.", "sorte": "consigne", "duree_s": 6})
	_check(m.poll(500).is_empty(), "moins d'une seconde après la lecture précédente : fichier pas relu")
	var c: Dictionary = m.poll(1000)
	_check(c.get("text", "") == "Roule à 100 watts." and c["kind"] == "consigne" and c["duration_s"] == 6.0,
			"nouvelle consigne lue : texte, sorte, durée")
	_check(m.poll(2000).is_empty(), "même id : pas répétée")
	_write(path, {"id": 2, "texte": "Vu, merci.", "sorte": "vu"})
	var v: Dictionary = m.poll(3000)
	_check(v.get("kind", "") == "vu" and v["duration_s"] == LiveCue.DEFAULT_DURATION_S, "id suivant dans la même seconde : lu, durée par défaut")
	_write(path, "pas du json")
	_check(m.poll(4000).is_empty(), "fichier illisible : ignoré")
	_write(path, {"id": 3, "texte": ""})
	_check(m.poll(5000).is_empty(), "texte vide : ignoré")

	_write(path, {"id": 7, "texte": "Consigne d'un essai d'hier"})
	var late = LiveCue.new(path)
	_check(late.poll(0).is_empty(), "fichier laissé par un essai précédent : pas affiché au lancement")
	_write(path, {"id": 1, "texte": "Nouvel essai"})
	_check(late.poll(1000).get("text", "") == "Nouvel essai", "essai suivant (id repart à 1) : affiché")

	DirAccess.remove_absolute(path)
	var nodes_after := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	_check(nodes_after == nodes_before, "aucun nœud créé")
	print("test_live_cue : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
