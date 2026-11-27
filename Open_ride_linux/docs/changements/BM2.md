# BM2 : banc des menus, gestes et vérifications sur un menu posé

- PR : à venir ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Banc des menus : à la souris, A maintenu clique sur l'élément sous le focus une fois le menu posé (état relu
    jusqu'au retour du focus, 5 s au plus, silences de l'engine non comptés). L'écran Prêt du vélodrome, reconstruit
    après le choix de l'épreuve, n'avait un instant aucun focus : le clic partait au centre de l'écran (échecs
    « clic sur «  » : sans réponse » de #1093 et #953, sans rapport avec ces PR).
  - Banc des menus : les attentes d'écran prennent le ralentissement du rendu logiciel comme les autres étapes ;
    une étape `transitoire` (écran d'un instant) est passée si le menu est déjà sur l'écran de l'étape suivante
    (#964 : « Compilation de … » fini pendant 13 s de silence de l'engine sur un runner lent).
  - Banc des menus : avant de déplacer le focus vers un élément, le banc attend que la liste remplie par le core
    montre l'élément et un focus (écran « Contenus » juste ouvert, parcours_demo au clavier, CI de #1108).
- SUIVI :
  - [ ] BM2 : banc des menus sur un menu posé (focus attendu avant un clic, écrans transitoires).
