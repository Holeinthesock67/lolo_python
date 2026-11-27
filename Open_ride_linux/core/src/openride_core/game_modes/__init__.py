"""Interface commune des modes de jeu (série IM, cadrage du 22 novembre : plans/CADRAGE_INTERFACE_MODES).

- `base.py` : `GameMode` (points d'appel de la séance, chacun avec un défaut qui ne fait rien) et `ModeContext`,
  vue étroite de la séance que lisent les adaptateurs ;
- `registry.py` : table des modes, dans l'ordre fixe d'appel (classique, WTF, survivant, Grand Prix, piste,
  Cyber-Rogue) ;
- un adaptateur par mode (`classic.py`, `wtf.py`, `survivor.py`, `grandprix.py`, `track.py`, `rogue.py`) : la colle
  sortie de `session.py`, sans changer les modules purs (`classic.py` du core, `wtf/`, `survivor.py`, `grandprix/`,
  `track/`, `rogue/`).

Lot IM1 : premier point d'appel, `fill_frame` (partie de la trame `state` propre à chaque mode). Les lots suivants
(IM2 à IM9) ajoutent les autres points d'appel ; aucun ne change le comportement (filet `scripts/modes_identique.py`).
"""
