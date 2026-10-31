# Lot O22 – Aide des parcours et du monde ouvert

## 1. Objectif

Question du propriétaire du 31 octobre : « Le menu est explicite avec des légendes pour ces fonctions ? » (monde ouvert et chargement de parcours). Constat sur `main` : rien n'expliquait comment ajouter un parcours (la liste vide disait seulement « Aucun parcours »). Le menu du globe n'avait qu'une ligne de touches, sans les boutons du Click ni explication du mode. Sur la carte de décision, le propriétaire a choisi « Aide puis import de traces » : ce lot fait l'aide, le lot O23 l'import depuis le menu.

## 2. Spécification

| # | Règle |
| --- | --- |
| O22-1 | La liste **Parcours** se termine, après le tri et le filtre, par « Ajouter un parcours » et « Comment ça marche ? ». Leur carte de détail donne l'explication de leur sujet. A maintenu ouvre l'écran **Aide parcours** sur ce sujet. |
| O22-2 | L'écran **Aide parcours** a un sujet par ligne : Choisir un parcours, Ajouter une trace, Fiche d'un parcours (`.toml`), Sans trace : le monde ouvert. L'explication du sujet sous le focus est dans la carte de droite, au Click comme au clavier. A maintenu ne fait rien. Y revient à la liste. |
| O22-3 | Une liste vide montre « Aucun parcours », désactivé, avec « dépose une trace dans ~/OpenRide/GPX/ », puis les deux lignes d'aide. Si la liste arrive pendant l'affichage, le focus passe au premier parcours. |
| O22-4 | L'entrée **Monde ouvert** de l'accueil porte la ligne « départ sur le globe, route créée en roulant ». |
| O22-5 | Chaque écran du menu du globe (globe, recherche, carte, cap, préchargement) montre une explication sous ses lignes. Au réglage du cap, l'explication donne aussi celle de la navigation choisie (Balade, Destination, Boucle) et le choix des branches aux carrefours en roulant. |
| O22-6 | Le menu du globe prend le bandeau des boutons des autres menus (`button_bar.gd`), avec une ligne pour le Click et une pour le clavier. Les entrées viennent de la même table, `button_help.gd` (`WORLD`). Au clavier, les lettres tapées sur le globe et dans la recherche cherchent un lieu : les touches sont données une à une, et une entrée sans bouton ou sans touche n'est montrée que sur l'autre ligne. Les attributions restent affichées pendant le préchargement, au-dessus du bandeau. |
| O22-7 | Le guide d'utilisation reçoit une section « 4 bis. Monde ouvert » et une phrase sur l'aide de la liste des parcours. |

## 3. Contrat

Le contrat IPC est inchangé : tout se passe dans l'engine.

## 4. Écarts relevés, non corrigés ici

- **Le globe s'écarte du plan des boutons (spécification générale §7.1).** A court y ouvre la carte, A long épingle la région et + / − longs inclinent le globe. Dans les autres menus, A long valide et ± long font cinq pas. Au clavier, A est une lettre de la recherche, et rien ne permet d'ouvrir la carte du centre : il faut passer par la recherche. Une remise au plan commun demande une décision du propriétaire (quel bouton pour épingler).
- **La carte ne se déplace d'ouest en est qu'avec les flèches du boîtier gauche.** Or rien d'indispensable ne doit être sur ce seul boîtier (§7.1).

## 5. Fichiers

- Engine : `route_help.gd` (nouveau, sujets de l'aide des parcours), `menu_model.gd` (lignes de fin de liste, focus, ligne de l'accueil), `menu_flow.gd` (écran et cartes), `button_help.gd` et `button_bar.gd` (aide du globe), `world_menu_view.gd` (explications, bandeau), `main.gd` (aide du globe dans l'état de test).
- Docs : `GUIDE_UTILISATION.md` §4 et §4 bis.
- Tests : `engine/tests/unit/test_menu_model.gd`, `test_menu_flow.gd`, `test_world_menu_view.gd`, et le banc des menus (`menu_scenarios/sessions.json`, `monde_ouvert.json`, avec l'aide du globe dans le texte comparé par `menu_bench.py`).
