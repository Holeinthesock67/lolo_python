# DPS1 : dépassement des cyclistes du décor, règle commune et garde finale

- PR : #1148 ; cahier : docs/lots/LOT_DPS1_depassement_ligne_cycliste.md ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Les cyclistes du décor ne se touchent plus et ne vous touchent plus, quel que soit le parcours : ils vous comptent comme un usager quand ils se doublent entre eux, ne se rabattent plus devant vous derrière un groupe lent, et une garde finale retient celui qui allait toucher.
- SUIVI :
  - [ ] DPS1 : règle commune de dépassement du décor et garde finale (core + engine), 0 contact sur 33 routes, 5 tirages, 8 vitesses.
- Filet « à l'identique » (IM0) : empreinte de la séance `wtf` mise à jour (`python3 scripts/modes_identique.py --maj`). Seules changent les voies (`lane_m`) du cycliste et de deux cyclistes du décor entre 3 212 et 3 232 m : le cycliste du décor s'écarte et le cycliste reste sur sa ligne (1,20 m), là où la garde de la chaussée (AS11) l'écartait jusqu'à 1,44 m.
