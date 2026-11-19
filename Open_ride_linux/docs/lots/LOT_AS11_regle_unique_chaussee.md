# Lot AS11 – Une seule règle de la chaussée pour tous les usagers de la route

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Solution générale aux contacts : registre unique de la chaussée et garde finale dans le core, tous les usagers envoyés par parties (révision IPC 1.20), engine qui affiche seulement, règle commune de dépassement et de rabattement, deux vélos de front au plus | Python, GDScript | AS10 | Grande | En PR le 19 novembre, banc PC à passer |

Demande du propriétaire du 17 novembre : « Il faut vraiment trouver une solution générale aux contacts. » Portée
validée le 17 novembre (« Règle unique pour tous » : cycliste, bots, voiture d'équipe, véhicules, cyclistes du décor ;
la tactique des bots reste une intention), avec les ajouts du même jour : usagers de l'autre voie et demi-tour,
rabattement plus tôt après un dépassement, deux vélos de front au plus. Plan :
`/mnt/project-files/plans/serie-as/PLAN_AS11_REGLE_UNIQUE_CHAUSSEE.md`.

## 1. Causes communes

1. **Une couture core/engine.** Le core faisait foi à 60 m (cyclistes) et 150 m (véhicules) ; au-delà, l'engine
   refaisait sa propre circulation avec d'autres budgets selon la qualité (véhicules 3/5/8, cyclistes 4/8/16), donc
   d'autres usagers, qui croisaient ceux du core (« décor / véhicule », « décor / décor »).
2. **Pas de garantie.** Aucune étape ne vérifiait qu'à la fin du pas personne ne se chevauchait.
3. **Des règles propres à chaque modèle** (zone de dépassement des véhicules de −60 à +30 m, rabattement des
   cyclistes du décor 20 m devant), longues au milieu de la route.

## 2. Ce que fait le lot

1. **Registre et garde finale** (`core/src/openride_core/road_space.py`, module pur) : à la fin de chaque pas
   (places finales, bots et Grand Prix compris), tous les usagers de la route, dans les deux voies et dans le
   repère de la circulation (u = L − s à rebours, lot N23), avec un gabarit unique par sorte ; tout chevauchement
   est écarté par ordre de priorité (objet, cycliste, voiture d'équipe, bot, véhicule, cyclistes du décor) : la
   plus petite place libre voisine, un coureur seulement retenu derrière (jamais avancé), le cycliste jamais
   déplacé ; marge en long de 0,4 m pour l'affichage (extrapolation et arrondi des listes), aucune entre coureurs
   ni entre un coureur et un véhicule (leur placement les tient roue dans la roue ou à l'abri). Chaque correction
   est comptée (`road_space_counts`, rejeu).
2. **Le core seul fait rouler les usagers de la route** (révision 1.20 du contrat IPC) : listes `vehicles` et
   `riders` complètes, par parties d'au plus 8, une partie par trame, `road_part` = [rang, parties] ; l'engine
   (`traffic_model.gd`, `road_cyclists_model.gd`, mode `core_full`) ne tire plus d'usagers, met à jour ceux de
   chaque partie, les extrapole, retire à la dernière partie ceux qu'aucune partie de ce tour ni du précédent n'a
   donnés ; le préréglage ne règle plus que le nombre dessiné (les plus proches). Les cyclistes du décor gardent,
   comme les véhicules, leur écart du core au cycliste de la trame (`core_s`) : le cycliste affiché est extrapolé
   à l'image (0,3 m de moins à 50 km/h, « cycliste / décor » roue dans la roue).
3. **Règle commune de dépassement** (`draft.pass_window`, engine `road_rules.gd`) : on sort quand il faut encore le
   temps de se décaler, plus 1 s, avant de toucher ; on se rabat dès que, rabattu, on ne touchera plus. Mêmes
   valeurs pour les véhicules (`traffic.pass_zone`) et les cyclistes du décor (`road_cyclists.overtake_window`, écart
   réel jusqu'à la ligne de dépassement). Exemple : voiture qui double à 10 km/h de plus, de −12 à +10 m au lieu de
   −60 à +30 m.
4. **Deux vélos de front au plus** (`draft.third_abreast`) : un vélo qui arrive à la hauteur de deux autres déjà de
   front, sans les doubler (par la gauche, ou plus vite qu'eux), rentre dans leur roue ; cyclistes du décor en file
   dès qu'un véhicule de leur sens arrive derrière (`_vehicle_coming`, 80 m) ; voie tenue du Grand Prix inchangée.
5. **Demi-tour** : les coureurs du sens du parcours se placent parmi tous les usagers de ce sens, plus seulement
   ceux proches du cycliste (à rebours, les bots, en face, rattrapaient sans les voir les cyclistes du décor de leur
   sens).

## 3. Tests

- `core/tests/test_road_space.py` : garde, priorités, coureurs, fenêtre commune, troisième vélo.
- `test_road_cyclists.py` (`road_round`, parties `road_part`), `test_decor_rebours.py`, `test_traffic.py`,
  `test_ipc_budget.py` (pire trame : 8 cyclistes ou 8 véhicules et `road_part`, sous 4 096 octets),
  `state.schema.json`, parité core/engine `engine/tests/data/road_cyclists_parity.json` régénérée.
- Empreintes TT2 recalées (0,18 m de plus en 10 min : abri un peu différent).

## 4. Rejeu cloud (19 novembre)

Outils : `python -m openride_core.tools.contacts_replay` (vrai core, `--traces`) puis
`engine/tests/rejeu_contacts.gd` (affichage de l'engine, 60 Hz avec à-coups, critère de `living_decor._count_contacts`),
main contre AS11, 8 parcours de démo, 15, 30 et 50 km/h, 4 bots, sans et avec demi-tour à 300 s, 900 s ;
Grand Prix à onze sur 3 parcours, 30 et 45 km/h. Tableau détaillé :
`/mnt/project-files/plans/serie-as/as11_rejeu/REJEU_AS11_2026-11-19.md`.

## 5. Recette PC

Banc « contacts » low, medium et high (parcours de démo, Irohazaka, `ow_6km`, demi-tour, Grand Prix à onze),
GPU dans les budgets (8 / 13 / 16 ms), planche avant/après validée par le propriétaire avant toute fusion.
