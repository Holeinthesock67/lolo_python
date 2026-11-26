shader_type spatial;
render_mode cull_disabled;

// Mobilier de rue de la ville néon (lots NV4 et NV5, neon_street.gd), sans texture.
// - couleur de sommet : teinte de la partie ; alpha 1 : partie ordinaire (éclairée par la scène) ; alpha 0 :
//   partie lumineuse (globe, cadre d'enseigne, ampoule), de la teinte de l'instance (INSTANCE_CUSTOM.rgb) si elle
//   en a une, sinon de sa couleur de sommet ;
// - global `neon_glow` (lot NV3) : part de l'ambiance ; les parties lumineuses restent à peine allumées sans elle.

global uniform float neon_glow;
uniform float energy = 3.2;

varying vec3 tint;

void vertex() {
	tint = INSTANCE_CUSTOM.rgb;
}

void fragment() {
	float lit = 1.0 - COLOR.a;
	vec3 glow = mix(COLOR.rgb, tint, step(0.001, tint.r + tint.g + tint.b));
	ALBEDO = mix(COLOR.rgb, vec3(0.02), lit);
	ROUGHNESS = 0.9;
	EMISSION = lit * glow * energy * max(neon_glow, 0.1);
}
