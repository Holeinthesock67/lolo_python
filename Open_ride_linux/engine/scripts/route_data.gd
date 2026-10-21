class_name RouteData
extends RefCounted

## Charge et échantillonne la couche route.json d'un .world selon le Format .world v1.

var version: String = "1.0"
var ds_m: float = 10.0
var n: int = 0
var length_m: float = 0.0
var type: String = "open"

var x: PackedFloat32Array = PackedFloat32Array()
var z: PackedFloat32Array = PackedFloat32Array()
var alt_m: PackedFloat32Array = PackedFloat32Array()
var grade_pct: PackedFloat32Array = PackedFloat32Array()
var heading_deg: PackedFloat32Array = PackedFloat32Array()


static func load_from_file(route_json_path: String) -> RouteData:
	if not FileAccess.file_exists(route_json_path):
		push_error("Fichier route introuvable: " + route_json_path)
		return null
	
	var file := FileAccess.open(route_json_path, FileAccess.READ)
	var content := file.get_as_text()
	var json_res = JSON.parse_string(content)
	if typeof(json_res) != TYPE_DICTIONARY:
		push_error("route.json invalide: " + route_json_path)
		return null
	
	var r := RouteData.new()
	r.version = json_res.get("version", "1.0")
	r.ds_m = float(json_res.get("ds_m", 10.0))
	r.n = int(json_res.get("n", 0))
	r.length_m = float(json_res.get("length_m", 0.0))
	r.type = json_res.get("type", "open")
	
	var raw_x: Array = json_res.get("x", [])
	var raw_z: Array = json_res.get("z", [])
	var raw_alt: Array = json_res.get("alt_m", [])
	var raw_grade: Array = json_res.get("grade_pct", [])
	var raw_heading: Array = json_res.get("heading_deg", [])
	
	r.x.resize(r.n)
	r.z.resize(r.n)
	r.alt_m.resize(r.n)
	r.grade_pct.resize(r.n)
	r.heading_deg.resize(r.n)
	
	for i in range(r.n):
		r.x[i] = float(raw_x[i])
		r.z[i] = float(raw_z[i])
		r.alt_m[i] = float(raw_alt[i])
		r.grade_pct[i] = float(raw_grade[i]) if i < raw_grade.size() else 0.0
		r.heading_deg[i] = float(raw_heading[i]) if i < raw_heading.size() else 0.0
	
	return r


func sample_point(s: float) -> Vector3:
	if n == 0:
		return Vector3.ZERO
	s = clampf(s, 0.0, length_m)
	var idx: int = int(floor(s / ds_m))
	if idx >= n - 1:
		return Vector3(x[n - 1], alt_m[n - 1], z[n - 1])
	
	var s0: float = idx * ds_m
	var s1: float = (idx + 1) * ds_m if idx + 1 < n - 1 else length_m
	var factor: float = (s - s0) / (s1 - s0) if s1 > s0 else 0.0
	
	var p0 := Vector3(x[idx], alt_m[idx], z[idx])
	var p1 := Vector3(x[idx + 1], alt_m[idx + 1], z[idx + 1])
	return p0.lerp(p1, factor)


func sample_heading(s: float) -> float:
	if n == 0:
		return 0.0
	s = clampf(s, 0.0, length_m)
	var idx: int = int(floor(s / ds_m))
	if idx >= n - 1:
		return heading_deg[n - 1]
	
	var s0: float = idx * ds_m
	var s1: float = (idx + 1) * ds_m if idx + 1 < n - 1 else length_m
	var factor: float = (s - s0) / (s1 - s0) if s1 > s0 else 0.0
	return lerp_angle(deg_to_rad(heading_deg[idx]), deg_to_rad(heading_deg[idx + 1]), factor)
