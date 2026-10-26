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

`combat_step(state, inputs, room, balance, dt) -> (state, events)`, pur et déterministe (tirages des coups critiques par un générateur à graine). `inputs` : puissance, cadence, posture, braquet, `w_bal_j`, état du Firewall, boutons de la trame (`A_SHORT`, `A_LONG`, `Z_SHORT`, `PLUS_SHORT`, `MINUS_SHORT` ; Y est la pause, décision R-Q6), objectif de la run.

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
| + / B | Vitesse +1 ou −1 (1 à 12), sauf piratage du Saboteur |
| A court | Attaque : sur une `strike_target` et avec au moins 50 d'adrénaline : consomme 50, inflige 6 % des PV max (brise un point d'armure de verrou ou de rocher). Diesel : libère les charges de tunnel. Hors cible : rien, pas de consommation |
| Z | Dans une `z_zone` : parade (onde de choc annulée) ; Puncheur : aspiration accrochée si la puissance des 2 dernières secondes dépasse de 10 % celle des 3 secondes d'avant, la bosse suivante est envoyée à moitié de sa pente. Hors zone : rien |
| A court (suite) | Sur une balise `purge` : purge le piratage (pas d'attaque) |
| A long | Disjoncteur : −4 vitesses d'un coup (au plus jusqu'à 1), une fois toutes les 30 s. Si une carte de module A est équipée, A long déclenche la carte et le Disjoncteur n'est plus disponible (décision R-Q8) |
| Y | Pause et reprise, comme dans les autres modes (décision R-Q6) ; jamais une action de jeu |

### 4.6 Mécaniques des archétypes

- **Perfect Shift :** changement de braquet dans le sens conseillé, dans une fenêtre de `ps_window_s` (1,5 s par défaut, réglée par R0) centrée sur l'arche : +10 d'adrénaline, événement `perfect_shift`. Un changement dans le mauvais sens ne compte pas.
- **Diesel, tunnels de cadence :** chaque 10 s dans 90 ± 3 rpm donne une charge (au plus 3) ; A court sur la `strike_target` de sortie du tunnel les libère : 4 % des PV max par charge, sans coût d'adrénaline.
- **Puncheur :** voir Z ci-dessus ; bosse non aspirée et effort sous la cible : −10 de bouclier.
- **Grimpeur :** 5 s continues en `ROC` chargent un coup ; A court sur un rocher avec un coup chargé retire un point d'armure ; rocher brisé = 8 % des PV max.
- **Sprinteur :** sur un `pad`, puissance ≥ 1,40 FTP et vitesse ≥ 10 : dégâts ×3 pendant le pavé.
- **Saboteur :** toutes les 60 s, un piratage de 15 s : soit + et B bloqués, soit un pignon imposé (tirage) ; la balise `purge` (A) l'annule. Sous piratage, les dégâts dépendent seulement de la puissance et de la cadence.

### 4.7 Or

Victoire : 20 + 2 par Perfect Shift ; ennemi enfui : 8 ; défaite : 0.

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/rogue/combat.py`, `core/tests/test_rogue_combat.py`.
- **Modifiés :** `core/src/openride_core/rogue/balance.py`, `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune (les noms d'événements sont ceux du contrat R1, §4.4).

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. Cycliste simulé sur la cible, vitesse 6, Fluide : victoire sur chaque archétype et variante entre 85 et 95 % de la distance.
3. Même entrée, même graine : mêmes événements, à la trame près.
4. Bouclier à 0 : événement `defeat`, phase `RECOVERY` de 60 s, or perdu selon le §4.3.
5. Perfect Shift : réussi à 0,7 s de l'arche, raté à 0,8 s avec une fenêtre de 1,5 s ; mauvais sens refusé.
6. Disjoncteur (A long) : −4 vitesses, refusé pendant 30 s ensuite ; A court sur balise annule le piratage sans attaque ; Y n'a aucun effet de jeu.
7. Surchauffe seulement en objectif endurance, après 5 s au-delà de 0,75 FTP.
8. Toutes les constantes du lot sont dans `RogueBalance` (test qui modifie une valeur et voit l'effet).

## 8. Hors périmètre

- Cartes et reliques (R6), enchaînement des salles (R6, R15), équilibrage final (R7).
