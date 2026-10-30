# OpenRide 4.0 – Bonus tactiques (série TT)

29 octobre 2026. Demande du propriétaire : des bonus tactiques en plus de ceux de la série T (Plume, Enclume, Camion, Casque aéro, Burrito, Rouleau compresseur, Fantôme). L'étude les a confrontés au moteur réel du core ; **toutes ses recommandations ont été retenues par le propriétaire le 29 octobre (« ok pour tout »)**. Ce plan les découpe en lots. Les cahiers seront rédigés au démarrage de la série et ajoutés à `docs/lots/00_INDEX.md`.

## 1. En résumé

- Les bonus de la série T existent déjà ([lot T6](../lots/LOT_T6_bonus.md), `core/src/openride_core/powerups.py`) : `lightweight` (masse × 0,90), `aero` (CdA × 0,75) et `power` (+10 %), 15 s chacun, une réserve, obtenus en fin de segment et sous une arche tous les 5 km, activés par Z court, coupés en ERG. Le Casque aéro est exactement `aero` ; la Plume est `lightweight` avec une autre durée.
- La 4.0 garde ce cadre et réécrit `powerups.py` sur **un seul modèle de bonus décrit par des données** (effet, facteur, durée, conditions), sans cas particulier dans le code.
- Les bonus restent **facultatifs** : le réglage « Bonus » passe de `on`/`off` à `off` / `classiques` / `tactiques`, `classiques` par défaut (comportement actuel inchangé).
- Ils n'agissent que sur la vitesse virtuelle. En SIM, seuls ceux qui changent l'abri, le CdA ou le Crr se sentent, par le supplément de pente déjà calculé (`grade_offset_pct` de `core/src/openride_core/wind.py`) ; en ERG, ils sont tous coupés.

## 2. Bonus retenus

Gains calculés avec `core/src/openride_core/physics.py` (cycliste et vélo de 84 kg, CdA 0,32 m², Crr 0,004, 250 W) : écart sur un cycliste identique sans bonus. Repère d'équilibrage : **1,5 à 2,5 s dans le terrain idéal**, presque rien ailleurs.

| Bonus | Identifiant (contrat) | Effet | Durée | Conditions | Gain dans le terrain idéal | Ressenti SIM |
| --- | --- | --- | --- | --- | --- | --- |
| Plume | `feather` | masse × 0,90 | **20 s** | — | ≈ 2 s à 8 % | Aucun (T-Q3) |
| Enclume | `anvil` | masse × **1,6** (relative, ≈ +50 kg pour 84 kg) | 15 s | Activation refusée si la pente dépasse −1,5 % ; masse en plus suspendue au-dessus de −0,5 % (le temps continue) | 1,5 s à −3 %, 2,3 s à −6 % | Aucun ; supplément de pente calculé avec la masse de base |
| Aspiration + (ex-Camion) | `draft_plus` | abri × 1,5, plafonné à **0,55** (plafond du cœur de groupe de la série AS), portée de l'abri 15 → 25 m | 40 s | Tiré seulement avec des bots | 2,0 s roue dans la roue | Oui : −1,0 → −1,4 point sur le plat |
| Casque aéro | `aero` | CdA × 0,75 | 15 s | — | 1,3 s sur le plat ; +8,8 m en 15 s au sprint à 600 W | Oui quand il y a vent ou abri |
| Puissance (T6) | `power` | puissance prise en compte × 1,10 | 15 s | — | 1,4 s à 8 % | Aucun |
| Échappée (Burrito + Fantôme fusionnés) | `breakaway` | les bots derrière toi ne reçoivent plus ton abri **et** ne répondent pas à ton attaque ; avatar semi-transparent | 20 s | Tiré seulement avec des bots ; refusé à moins de 400 m de l'arrivée ou de la fin d'un sprint | Un suiveur collé perd ≈ 14 m (1,4 s) | Aucun |
| Rouleau compresseur | `roller` | Crr du bitume sur une surface non revêtue, transitions de 20 m | 30 s | Tiré seulement avec le gravel actif et au moins 1 km non revêtu dans les 5 km devant | ≈ 2,5 s | Oui : le supplément du gravel disparaît (−0,6 point) |

Noms : « Camion » se confondait avec l'abri derrière un vrai véhicule lent (série AS) ; « Fantôme » est déjà le bot de rejeu (`kind = "ghost"`).

## 3. Règles communes

- **Obtention :** inchangée (fin de segment, arche tous les 5 km, une réserve, un nouveau remplace l'ancien), avec un **tirage qui exclut les bonus inutiles** (conditions du tableau ; Enclume seulement s'il y a une descente d'au moins 300 m sous −1,5 % dans les 5 km devant). Jeu `classiques` : Plume, Casque, Puissance ; jeu `tactiques` : les sept. Pas de tirage selon la place (il fausserait les records).
- **Activation :** Z court (et sa touche, lot O17), plan de boutons inchangé ([spécification générale](../SPECIFICATION_GENERALE.md) §7.1). Un seul bonus actif. Un bonus dont la condition n'est pas remplie est refusé : réserve gardée, raison affichée 2 s, refus au journal.
- **ERG :** tous coupés, réserve gardée (T-Q2), **ERG d'une session libre compris** : c'est déjà le comportement du code (`race.set_erg` dès que le mode vaut `ERG`) ; la ligne O18-7 et le §7.1 de la spécification, qui disent le contraire, sont corrigés par TT1.
- **Bots :** ils ne prennent pas de bonus dans la 4.0 ; le calibrage T13 reste juste.
- **Records :** tables « avec » et « sans bonus » (T-Q1) ; tout bonus tactique compte « avec ».
- **Journal et FIT :** puissance mesurée intacte ; événement `powerup` (type, début, durée, refus).
- **Fichier de valeurs :** `~/OpenRide/powerups.toml` gagne une section par bonus (facteur, durée, conditions), avec des bornes par bonus (l'Enclume sort de la borne actuelle 0,5–1,5).
- **Option coupée :** avec `off`, une séance est identique au bit près ; avec `classiques`, identique à la 2.0 (test).

## 4. Lots

| Lot | Contenu | Dépend de | Type |
| --- | --- | --- | --- |
| TT0 | Ce plan ; cahiers TT1 à TT8 et lignes de `docs/lots/00_INDEX.md` | — | Interne (docs) |
| TT1 | Contrat IPC, **première révision libre au moment de la fusion** (la 1.6 est réservée à titre provisoire à la série U ; règle : ordre des fusions) : valeurs `feather`, `anvil`, `draft_plus`, `aero`, `power`, `breakaway`, `roller` de `held` et `active` (`light` gardé comme alias de `feather` pendant une révision), champ facultatif `refused` (raison, 2 s), réglage `powerups.mode` à trois choix (message `settings` sous 1 400 octets) ; correction ERG libre de la spécification ; engine tolérant aux valeurs inconnues | Révision 1.5 fermée | Interne (contrat) |
| TT2 | Core : modèle unique de bonus dans `powerups.py`, tirage contextuel, refus motivé ; Plume, Casque, Puissance, Enclume ; supplément de pente SIM à masse de base ; séance identique avec `off` et `classiques` | TT1, T6, T7 | Délégable |
| TT3 | Aspiration + dans `core/src/openride_core/draft.py` : multiplicateur, plafond 0,55, portée 25 m | TT2, AS1 (AS4 souhaitable) | Délégable |
| TT4 | Échappée : abri donné aux suiveurs annulé (1D, puis cône avec la zone 2D d'AS2) et bots aveugles à l'attaque (règle de réponse du [lot Y10](../lots/LOT_Y10_comportement_bots_core.md)) | TT2, AS1, Y10 | Délégable |
| TT5 | Rouleau compresseur | TT2, U20, [U21](../lots/LOT_U21_gravel_physique_core.md) | Délégable |
| TT6 | Engine : icônes des sept bonus, état refusé, compte à rebours (T9), jauge d'abri en couleur pendant Aspiration +, avatar semi-transparent de l'Échappée. **Maquettes validées par le propriétaire avant le code**, captures validées avant fusion, banc **low, medium et high** sur la GTX 1060 | TT1 ; TT3 à TT5 pour les effets | Interne (rendu) |
| TT7 | Menu « Bonus » à trois choix ; guide d'utilisation (quand lancer chaque bonus) | TT1, TT6 | Interne |
| TT8 | Équilibrage au banc simulé (cycliste virtuel X27, chaque bonus dans son terrain idéal, cible 1,5 à 2,5 s), puis recette sur le vélo en étapes de 10 min au plus | TT2 à TT7 | Propriétaire |

Ordre : TT1 → TT2 → TT3, TT4, TT5 (chacun dès que sa dépendance est fusionnée) → TT6 → TT7 → TT8. TT2 seul apporte déjà Plume, Enclume, le jeu `classiques` réécrit et le tirage contextuel.

Coût : quelques opérations par pas de 50 Hz dans le core et quelques octets dans la trame `state` (pire trame mesurée 2 456 octets sur 4 096). Seul l'avatar semi-transparent (TT6) peut coûter au GPU : il est mesuré en low, medium et high.

## 5. Liens avec les autres séries

- **Série T (2.0) :** cadre des bonus, records avec et sans bonus, HUD T9, arches T8 ([plan](../2.0/PLAN_SERIE_T.md)).
- **Série AS (aspiration plus fine) :** AS1 (bots abrités derrière le joueur, 1.x) est nécessaire à l'Échappée et à l'Aspiration + ; AS4 fixe le plafond de 0,55.
- **Y10 :** réponse des bots aux attaques, nécessaire à l'Échappée.
- **Série U (3.0) :** gravel (U20, U21), nécessaire au Rouleau.
- **Série CT (5.0, course tactique) :** sa jauge de capacités paie ces bonus ; elle reprend les effets de TT2 à TT5 sans les redéfinir.

## 6. Décisions du propriétaire (29 octobre)

- [x] Fusion de Burrito et Fantôme en un seul bonus, l'Échappée.
- [x] Plume de 20 s (au lieu de 30 s), réglable dans le fichier de valeurs.
- [x] Noms : Aspiration + (ex-Camion), Échappée.
- [x] Enclume relative (masse × 1,6) plutôt que +50 kg fixes.
- [x] Bots sans bonus dans la 4.0.
- [x] Réglage « Bonus » à trois choix, `classiques` par défaut ; bonus coupés dans tout ERG.
