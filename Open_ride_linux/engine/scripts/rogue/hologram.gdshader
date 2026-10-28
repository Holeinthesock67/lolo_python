shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled;

// Hologramme (lot R17) : lignes de balayage fines et scintillement léger (au plus ~1 Hz), translucide.
// Sert au HUD de R11, aux cartes et aux portes de R13 ; `scan_strength` et `flicker` à 0 donnent du verre.
uniform vec3 tint : source_color = vec3(0.1, 0.9, 1.0);
uniform float base_alpha = 0.35;
uniform float scan_strength = 0.35;
uniform float scan_density = 90.0;
uniform float flicker = 0.06;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float scan = 0.5 + 0.5 * sin(world_pos.y * scan_density - TIME * 2.0);
	float flick = 1.0 - flicker * (0.5 + 0.5 * sin(TIME * 6.0));
	float a = base_alpha * (1.0 - scan_strength + scan_strength * scan) * flick;
	ALBEDO = tint * a;
}
