# Lot CH1 – Ligue d'hiver : cœur de la saison

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CH : module pur `league.py` (calendrier de 8 manches, 11 rivaux fixes, barème, 6 meilleurs, classique, pause, trophées), saison dans `ligue.json` du profil | Python | CH0 (livré, #968), BR4 (#986, rivaux) | Moyenne | En PR le 21 novembre 2026 ; core seul, sans contrat ni affichage |

Série CH (version 6.0, ligue d'hiver, demande du propriétaire du 21 novembre 2026). Plan : `docs/6.0/PLAN_SERIE_CH.md`.

## 1. Objectif

Tenir une saison de ligue en module pur, sans séance ni affichage : ce que les lots CH2 à CH5 branchent ensuite.

## 2. Règles codées (plan §3)

- **Calendrier** (`ROUNDS`) : 8 manches, une par semaine ISO du lundi au dimanche ; modes existants à tour de rôle
  (`race` en tours, `survivor`, `grandprix`, `track` épreuve `elimination`, `race` arrivée en côte, `survivor`,
  `grandprix`, finale `race` en tours) ; le Cyber-Rogue n'y entre pas. La saison commence le lundi de sa semaine.
- **Rivaux** : 11 bots fixes, 3 grimpeurs, 3 rouleurs, 3 sprinteurs, 2 diesels (`FIELD`), nom fictif, équipe écrite
  et couleur ; identité `climber#1`… celle de la cote Elo (`bot_elo.bot_key`), dans l'ordre de `field_profiles`.
  Noms, équipes et couleurs viennent du groupe des rivaux du profil (`rivals.py`, lot R4, `rivaux.json`) : les
  mêmes rivaux que dans les autres modes, aucune liste propre à la ligue (audit du 22 novembre, L4). Une nouvelle
  saison en garde 8 et remplace 3 rivaux (`Roster.renew`, le nouveau venu garde l'identité et la cote).
- **Points** : 25, 20, 16, 13, 11, 10, 9, 8, 7, 6, 5, 4 ; semaine non courue 0 ; total des 6 meilleures manches plus
  la classique × 1,5 ; égalité départagée par les victoires, puis la place à la finale.
- **Une seule tentative** : le premier résultat de la manche de la semaine compte ; une manche d'une autre semaine
  est refusée. Une manche abandonnée n'envoie pas de résultat (CH3).
- **Semaine non courue** : à la semaine suivante (`advance`), le classement des rivaux est tiré d'après leur cote et
  l'avantage de leur caractère sur le terrain de la manche (`simulate_order`, Plackett-Luce à l'échelle de l'Elo,
  reproductible par la graine de la saison) ; le simulateur est un paramètre, que CH2 peut remplacer.
- **Classique** : un samedi ou un dimanche de la saison, pas dans le passé ; elle se court de cette date à la fin
  de la semaine 8 (la date reste changeable tant qu'elle n'est pas courue) ; non courue, simulée à la fin.
- **Pause** : gèle le calendrier par semaines entières (lundis franchis) ; plus de 4 semaines gelées en tout :
  saison close au classement du moment, sans trophée.
- **Fin** : trophée d'or, d'argent ou de bronze sur le podium, « Trophée de régularité » pour 6 manches courues
  hors podium.
- **Intensité facile** (R1) : gardée avec le résultat (`easy`), affichée au classement de la manche (CH4).
- **Ligne d'accueil** (`home_line`) : « 4e · manche 3/8 : Grand Prix, à courir cette semaine », puis « 4e · manche
  3/8 faite · prochaine lundi » ; saison en pause, finie ou close écrites en mots.
- **Fichier** : `<profil>/ligue.json`, version 1, écriture sûre ; un fichier abîmé est mis de côté
  (`ligue.json.abime`) et la ligue repart sans saison.

## 3. Livraison (21 novembre 2026)

- Core : `core/src/openride_core/league.py`.
- Tests : `core/tests/test_league.py` (barème, tentative unique, semaines sautées simulées, 6 meilleurs, classique,
  égalités, pause courte et longue, trophées, ligne d'accueil, nouvelle saison, fichier abîmé et refus, simulation
  selon la cote et le terrain, 60 saisons simulées : part juste du cycliste de même force, environ 1/12).

## 4. Reste

- CH2 : calibrage à 10 % de victoire depuis la FTP et la cote Elo (#941), par type de manche.
- CH3 : lancer la manche de la semaine (plateau dans l'ordre `field_profiles`, résultat renvoyé par `record`),
  contrat IPC révision 1.30.
- CH4 : écrans ; CH5 : classique (choix de la date, 1 h 30, séance conseillée).

## Recette PC
Catégorie : logique
- Cloud : tests du core (`core/tests/test_league.py`), rien d'autre : le module n'est branché nulle part.
- PC : aucun banc (rien ne change à l'écran ni dans la séance) ; la fumée du paquet suffit s'il y en a un.
- Versions : aucune (WORLDGEN_VERSION, SCHEMA_VERSION et révision IPC inchangés)
