shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled;

// Mur de lumière translucide et ondulant (lot R17) : Firewall, traînées, mur du Puncheur. L'ondulation
// est lente (une période toutes les 2 à 3 s) ; le bord haut s'efface.
uniform vec3 tint : source_color = vec3(1.0, 0.18, 0.3);
uniform float base_alpha = 0.55;
uniform float wave_amp_m = 0.15;
uniform float wave_speed = 2.0;

varying float wave_phase;

void vertex() {
	wave_phase = sin(VERTEX.x * 3.0 + TIME * wave_speed);
	VERTEX.z += wave_phase * wave_amp_m;
}

void fragment() {
	float edge = 1.0 - smoothstep(0.7, 1.0, UV.y);
	float ripple = 0.8 + 0.2 * wave_phase;
	ALBEDO = tint * base_alpha * edge * ripple;
}
