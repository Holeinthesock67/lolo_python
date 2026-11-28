# CN1 : plus de bandeau « Core non joignable » après une action du menu Profil

- PR : à venir ; cahier : aucun (bug vu par le propriétaire le 28 novembre sur main 4363c9cb) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Renommer un profil, vider le profil d'essai ou remettre à zéro n'affiche plus « Core non joignable » ni
    « Commande … sans réponse du core » : le core ne sature plus quand l'accueil redemande ses listes.
- SUIVI :
  - [ ] CN1 : copies d'une requête non recalculées pendant 1 s (`ipc_server.QUERY_COPY_WINDOW_S`), `league_status`
    calculé hors de la boucle à 50 Hz ; test `core/tests/test_copies_requetes.py`.
