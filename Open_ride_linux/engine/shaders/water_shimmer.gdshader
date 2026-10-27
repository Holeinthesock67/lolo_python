shader_type spatial;

// Eau qui scintille (Lot P12) : même couleur et même rugosité que le matériau d'eau d'E4, plus une
// normale perturbée par deux réseaux d'ondes qui défilent avec le vent (`flow`, avancé par
// water_mesh.gd) ; les reflets du soleil glissent sur la surface. Aucune valeur aléatoire par image,
// donc aucun clignotement : tout est continu en position et en temps.
uniform vec3 albedo : source_color = vec3(0.12, 0.32, 0.38);
uniform float roughness_base = 0.10;
uniform vec2 flow = vec2(0.0);        // décalage accumulé (m), dans le sens du vent
uniform float strength = 0.3;         // amplitude des ondes, 0 à 1

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = world_pos.xz;
	vec2 a = p * 0.9 + flow;
	vec2 b = p * 1.7 - flow.yx * 0.6;
	float dx = cos(a.x + 0.6 * a.y) * 0.6 + cos(b.x * 1.3 - b.y) * 0.4;
	float dz = cos(a.y - 0.4 * a.x) * 0.6 + cos(b.y * 1.1 + b.x * 0.7) * 0.4;
	float s = 0.15 + 0.35 * strength;
	NORMAL_MAP = normalize(vec3(0.5 + 0.5 * dx * s, 0.5 + 0.5 * dz * s, 1.0));
	ALBEDO = albedo;
	ROUGHNESS = roughness_base;
	SPECULAR = 0.6;
}
