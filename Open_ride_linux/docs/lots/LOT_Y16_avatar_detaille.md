# Lot Y16 – Avatar du cycliste plus détaillé, pédalage dans le bon sens

**Statut : livré le 28 octobre (PR à venir)**, mesure sur la GTX 1060 (medium, 58 images/s) par la file des mesures du PC.

## 1. Objectif

Demandes du propriétaire du 28 octobre, pendant une séance : « l'avatar pourrait être mieux modélisé, c'est trop simpliste », puis « j'ai l'impression qu'il pédale à l'envers ». Avant ce lot, l'avatar des lots V6 et V7 était fait de capsules, de sphères et de pavés (tronc en capsule, tête en boule, vélo en trois pavés), et sa pédale du bas partait vers l'avant alors que le vélo avance vers −Z.

## 2. Règles (pas d'exception)

- **Même style que les personnages du décor (Y14)** : volumes effilés à sections elliptiques et normales lissées, sans texture ni fichier de modèle ; cuissard noir, gants sombres et casque à aérations comme les coureurs de `people_mesh.gd`.
- **Détails par couleurs de sommet**, pas par pièces ni matériaux en plus : bande du cuissard, aérations et bord du casque, semelles, guidoline. Trois matériaux partagés (corps, vélo brillant, motif de tenue) et 26 nœuds au niveau 0 au lieu d'une cinquantaine : moins d'appels de dessin qu'avant (vue de dos de la vitrine : 153 au lieu de 263).
- **Budgets de triangles inchangés** : 6 000 / 1 500 / 300 par niveau de détail, équipement le plus lourd compris.
- **Un seul sens de rotation** : `AvatarMesh.spin_x(angle)` sert au pédalier et aux roues ; `pedal_pos` place la pédale du bas vers l'arrière quand l'angle croît (comme `crowd.gdshader` pour les coureurs du décor).

## 3. Contenu

| Élément | Avant | Après |
| --- | --- | --- |
| Tronc | capsule | maillot effilé (bassin, taille, poitrine, épaules, col), dos légèrement bombé, manches courtes au motif de la tenue, cuissard noir dessous |
| Jambes | capsules | cuisse au cuissard noir et bande à la couleur secondaire, genou, mollet, cheville ; chaussettes au profil du mollet (rayées : bandes à la couleur secondaire) |
| Bras | capsules | épaule, biceps, avant-bras, poignet ; mains gantées sur les cocottes |
| Tête | boule | crâne, mâchoire, nez, oreilles, cou ; cheveux sur la nuque seulement ; lunettes enveloppantes |
| Casque | sphère aplatie | coque allongée et inclinée, quatre aérations, bord sombre, sangles ; aéro et visière gardés |
| Chaussures | pavés | chaussure de vélo (talon, pointe, semelle, molette) posée sur la pédale, cheville qui bascule au fil du tour |
| Vélo | trois pavés, selle et cintre en pavés | cadre en losange (tubes de selle, horizontal, oblique, douille, bases, haubans), fourche, potence, cintre de route avec cocottes et leviers, tige et selle à la hauteur de la hanche, bidon, cassette, dérailleur, chaîne ; un seul maillage |
| Roues | tore et rayons en pavés, fixes | pneu, jante selon la roue, 20 / 16 / 12 rayons croisés ou disque, moyeu ; tournent à la vitesse du vélo |
| Pédalier | deux pavés | plateaux, étoile, axe, manivelles ; un maillage qui tourne autour du boîtier |
| Posture | cintre plus haut que la hanche, buste à 57° | mains sur les cocottes sous la hanche, buste à 50°, tête au-dessus et en avant des épaules |

## 4. Vérification

- Tests : `tests/unit/test_avatar_model.gd` (sens du pédalage et des roues, manivelle du maillage sur la pédale de la cinématique, chaussure sur la pédale, proportions, budgets par niveau et avec l'équipement le plus lourd, au plus 30 nœuds, roues qui tournent avec la vitesse).
- Vitrine : `tests/vitrine_avatar.gd` (dos, profil, trois quarts, de près, niveau intermédiaire, avec les cyclistes du décor, quatre profils à des angles de pédalier successifs).
- Sur le PC : mesure medium à 58 images/s (file des mesures), puis coup d'œil en séance.
