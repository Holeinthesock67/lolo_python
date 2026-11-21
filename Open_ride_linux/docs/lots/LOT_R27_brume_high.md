# Lot R27 : Cyber-Rogue sans voile en high

## Contexte

Retour du propriétaire en run, le 21 novembre : « Il y a une sorte de brouillard dans le Cyber-Rogue ». La galerie du
Cyber-Rogue le reproduit en qualité high seulement : le ciel et l'horizon deviennent gris-mauve, alors qu'ils restent
bleu nuit presque noir en low et en medium. Comparé à côté, le high « est moins bien » (propriétaire).

## Cause

`rogue_environment.gd` (lot R17 §4.3) donnait au high une brume exponentielle (densité 3 / 900 m) et un glow plus
large (7 niveaux, intensité 1,1, bloom 0,15). La brume exponentielle couvre aussi le ciel `void` et le grisait en
entier ; le glow large étalait le halo de la grande route jaune sur tout l'écran. Un premier essai avec le seul glow
du medium réduit à peine le voile ; avec la brume linéaire en plus, il disparaît.

## Correctif

- Une seule règle de brume pour les trois préréglages : linéaire (mode « profondeur ») du joueur à `fog_end_m`
  (400, 600 ou 900 m). Clé `fog_exponential` et fonction `exponential_density` retirées (pas d'exception au high).
- Glow du high ramené à celui du medium : 5 niveaux, intensité 1,0, bloom 0,10. Le high garde sa brume plus
  lointaine, toutes ses particules et l'aberration chromatique des effets de glitch.
- Tableau du lot R17 §4.3 mis à jour.

## Tests

- `engine/tests/unit/test_neon_palette.gd` : glow du high, brume linéaire et fin de brume dans les trois préréglages.
- Galerie du Cyber-Rogue en high (Xvfb, lavapipe) : 168 contrôles sur 168 ; planche avant et après :
  `rogue-r27/AVANT_APRES_brouillard_high.png` dans les fichiers du projet.

## Reste

Galerie low, medium et high sur la branche, planche validée par le propriétaire, passe PC (budgets GPU) et
« go » de fusion.
