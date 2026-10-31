# Lot R14 – Recette du mode Cyber-Rogue sur le PC et le vélo

## 1. Objectif

Vérifier par le propriétaire, sur le PC cible (GTX 1060) et sur le vélo, que le mode Cyber-Rogue est jouable, lisible, sûr et fidèle à l'objectif choisi. Lot du propriétaire ; Claude prépare la fiche et lit les journaux.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_R.md`, `docs/lots/LOT_R0_delai_frein.md` (valeurs retenues), `LOT_R7_equilibrage_run_simulee.md` (cibles).
2. `docs/RECETTE_E3_E4.md` (forme d'une fiche de recette).

## 3. Prérequis

R8, R9 et R10 à R13 livrés ; R15 et R16 livrés.

## 4. Travail demandé

### 4.1 Fiche de recette (rédigée par Claude au début du lot)

| # | Essai | Attendu |
| --- | --- | --- |
| 1 | Lancement depuis le bureau, accueil, « Cyber-Rogue », départ, prêt | Aucun clavier nécessaire ; durée et objectif gardés |
| 2 | Run de 30 min en endurance | IF entre 0,62 et 0,72 ; surchauffe ressentie comme juste |
| 3 | Run de 45 min en seuil | Calendrier tenu à ± 1 min ; boss atteint à 30 min |
| 4 | Run de 45 min en VO2max | Bosses ressenties sur le trainer ; Perfect Shifts réussis quand le geste est bon |
| 5 | Boutons | + et B courts et longs, Z court et long, A court et long reconnus à chaque appui ; Z n'a qu'un sens à chaque instant ; Y met en pause et reprend ; aucune pause involontaire |
| 6 | Click éteint 30 s pendant une salle | Firewall arrêté, reprise propre |
| 7 | Core tué pendant une salle | Reprise au début de la salle |
| 8 | Abandon depuis la pause | Bilan `abandoned`, FIT enregistré |
| 9 | Image | 60 images/s ou plus en `low` sur la GTX 1060, salle du Saboteur et boss compris |
| 10 | FIT | Lu par GoldenCheetah et Garmin Connect, tours par salle |

### 4.2 Après la recette

- Valeurs à retoucher dans `balance.toml` (R7) notées avec leur raison ; défauts constatés en issues.
- Ressenti du propriétaire sur la difficulté, la lisibilité et l'envie de rejouer.

## 5. Fichiers concernés

- **Créés :** `docs/RECETTE_SERIE_R.md` (fiche et résultats, sans données personnelles : ni nom, ni poids, ni FTP réelle, ni trace).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Les 10 essais faits ; chaque écart a une issue ou une décision du propriétaire.
2. Le propriétaire déclare le mode publiable pour la 2.0.

## 8. Hors périmètre

- Nouvelles cartes, nouveaux archétypes (après la 2.0).

## 9. Partie automatique (lot X51, 30 octobre)

Les essais 2, 3, 4 (calendrier et IF), 6 (Click coupé 30 s), 7 (core tué), 8 (abandon) et 10 (FIT lu par le SDK de Garmin, un tour par salle) passent dans la vraie séance du core avec `python -m openride_core.tools.rogue_recette`, sans vélo. L'essai 5 est couvert pour la logique par la matrice des boutons (X42), et l'essai 9 par `rogue_bench.py --native` sur la GTX 1060. Restent au propriétaire : le ressenti (surchauffe, bosses, tenue du seuil, dont l'IF simulé est au bas de la plage), les vrais appuis sur le Click, l'import du FIT dans Garmin Connect et GoldenCheetah, le regard sur `engine/tests/rogue_galerie.py` et l'écoute sur `engine/tests/rogue_ecoute.py`.
