"""Mode « What the fuck » (série WTF) : règles absurdes désactivables une à une, modules purs.

- `rules.py` : catalogue des 13 règles, fichier `~/OpenRide/wtf.toml` (règles actives, rythme) ;
- `events.py` : événements à durée limitée (gravité, monde à l'envers, route qui s'effondre,
  fromage, micro-défis, œufs, tempête, vélo minuscule, caméra folle) ;
- `chef.py` : la surprise du chef (plats tirés au hasard, refusables) ;
- `mode.py` : `WtfMode`, le chef d'orchestre : tirage des événements, règles permanentes
  (Katamari, peloton délirant, cadence qui pilote le monde), effets sur la physique et la pente
  ressentie, champ `wtf` proposé pour la trame `state`, lignes du journal.

Plan : `docs/2.0/PLAN_SERIE_WTF.md`.
"""
