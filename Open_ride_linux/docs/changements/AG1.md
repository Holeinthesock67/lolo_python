# AG1 : en Course, les bots chassent le premier en puisant dans leur réserve

- PR : à venir ; cahier : aucun (retour d'essai du 28/11, manche 1 de la ligue d'hiver) ; version : 6.0
- CHANGELOG (section « Modifié ») :
  - Course et manches « Course » de la ligue : un bot distancé par le premier (2 à 60 s) le chasse entre 1,06 et
    1,15 × sa CP, sa réserve se vide (barre qui baisse) et il s'arrête sous 15 % ; le bandeau l'écrit (« suit »).
    Les autres modes (séance libre, Grand Prix, Dernier survivant, piste) ne changent pas.
- SUIVI :
  - [ ] AG1 : chasse des bots sur le premier en Course (`bot_tactics._chase`, ligne `race` de `MODE_TACTICS`).
