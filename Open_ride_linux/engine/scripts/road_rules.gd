extends RefCounted

## Règle commune de dépassement des usagers de la route (lot AS11, demande du propriétaire du 17 novembre : « rabattre
## plus tôt »), jumelle de `draft.pass_window` du core (mêmes valeurs) : fenêtre (début, fin) de l'écart du centre de
## celui qui double au centre de celui qu'il double (négatif : derrière) où il roule hors de sa ligne. Il sort quand
## il lui faut encore le temps de se décaler de `lateral_m` à `lateral_mps`, plus PASS_SAFETY_S, avant de toucher ;
## il se rabat dès que, rabattu à cette vitesse de rapprochement, il ne touchera plus.
const PASS_SAFETY_S := 1.0
const PASS_MARGIN_M := 0.3
const BIKE_LENGTH_M := 1.7


static func pass_window(len_a: float, len_b: float, closing_mps: float, lateral_m: float, lateral_mps: float,
		margin_m: float = PASS_MARGIN_M) -> Vector2:
	var reach := 0.5 * (len_a + len_b) + margin_m
	var t_lat := absf(lateral_m) / maxf(lateral_mps, 0.1)
	var dv := maxf(closing_mps, 0.5)
	return Vector2(-(reach + dv * (t_lat + PASS_SAFETY_S)), reach + dv * t_lat)
