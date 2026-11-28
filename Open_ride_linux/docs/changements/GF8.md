# GF8 : banc des menus, touche simulée perdue par le banc dite comme telle

- PR : #1166 ; fil « Fiabiliser les outils de banc » (27 novembre 2026), échecs rGL2 de #1054 (24/11) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Banc des menus, voie clavier : la touche simulée part en un seul datagramme sur le port des trames `state`.
    Pendant un blocage du fil principal de l'engine (monde ouvert, « engine muet 14,5 s » des bancs rGL2 high et
    low), le datagramme peut être perdu : « LEFT_SHORT reçu par l'engine » en échec, mis au compte de la PR. Un geste
    non reçu dit maintenant si l'engine a accusé la touche (« [test] key done ») : « touche jamais accusée par
    l'engine : perdue par le banc (outil), pas par le jeu ». Aucun renvoi : la première version renvoyait la
    touche, et au cloud une touche seulement tardive faisait un double appui (trains #1170 et #1172).
- SUIVI :
  - [ ] GF8 : menu_bench, touche simulée sans accusé de l'engine dite perdue par le banc.
