# AG1 : en Course, les bots chassent le premier en puisant dans leur réserve

- PR : #1174 ; cahier : aucun (retour d'essai du 28/11, manche 1 de la ligue d'hiver) ; version : 6.0
- CHANGELOG (section « Modifié ») :
  - Course et manches « Course » de la ligue : un bot distancé par le premier (2 à 60 s) le chasse entre 1,06 et
    1,15 × sa CP, sa réserve se vide (barre qui baisse) et il s'arrête sous 15 % ; le bandeau l'écrit (« suit »).
    Moments critiques : en montée et quand l'écart se creuse (3 s de plus en 30 s), la chasse part dès 30 % de
    réserve et à fond. Final (5 derniers km, ou dernier tour s'il fait moins de 10 km) : tout pour le tout,
    puissance dosée pour finir la réserve vide à la ligne ; dans le groupe du premier, attaque aux 1 500 derniers m.
    Les autres modes (séance libre, Grand Prix, Dernier survivant, piste) ne changent pas.
- SUIVI :
  - [ ] AG1 : chasse des bots sur le premier en Course (`bot_tactics._chase`, ligne `race` de `MODE_TACTICS`).
