# Lot CH3 – Ligue d'hiver : lancer la manche de la semaine

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CH : manche de la ligue lancée par la séance (CH3a : la Course), résultat dans `ligue.json`, cote tenue, encart du bilan, contrat IPC 1.30 | Python | CH1, CH2, CR1 (#939), BOT-elo (#941) | Moyenne | En PR le 22 novembre 2026 ; core seul, écrans au lot CH4 |

Plan : `docs/6.0/PLAN_SERIE_CH.md` §3.1 et §3.4. Objectif du propriétaire (22 novembre) : démarrer un championnat le
week-end du 28-29 novembre. CH3a branche la manche 1 (Course en tours) ; CH3b branchera les autres modes avant leur
semaine (Dernier survivant en semaine 2).

## 1. La règle

- **Commandes** (révision 1.30) : `league_status` (saison mise à jour au jour, semaines passées simulées pour les
  rivaux) et `league_new` (nouvelle saison, refusée si une saison court) ; réponse `league` (schéma `league`).
- **`start` avec `league` = `true`** : manche de la semaine, dans le mode de la manche (`race` en CH3a). Le core
  compose le plateau des 11 rivaux dans l'ordre de la saison (identités Elo), niveau = « Niveau des bots » × facteur
  de leur cote de manche (CH2, 10 % de chances de victoire), noms des rivaux. Sur une boucle, le nombre de tours
  vise environ 27 min à la puissance visée du jour (`league.laps_for`, 1 à 10 tours). La cote commune n'est pas mise
  à jour par la règle générale : la manche la tient elle-même (`league.rider_update`).
- **Arrivée** : premier résultat écrit dans `ligue.json` du profil, cote dans `elo.json`, `summary.league` (place,
  points, place au général avant et après, mouvement écrit, intensité facile, cinq lignes du classement) et
  `summary.elo` (`mode` = `league`) ; journal : `league_start`, `league_round`, `elo`.
- **Manche arrêtée avant l'arrivée** : rien n'est compté, elle se recourt dans la semaine.
- **Plantage du core pendant une manche** : la reprise ne restaure pas les courses ; aucun résultat n'est écrit,
  la manche compte comme abandonnée et se recourt dans la semaine (audit du 22 novembre, L10).
- **Horloge qui recule** : `ligue.json` garde le dernier jour vu (`last_seen`) ; la ligue ne revient jamais avant
  lui (pile du BIOS, double amorçage ; audit L11).
- **Refus** (`bad_args`, rien ne démarre) : sans saison ou manche déjà faite, mode qui n'est pas celui de la
  manche ou pas encore jouable, ERG ou argument `bots`, parcours en ligne pour une manche en tours, monde ouvert.
- **Intensité du jour** : « facile » (objectif endurance ou récupération) est gardé avec le résultat.

## 2. Vérification

- `core/tests/test_league_session.py` : saison créée et message validé par son schéma, manche courue (11 rivaux à
  leurs noms et profils, un tour en test), résultat, cote et bilan, une seule tentative, manche arrêtée non comptée,
  refus, intensité facile, manche coupée par un plantage, horloge qui recule.
- Contrat : `docs/contracts/ipc_v1.md` (commandes, `start.league`, journal 1.30), `league.schema.json`,
  `state.schema.json` (`summary.league`), `cmd.schema.json`.

## Correctifs de la revue du 23 novembre (CH3c, rapport `statut/revue-code-vague2/F1.md`)

- F1-01 : la manche s'enregistre au jour de son départ (dimanche soir, arrivée après minuit : elle compte).
- F1-02 : la classique n'est simulée que si le cycliste l'a datée ; tant qu'elle n'est pas jouable (CH5), personne
  ne la marque. Choix à confirmer par le propriétaire (le plan §3.2 dit « la manquer ne coûte rien »).
- F1-03 : une semaine dont le mode n'était pas encore jouable est neutralisée (source `neutre`, personne ne marque)
  au lieu d'être simulée avec 0 point pour le cycliste seul.
- F1-04 : lignes de l'encart du bilan réduites à place, nom, points et `me` ; la trame d'arrivée tient sous 4 096
  octets (test avec le bilan le plus lourd du budget).
- F1-05 : la manche « arrivée en côte » refuse une boucle ; longueur d'un parcours en ligne vérifiée avant le départ.
- F1-07 : `league_new` garde la saison close dans `ligue_saison_<n>.json` ; rivaux écrits avant la saison (F1-12).
- F1-08 : types faux dans `ligue.json` refusés (fichier mis de côté), jamais une autre exception.
- F1-14 : `league_status` est une requête (réponse à chaque copie). F1-15 : jour vu remis à zéro au changement de profil.
- Non traités ici : F1-06 (essai au clavier sur le vrai profil : à éviter, la remise à zéro du 28/11 traite les trois
  fichiers), F1-09, F1-10, F1-11, F1-13.

## 3. Limites connues (lots suivants)

- Écrans (accueil, écran de la ligue, encart du bilan) : CH4. Pas d'échauffement ERG propre à la manche tant que la
  règle d'échauffement des courses n'est pas dans main.
- `bots_preview` sur l'écran Prêt donne encore les watts du plateau général, pas ceux des rivaux de la manche.

## Recette PC
Catégorie : logique
- Cloud : tests du core (`test_league_session.py`, contrat IPC).
- PC : fumée + medium (une manche de Course en mode simulé, 11 rivaux) ; pas de capture (aucun écran ajouté).
- Versions : révision IPC 1.30 (WORLDGEN_VERSION et SCHEMA_VERSION inchangés)
