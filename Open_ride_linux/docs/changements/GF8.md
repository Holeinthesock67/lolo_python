# GF8 : banc des menus, touche simulée accusée et renvoyée une fois

- PR : #1166 ; fil « Fiabiliser les outils de banc » (27 novembre 2026), échecs rGL2 de #1054 (24/11) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Banc des menus, voie clavier : la touche simulée part en un seul datagramme sur le port des trames `state`.
    Pendant un blocage du fil principal de l'engine (monde ouvert, « engine muet 14,5 s » des bancs rGL2 high et
    low), le tampon du noyau se remplit de trames et la touche se perdait : « LEFT_SHORT reçu par l'engine » en
    échec, mis au compte de la PR. Le banc attend maintenant l'accusé « [test] key done=<touche> » (silences de
    l'engine non comptés) et renvoie la touche une seule fois s'il ne vient pas ; le rapport le relève en INFO
    (« touches perdues par le banc, renvoyées une fois »).
- SUIVI :
  - [ ] GF8 : menu_bench, accusé de la touche simulée et renvoi unique.
