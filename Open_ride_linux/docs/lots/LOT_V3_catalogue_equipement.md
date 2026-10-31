# Lot V3 – Catalogue d'équipement, effets bornés et temps gagné par l'équipement

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Catalogue d'équipement, effets bornés sur `PhysicsParams`, conseil par terrain, temps gagné par l'équipement | Python | V2 | Moyenne | **Livré le 27 octobre** (PR #278, issue #241) ; branchement par V11 |

## 1. Objectif

Décrire l'équipement de la série V dans un fichier de données, appliquer les effets de masse et de CdA aux `PhysicsParams` dans des bornes strictes, conseiller l'équipement selon le terrain et compter le temps gagné ou perdu grâce à l'équipement. Module pur, testé en pytest ; le branchement dans la séance vient avec V11.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` §2.2 ; `docs/2.0/PLAN_SERIE_T.md` §3.3 (les bonus passent par la même voie).
2. Code : `core/src/openride_core/physics.py` (`PhysicsParams`, `RiderPhysics.step`, `DT_DEFAULT`), `journal.py` (relevés), `progression.py` (lot V2 : chargement du fichier de données, défis).

## 3. Prérequis

V2 fusionné (fichier de données et défis).

## 4. Travail demandé

### 4.1 Catalogue (`[[items]]` du fichier `progression.toml`)

Chaque pièce : `id`, `slot` (`frame`, `wheels`, `helmet`, `kit`, `socks`, `glasses`), `name`, `level` (niveau où elle devient achetable), `price` (pièces, lot V3b), `mass_delta_kg`, `cda_delta_pct`, `terrain` (`flat`, `rolling`, `climb`, `all`), `look` (identifiant de rendu pour V7), `default` (possédée dès le départ). Catalogue proposé (V-Q9) :

| Pièce | Emplacement | Masse | CdA | Terrain | Niveau | Prix |
| --- | --- | --- | --- | --- | --- | --- |
| Polyvalent | cadre | 0 | 0 % | tout | 1 (offert) | 0 |
| Grimpeur | cadre | −1,5 kg | 0 % | col | 5 | 150 |
| Aéro | cadre | +0,5 kg | −3 % | plat | 10 | 250 |
| Polyvalent léger | cadre | −0,8 kg | −1,5 % | vallonné | 25 | 450 |
| Contre-la-montre | cadre | +0,5 kg | −4 % | plat | 30 | 500 |
| Standard | roues | 0 | 0 % | tout | 1 (offert) | 0 |
| Légères | roues | −0,5 kg | 0 % | col | 3 | 100 |
| Profilées | roues | +0,2 kg | −2 % | vallonné | 8 | 200 |
| Lenticulaire | roues | +0,5 kg | −3 % | plat | 15 | 350 |

Apparence (aucun effet) : trois casques, six tenues (dont « Maillot à pois » et « Néon » offertes par défi), quatre paires de chaussettes, trois lunettes ; une pièce par emplacement est offerte au départ. Les défis de V2 offrent : 1 000 km → tenue « Mille bornes », 10 000 m → casque « Sommet », 50 km → chaussettes « Longue distance », 10 ERG terminés → lunettes « Métronome », premier col HC → cadre Grimpeur, premier maillot à pois → tenue « Maillot à pois », premier boss → tenue « Néon ».

Validation au chargement : identifiants uniques, emplacement connu, valeurs bornées (masse de −2 à +1 kg, CdA de −5 à 0 % par pièce), une pièce par défaut par emplacement, récompenses de défi existantes.

### 4.2 Effets bornés

`apply_equipment(base: PhysicsParams, loadout, catalogue) -> PhysicsParams` : masse totale + somme des deltas du cadre et des roues, CdA × (1 + somme des deltas). Bornes du plan, cadre et roues ensemble : la masse ne baisse jamais de plus de 3 % de la masse totale de départ, le CdA de plus de 6 %. Les hausses ne sont pas bornées. Les pièces d'apparence n'ont aucun effet. La fonction ne touche ni `crr` ni le rendement, et les bonus de la série T se composent ensuite par multiplication (T6). La résistance au trainer reste inchangée : seul le calcul de la vitesse virtuelle utilise ces paramètres (branché par V11).

### 4.3 Conseil par terrain

`route_terrain(length_m, climb_m) -> str` : `flat` sous 5 m de D+ par km, `climb` au-delà de 15 m/km, `rolling` entre les deux. `advice(terrain, catalogue)` : pour le cadre et les roues, la pièce conseillée (même terrain, sinon `all`), et le texte de la fiche (« Conseillé : col »).

### 4.4 Temps gagné par l'équipement

`equipment_time_gain(records, equipped, base, s_start=None, s_end=None) -> float | None` : rejoue la puissance mesurée seconde par seconde sur le profil de pente du journal (pente en fonction de la distance), avec `RiderPhysics` au pas de la physique, une fois avec l'équipement choisi, une fois avec l'équipement de départ. Résultat : temps pour couvrir la même distance avec l'équipement choisi moins temps avec l'équipement de départ (négatif si l'équipement fait gagner du temps), sur toute la séance ou sur `[s_start, s_end]` (segment de la série T). `None` sans puissance ou sans distance. Texte d'affichage : `gain_text(slot_name, seconds, where)` → « Cadre grimpeur : −14 s dans la montée ».

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/equipment.py`, `core/tests/test_equipment.py`.
- **Modifiés :** `core/src/openride_core/data/progression.toml` (catalogue), `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** `physics.py` (lecture seule), `session.py`, l'IPC, l'engine.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Contre-la-montre + lenticulaire : CdA −6 % (borne), pas −7 % ; Grimpeur + Légères avec 84 kg : −2,0 kg ; avec une masse totale de 60 kg : −1,8 kg (borne de 3 %).
3. Pièces d'apparence seules : `PhysicsParams` identiques au départ.
4. Montée régulière de 5 km à 7 %, 250 W, 75 kg : le cadre Grimpeur fait gagner du temps, le cadre Aéro en fait perdre ; plat de 20 km à 250 W : l'Aéro gagne nettement plus que le Grimpeur (qui, plus léger, ne perd rien sur le plat). Les ordres de grandeur sont notés dans le test (quelques secondes à quelques dizaines de secondes).
5. `equipment_time_gain` avec l'équipement de départ : 0 s exactement.
6. Un catalogue invalide (doublon, emplacement inconnu, effet hors bornes) est refusé avec un message qui nomme la pièce.

## 8. Hors périmètre

Achat et solde (V3b), choix enregistré (V4), branchement dans la séance (V11), rendu (V7), sons et traînées d'air (V7), pénalité de la lenticulaire par vent de travers (V-Q13 : la série P ne modélise pas encore le vent de travers).

## 9. Livraison (26 octobre 2026, issue #241)

- Code et tests : `equipment.py`, catalogue `[[items]]` de `data/progression.toml`, `core/tests/test_equipment.py` (23 tests).
- Champ ajouté au catalogue : `buyable = false` pour les pièces offertes par un défi seulement (lu par V3b).
- Temps gagné mesuré (même puissance de 250 W, 75 kg) : montée de 5 km à 7 % : Grimpeur −20 s, Grimpeur + Légères −27 s, Aéro +5 s, Contre-la-montre + Lenticulaire +10 s ; plat de 20 km : Aéro −18 s, Contre-la-montre + Lenticulaire −37 s, Grimpeur −2 s.
