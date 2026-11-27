# EC2 : affichage du monde ouvert, l'ancien décor gardé jusqu'au nouveau

- PR : #1140 ; revue de code vague 3 engine (E5-01, E5-03, E5-04, E5-05, E5-12, E6-04, E7-01, E7-10, E8-01, E8-03 ;
  E5-02 déjà corrigé par OW8, #1105) ; engine seul, sans IPC ni format ; branche partie de main + #1105 (OW8) + #1134 (EC12)
- CHANGELOG (section « Corrigé ») :
  - Monde ouvert : à chaque révision de la route (prolongement, branche choisie), la chaussée, les bâtiments, l'eau,
    les ponts et les tunnels du kilomètre où l'on roule restent affichés jusqu'à ce que leurs remplaçants soient prêts
    (avant : une à plusieurs images sans chaussée sous le vélo, bâtiments retirés le temps d'une tâche).
  - Monde ouvert : l'herbe, les rochers, herbes hautes, murets et la lave ne disparaissent plus autour du cycliste à
    chaque révision ; seuls les tronçons dont la route change sont refaits, et la garde de distance à la route se
    construit en tâche de fond (avant : refaite trois fois sur toute la route connue dans le fil principal).
  - Monde ouvert : les bâtiments, ponts et tunnels du carré où l'on roule ne disparaissent plus quand le tronçon qui
    les porte sort de la fenêtre ; un carré repassé plus tard est de nouveau affiché ; les arbres d'une tuile lisent
    directement ses carrés (forêts OSM et bâtiments exclus pris en compte).
  - Monde ouvert : un tronçon construit avant l'arrivée de ses carrés est refait quand ils arrivent (avant : resté
    sans bâtiments ni eau jusqu'à ce qu'on l'ait dépassé).
  - Monde ouvert : les tuiles lointaines sous la route nouvelle ou autour d'une tuile proche arrivée sont refaites
    (creusement sous la route, enfoncement sous le proche), comme les tuiles proches que la route nouvelle traverse
    (couloir sans arbres) et les voisines d'une tuile arrivée (raccord) ; l'ancien maillage reste jusque-là.
  - Monde ouvert : révisions sautées ou générateur prudent : seules les parties de route qui changent vraiment sont
    refaites (avant : tout depuis la partie 0).
  - Monde ouvert : véhicules et cyclistes du décor posés tout de suite sur la route révisée (avant : sur l'ancienne
    branche le temps de la tâche du décor) ; brouillard, ciel et soleil suivent les biomes de la route à jour (avant :
    ceux du bout de la première route lue pour toute la balade).
- SUIVI :
  - [ ] EC2 : règle « ancien gardé jusqu'au nouveau » pour toute clé de `world_streamer.gd` (`_stale_near`, ruban
    compris) et pour les tronçons d'`osm_streamer.gd` (`_stale_chunks`) ; tronçons propriétaires gardés près de la
    caméra (`OWN_KEEP_M`) ; `OsmLayers.load_tiles_live` ; `live_world.first_changed_part` ; `route_revision.gd` et
    `retarget` de l'herbe, du sol et de la lave, `living_world.update_route` (garde en tâche de fond) ;
    `atmosphere_view.update_route`. Tests : `test_ec2_affichage_ow.gd`, cas ajoutés à `test_live_world.gd` et
    `test_living_decor.gd`. À mesurer au banc multi-zones (cache séparé) : à-coups à chaque révision, avant et après.
