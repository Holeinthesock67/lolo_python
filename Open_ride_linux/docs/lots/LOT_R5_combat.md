# Lot R5 – Combat : bouclier, adrénaline, dégâts, fenêtres de timing, Perfect Shift, surchauffe

## 1. Objectif

Les règles d'une salle de combat, en module pur : à chaque pas, à partir de la puissance, de la cadence, de la posture, du braquet, des boutons et des marqueurs de la salle, calculer les dégâts infligés à l'ennemi, le bouclier, l'adrénaline, l'or et les événements de jeu. Toutes les valeurs sont **des valeurs de départ**, rangées dans `RogueBalance` et calibrées par la run simulée (R7).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/2.0/GDD_CYBER_ROGUE.md` §1.2, §2.2 à §2.5 (avec leurs corrections), `docs/2.0/PLAN_SERIE_R.md` §2 (Q3) et §7.
2. `docs/lots/LOT_R2_wbal_postures.md`, `LOT_R3_generateur_salles.md`, `LOT_R4_firewall.md`, `LOT_R0_delai_frein.md` §4.3.

## 3. Prérequis

R2, R3 et R4 livrés. Valeurs de R0 (fenêtre de Perfect Shift) ou leurs défauts.

## 4. Travail demandé

### 4.1 Interface

`combat_step(state, inputs, room, balance, dt) -> (state, events)`, pur et déterministe (tirages des coups critiques par un générateur à graine). `inputs` : puissance, cadence, posture, braquet, `w_bal_j`, état du Firewall, boutons de la trame (`Z_SHORT`, `Z_LONG`, `PLUS_SHORT`, `MINUS_SHORT`, `PLUS_LONG`, `MINUS_LONG` ; Y est la pause et A sert aux choix, plan de boutons commun), objectif de la run.

### 4.2 Dégâts

- Par seconde : `d = (P / FTP) × m_gear × m_posture × m_cards`, avec `m_gear = 1 + 0,04 × (vitesse − 6)` (0,80 en 1, 1,24 en 12).
- Points de vie de l'ennemi : `HP = 0,9 × moyenne(target_frac) × nominal_s` : un cycliste sur la cible, en vitesse 6 et en Fluide, le bat à 90 % de la salle.
- `ROC` : `m_posture` = 1 ; armure +30 % (les pertes de bouclier sont réduites de 30 %).
- `FLUIDE` : 1.
- `VELOCE` : 1, mais chaque seconde a 15 % de chances d'être un coup critique (dégâts doublés) ; armure −20 % (pertes augmentées de 20 %).
- `ARRET` : aucun dégât.
- Fin de salle : à la fin de la distance de la salle, ennemi à 0 PV = **victoire**, sinon l'ennemi **s'enfuit** (butin réduit).

### 4.3 Bouclier et défaite

- `shield_max` = 100 ; plein au départ de la run.
- Contact du Firewall : −4 par seconde (armure de la posture comprise) et −1 or par seconde.
- Onde de choc du boss ou attaque du Puncheur non parée : −10.
- Couloir : +2 par seconde.
- **Défaite** à 0 : la salle s'arrête, 60 s de récupération forcée à 0 % (`RECOVERY`), or de la salle perdu et 25 % de l'or de la run perdu, bouclier remis à 50, puis la run continue au couloir suivant (pas de « game over », GDD §1.2). Pendant le boss : le boss s'enfuit sans coffre, on passe au retour au calme.

### 4.4 Adrénaline (0 à 100)

- +0,5 par seconde quand la puissance est au moins à la cible du tronçon ; ×0,7 en `ROC`, ×1,5 en `VELOCE` (« recharge de l'attaque plus rapide »).
- +10 par Perfect Shift réussi (GDD §2.4).
- **Surchauffe** (objectif endurance seulement, décision Q3) : au-delà de 0,75 FTP pendant plus de 5 s, l'adrénaline perd 2 par seconde et `overheat` est vrai ; aucun dégât en plus pendant la surchauffe.

### 4.5 Boutons en combat

| Bouton | Règle |
| --- | --- |
| + / B courts | Vitesse +1 ou −1 (1 à 12), sauf piratage du Saboteur |
| + / B longs | Vitesse +3 ou −3 (bornée à 1 et 12), sauf piratage. B long remplace le Disjoncteur du GDD (purge d'urgence), sans délai de recharge |
| Z court sur une cible | Attaque : sur une `strike_target` et avec au moins 50 d'adrénaline : consomme 50, inflige 6 % des PV max (brise un point d'armure de verrou ou de rocher). Diesel : libère les charges de tunnel. Sans adrénaline suffisante : rien |
| Z court dans une `parry_zone` | Parade (onde de choc annulée) ; Puncheur : aspiration accrochée si la puissance des 2 dernières secondes dépasse de 10 % celle des 3 secondes d'avant, la bosse suivante est envoyée à moitié de sa pente |
| Z court sur une balise `purge` | Purge le piratage (pas d'attaque) |
| Z court ailleurs | Rien. Le générateur (R3) ne fait jamais se chevaucher cibles, zones de parade et balises, pour qu'un appui n'ait qu'un sens |
| Z long | Carte ou relique active équipée (Inversion polaire…) ; rien sans carte active (décision R-Q8 revue) |
| Y | Pause et reprise, comme dans les autres modes ; jamais une action de jeu |
| A court, A long | Aucun effet en combat : vue de caméra suivante, vue par défaut (engine) |

### 4.6 Mécaniques des archétypes

- **Perfect Shift :** changement de braquet dans le sens conseillé, dans une fenêtre de `ps_window_s` (1,5 s par défaut, réglée par R0) centrée sur l'arche : +10 d'adrénaline, événement `perfect_shift`. Un changement dans le mauvais sens ne compte pas.
- **Diesel, tunnels de cadence :** chaque 10 s dans 90 ± 3 rpm donne une charge (au plus 3) ; Z court sur la `strike_target` de sortie du tunnel les libère : 4 % des PV max par charge, sans coût d'adrénaline.
- **Puncheur :** voir Z ci-dessus ; bosse non aspirée et effort sous la cible : −10 de bouclier.
- **Grimpeur :** 5 s continues en `ROC` chargent un coup ; Z court sur un rocher avec un coup chargé retire un point d'armure ; rocher brisé = 8 % des PV max.
- **Sprinteur :** sur un `pad`, puissance ≥ 1,40 FTP et vitesse ≥ 10 : dégâts ×3 pendant le pavé.
- **Saboteur :** toutes les 60 s, un piratage de 15 s : soit + et B bloqués, soit un pignon imposé (tirage) ; la balise `purge` (A) l'annule. Sous piratage, les dégâts dépendent seulement de la puissance et de la cadence.

### 4.7 Or

Victoire : 20 + 2 par Perfect Shift ; ennemi enfui : 8 ; défaite : 0.

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/rogue/combat.py`, `core/tests/test_rogue_combat.py`.
- **Modifiés :** `core/src/openride_core/rogue/balance.py`, `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune (les noms d'événements sont ceux du contrat T1, §4.3).

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. Cycliste simulé sur la cible, vitesse 6, Fluide : victoire sur chaque archétype et variante entre 85 et 95 % de la distance.
3. Même entrée, même graine : mêmes événements, à la trame près.
4. Bouclier à 0 : événement `defeat`, phase `RECOVERY` de 60 s, or perdu selon le §4.3.
5. Perfect Shift : réussi à 0,7 s de l'arche, raté à 0,8 s avec une fenêtre de 1,5 s ; mauvais sens refusé.
6. B long : −3 vitesses d'un coup, sans délai ; Z court sur balise annule le piratage sans attaque ; Z court dans une zone de parade ne déclenche pas d'attaque ; Y et A n'ont aucun effet de jeu.
7. Surchauffe seulement en objectif endurance, après 5 s au-delà de 0,75 FTP.
8. Toutes les constantes du lot sont dans `RogueBalance` (test qui modifie une valeur et voit l'effet).

## 8. Hors périmètre

- Cartes et reliques (R6), enchaînement des salles (R6, R15), équilibrage final (R7).

## 9. Livraison (27 octobre 2026)

- `rogue/combat.py` (`combat_start`, `combat_step`, `apply_gear_buttons`, `CombatInputs`, `CombatState`) et les constantes du combat dans `RogueBalance`. Tests : `core/tests/test_rogue_combat.py`.
- **Partage avec la session (R8) :** le combat ne traite pas les boutons de vitesse ; la session les applique avec `apply_gear_buttons` (±1 court, ±3 long, 1 à 12, piratage respecté), passe le braquet obtenu dans `CombatInputs.gear` et lit `hack_kind` / `forced_gear` (piratage en cours) et `grade_scale` (0,5 quand une bosse du Puncheur est aspirée) dans l'état. Les entrées reçoivent aussi la distance dans la salle et la vitesse (fenêtres de temps converties en distance).
- **Choix de lecture :** une parade (zone `parry_zone`) vaut pour l'onde de choc du boss et pour l'aspiration du Puncheur ; le coup non paré du Puncheur coûte 10 de bouclier seulement si la bosse n'est pas aspirée et que la puissance est sous la cible. Le piratage du Saboteur commence à la distance de la salle qui correspond à (balise de purge − délai du marqueur) et dure jusqu'à la purge, au plus 30 s (`hack_max_s`) : avec 15 s il aurait fini avant la balise posée par R3 à 20 s. Surchauffe : plus de critique, de pavé ni d'attaque. Dégâts sous piratage : pas de multiplicateur de braquet.
- **Constat pour R7 :** les dégâts sont proportionnels à la puissance multipliée par la durée ; un cycliste à 80 % de la cible roule plus longtemps (la salle a une distance fixe) et inflige à peu près le même total. Seul le Firewall le sanctionne (contact, bouclier, or). La run simulée dira si les multiplicateurs de braquet et de posture suffisent à rendre l'effort utile.
- Les critères 2 et 3 sont vérifiés avec le cycliste simulé du générateur (R3) : victoire entre 85 et 95 % de la distance sur chaque archétype, objectif et phase du boss.
