shader_type spatial;
render_mode cull_back;

// Volume sombre à arêtes lumineuses (lot R17) : l'arête est la bande de l'UV proche du bord de chaque
// face, d'épaisseur constante à l'écran (`width_px`, mesurée avec fwidth). Pas de texture.
uniform vec3 body_color : source_color = vec3(0.07, 0.08, 0.12);
uniform vec3 line_color : source_color = vec3(0.1, 0.9, 1.0);
uniform float width_px = 2.0;

void fragment() {
	vec2 d = min(UV, vec2(1.0) - UV);
	float e = min(d.x, d.y);
	float w = max(fwidth(e), 0.00001) * width_px;
	float m = 1.0 - smoothstep(0.0, w, e);
	ALBEDO = body_color;
	ROUGHNESS = 0.9;
	EMISSION = line_color * m;
}
