# CD1 : une seule chaussée dessinée pour tout le décor (version simple)

- PR : à venir ; cahier : plans/CADRAGE_CHAUSSEE_DESSINEE_2026-11-26.md (dossier du projet), version simple sans la
  mise à jour par révision du monde ouvert libre (abandonné le 27/11) ; version : 6.0. Engine seul, ni IPC ni WORLDGEN.
- CHANGELOG (section « Corrigé ») :
  - Décor : herbe, arbres, forêts, animaux, bâtiments, cours d'eau, candélabres, balises, panneaux, spectateurs et
    passants voient la même chaussée (route dessinée et amorces du départ et de l'arrivée) : plus de maison posée
    sur la route ou sur une amorce, plus de rivière qui traverse une amorce ou une autre portion d'une route qui
    repasse, plus de candélabre, de balise ni de spectateur sur la portion d'en face d'une épingle.
  - Arbres : plus aucun arbre dans un lac, la mer ou une grande rivière (reprise de #1056).
- SUIVI :
  - [ ] CD1 : `drawn_road.gd`, chaussée dessinée unique (CD1a : `road_clearance.gd` en façade, sans changement ;
    CD1b : arbres, forêts, faune ; CD1c : bâtiments et cours d'eau, arbres hors de l'eau ; CD1d : garde finale des
    objets du bord de route) ; tests `test_drawn_road.gd`, `test_drawn_road_usage.gd` ; banc du périmètre de
    non-régression (5 parcours de référence, paire main/branche) à faire après le championnat.
