extends RefCounted

## HUD du « Grand Prix des objets » (série GP, lot GP8, contrat 1.7), sans aucun nœud, d'après les maquettes
## GP6 validées par le propriétaire le 7 novembre 2026 (scènes 3, 4 et 6 pour la course, 7 pour le bilan) :
## - `item` : case d'objet (objet en réserve, charges « ×2 », roulette pendant le tirage de 2 s, invite
##   « Z : Trois musettes ») ; case vide en pointillés sans objet ;
## - `fx` : effets en cours sur le cycliste, avec leur reste en secondes (sous la case) ;
## - `place` : « 3e », « / 5 », « tour 2 / 3 » sur un circuit, écart avec le coureur de devant (« à 6,4 s de
##   Rouleur », « à 6,4 s du premier » pour le deuxième, « 2,1 s d'avance » en tête) ;
## - `strip` : bande de course, coureurs dans l'ordre (cycliste « Toi » à sa place du core), retard sur le
##   premier, objet tenu, pastille « touché » (effet d'un objet d'attaque, de piège ou contre la tête) ;
## - `lanes` : trois traits de voie, voie choisie en blanc ou en gris en placement automatique, aide des
##   boutons (« Bidon glissant en vue : A ou ← → » quand A change de voie et qu'un objet est en vue) ;
## - `warn` : menace sur le cycliste (« Musette guidée derrière ! », flèche vers le bas, contour de l'écran
##   et chevrons en bas), ou orage lancé vers un autre premier (« Orage vers le premier », sans contour).
## Objet `gp` de `state` et éléments de `bots` (`item`, `fx`, `name` : les bots loin ne les portent qu'à tour de
## rôle, le modèle garde les derniers reçus). Ne décide rien : le core arbitre tout.
## Lignes du bilan (`summary.gp`) : summary_lines(). Pas de class_name :
## preload("res://scripts/grandprix/gp_hud_model.gd").

const Items := preload("res://scripts/grandprix/gp_items.gd")

const ME := "me"
const ME_NAME := "Toi"
const MAX_ROWS := 12               # 11 bots et le cycliste (lot GP10)
const MAX_FX := 4
const ROLL_STEP_S := 0.12          # roulette : un objet toutes les 0,12 s pendant le tirage
const ON_ME_M := 2.0               # menace à moins de 2 m : « sur toi » (nuage d'orage au-dessus du cycliste)
const PICK_VIEW_M := 150.0         # objet « en vue » sur sa voie, pour l'aide du choix de voie
const GAP_MIN_SPEED_MPS := 1.0     # vitesse plancher d'un écart estimé (gaps.py MIN_SPEED_MPS)
const MAX_ITEM_LINES := 6          # lignes « temps par objet » du bilan

var names := {}                    # id du bot -> nom
var items := {}                    # id du bot -> objet en réserve ("" : aucun)
var fxs := {}                      # id du bot -> objets dont un effet est en cours


func reset() -> void:
	names.clear()
	items.clear()
	fxs.clear()


## Nom, objet et effets des bots de la trame ; un champ absent (bot loin, lot PL1) garde la dernière valeur.
func remember_bots(bots) -> void:
	if not bots is Array:
		return
	for b in bots:
		if not b is Dictionary:
			continue
		var id := str(b.get("id", ""))
		if id == "":
			continue
		if b.has("name"):
			names[id] = str(b["name"])
		if b.has("item"):
			items[id] = "" if b["item"] == null else str(b["item"])
		if b.has("fx") and b["fx"] is Array:
			fxs[id] = (b["fx"] as Array).duplicate()


func name_of(id: String) -> String:
	if id == ME:
		return ME_NAME
	return str(names.get(id, id))


## Vue du HUD pour la trame `state` (null ou sans `gp` : rien).
func view(state, now_s: float) -> Dictionary:
	var gp = state.get("gp", null) if state is Dictionary else null
	if not gp is Dictionary:
		return {"visible": false}
	remember_bots(state.get("bots", null))
	var strip := strip_rows(gp, state.get("bots", null), _num(state.get("s", null), NAN), _num(state.get("v", null), 0.0))
	return {"visible": true, "item": item_view(gp, now_s), "fx": fx_view(gp), "place": place_view(gp, strip),
		"strip": strip, "lanes": lanes_view(gp, _num(state.get("s", null), NAN)), "warn": warn_view(gp)}


## Case d'objet : {kind, rolling, n (charges affichées, 0 : pas de badge), key, empty}.
func item_view(gp: Dictionary, now_s: float) -> Dictionary:
	if _num(gp.get("roll_s", null), 0.0) > 0.0:
		var i := posmod(int(floor(now_s / ROLL_STEP_S)), Items.IDS.size())
		return {"kind": str(Items.IDS[i]), "rolling": true, "n": 0, "key": "Tirage…", "empty": false}
	var held = gp.get("held", null)
	if held == null or not Items.known(str(held)):
		return {"kind": "", "rolling": false, "n": 0, "key": "", "empty": true}
	var kind := str(held)
	var n := int(_num(gp.get("n", null), 1.0))
	return {"kind": kind, "rolling": false, "n": n if Items.charges(kind) > 1 and n >= 1 else 0,
		"key": "Z : " + Items.label(kind), "empty": false}


## Effets en cours sur le cycliste : [{kind, text}] (« Super-forme 5 s »), MAX_FX au plus.
func fx_view(gp: Dictionary) -> Array:
	var out: Array = []
	var fx = gp.get("fx", null)
	if not fx is Array:
		return out
	for e in fx:
		if e is Array and e.size() >= 2 and Items.known(str(e[0])) and out.size() < MAX_FX:
			out.append({"kind": str(e[0]), "text": "%s %d s" % [Items.label(str(e[0])), int(ceil(_num(e[1], 0.0)))]})
	return out


## Place, tours et écart : {place, of, lap, gap} ; {} sans place.
func place_view(gp: Dictionary, strip: Array) -> Dictionary:
	var place := int(_num(gp.get("place", null), 0.0))
	var of := int(_num(gp.get("of", null), 0.0))
	if place < 1:
		return {}
	var gap_text := ""
	var gap = gp.get("gap_s", null)
	if _is_num(gap):
		var g := absf(float(gap))
		if place == 1:
			gap_text = "%s s d'avance" % fr1(g)
		elif place == 2:
			gap_text = "à %s s du premier" % fr1(g)
		else:
			var ahead := ""
			for r in strip:
				if int(r["place"]) == place - 1:
					ahead = str(r["name"])
			gap_text = ("à %s s de %s" % [fr1(g), ahead]) if ahead != "" else ("à %s s" % fr1(g))
	var lap_text := ""
	var lap = gp.get("lap", null)
	if lap is Array and lap.size() >= 2:
		lap_text = "tour %d / %d" % [int(_num(lap[0], 1.0)), int(_num(lap[1], 1.0))]
	return {"place": place_text(place), "of": ("/ %d" % of) if of > 0 else "", "lap": lap_text, "gap": gap_text}


## Bande de course : [{place, name, me, gap, item, hit, boost}], du premier au dernier, MAX_ROWS au plus.
## Le cycliste est rangé à la place que donne le core (`gp.place`), les bots par position sur la route ;
## `gap` : retard sur le premier (« — » pour lui), d'après les écarts `gap_s` des bots ou, pour un bot loin
## qui ne les porte plus, distance ÷ vitesse du cycliste (repli du core).
func strip_rows(gp: Dictionary, bots, rider_s := NAN, rider_v := 0.0) -> Array:
	var others: Array = []   # [id, s, retard sur le cycliste en s (négatif devant)]
	if bots is Array:
		for b in bots:
			if not b is Dictionary or str(b.get("id", "")) == "" or str(b.get("kind", "constant")) == "ghost":
				continue
			var s := _num(b.get("s", null), NAN)
			var behind := NAN
			if _is_num(b.get("gap_s", null)):
				behind = -float(b["gap_s"])
			elif not is_nan(s) and not is_nan(rider_s):
				behind = (rider_s - s) / maxf(rider_v, GAP_MIN_SPEED_MPS)
			others.append([str(b["id"]), s if not is_nan(s) else -INF, behind])
	others.sort_custom(func(a: Array, b: Array) -> bool: return a[1] > b[1] or (a[1] == b[1] and a[0] < b[0]))
	var order: Array = []
	for o in others:
		order.append(o)
	var my_place := clampi(int(_num(gp.get("place", null), float(others.size() + 1))), 1, others.size() + 1)
	order.insert(my_place - 1, [ME, rider_s, 0.0])
	var lead := INF
	for o in order:
		if not is_nan(float(o[2])):
			lead = minf(lead, float(o[2]))
	var rows: Array = []
	for i in range(mini(order.size(), MAX_ROWS)):
		var id := str(order[i][0])
		var behind := float(order[i][2])
		var gap_text := "—" if i == 0 else ("" if is_nan(behind) or is_inf(lead) else "+%s s" % fr1(maxf(behind - lead, 0.0)))
		var held := ""
		var fx: Array = []
		if id == ME:
			held = str(gp.get("held", "")) if gp.get("held", null) != null and _num(gp.get("roll_s", null), 0.0) <= 0.0 else ""
			if gp.get("fx", null) is Array:
				for e in gp["fx"]:
					if e is Array and e.size() >= 1:
						fx.append(str(e[0]))
		else:
			held = str(items.get(id, ""))
			fx = fxs.get(id, [])
		rows.append({"place": i + 1, "name": name_of(id), "me": id == ME, "gap": gap_text,
			"item": held if Items.known(held) else "", "hit": _any_family(fx, Items.HIT_FAMILIES),
			"boost": _any_family(fx, ["self"])})
	return rows


static func _any_family(fx: Array, families: Array) -> bool:
	for k in fx:
		if Items.family(str(k)) in families:
			return true
	return false


## Choix de voie : {lane, auto, pick, hint}.
func lanes_view(gp: Dictionary, rider_s: float) -> Dictionary:
	var lane := clampi(int(_num(gp.get("lane", null), 1.0)), 0, 2)
	var pick := bool(gp.get("pick", false))
	var hint := "← → : voie"
	if pick:
		hint = "A : voie suivante · ← → : voie"
		var seen := _object_in_view(gp, lane, rider_s)
		if seen != "":
			hint = "%s en vue : A ou ← →" % Items.label(seen)
	return {"lane": lane, "auto": bool(gp.get("auto", false)), "pick": pick, "hint": hint}


## Objet le plus proche devant sur la voie du cycliste (ou sur toute la route), à moins de PICK_VIEW_M.
static func _object_in_view(gp: Dictionary, lane: int, rider_s: float) -> String:
	if is_nan(rider_s) or not gp.get("obj", null) is Array:
		return ""
	var best := ""
	var best_d := PICK_VIEW_M
	for o in gp["obj"]:
		if not o is Array or o.size() < 4:
			continue
		var d := _num(o[2], NAN) - rider_s
		var l := int(_num(o[3], -1.0))
		if d > 0.0 and d <= best_d and (l == lane or l == -1):
			best_d = d
			best = str(o[1])
	return best


## Avertissement : {text, kind, arrow ("down", "up" ou ""), color, outline, chevrons} ; {} sans menace.
func warn_view(gp: Dictionary) -> Dictionary:
	var w = gp.get("warn", null)
	if w is Array and w.size() >= 2:
		var kind := str(w[0])
		var on_me := _num(w[1], 0.0) < ON_ME_M
		return {"text": ("%s sur toi !" if on_me else "%s derrière !") % Items.label(kind), "kind": kind,
			"arrow": "" if on_me else "down", "color": Items.color(kind), "outline": true, "chevrons": not on_me}
	if gp.get("obj", null) is Array:
		for o in gp["obj"]:
			if o is Array and o.size() >= 2 and str(o[1]) == "storm":
				return {"text": "Orage vers le premier", "kind": "storm", "arrow": "up", "color": Items.SLING,
					"outline": false, "chevrons": false}
	return {}


## Lignes du bilan (`summary.gp`, maquette 7), au format de summary_view_model.gd : [{label, value, unit}].
## Place ; objets lancés, reçus et esquivés ; temps gagné ou perdu par objet (les MAX_ITEM_LINES plus forts) ;
## bilan des objets ; rappel que puissance et vitesse réelles sont au journal et au FIT.
static func summary_lines(gp: Dictionary) -> Array:
	var place := int(_num(gp.get("place", null), 0.0))
	var of := int(_num(gp.get("of", null), 0.0))
	var out: Array = [{"label": "Grand Prix des objets",
		"value": ("%s sur %d" % [place_text(place), of]) if place >= 1 else "course non finie", "unit": ""}]
	var launched := _counts(gp.get("launched", null))
	var received := _counts(gp.get("received", null))
	out.append({"label": "Objets", "value": "%d lancés · %d reçus · %d esquivés" % [_sum(launched), _sum(received),
		int(_num(gp.get("dodged", null), 0.0))], "unit": ""})
	var rows: Array = []   # [|temps|, ligne]
	var total := 0.0
	var gained = gp.get("gained_s", null)
	var lost = gp.get("lost_s", null)
	for kind in Items.IDS:
		var g := _num(gained.get(kind, null), 0.0) if gained is Dictionary else 0.0
		var l := _num(lost.get(kind, null), 0.0) if lost is Dictionary else 0.0
		total += g - absf(l)
		if int(launched.get(kind, 0)) > 0 or g != 0.0:
			rows.append([absf(g), {"label": Items.label(kind),
				"value": "%s · lancé ×%d" % [signed_s(g), int(launched.get(kind, 0))], "unit": ""}])
		if int(received.get(kind, 0)) > 0 or l != 0.0:
			rows.append([absf(l), {"label": Items.label(kind),
				"value": "%s · reçu ×%d" % [signed_s(-absf(l)), int(received.get(kind, 0))], "unit": ""}])
	rows.sort_custom(func(a: Array, b: Array) -> bool: return a[0] > b[0])
	for i in range(mini(rows.size(), MAX_ITEM_LINES)):
		out.append(rows[i][1])
	out.append({"label": "Bilan des objets", "value": signed_s(total), "unit": ""})
	out.append({"label": "Journal et FIT", "value": "puissance et vitesse réelles", "unit": ""})
	out.append({"label": "Records", "value": "aucun dans ce mode", "unit": ""})
	return out


static func _counts(d) -> Dictionary:
	var out := {}
	if d is Dictionary:
		for k in d:
			out[str(k)] = int(_num(d[k], 0.0))
	return out


static func _sum(d: Dictionary) -> int:
	var n := 0
	for k in d:
		n += int(d[k])
	return n


static func _is_num(x) -> bool:
	return x is float or x is int


static func _num(x, fallback: float) -> float:
	return float(x) if (x is float or x is int) else fallback


static func place_text(n: int) -> String:
	return "1er" if n == 1 else "%de" % n


static func fr1(v: float) -> String:
	return ("%.1f" % v).replace(".", ",")


static func signed_s(t: float) -> String:
	if absf(t) < 0.05:
		return "0 s"
	return ("+" if t > 0.0 else "−") + fr1(absf(t)) + " s"
