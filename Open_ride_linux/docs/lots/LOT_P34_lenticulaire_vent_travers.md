# Lot P34 – Roue lenticulaire et vent de travers

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série P : pénalité de la roue lenticulaire par vent de travers (question V-Q13), à partir du vent de travers déjà calculé pour l'abri | Python | P2, AS3, V3 | Petite | En PR (8 novembre, version 3.0) |

Question V-Q13 (plan V, validée le 27 octobre) : la lenticulaire est pénalisée par sa masse en montée seulement, et la pénalité au vent de travers « attend un lot de la série P ». Ce lot n'existait pas ; relevé le 8 novembre. Le vent de travers est déjà calculé pour la bordure (AS3, `draft.py`).

## 1. Objectif

Donner à la roue lenticulaire un vrai compromis : rapide par vent calme, moins efficace par fort vent de travers.

## 2. À lire

`docs/2.0/PLAN_SERIE_V.md` §5 (V-Q13) ; `core/src/openride_core/equipment.py` (effets bornés de V3) ; `core/src/openride_core/draft.py` (composante de travers, AS3) ; `core/src/openride_core/wind.py`.

## 3. Travail demandé

- Effet sur le CdA de la lenticulaire selon la composante de travers (gain réduit puis annulé au-delà d'un seuil), borné comme les autres effets de V3 (CdA −6 % au plus).
- « Temps gagné » affiché au Garage (V5) recalculé avec le vent du parcours.
- Aucun effet sur la puissance enregistrée (invariant A7).

## 4. Critères d'acceptation

1. Sans vent, résultats identiques à aujourd'hui (test).
2. Par vent de travers fort, la lenticulaire ne fait pas mieux que la roue à hauts profils (test).

## 5. Fichiers touchés

`core/src/openride_core/equipment.py`, `core/src/openride_core/data/progression.toml` (`wheels_disc`), tests.

## 6. Réalisation (8 novembre)

- **Lacet du vent apparent** : `wind.apparent_yaw_deg(v, head, cross)` = atan2(|travers|, v + face), partagé avec l'abri en bordure (`draft.crosswind_residual`, AS3, inchangé) ; `wind.cross_component` remplace le calcul en ligne de la séance.
- **Catalogue** : deux clés facultatives par pièce, `crosswind_fade_deg` et `crosswind_zero_deg` (0 : insensible). `wheels_disc` : gain complet jusqu'à 10° de lacet, nul au-delà de 20°, en ligne droite entre les deux ; la masse (+0,5 kg) ne change pas. Vérifiées au chargement : seulement pour une pièce physique qui baisse le CdA, 0 ≤ début < fin ≤ 90°.
- **Effet** : `physical_deltas` et `apply_equipment` prennent le lacet (0 par défaut, résultat d'avant) ; la borne de −6 % s'applique après la réduction. `crosswind_cda_ratio` donne le facteur du CdA équipé ; la séance l'applique au CdA du pas (vitesse virtuelle et supplément de pente ressenti), jamais à la puissance mesurée (A7). Mode Cyber-Rogue : équipement sans effet, rien ne change.
- **Repères** : à 35 km/h, vent de 5 km/h plein travers : 8°, gain complet ; 10 km/h : 16°, 40 % du gain ; 15 km/h : 23°, aucun gain. La lenticulaire (−3 %) passe derrière les Profilées (−2 %) dès 13,3°.
- **Journal** : clé facultative `cross_mps` (m/s, positive venant de droite) à côté de `head_mps`, absente vent coupé. Pas de changement du contrat IPC.
- **Temps gagné** (bilan `xp_result` et passages de segment, V5) : les deux simulations rejouent le vent de face relevé, et l'équipement le CdA au lacet relevé. Sans vent relevé, calcul d'avant. Journaux d'avant le lot (sans `cross_mps`) : vent de face seul.
- **Tests** : `core/tests/test_equipment_crosswind.py` (critères 1 et 2, borne, masse, catalogue invalide, temps gagné sur séance et segment, journal).
- **Mesures** : calcul Python seulement, rien côté rendu (pas de capture) ; coût à 50 Hz : un `atan2` et deux sommes de pièces quand le vent est actif.
