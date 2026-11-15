extends RefCounted
## Parcours vu à rebours (lot N23) : abscisse u = L - s, même tracé, cap retourné, pente opposée.
##
## Jumeau de `openride_core/route_mirror.py`. Après un demi-tour (lot N17), la circulation (traffic_model.gd) et les
## cyclistes du décor (road_cyclists_model.gd) roulent tels quels sur ce parcours retourné, où le cycliste avance
## encore vers les u croissants : mêmes cases tirées que le core, et leurs poses (`world_transform`) se calculent
## sans changement (cap + 180° : la droite du sens de marche est la gauche du sens du parcours).
## Pas de class_name : chargé par preload, comme route_data.gd.

var base = null
var length_m: float = 0.0


func _init(p_base) -> void:
	base = p_base
	length_m = float(base.length_m)


## Abscisse dans l'autre repère ; l'opération est sa propre réciproque.
static func flip_s(p_length_m: float, s: float) -> float:
	return p_length_m - s


func is_loop() -> bool:
	return base.has_method("is_loop") and base.is_loop()


func wrap_s(u: float) -> float:
	return flip_s(length_m, base.wrap_s(flip_s(length_m, u))) if base.has_method("wrap_s") else u


func sample(u: float) -> Dictionary:
	var smp: Dictionary = base.sample(flip_s(length_m, u)).duplicate()
	smp["grade_pct"] = -float(smp.get("grade_pct", 0.0))
	smp["heading_deg"] = fposmod(float(smp.get("heading_deg", 0.0)) + 180.0, 360.0)
	return smp


func sample_grade(u: float) -> float:
	return -float(base.sample_grade(flip_s(length_m, u)))


## Tangage (> 0 en montée vers les u croissants) : celui du parcours, de signe opposé.
func display_pitch(u: float, probe_m: float = 1.5) -> float:   # 1,5 m : SLOPE_PROBE_M de route_data.gd
	return -float(base.display_pitch(flip_s(length_m, u), probe_m))


func surface_at(u: float) -> String:
	return str(base.surface_at(flip_s(length_m, u))) if base.has_method("surface_at") else "paved"
