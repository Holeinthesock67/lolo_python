extends RefCounted

## Habillage du mode « What the fuck » (série WTF, lot WTF7), sans nœud : traduit l'objet `wtf` de la trame
## `state` (contrat 1.5) en ce que wtf_view.gd affiche, d'après les maquettes validées le 30 octobre :
## - `banner` : bandeau du gag en haut au centre (texte, couleur, temps restant, points) ;
## - `card` : carte du gag à gauche, au-dessus du Katamari (titre, valeur, jauge de 0 à 1 ou −1 sans jauge, note) ;
## - `prompt` : invite d'un bouton (Z : « Non merci, chef ! ») ;
## - `kata`, `clock` : cartes des règles permanentes (Katamari, horloge sous lui).
## Pas de class_name : preload("res://scripts/wtf/wtf_hud_model.gd").

const PINK := Color(1.0, 0.31, 0.6)
const YELLOW := Color(1.0, 0.82, 0.25)
const CYAN := Color(0.18, 0.77, 0.95)
const GREEN := Color(0.48, 0.85, 0.29)
const ORANGE := Color(1.0, 0.54, 0.24)
const PURPLE := Color(0.56, 0.36, 1.0)
const WHITE := Color(1.0, 1.0, 1.0)
const INK := Color(0.106, 0.106, 0.184)

const CAMERAS := {"pigeon": "CAMÉRA PIGEON !", "snail": "CAMÉRA ESCARGOT !", "wheel": "CAMÉRA ROUE !"}
const DISHES := {"spaghetti": "SPAGHETTI", "jelly": "GELÉE", "musette": "BAL MUSETTE", "souffle": "SOUFFLÉ",
	"chili": "PIMENT"}
const KATA_OBJECTS := {"apple": "une pomme", "sign": "un panneau", "cow": "une vache", "car": "une voiture",
	"house": "une maison", "church": "une église"}
const EGGS_TOTAL := 6
const COLLAPSE_START_M := 120.0
const CHEESE_ESCAPE_M := 250.0
const STORM_MAX_M := 30.0


## Vue complète ; `wtf` absent ou nul : rien d'affiché.
static func view(wtf: Variant) -> Dictionary:
	if typeof(wtf) != TYPE_DICTIONARY:
		return {"visible": false}
	var out := {"visible": true, "banner": {}, "card": {}, "prompt": {}, "kata": {}, "clock": {}}
	var pts := "%d pts" % int(wtf.get("points", 0))
	var ev = wtf.get("event", null)
	if typeof(ev) == TYPE_DICTIONARY:
		_event(ev, pts, out)
	else:
		var next = wtf.get("next_s", null)
		out["banner"] = {"text": "MODE WTF", "color": WHITE,
			"time": ("prochain gag dans %d s" % int(next)) if next != null else "", "points": pts}
	var kata = wtf.get("kata", null)
	if typeof(kata) == TYPE_DICTIONARY:
		var size := float(kata.get("size", 1.0))
		var last := str(kata.get("last", ""))
		out["kata"] = {"title": "KATAMARI × %s" % _dec(size), "line": "%d objets%s" % [int(kata.get("count", 0)),
			(" · dernier : " + KATA_OBJECTS.get(last, last)) if last != "" and last != "<null>" else ""],
			"bar": clampf((size - 1.0) / 5.0, 0.0, 1.0)}
	if wtf.has("clock_h"):
		var h := float(wtf.get("clock_h", 0.0))
		out["clock"] = {"text": "%d h %02d" % [int(h), int((h - floorf(h)) * 60.0)], "fish": bool(wtf.get("fish", false))}
	return out


static func _event(ev: Dictionary, pts: String, out: Dictionary) -> void:
	var id := str(ev.get("id", ""))
	var left := _clock(float(ev.get("left_s", 0.0)))
	var b := {"text": "", "color": YELLOW, "time": left, "points": pts}
	var card := {}
	match id:
		"gravity":
			var moon := str(ev.get("planet", "moon")) == "moon"
			b["text"] = "GRAVITÉ : LA LUNE !" if moon else "GRAVITÉ : JUPITER !"
			b["color"] = YELLOW if moon else ORANGE
			card = _card("Pentes", "× 0,17" if moon else "× 2,5", -1.0,
				"Le vélo bondit" if moon else "Un faux plat devient un mur (10 % au plus sous les pieds)")
		"upside_down":
			b["text"] = "MONDE À L'ENVERS !"
			b["color"] = ORANGE
			card = _card("Pentes", "inversées", -1.0, "Les descentes durcissent, les montées sont faciles")
		"collapse":
			var gap := float(ev.get("gap_m", 0.0))
			b["text"] = "LA ROUTE S'EFFONDRE !"
			b["color"] = PINK
			card = _card("Écart avec l'effondrement", "%d m" % int(round(gap)), clampf(gap / COLLAPSE_START_M, 0.0, 1.0),
				"Garde plus de 60 % de ta FTP")
		"cheese":
			var gap := float(ev.get("gap_m", 0.0))
			b["text"] = "ÉCRASÉ !" if bool(ev.get("squashed", false)) else "LE FROMAGE ARRIVE !"
			card = _card("Avance sur la meule", "%d / %d m" % [int(round(gap)), int(CHEESE_ESCAPE_M)],
				clampf(gap / CHEESE_ESCAPE_M, 0.0, 1.0), "250 m d'avance et tu lui échappes")
		"micro":
			b["text"] = "MICRO-DÉFI %d / 3" % int(ev.get("round", 1))
			b["color"] = CYAN
			b["time"] = _clock(float(ev.get("round_left_s", 0.0)))
			card = _micro(ev)
		"eggs":
			b["text"] = "LIVRAISON D'ŒUFS"
			b["color"] = WHITE
			b["time"] = "%s km" % _dec(float(ev.get("left_m", 0.0)) / 1000.0)
			var eggs := int(ev.get("eggs", EGGS_TOTAL))
			card = _card("Œufs intacts", "%d / %d" % [eggs, EGGS_TOTAL], float(eggs) / EGGS_TOTAL,
				"Chaque à-coup de puissance en casse un")
		"tiny":
			b["text"] = "TOUT PETIT !"
			b["color"] = GREEN
		"storm":
			var push := float(ev.get("pushback_m", 0.0))
			b["text"] = "TORNADE DE VACHES !"
			b["color"] = ORANGE
			card = _card("Le vent te repousse", "%d m" % int(round(push)), clampf(push / STORM_MAX_M, 0.0, 1.0),
				"Pousse au-dessus de 50 % de ta FTP pour revenir")
		"camera":
			b["text"] = CAMERAS.get(str(ev.get("view", "")), "CAMÉRA IMPROBABLE !")
		"chef":
			_chef(ev, b, out)
			card = _dish_card(ev)
		_:
			b["text"] = id.to_upper()
	out["banner"] = b
	out["card"] = card


static func _micro(ev: Dictionary) -> Dictionary:
	var target := int(round(float(ev.get("target", 0.0))))
	var bar := float(ev.get("progress", 0.0))
	match str(ev.get("kind", "")):
		"cadence":
			return _card("CADENCE PILE !", "%d rpm (± 3)" % target, bar, "Tiens-la 60 % du temps")
		"sprint":
			return _card("SAUTE LE RAVIN !", "%d W pendant 5 s" % target, bar, "150 % de ta FTP")
		"cap":
			return _card("LE GÂTEAU TIENT ?", "moins de %d W" % target, bar, "3 s de dépassement et il tombe")
		"steady":
			return _card("RÉGULIER !", ("%d W ± 10 %%" % target) if target > 0 else "fixe ta puissance…", bar,
				"Garde la même puissance")
		"spin":
			return _card("MOULINETTE !", "%d rpm pendant 10 s" % target, bar, "")
	return {}


static func _chef(ev: Dictionary, b: Dictionary, out: Dictionary) -> void:
	var phase := str(ev.get("phase", ""))
	var dish: String = DISHES.get(str(ev.get("dish", "")), "")
	b["color"] = PINK
	match phase:
		"arrive":
			b["text"] = "LE CHEF ARRIVE…"
		"reveal":
			b["text"] = "SURPRISE DU CHEF : %s !" % dish
			out["prompt"] = {"key": "Z", "text": "NON MERCI, CHEF !",
				"time": "%d s" % int(ceilf(float(ev.get("phase_left_s", 0.0))))}
		_:
			b["text"] = "%s !" % dish
			b["time"] = _clock(float(ev.get("phase_left_s", 0.0)))


static func _dish_card(ev: Dictionary) -> Dictionary:
	if str(ev.get("phase", "")) != "eat":
		return {}
	match str(ev.get("dish", "")):
		"spaghetti":
			return _card("Spaghetti", "la route ondule", -1.0, "± 1,5 point toutes les 8 s")
		"jelly":
			return _card("Gelée", "ça colle", -1.0, "Roulement × 1,5")
		"musette":
			return _card("Tempo du bal", "%d rpm" % int(ev.get("tempo_rpm", 0)), -1.0, "À ± 4 rpm, la foule danse")
		"souffle":
			var h := float(ev.get("souffle", 0.0))
			return _card("Hauteur du soufflé", "%d %%" % int(round(h * 100.0)), h, "Réussi au-dessus de 80 %")
		"chili":
			var burning := bool(ev.get("burning", false))
			return _card("Piment", "ÇA BRÛLE ! − 15 %" if burning else "+ 25 %", -1.0, "Vitesse virtuelle seulement")
	return {}


static func _card(title: String, value: String, bar: float, note: String) -> Dictionary:
	return {"title": title, "value": value, "bar": bar, "note": note}


## Temps restant « m:ss ».
static func _clock(s: float) -> String:
	var t := int(ceilf(maxf(s, 0.0)))
	return "%d:%02d" % [t / 60, t % 60]


## Nombre à une décimale avec la virgule française.
static func _dec(x: float) -> String:
	return ("%.1f" % x).replace(".", ",")
