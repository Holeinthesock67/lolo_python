extends CanvasLayer

## Préparation des graphismes au premier lancement (lot PG1, cahier docs/lots/LOT_PG1_preparation_graphismes.md).
## À cache de shaders vide, chaque shader nouveau compile ses pipelines à la création puis au premier dessin de son
## objet : 100 à 250 ms par pipeline sur la GTX 1060, des secondes d'écran figé quand tout le décor naît dans la
## même image. Ici, toutes les doublures du catalogue (graphics_catalog.gd) passent une fois, avant le parcours :
## shader_warm.gd en crée une par image, puis la dessine deux images plus tard. L'écran reste animé, avec une barre
## et un texte écrits. Les lancements suivants ne refont rien tant que la clé (version du jeu, de Godot, carte
## graphique et pilote) ne change pas et que le cache de Godot est là.
## Pas de class_name : charger par preload("res://scripts/graphics_prep.gd").

const Catalog := preload("res://scripts/graphics_catalog.gd")

const KEY_FILE := "user://graphismes/prepare.json"
const SHADER_CACHE_DIR := "user://shader_cache"

## shader_warm.gd (posé par main.gd).
var warm = null
## Fichier de la clé écrit à la fin (les tests en donnent un à eux).
var key_file := KEY_FILE
## Doublures confiées à shader_warm, et combien sont passées.
var total := 0
var done := 0
var running := false
var _label: Label = null
var _bar: ProgressBar = null
var _t0_ms := 0


## Clé de la préparation : ce qui invalide les caches de shaders et de pipelines.
static func current_key() -> String:
	var parts: Array = [str(ProjectSettings.get_setting("application/config/version", "")),
		str(Engine.get_version_info().get("string", "")),
		RenderingServer.get_video_adapter_name(), RenderingServer.get_video_adapter_api_version()]
	parts.append_array(OS.get_video_adapter_driver_info())
	return " | ".join(parts)


## Vrai si la préparation est à faire : clé changée (ou jamais écrite), ou cache de shaders de Godot vide.
static func needed(key_file: String = KEY_FILE, cache_dir: String = SHADER_CACHE_DIR) -> bool:
	if not FileAccess.file_exists(key_file):
		return true
	var data = JSON.parse_string(FileAccess.get_file_as_string(key_file))
	if not (data is Dictionary) or str(data.get("key", "")) != current_key():
		return true
	return not DirAccess.dir_exists_absolute(cache_dir)


static func write_key(key_file: String = KEY_FILE) -> void:
	DirAccess.make_dir_recursive_absolute(key_file.get_base_dir())
	var f := FileAccess.open(key_file, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify({"key": current_key(), "date": Time.get_datetime_string_from_system()}))


## Lance la préparation avec ces doublures (catalogue lu par l'appelant) ; rien à faire si la liste est vide.
func start(proxies: Array) -> void:
	if warm == null or proxies.is_empty():
		for p in proxies:
			(p as Node).free()
		return
	total = warm.prime(proxies)
	if total == 0:
		return
	running = true
	_t0_ms = Time.get_ticks_msec()
	layer = 120
	_build()
	print("Préparation des graphismes : %d doublures (première fois seulement)" % total)


func _build() -> void:
	var box := PanelContainer.new()
	box.anchor_left = 0.25
	box.anchor_right = 0.75
	box.anchor_top = 0.78
	box.anchor_bottom = 0.9
	var v := VBoxContainer.new()
	box.add_child(v)
	_label = Label.new()
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(_label)
	_bar = ProgressBar.new()
	_bar.min_value = 0
	_bar.max_value = total
	_bar.show_percentage = false
	v.add_child(_bar)
	add_child(box)
	_refresh()


func _refresh() -> void:
	if _label != null:
		_label.text = "Préparation des graphismes : première fois seulement (%d sur %d)" % [done, total]
	if _bar != null:
		_bar.value = done


func _process(_delta: float) -> void:
	if not running or warm == null:
		return
	done = mini(total, int(warm.primed_shown))
	_refresh()
	if done >= total or int(warm.primed_left()) <= 0:
		running = false
		if int(warm.primed_shown) >= total:   # séance partie avant la fin : refaite au lancement suivant
			write_key(key_file)
		print("Préparation des graphismes finie : %d doublures en %d ms" % [total, Time.get_ticks_msec() - _t0_ms])
		for c in get_children():
			c.queue_free()
