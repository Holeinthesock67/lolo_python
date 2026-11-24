# Lot CH2 – Ligue d'hiver : dureté à 10 % de victoire

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CH : cotes des rivaux par manche pour environ 10 % de chances de victoire, cote du cycliste tenue contre elles, banc `ligue_campagne` | Python | CH1, BOT-elo (#941) | Petite | En PR ; core seul, branché par CH3 |

Plan : `docs/6.0/PLAN_SERIE_CH.md` §3.3. Décision du propriétaire du 21 novembre : bots calés sur la FTP pour environ
10 % de chances de gagner une manche (part juste à 12 coureurs : 8 %), tenus par la cote Elo.

## 1. La règle

- La puissance des bots suit déjà la FTP du cycliste (`bot_effort` : FTP × courbe de puissance × objectif du jour) ;
  la cote Elo (#941) règle leur niveau autour de ce point (+2,5 % de puissance par 100 points, `level_factor`).
- **Cotes de manche** (`league.round_ratings`) : cote du cycliste + écart propre du bot (#941) + **étalement de la
  saison** (rang de force tiré par la graine, de +75 à −75 points, `SPREAD_WIDTH`) + avantage du caractère sur le
  terrain (`AFFINITY`), le tout décalé pour que la probabilité de victoire du cycliste (Plackett-Luce à l'échelle
  Elo, `win_probability`) vaille exactement `TARGET_WIN` = 10 %, manche par manche et donc par type de manche.
- **Cote du cycliste** (`league.rider_update`) : même Elo à plusieurs que `EloBook.update` (K, bornes, écarts des
  bots recentrés), mais contre les cotes de manche. À l'équilibre, la cote est la vraie force du cycliste, et il
  gagne 10 % des manches quel que soit son niveau : un cycliste qui progresse voit sa cote monter et le plateau
  avec, la chance de victoire reste la même.
- `league.level_factors` : facteur de niveau de chaque bot pour la séance (CH3).

## 2. Vérification

Pas d'essai vélo (une manche par semaine ne dit rien du réglage). Banc `python -m openride_core.tools.ligue_campagne`
(`docs/OUTILS_DE_TEST.md`) : 100 saisons par force (1 200, 1 500, 1 900 points), 80 % de présence, 3 saisons de
rodage. Relevé du 21 novembre (graine 1, 200 saisons) : 10,3 %, 9,2 % et 9,7 % de victoires, place moyenne 5,7 à
5,8, cote finale à moins de 15 points de la force. À FTP 250 W au Tempo, rivaux d'une manche type de 193 à 203 W à
la cote de départ.

Limite connue : le banc juge le modèle (arrivée tirée selon l'Elo), pas la physique ; le lien cote → watts →
arrivée réelle se mesure avec la vraie séance quand CH3 lance les manches (banc `elo_campagne` étendu).

## 3. Livraison

- `core/src/openride_core/league.py` (section « calibrage »), `core/src/openride_core/tools/ligue_campagne.py`.
- Tests : `core/tests/test_league_calibrage.py`.

## Recette PC
Catégorie : logique
- Cloud : tests du core et banc `ligue_campagne` (sans GPU, moins d'une seconde).
- PC : aucun banc (rien n'est branché dans la séance).
- Versions : aucune (WORLDGEN_VERSION, SCHEMA_VERSION et révision IPC inchangés)
