# Lot Y10 – Comportement des bots dans le core : groupes, relais, attaques et fatigue

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Comportement des bots dans le core (profils, attaques, abri) | Python | Y9, séries T et R | Moyenne | Oui ; issue #366 |

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
