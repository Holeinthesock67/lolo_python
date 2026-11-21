# Lot GPH1 – Expliquer le Grand Prix des objets dans le jeu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Aide du Grand Prix des objets : « Comment ça marche ? » sur l'écran Prêt (résumé dans la carte, écran « Aide Grand Prix » en cinq sujets) et aide des voies du HUD qui dit à quoi sert la voie (boîte libre, prise, réserve pleine, bidon devant, musette derrière) | GDScript, JSON | GP8, GP9, GPL1 | Petite | En cours (21 novembre) |

Demande du propriétaire (21 novembre 2026, 10 h 10) : « À quoi sert le changement de voie en Grand Prix ? Impact sur le jeu ? », puis « Aucune explication nulle part ». Constat : l'écran Prêt du mode ne montrait que la fiche du parcours, le guide décrivait les réglages sans les voies, et l'aide du HUD disait « Bidon glissant en vue : A ou ← → » ou « A : voie suivante · ← → : voie » sans dire pourquoi changer de voie. Branche partie de celle de GPL1 (#942, tête 35b0825b). Principes du propriétaire : libellés simples, pas de consigne pendant qu'il pédale sauf utile, pas d'exception.

## 1. Règles du jeu expliquées (vérifiées dans le core)

- Trois voies ; une rangée de trois boîtes (une par voie) tous les 500 m par défaut ; on ne prend que la boîte de **sa** voie, et seulement réserve vide ; une boîte prise se reforme en 2 s (`grandprix/mode.py`, `boxes.py`).
- Bidon : posé derrière le lanceur sur sa voie ; musette : tout droit devant sur la voie du lanceur ; musette guidée : suit sa cible quelle que soit la voie (le changement de voie ne l'évite pas, la parade est un bidon ou une musette en réserve).
- A court change de voie quand une boîte ou un objet est à moins de 150 m devant ou un projectile à moins de 100 m derrière (`lane_choice_shown`), sinon vue suivante ; flèches toujours ; changement en 0,6 s ; A long : placement automatique, repris seul après 20 s sans objet en vue.
- Seul effet sur la physique : en voie choisie, le cycliste ne se range plus dans la roue du coureur devant (`session.py`, `lane.follow = False`) : l'abri peut être perdu.

## 2. Réalisation

- **Écran Prêt** : dernière ligne « Comment ça marche ? » (`MenuModel.GP_HELP_ID`), comme l'aide des parcours et du sous-menu ERG ; focus dessus : la carte de droite montre le résumé (« Le Grand Prix en bref ») à la place de la fiche du parcours ; A maintenu ouvre l'écran « Aide Grand Prix ».
- **Écran « Aide Grand Prix »** (`engine/scripts/grandprix/gp_help.gd`, même forme que `route_help.gd`) : Le Grand Prix en bref, Boîtes et objets, À quoi servent les voies, Boutons, Coups reçus et défense ; un sujet par ligne, son texte dans la carte ; Y revient à l'écran Prêt.
- **HUD** (`gp_hud_model.gd`, `lanes_view`) : la ligne d'aide sous les trois traits dit ce qui est en vue et à quoi sert la voie, dans cet ordre : « Bidon glissant devant sur ta voie : A ou ← → pour l'éviter », « Musette derrière sur ta voie : A ou ← → pour l'éviter », « Boîte devant, réserve pleine : Z d'abord pour en prendre une », « Boîte sur ta voie : passe dessus pour un objet », « Boîte prise sur ta voie : A ou ← → pour en changer » ; sinon « A ou ← → : changer de voie », et sans choix affiché « ← → : changer de voie » (placement automatique) ou « ← → : changer de voie · A maintenu : placement auto » (voie choisie). Rien de nouveau à l'écran : la même ligne, avec un sens. Lue dans la trame `gp` existante (`obj`, `boxes`, `boxes_gone`, `held`, `roll_s`) : aucun changement du core ni du contrat IPC.
- **Documents** : guide d'utilisation (Grand Prix des objets), recette de la série GP.

## 3. Tests

- `test_gp_hud.gd` : chaque cas de l'aide des voies (bidon devant, musette derrière, musette d'une autre voie et musette guidée sans consigne d'esquive, boîte libre, prise sur sa voie ou sur une autre, réserve pleine et tirage en cours, placement automatique ou voie choisie).
- `test_grandprix_menu.gd` : ligne « Comment ça marche ? », résumé dans la carte, écran et sujets, retour par Y.
- Banc des menus `grand_prix` : étapes et captures `gph1_pret_aide` et `gph1_aide_voies` ; galerie du HUD : cas `gp_boite_prise`.

## 4. Recette

Catégorie : logique (écrans de menu et texte du HUD, aucun changement de rendu 3D). Captures des deux écrans de menu et de la ligne d'aide du HUD à valider par le propriétaire.
