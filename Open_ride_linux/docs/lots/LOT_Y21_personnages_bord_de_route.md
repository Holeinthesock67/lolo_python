# Lot Y21 – Personnages du bord de route plus vivants

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série Y (rendu) : spectateurs et passants remodelés (tubes profilés, coude articulé, mains, chaussures, visage), tenues plus variées (short, jupe, veste, casquette, chapeau, barbe, moustache, lunettes de soleil, queue de cheval, chignon, sac à dos, écharpe de supporter), huit gestes d'encouragement et quatre attitudes au calme, tête qui suit le cycliste, drapeaux à motifs, pancartes, taille et carrure tirées par personne, deux niveaux de détail | GDScript + shader | Y14, P15, P21 | Moyenne | **En PR** (prévu en 5.0, lancé le 5 novembre) ; captures à valider, banc PC en low, medium et high |

## 1. Objectif

Demandes du propriétaire : « Pour v5 améliorer personnages bord de route » (1er novembre, 19 h 08), lancées le 5 novembre (« lancer le sujet personnages du bord de route », puis « et améliorer la modélisation », puis « Peux-tu faire mieux ? » après la première planche : deuxième passe Y21-8 à Y21-10). Suite du lot Y14 (`people_mesh.gd`).

Avant ce lot (captures de la vitrine du 5 novembre) : tous les spectateurs ont la même taille, la même pose (les deux bras levés), des bras raides d'un seul tenant, des chaussures en pavés, des drapeaux unis ; ils regardent tous droit devant eux.

Hors du lot : les cyclistes du décor (#704, avatar des bots), les bots (Y18), le placement et le comportement des modèles (`crowd_model.gd`, `passersby_model.gd`), les budgets du décor vivant.

## 2. Spécification

| # | Règle |
| --- | --- |
| Y21-1 | **Modélisation** (`people_mesh.gd`, un seul constructeur comme Y14) : `Builder.tube` (tube profilé, anneaux sans bouchon intermédiaire, normales selon la pente du profil) pour le mollet, le genou, la cuisse, le bassin, la taille, la poitrine et les épaules arrondies ; épaule, bras, coude, avant-bras, main en moufle et pouce ; chaussure à bout rond et tige ; tête en crâne et mâchoire, nez, oreilles, yeux (blanc et pupille), sourcils, lèvres, joues ; ourlets des manches. |
| Y21-2 | **Tenue** (`PeopleMesh.outfit`, entier exact, réparti dans la donnée d'instance par `instance_custom`) : peau, cheveux, pantalon, style (cheveux longs, bande, veste ouverte à manches longues), bas (pantalon, short, jupe), coiffe (rien, casquette, chapeau de paille), geste, détail. Pièces montrées selon la tenue (`EXTRA_*`, repliées dans la tête sinon). `outfit_of` : environ 7 sur 10 en pantalon, 2 en short, 1 en jupe ; 3 sur 10 en casquette, 1 sur 8 en chapeau. |
| Y21-3 | **Gestes** (`crowd.gdshaderinc`, coude articulé : CUSTOM0.y = 1 sous le coude) : en encourageant, bras levés qui s'agitent, applaudit, poing levé, mains en porte-voix, photo au téléphone (téléphone montré), sautille en applaudissant, salue d'un bras, deux poings ; au calme (`geste % 4`), bras le long du corps, croisés, mains sur les hanches, mains jointes. Les passants qui marchent ou courent plient le coude (coureur : coudes à angle droit). |
| Y21-4 | **Regard** : debout, assis ou sautillant, la tête suit la caméra (le cycliste) à moins de 40 m, au plus 1,1 rad ; le porteur de pancarte (animation 9) tourne tout le corps vers la caméra (au plus 0,9 rad) pour que la pancarte se lise depuis la route. |
| Y21-5 | **Drapeaux et pancartes** : drapeau en motif (tricolore, deux bandes, croix nordique, à pois rouges), deuxième couleur éloignée de la première ; pancarte tenue à deux mains au-dessus de la tête, fond clair, bord à la couleur du haut, deux lignes de lettres. `crowd_model.gd` : `sign` pour 14 % des spectateurs sans drapeau (tirage séparé, les drapeaux ne changent pas). |
| Y21-6 | **Silhouettes** : taille 0,95 à 1,05 et carrure 0,92 à 1,12 tirées du numéro de la personne (`CrowdRenderer.morph`). |
| Y21-8 | **Détail** (un par personne, 6 sur 10) : barbe, moustache, lunettes de soleil (sans cheveux longs pour barbe et moustache), queue de cheval, chignon (avec cheveux longs), sac à dos, écharpe de supporter rayée aux couleurs du haut et d'appoint. Barbe, moustache et lunettes de près seulement. |
| Y21-9 | **Donnée d'instance sûre** : chaque composante reste un entier exact sous 2 048 (x = détail + phase, z = animation + 10 × (bas + 3 × (coiffe + 3 × geste)), w = peau, cheveux, pantalon et style). Constaté au cloud : au-delà d'environ 65 000 dans une composante, la tenue lue par le shader était fausse (donnée rangée en demi-flottants), d'où des personnes toutes en jupe et veste. |
| Y21-10 | **Ombrage et allure** : ombre de contact vers le sol et sous les bras, contre-jour léger (`RIM`) sur les vêtements ; au calme, léger balancement du haut du corps. Motif du drapeau tiré de la phase de la personne. |
| Y21-7 | **Niveau de détail** : de près en deçà de `QualityPresets.PEOPLE_LOD_M` (low 12 m, medium 25 m, high 40 m), maillage réduit au-delà (moins de côtés, sans pouces, visage fin ni téléphone) ; un MultiMesh par sorte et par niveau (`Crowd_plain`, `Crowd_plain_loin`, … ; `Passersby_people`, `Passersby_people_loin`). Choix refait à chaque nouvelle sélection (tous les 20 m pour les spectateurs). |

## 3. Coût

| Maillage | Avant (Y14) | De près | Au loin |
| --- | --- | --- | --- |
| Personnage | 892 | 3 176 | 1 098 |
| Porte-drapeau | 892 + hampe et toile | 3 204 | 1 138 |
| Porteur de pancarte | — | 3 188 | 1 122 |

Les pièces cachées par la tenue comptent dans ces totaux (repliées dans la tête par le shader).

Vitrine de rendu (`vitrine_rendu.gd`, même scène, 5 novembre) :

| Vue | low avant → après | medium avant → après | high avant → après |
| --- | --- | --- | --- |
| `foule` (triangles / appels) | 92 924 / 56 → 156 292 / 60 | 326 852 / 101 → 390 220 / 105 | 758 852 / 112 → 828 454 / 116 |
| `passants` (triangles / appels) | 67 332 / 44 → 115 352 / 47 | 301 260 / 89 → 349 280 / 92 | 733 260 / 91 → 829 414 / 94 |

Le nuanceur de sommets fait un peu plus (coude, rotation de la tête calculée seulement pour les sommets de la tête). Temps du processeur graphique à mesurer sur la GTX 1060 (budgets 6 / 12 / 14 ms). Rappel : la démo compilée est déjà au bord du budget sur main en medium et en high. Si la mesure dépasse : réduire d'abord `PEOPLE_LOD_M`, puis les côtés de près (`LOD_SIDES`, 10 et 5).

## 4. Vérification

- Tests : `tests/unit/test_people_mesh.gd` (huit champs de tenue, donnée d'instance relue comme le shader et sous 2 048, répartition des bas, coiffes et gestes, zones, pièces, articulations, triangles par niveau), `test_crowd_model.gd`, `test_passersby_model.gd`, `render/test_crowd_render.gd`.
- Captures : `tests/vitrine_personnages.gd` (planche des gestes, tenues, drapeaux et pancartes, de près et au loin) et `vitrine_rendu.gd` (vues `foule`, `foule_pres`, `passants`, `cyclistes`) ; captures du 5 novembre dans `/mnt/project-files/captures/y21-personnages/`, à valider par le propriétaire avant la fusion.
- Banc PC (fil de fusion) : main contre la branche, low, medium et high, scène avec spectateurs (montée de fin de parcours).
