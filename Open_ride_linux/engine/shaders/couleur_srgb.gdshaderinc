// Règle des couleurs des shaders (03/11) : toute couleur écrite par le projet est en sRGB, telle qu'on la lit
// dans un nuancier, un thème ou une palette : constantes (`const vec3 BOIS`), uniformes sans indication
// (`uniform vec3 paint`), couleurs de sommet et d'instance (COLOR), valeurs littérales. Le shader calcule sa
// teinte en sRGB et la convertit UNE fois, au moment de l'écrire : `ALBEDO = lineaire(c)`, `EMISSION =
// lineaire(lueur) * force`. Exceptions de Godot, déjà linéaires à la lecture : uniformes `: source_color`,
// uniformes réglés avec une Color (set_shader_parameter) et textures `: source_color` ; un shader qui les
// mêle à ses couleurs les lit avec `srgb()` d'abord.
//
// Pourquoi : Forward+ (le jeu) traite toute couleur brute comme linéaire ; sans conversion, elle sort plus
// claire et grisée (gravier pâle et bleuté, sable presque blanc, sols des biomes 47 % trop clairs). Le moteur
// Compatibility, lui, affiche les couleurs telles qu'écrites : c'est le seul endroit qui distingue les deux.
// Les essais rendent en Forward+ comme le jeu (engine/tests/rendu_jeu.py).

vec3 lineaire(vec3 c) {
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	return c;
#else
	c = max(c, vec3(0.0));
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
#endif
}

// Inverse de lineaire() : couleur `source_color` (uniforme ou texture, déjà linéaire) ramenée en sRGB.
vec3 srgb(vec3 c) {
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	return c;
#else
	c = max(c, vec3(0.0));
	return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c));
#endif
}
