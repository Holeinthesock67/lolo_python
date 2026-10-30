shader_type spatial;
render_mode cull_disabled, unshaded, depth_draw_opaque;

// Fantôme de la dernière séance (bots_view.gd, lot O7) : même coureur et même vélo que les bots
// (crowd.gdshaderinc), translucide et sans éclairage.
#define CROWD_GHOST
#include "res://shaders/crowd.gdshaderinc"
