# Lot Y21 – Personnages du bord de route plus vivants

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série Y (rendu) : spectateurs et passants remodelés (tubes profilés, coude articulé, mains, chaussures, visage), tenues plus variées (short, jupe, veste, casquette, chapeau), huit gestes d'encouragement et quatre attitudes au calme, tête qui suit le cycliste, drapeaux à motifs, pancartes, taille et carrure tirées par personne, deux niveaux de détail | GDScript + shader | Y14, P15, P21 | Moyenne | **En PR** (prévu en 5.0, lancé le 5 novembre) ; captures à valider, banc PC en low, medium et high |

## 1. Objectif

Demandes du propriétaire : « Pour v5 améliorer personnages bord de route » (1er novembre, 19 h 08), lancées le 5 novembre (« lancer le sujet personnages du bord de route », puis « et améliorer la modélisation »). Suite du lot Y14 (`people_mesh.gd`).

Avant ce lot (captures de la vitrine du 5 novembre) : tous les spectateurs ont la même taille, la même pose (les deux bras levés), des bras raides d'un seul tenant, des chaussures en pavés, des drapeaux unis ; ils regardent tous droit devant eux.

Hors du lot : les cyclistes du décor (#704, avatar des bots), les bots (Y18), le placement et le comportement des modèles (`crowd_model.gd`, `passersby_model.gd`), les budgets du décor vivant.

## 2. Spécification

| # | Règle |
| --- | --- |
| Y21-1 | **Modélisation** (`people_mesh.gd`, un seul constructeur comme Y14) : `Builder.tube` (tube profilé, anneaux sans bouchon intermédiaire, normales selon la pente du profil) pour le mollet, le genou, la cuisse, le bassin, la taille, la poitrine et les épaules arrondies ; épaule, bras, coude, avant-bras, main en moufle et pouce ; chaussure à bout rond et tige ; tête en crâne et mâchoire, nez, oreilles, yeux, sourcils, bouche. |
| Y21-2 | **Tenue** (INSTANCE_CUSTOM.w, entier exact) : peau, cheveux, pantalon, style (cheveux longs, bande, veste ouverte à manches longues), bas (pantalon, short, jupe), coiffe (rien, casquette, chapeau de paille), geste. Pièces montrées selon la tenue (`EXTRA_*`, repliées dans la tête sinon). `outfit_of` : environ 7 sur 10 en pantalon, 2 en short, 1 en jupe ; 3 sur 10 en casquette, 1 sur 8 en chapeau. |
| Y21-3 | **Gestes** (`crowd.gdshaderinc`, coude articulé : CUSTOM0.y = 1 sous le coude) : en encourageant, bras levés qui s'agitent, applaudit, poing levé, mains en porte-voix, photo au téléphone (téléphone montré), sautille en applaudissant, salue d'un bras, deux poings ; au calme (`geste % 4`), bras le long du corps, croisés, mains sur les hanches, mains jointes. Les passants qui marchent ou courent plient le coude (coureur : coudes à angle droit). |
| Y21-4 | **Regard** : debout, assis ou sautillant, la tête suit la caméra (le cycliste) à moins de 40 m, au plus 1,1 rad ; le porteur de pancarte (animation 9) tourne tout le corps vers la caméra (au plus 0,9 rad) pour que la pancarte se lise depuis la route. |
| Y21-5 | **Drapeaux et pancartes** : drapeau en motif (tricolore, deux bandes, croix nordique, à pois rouges), deuxième couleur éloignée de la première ; pancarte tenue à deux mains au-dessus de la tête, fond clair, bord à la couleur du haut, deux lignes de lettres. `crowd_model.gd` : `sign` pour 14 % des spectateurs sans drapeau (tirage séparé, les drapeaux ne changent pas). |
| Y21-6 | **Silhouettes** : taille 0,95 à 1,05 et carrure 0,92 à 1,12 tirées du numéro de la personne (`CrowdRenderer.morph`). |
| Y21-7 | **Niveau de détail** : de près en deçà de `QualityPresets.PEOPLE_LOD_M` (low 12 m, medium 25 m, high 40 m), maillage réduit au-delà (moins de côtés, sans pouces, visage fin ni téléphone) ; un MultiMesh par sorte et par niveau (`Crowd_plain`, `Crowd_plain_loin`, … ; `Passersby_people`, `Passersby_people_loin`). Choix refait à chaque nouvelle sélection (tous les 20 m pour les spectateurs). |

## 3. Coût

| Maillage | Avant (Y14) | De près | Au loin |
| --- | --- | --- | --- |
| Personnage | 892 | 1 904 | 846 |
| Porte-drapeau | 892 + hampe et toile | 1 932 | 886 |
| Porteur de pancarte | — | 1 916 | 870 |

Vitrine de rendu (`vitrine_rendu.gd`, même scène, 5 novembre) :

| Vue | low avant → après | medium avant → après | high avant → après |
| --- | --- | --- | --- |
| `foule` (triangles / appels) | 92 924 / 56 → 125 140 / 60 | 326 852 / 101 → 359 068 / 105 | 758 852 / 112 → 794 242 / 116 |
| `passants` (triangles / appels) | 67 332 / 44 → 93 524 / 47 | 301 260 / 89 → 327 452 / 92 | 733 260 / 91 → 788 818 / 94 |

Le nuanceur de sommets fait un peu plus (coude, rotation de la tête calculée seulement pour les sommets de la tête). Temps du processeur graphique à mesurer sur la GTX 1060 (budgets 6 / 12 / 14 ms). Rappel : la démo compilée est déjà au bord du budget sur main en medium et en high. Si la mesure dépasse : réduire d'abord `PEOPLE_LOD_M`, puis les côtés de près (`LOD_SIDES`).

## 4. Vérification

- Tests : `tests/unit/test_people_mesh.gd` (sept champs de tenue, diviseurs du shader, répartition des bas, coiffes et gestes, zones, pièces, articulations, triangles par niveau), `test_crowd_model.gd`, `test_passersby_model.gd`, `render/test_crowd_render.gd`.
- Captures : `tests/vitrine_personnages.gd` (planche des gestes, tenues, drapeaux et pancartes, de près et au loin) et `vitrine_rendu.gd` (vues `foule`, `foule_pres`, `passants`, `cyclistes`) ; captures du 5 novembre dans `/mnt/project-files/captures/y21-personnages/`, à valider par le propriétaire avant la fusion.
- Banc PC (fil de fusion) : main contre la branche, low, medium et high, scène avec spectateurs (montée de fin de parcours).
