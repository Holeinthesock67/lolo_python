# GF6 : banc des menus, engine sans hello_ack diagnostiqué puis relancé une fois

- PR : à venir ; fil « Fiabiliser les outils de banc » (27 novembre 2026) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Banc des menus : sans hello_ack en 40 s, le rapport écrit pourquoi (engine vivant ou code de sortie, hello vu
    ou non par le core, dernières lignes de l'engine), puis relance l'engine une seule fois ; un passage sauvé par la
    relance le dit (« hello_ack après une relance de l'engine »). Train #1151 : 1 passage sur 18, rien pour trancher.
- SUIVI :
  - [ ] GF6 : menu_bench, diagnostic du hello_ack manquant et relance unique de l'engine.
