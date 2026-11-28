# Lot BR5 – Gestes de base des bots du Grand Prix et du Dernier survivant (R5 de la stratégie des bots)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Bots : réponse aux attaques au Grand Prix, attaque avant l'arche et réponse au Dernier survivant, derrière ce qui est propre au mode | Python | Y10, DS3, GP3 | Petite | **Livré le 24 novembre** (PR #969) |

Recommandation R5 de la note « Stratégie des bots et de l'IA d'OpenRide » (accord du propriétaire du 21 novembre 2026 : « Ok r1 et r5 »). Ce n'est pas une refonte : on coche dans la table existante (`bot_tactics.MODE_TACTICS`, lot Y10) les gestes utiles aux deux modes qui étaient à « none ».

## 1. Constat (21 novembre)

- La tactique de groupe du lot Y10 (relais, attaques, réponses aux départs) ne jouait qu'en session libre : `Session._new_race` donnait « none » au Dernier survivant et au Grand Prix.
- L'abri (roue suivie, lots AS1 et AS2) marche déjà dans tous les modes : rien à ajouter.
- Au Dernier survivant, il ne restait que le sprint de survie et l'économie du lot DS3 ; au Grand Prix, le cerveau du lot GP3 (objets, voies, esquive), qui ne touche jamais à la puissance.

## 2. Règle du propriétaire

Ce qui est propre au mode garde la priorité. Les gestes de base ne jouent que quand le mode n'a rien à dire.

## 3. Livraison

- `bot_tactics.MODE_TACTICS` : lignes `grandprix` (réponses aux départs ; ni relais organisés ni attaques) et `survivor` (attaques en montée et au dernier kilomètre d'un sprint, où sont calées les arches, et réponses aux départs). Ni forme du jour ni fatigue de longue durée : le calibrage des bots (± 2 %) et la cote ne bougent pas. `GAME_MODES` liste les modes de jeu qui ont leur ligne.
- `ProfileBot.mode_speaks()` (`bots.py`) : vrai quand le mode décide ce pas : voie tenue au Grand Prix (esquive du lot GP3, `mode_hold` posé par `Session._sync_grandprix_lanes`), sprint de survie ou économie « à l'abri » du Dernier survivant. Le bot appelle alors `Tactics.yield_to_mode()` (attaque et réponse en cours arrêtées) au lieu de `Tactics.adjust`, et `update_field` ne lui fait juger aucun départ.
- `Session._mode_tactics(game_mode)` : ligne de la table selon le mode (piste : réglage « Tactique des bots » du lot VD7, inchangé ; WTF : toujours « none »).
- Tests : `core/tests/test_bot_gestes_br5.py` (table, priorité du mode, champ, et deux courses complètes en simulation où le cycliste attaque : les bots répondent, une élimination par arche au Dernier survivant).

## 4. Vérification en simulation (pas d'essai vélo)

Courses de la séance (vrai core, cycliste à puissance constante qui attaque à 480 W pendant 40 s au bout de 90 s), avec et sans le lot, graines 1 et 2 :

| Mode | Sans R5 | Avec R5 |
| --- | --- | --- |
| Grand Prix, 4 bots, 3 tours | 0 réponse | 1 à 4 réponses, classement proche (le cycliste 3e à 5e) |
| Dernier survivant, 4 bots, arches à 1 km | 0 attaque, 0 réponse | 0 à 2 attaques, 1 réponse ; même vainqueur, une élimination par arche |

`tools/grandprix_sim.py` (GP5, juste part) ne passe pas par les bots à profil : inchangé par construction.

## 5. Reste

- Recette PC, catégorie logique : fumée + medium (scénarios `grand_prix` et `dernier_survivant`).
- Après #941 (cote Elo) : `elo_campagne` doit encore converger avec ces gestes.
