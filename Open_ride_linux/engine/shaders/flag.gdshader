shader_type spatial;
render_mode cull_disabled;

// Tissu des drapeaux du Lot P12 : le maillage part du mât (x = 0) vers +x local, que flags.gd oriente
// vers où souffle le vent. Vague qui court le long du tissu, d'amplitude croissante vers le bord libre ;
// par vent faible, le tissu retombe le long du mât.
uniform vec3 albedo : source_color = vec3(0.85, 0.15, 0.15);
uniform float strength = 0.0;   // 0 à 1 (1 = 60 km/h), wind_model.gd
uniform float gust = 0.0;       // 0 à 1
uniform float phase = 0.0;      // phase continue du vent (s), wind_model.gd

void vertex() {
	float u = clamp(VERTEX.x / 1.5, 0.0, 1.0);
	float lift = clamp(strength * 2.5, 0.0, 1.0);
	// Retombée : sans vent, le bord libre descend le long du mât.
	float droop = (1.0 - lift) * u;
	VERTEX.y -= droop * VERTEX.x * 0.9;
	VERTEX.x *= mix(0.25, 1.0, lift);
	float amp = (0.06 + 0.12 * gust) * u * (0.3 + lift);
	VERTEX.z += sin(VERTEX.x * 4.0 - phase * (3.0 + 6.0 * strength)) * amp;
}

void fragment() {
	ALBEDO = albedo;
	ROUGHNESS = 0.8;
}
