shader_type spatial;
render_mode cull_disabled, fog_disabled;

// Avions de ligne du Lot P26 (sky_mesh.gd), dessinés par homothétie autour de la caméra à
// sky_traffic_model.gd RENDER_M au lieu de leurs 10 km : pas de brouillard (il les effacerait à cette
// distance), mêmes zones et paramètres que vehicle.gdshader.
#include "res://shaders/vehicle.gdshaderinc"
