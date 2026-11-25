# Lot EO1 – Rotors des éoliennes qui tournent au vent du moyeu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Rotor des éoliennes jugé au vent à hauteur du moyeu (loi de puissance 1/7), avec inertie et hystérésis : les éoliennes tournent au vent du thème par défaut | GDScript | P12, P4 | Petite | **Livré le 21 novembre** (PR #951) |

Demande du propriétaire du 21 novembre 2026 à 10 h 12 : « Il y a moyen de faire tourner éolienne ? »

## 1. Constat

Les éoliennes du lot P12 savaient tourner, mais restaient arrêtées avec les réglages par défaut : le vent du jeu est coupé par défaut (lot P16), le décor prend alors le vent du thème (8 km/h, rafales de 20 % : 7,2 à 8,8 km/h), et le rotor ne démarrait qu'à 10 km/h **mesurés au sol**. Le vent « fixe » par défaut (5 km/h) les laissait arrêtées aussi.

## 2. Conception (sans exception)

- Le vent du jeu est un vent à 10 m (Open-Meteo : `wind_speed_10m`). Chaque rotor suit le vent **à hauteur de son moyeu** : `v_moyeu = v_sol × (h / 10)^(1/7)` (loi de puissance classique, ×1,39 à 100 m, jamais moins qu'au sol). Aucune valeur propre au thème ni à la démo : un moyeu plus haut tourne un peu plus vite par le même vent, partout.
- Démarrage à 10 km/h au moyeu, arrêt seulement sous 8 km/h au moyeu (hystérésis) : pas d'arrêts et de redémarrages à chaque rafale.
- Inertie du rotor : la vitesse suit la cible au premier ordre de constante 6 s (démarrage et arrêt progressifs, sans dépassement).
- Vitesse inchangée : `5 + 12 × (v_moyeu / 60 km/h)` tr/min, plafonnée à 17 tr/min. Vent du thème par défaut : environ 7,3 tr/min.
- Sens horaire vu de face (le rotor regarde d'où vient le vent), comme les vraies éoliennes ; nacelle inchangée (P12).
- `settle(wind)` pose les rotors sur leur régime établi (scènes figées des tests graphiques).
- Coût : un angle par éolienne et par image (20 au plus), aucun nœud, aucun maillage ni matériau en plus. Même comportement en low, medium et high.

## 3. Tests

`engine/tests/unit/test_wind_turbines.gd` : facteur du vent au moyeu, hystérésis, vent du thème par défaut (deux minutes de rafales : rotor toujours en marche, 6 à 8,5 tr/min), inertie (63 % en 6 s, sans dépassement), régime établi à 30 km/h au sol (13,3 tr/min), ralentissement progressif au calme, moyeu de 150 m plus rapide que 100 m ; budget `turbines_flags_frame` inchangé.

## 4. Recette sur le PC

Catégorie rendu (doute → rendu) : « Circuit des Prés » (deux éoliennes), vent coupé (vent du thème), en low, medium et high : rotors qui tournent doucement, sans à-coup ; temps GPU dans les budgets (#732).

## Livraison

21 novembre, branche `claude/project-thread-lgiuha` : `wind_turbines.gd` (vent au moyeu, hystérésis, inertie, `settle`), tests ci-dessus. Planche hors dépôt : `/mnt/project-files/captures/eo1-eoliennes/planche_rotor_8kmh_medium.png` (rotor vu de face, vent du thème, toutes les 0,5 s).
