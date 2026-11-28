extends SceneTree

## Tests sans écran du mobilier de rue de la ville néon (lots NV4 et NV5, neon_street.gd) : rien hors de la ville
## néon, placement identique d'un appel à l'autre, bande du trottoir respectée, côté mer sans voiture ni enseigne,
## rien dans une zone exclue, noms d'enseignes de la liste, préréglage `low` allégé, tronçons construits autour de
## la caméra et libérés derrière, maillages non vides.
## Lancement : godot --headless --path engine --script res://tests/unit/test_neon_street.gd

const NeonStreet := preload("res://scripts/neon_street.gd")

var _failures := 0
var _checked := 0


class _Route:
	var length_m := 1000.0
	func sample(s: float) -> Dictionary:   # route droite vers le nord (−z), cap 0 : la droite est +x
		return {"x": 0.0, "y": 6.0, "z": -s, "heading_deg": 0.0}
	func is_loop() -> bool:
		return false


class _Model:
	var neon := true
	func any_neon() -> Dictionary:
		return {"pink": "#ff2a9e", "cyan": "#1ad9ff", "violet": "#8c40ff", "orange": "#ff8c1f", "density": 1.0}
	func neon_at(_x: float, z: float) -> Dictionary:
		return any_neon() if neon and z > -800.0 else {}   # les 200 derniers mètres hors de la ville


class _Zone:
	func contains(x: float, z: float) -> bool:
		return x > 0.0 and z <= -100.0 and z >= -200.0   # tout le côté droit du deuxième tronçon


func _init() -> void:
	var st = NeonStreet.new()
	st.configure(_Route.new(), null)
	_check(not st.active() and st.items_of_chunk(0).is_empty(), "sans modèle de biome : rien")
	var model := _Model.new()
	st.configure(_Route.new(), model)
	_check(st.active() and st.chunk_count() == 10, "ville néon : actif, 10 tronçons de 100 m")
	var a: Array = st.items_of_chunk(0)
	var b: Array = st.items_of_chunk(0)
	_check(str(a) == str(b) and a.size() > 20, "placement identique d'un appel à l'autre (%d objets)" % a.size())
	var kinds := {}
	var band := true
	var named := true
	for it in a:
		kinds[it["kind"]] = int(kinds.get(it["kind"], 0)) + 1
		var off := absf(float(it["pos"].x))
		if it["kind"] != "garland" and (off < 3.3 or off > 9.6):
			band = false
		if it["kind"] == "sign" and not (it["name"] in NeonStreet.SIGN_NAMES):
			named = false
	_check(kinds.get("palm", 0) == 10 and kinds.get("lamp", 0) == 8 and kinds.get("sign", 0) == 4 and kinds.get("garland", 0) == 2,
		"tronçon de ville : 10 palmiers, 8 lampadaires, 4 enseignes, 2 guirlandes (%s)" % str(kinds))
	_check(int(kinds.get("car", 0)) >= 6 and int(kinds.get("car", 0)) <= 24, "voitures garées : environ une place sur deux (%d)" % int(kinds.get("car", 0)))
	_check(band, "tout dans la bande du trottoir (3,3 à 9,6 m de l'axe)")
	_check(named, "enseignes : noms de la liste inventée")
	_check(st.items_of_chunk(9).is_empty(), "hors de la ville néon : rien")
	st.exclusions = _Zone.new()
	var right := 0
	for it in st.items_of_chunk(1):
		right += 1 if it["kind"] != "garland" and float(it["pos"].x) > 0.0 else 0
	_check(right == 0, "zone exclue (bâtiment, eau) : aucun objet dedans")
	st.exclusions = null
	st.height_at = func(x: float, _z: float) -> float: return -3.0 if x < -40.0 else 6.0   # la mer à gauche
	var shore_ok := true
	var shore_palms := 0
	for it in st.items_of_chunk(0):
		if float(it["pos"].x) < 0.0:
			shore_ok = shore_ok and it["kind"] in ["palm", "lamp"]
			shore_palms += 1 if it["kind"] == "palm" else 0
		elif it["kind"] == "garland":
			shore_ok = false
	_check(st.side_kind(50.0, -1) == "shore" and st.side_kind(50.0, 1) == "city", "côté mer reconnu par le terrain")
	_check(shore_ok and shore_palms == 16, "côté mer : double rangée de palmiers et lampadaires seulement, pas de guirlande (%d palmiers)" % shore_palms)
	st.height_at = Callable()
	st.set_quality("low")
	var low_cars := 0
	var low_garlands := 0
	for k in range(8):
		for it in st.items_of_chunk(k):
			low_cars += 1 if it["kind"] == "car" else 0
			low_garlands += 1 if it["kind"] == "garland" else 0
	st.set_quality("medium")
	var cars := 0
	for k in range(8):
		for it in st.items_of_chunk(k):
			cars += 1 if it["kind"] == "car" else 0
	_check(low_garlands == 0 and low_cars < cars * 0.7, "préréglage low : pas de guirlande, moins de voitures (%d contre %d)" % [low_cars, cars])
	get_root().add_child(st)
	st.update(250.0, 0.0)
	var c: Dictionary = st.counts()
	_check(int(c["chunks"]) == NeonStreet.CHUNKS_BEHIND + NeonStreet.CHUNKS_AHEAD + 1, "scène figée : %d tronçons construits d'un coup" % int(c["chunks"]))
	_check(int(c["palm"]) > 40 and int(c["lamp"]) > 30 and int(c["sign"]) > 10 and int(c["car"]) > 20, "objets affichés : %s" % str(c))
	st.update(250.0, 0.016)
	st.update(950.0, 0.016)
	_check(int(st.counts()["chunks"]) <= 4, "caméra en bout de route : tronçons de derrière libérés")
	for key in ["palm", "lamp", "garland"]:
		var m: Mesh = st._mesh(key)
		_check(m != null and m.get_surface_count() == 1 and m.get_aabb().size.y > 5.0, "maillage %s non vide, plus de 5 m de haut" % key)
	_check(NeonStreet.two_lines("CAFÉ CORAIL") == "CAFÉ CORAIL" and NeonStreet.two_lines("PIZZERIA DU PHARE") == "PIZZERIA\nDU PHARE",
		"nom d'enseigne : une ligne, ou deux coupées près du milieu")
	_check(NeonStreet.build_sign(Color.RED).get_aabb().size.x > 2.9, "maillage d'enseigne : caisson de 2,9 m")
	print("test_neon_street : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)
