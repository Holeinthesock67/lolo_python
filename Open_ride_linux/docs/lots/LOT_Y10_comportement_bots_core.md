# Lot Y10 – Comportement des bots dans le core : groupes, relais, attaques et fatigue

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Comportement des bots dans le core (profils, attaques, abri) | Python | Y9, séries T et R | Moyenne | En PR (6 novembre) ; reste la course de 45 min sur le PC ; issue #366 |

## 1. Objectif

Décision du propriétaire du 27 octobre (`docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §0, question 12) : **bots réalistes**, avec attaques dans les montées, fatigue et abri, calculés dans le core, qui reste le maître de l'état. Le lot T12 donne déjà à chaque bot du mode classique un profil (CP, W′, masse, pic), une stratégie par segment et une réserve W′bal ; T13 les met à l'échelle de la FTP du cycliste. Il manque ce qui fait une course :

- les bots **s'abritent** les uns derrière les autres et derrière le cycliste (l'aspiration de P3 ne profite aujourd'hui qu'au cycliste) ;
- un groupe de bots **prend des relais** sur le plat ;
- les bots **attaquent** et **répondent** aux attaques, selon leur profil et leur réserve ;
- les bots **se fatiguent** sur une longue séance, au-delà de ce que W′bal décrit.

## 2. À lire

1. `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §7 ; `docs/2.0/PLAN_SERIE_T.md` §3.4 et §6 ; cahiers `LOT_T12_bots_profil.md`, `LOT_T13_equilibrage_bots.md`, `LOT_P3_aspiration_bots.md`, `LOT_N9_bots_core.md`, `LOT_R2_wbal_postures.md`.
2. Code : `core/src/openride_core/bots.py` (`ConstantPowerBot`, `ProfileBot` de T12), `draft.py` (aspiration), `classic.py`, `segments.py`, `rogue/wbal.py`, `physics.py`, `session.py`.

## 3. Prérequis

T12 et T13 livrés (profils, stratégies, calibrage) ; Y9 utile (on voit les groupes et les dépassements à l'écran) ; P3 livré.

## 4. Travail demandé

Tout dans le core, en module pur testable (nouveau `core/src/openride_core/bot_tactics.py`), appelé par `ProfileBot` à chaque pas ; les bots à puissance constante (N9) et les fantômes ne changent pas.

- **Abri entre bots** : chaque `ProfileBot` calcule son aspiration avec `draft.py` derrière le bot ou le cycliste qui le précède (même courbe, même plafond de 0,45 que le cycliste ; le fantôme n'abrite toujours pas) ; à puissance égale, il va donc plus vite dans la roue. Le cycliste abrite les bots qui le suivent.
- **Groupes** : des bots à moins de 2 s les uns des autres forment un groupe. Sur le plat (pente sous 2 %), le premier roule à sa puissance de stratégie pendant un relais de 30 à 60 s (selon sa réserve), puis se décale et se laisse glisser en queue (sa puissance baisse de 15 % pendant 5 s) ; un sprinteur ou un bot dont la réserve est sous 30 % ne prend pas de relais. Les relais ne se font pas dans une montée.
- **Attaques** : dans une montée de la couche `segments` (ou au dernier kilomètre d'un sprint), un bot attaque (1,15 à 1,30 × CP pendant 20 à 60 s) si sa réserve dépasse 50 %, une fois par montée au plus, à un moment tiré de la graine de la séance ; le grimpeur attaque plus tôt et plus souvent, le diesel jamais. **Réponse** : quand le cycliste ou un bot du groupe part (écart qui grandit de plus de 0,5 s par seconde pendant 3 s), un bot dont la réserve dépasse 40 % suit avec une chance qui dépend de son profil (grimpeur en montée, rouleur sur le plat), sinon il garde son rythme.
- **Fatigue de longue durée** : au-delà de 60 min de séance, la CP de chaque bot baisse de `DURABILITY_PCT_PER_H` (proposition : 3 % par heure, plus pour le sprinteur, moins pour le diesel) ; valeurs dans la table des profils de T12.
- **Jour avec, jour sans** : au départ, chaque bot tire de la graine de la séance un facteur de forme de 0,97 à 1,03 sur sa CP, pour que deux courses ne se ressemblent pas ; à graine égale, même course (tests et rejeu).
- **Calibrage** : la simulation de T13 tourne avec les tactiques ; les niveaux 90, 100 et 110 % gardent leur sens (temps d'arrivée moyen d'un bot au niveau 100 % à ± 2 % de celui du cycliste simulé à sa FTP).

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/bots.py`, `draft.py` (calcul pour un bot), `classic.py` (ordre de mise à jour : cycliste, puis bots du premier au dernier), et le module de calibrage de T13 ; tests du core correspondants ; `docs/2.0/PLAN_SERIE_T.md` (renvoi), ce cahier, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`, `README.md` (compteurs).
- **Nouveaux :** `core/src/openride_core/bot_tactics.py`, `core/tests/test_bot_tactics.py`.
- **Interdits :** l'engine (aucun affichage nouveau), le contrat IPC, la physique du cycliste.

## 6. Modifications de contrat autorisées

Aucune : les bots gardent les champs de la révision 1.4. Montrer l'action d'un bot (« attaque », « relais ») dans le HUD demanderait un champ de plus (révision du contrat) : à proposer au propriétaire à part, après la recette.

## 7. Critères d'acceptation

1. `pytest -q` passe dans le core ; le pas d'un bot reste sous 0,1 ms (5 bots, 50 Hz).
2. Abri : un bot à 1,5 m derrière un autre, à même puissance, va plus vite que seul (gain conforme à `draft.py`) ; aucun abri derrière un fantôme.
3. Groupe de trois rouleurs sur 10 km de plat : au moins 8 changements de tête, aucun relais en montée ni par un bot à moins de 30 % de réserve.
4. Montée de 5 km : le grimpeur attaque une fois au plus, quand sa réserve dépasse 50 % ; le diesel jamais ; une attaque simulée du cycliste est suivie par au moins un bot à réserve suffisante sur 20 tirages.
5. Déterminisme : même graine, mêmes positions au mètre près après 1 h ; autre graine, autre course.
6. Calibrage de T13 tenu à ± 2 %.

**Sur le PC cible (le propriétaire) :** course de 45 min contre 4 bots à profil sur un parcours avec deux montées (T11) : groupes qui se forment, relais visibles sur le plat, attaque d'un grimpeur dans une montée, bots qui suivent quand on attaque ; avis sur la difficulté.

## 8. Hors périmètre

- Affichage des actions des bots dans le HUD (révision du contrat, à part) ; lissage et position latérale à l'écran (Y9).
- Bots du monde ouvert (série W) et ennemis du Cyber-Rogue (série R) ; apprentissage automatique.

## 9. Réalisation (6 novembre 2026)

Module commun `core/src/openride_core/bot_tactics.py`, conçu pour être prolongé par le vélodrome (lot VD7, `docs/4.0/PLAN_SERIE_VD.md` §6.1 : coalitions, marquage, bluff, gestion du classement, fatigue visible, personnalités, réglage « Tactique des bots : aucune, simple, complète ») sans second système de tactique :

- **Table des modes** `MODE_TACTICS` : chaque mode active ses comportements (`Behaviours` : relais, attaques, réponses, fatigue de longue durée, forme du jour). `classic` a tout ; `none` rien (Dernier survivant, WTF, monde ouvert et vélodrome jusqu'à leur propre lot) ; `essai` sans la forme du jour (banc `bots_race`, qui juge chaque bot à ± 2 %) ; `calibration` les attaques et la fatigue (simulation du lot T13). VD7 ajoute ses comportements comme champs de `Behaviours` et ses lignes à la table.
- **Caractère par profil** (`Character`, champ `character` de la table `PROFILES` du T12) : chance et moment des attaques (grimpeur 90 % entre 10 et 35 % de la montée, rouleur 35 % entre 40 et 85 %, sprinteur et diesel jamais ; attaque au dernier kilomètre d'un sprint : rouleur 40 %, grimpeur 10 %), chance de suivre en montée et sur le plat, relais (pas le sprinteur), fatigue (`durability_pct_per_h` : 3 % par heure, 4,5 % pour le sprinteur, 1,5 % pour le diesel ; plancher de 70 % de la CP).
- **Pas du bot** (`Tactics.adjust`, appelé par `ProfileBot.step`) : seule la puissance demandée change, et l'envie de quitter la roue suivie (lot AS1) ; la réserve W′bal vide ramène toujours à la CP. **Pas du champ** (`update_field`, appelé par la séance avant le pas des bots, relu deux fois par seconde) : groupes à moins de 2 s, relais, départs.
- **Graine** : tous les tirages viennent de la graine de la séance (`draw`, CRC32 de la graine et des clés), tirée au départ et écrite au journal du core (« Tactique des bots : classic, graine … ») ; `CoreSession.bot_tactics_seed` la fixe (essais, rejeu).

Écarts assumés avec la lettre du §4, à valider sur le vélo :

- **Abri entre bots** : déjà livré par les lots AS1 à AS4 (`draft.update_bots`, plafond de groupe de 0,55 du lot AS4 au lieu de 0,45) ; Y10 n'y touche pas, le critère 2 est vérifié par un test.
- **Fin de relais** : le bot qui se relève roule à −15 % au moins 5 s **et jusqu'à être doublé** (15 s au plus) : à −15 % pendant 5 s seulement, les suivants n'ont pas le temps de le doubler et il reprend la tête. Il se décale de 1 m vers l'axe (place de repos du placement AS2) pour que les autres passent sans sortir de leur ligne, puis ne reprend pas la tête avant 20 s.
- **Départ détecté** : l'écart grandit de plus de 0,5 s **en 3 s**, à chaque relevé (la lettre « 0,5 s par seconde » ne verrait aucune attaque réelle : à 1,25 × CP, l'écart grandit d'environ 0,2 s par seconde). Le bot qui suit roule à 1,25 × CP jusqu'à revenir à 0,3 s (60 s au plus, arrêt sous 20 % de réserve), puis reprend la roue (AS1).
- **Calibrage** : la simulation du T13 roule seule avec les attaques et la fatigue ; la forme du jour (0,97 à 1,03) s'applique après, sur la CP calibrée, et les relais ne jouent qu'en groupe. Le critère 6 est donc tenu en moyenne (test sur trois graines, forme comprise) et bot par bot au banc `bots_race`, qui tourne en mode `essai`.

Tests : `core/tests/test_bot_tactics.py` (critères 1 à 6 du §7, physique et réserve inchangées par la tactique, mode `none` neutre). Aucun changement d'engine ni de contrat : pas de nouveau coût GPU ; la course de 45 min contre 4 bots (T11) reste à faire sur le PC.
