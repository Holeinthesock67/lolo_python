extends RefCounted

## Montées du parcours d'après son profil d'altitude (Lot P14), sans aucun nœud ; résultat partagé avec
## P15 (spectateurs). Pas de class_name : charger par preload("res://scripts/climb_detector.gd").
##
## `detect(route)` rend un tableau de montées `{start_s, summit_s, length_m, gain_m, avg_grade_pct,
## max_km_grade_pct, summit_alt_m}`, dans l'ordre du parcours :
## 1. profil rééchantillonné tous les STEP_M et lissé sur SMOOTH_M (moyenne glissante) ;
## 2. creux et sommets à hystérésis de HYSTERESIS_M de dénivelé ;
## 3. une montée s'arrête après MERGE_GAP_M sans gagner PLATEAU_RISE_M ; montées voisines séparées
##    par moins de MERGE_GAP_M de replat ou de descente fusionnées ;
## 4. gardées si elles font au moins MIN_LENGTH_M à MIN_AVG_PCT de moyenne, ou MIN_GAIN_M de dénivelé ;
## 5. début et sommet recalés sur le profil brut : premier point à moins de SNAP_M du plus haut (et du
##    plus bas pour le début), à moins de REFINE_M du point lissé.
## `max_km_grade_pct` : pente moyenne la plus forte sur un kilomètre glissant (pas de STEP_M) dans la
## montée, ou la pente moyenne si elle est plus courte qu'un kilomètre.

const STEP_M := 20.0
const SMOOTH_M := 100.0
const HYSTERESIS_M := 8.0
const MERGE_GAP_M := 300.0
const PLATEAU_RISE_M := 1.5
const MIN_LENGTH_M := 1500.0
const MIN_AVG_PCT := 4.0
const MIN_GAIN_M := 80.0
const REFINE_M := 150.0
const SNAP_M := 0.3


static func _profile(route) -> Dictionary:
	var n := int(floor(route.length_m / STEP_M)) + 1
	var s_arr := PackedFloat64Array()
	var raw := PackedFloat64Array()
	for i in range(n):
		var s := minf(i * STEP_M, route.length_m)
		s_arr.append(s)
		raw.append(float(route.sample(s)["alt_m"]))
	var half := int(round(SMOOTH_M / STEP_M / 2.0))
	var smooth := PackedFloat64Array()
	smooth.resize(n)
	var acc := 0.0
	var count := 0
	# Moyenne glissante centrée (fenêtre tronquée aux bouts)
	for i in range(mini(half, n)):
		acc += raw[i]
		count += 1
	for i in range(n):
		var add := i + half
		if add < n:
			acc += raw[add]
			count += 1
		var rem := i - half - 1
		if rem >= 0:
			acc -= raw[rem]
			count -= 1
		smooth[i] = acc / count
	return {"s": s_arr, "raw": raw, "smooth": smooth}


static func detect(route) -> Array:
	if route == null or route.n < 2 or route.length_m <= STEP_M:
		return []
	var p := _profile(route)
	var s_arr: PackedFloat64Array = p["s"]
	var raw: PackedFloat64Array = p["raw"]
	var sm: PackedFloat64Array = p["smooth"]
	var n := s_arr.size()

	# Creux et sommets à hystérésis ; une montée se termine aussi après MERGE_GAP_M sans reprendre
	# PLATEAU_RISE_M (replat au sommet). Creux : dernier point le plus bas (fin du replat).
	var ascents := []   # [i_creux, i_sommet]
	var going_up := true
	var i_min := 0
	var i_max := 0
	var i_rise := 0
	for i in range(1, n):
		if going_up:
			if sm[i] > sm[i_max]:
				i_max = i
			if sm[i] > sm[i_rise] + PLATEAU_RISE_M:
				i_rise = i
			var dropped := sm[i] < sm[i_max] - HYSTERESIS_M
			var plateau := s_arr[i] - s_arr[i_rise] >= MERGE_GAP_M
			if dropped or plateau:
				if sm[i_max] - sm[i_min] >= HYSTERESIS_M:
					ascents.append([i_min, i_max])
				going_up = false
				i_min = i
		else:
			if sm[i] <= sm[i_min]:
				i_min = i
			if sm[i] > sm[i_min] + HYSTERESIS_M:
				going_up = true
				i_max = i
				i_rise = i
	if going_up and i_max > i_min and sm[i_max] - sm[i_min] >= HYSTERESIS_M:
		ascents.append([i_min, i_max])

	# Fusion des montées séparées par un court replat ou une courte descente
	var merged := []
	for a in ascents:
		if not merged.is_empty() and s_arr[a[0]] - s_arr[merged[-1][1]] < MERGE_GAP_M and sm[a[1]] >= sm[merged[-1][1]]:
			merged[-1][1] = a[1]
		else:
			merged.append([a[0], a[1]])

	var out := []
	for m in merged:
		var i0: int = _snap_low(raw, m[0], n)
		var i1: int = _snap_high(raw, m[1], n)
		if i1 <= i0:
			continue
		var length := s_arr[i1] - s_arr[i0]
		var gain := raw[i1] - raw[i0]
		var avg := gain / length * 100.0 if length > 0.0 else 0.0
		if not ((length >= MIN_LENGTH_M and avg >= MIN_AVG_PCT) or gain >= MIN_GAIN_M):
			continue
		var win := int(round(1000.0 / STEP_M))
		var max_km := avg
		if i1 - i0 >= win:
			max_km = -INF
			for j in range(i0, i1 - win + 1):
				max_km = maxf(max_km, (raw[j + win] - raw[j]) / (s_arr[j + win] - s_arr[j]) * 100.0)
		out.append({
			"start_s": s_arr[i0],
			"summit_s": s_arr[i1],
			"length_m": length,
			"gain_m": gain,
			"avg_grade_pct": avg,
			"max_km_grade_pct": max_km,
			"summit_alt_m": raw[i1],
		})
	return out


## Premier point du profil brut à moins de SNAP_M du plus haut, à moins de REFINE_M de `i`.
static func _snap_high(raw: PackedFloat64Array, i: int, n: int) -> int:
	var r := int(REFINE_M / STEP_M)
	var lo := maxi(0, i - r)
	var hi := mini(n - 1, i + r)
	var best := lo
	for j in range(lo, hi + 1):
		if raw[j] > raw[best]:
			best = j
	for j in range(lo, best + 1):
		if raw[j] >= raw[best] - SNAP_M:
			return j
	return best


## Dernier point du profil brut à moins de SNAP_M du plus bas, à moins de REFINE_M de `i`.
static func _snap_low(raw: PackedFloat64Array, i: int, n: int) -> int:
	var r := int(REFINE_M / STEP_M)
	var lo := maxi(0, i - r)
	var hi := mini(n - 1, i + r)
	var best := lo
	for j in range(lo, hi + 1):
		if raw[j] <= raw[best]:
			best = j
	for j in range(hi, best - 1, -1):
		if raw[j] <= raw[best] + SNAP_M:
			return j
	return best
