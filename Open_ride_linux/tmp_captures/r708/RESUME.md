# #708 route posée sur le sol – mesures sur le PC du propriétaire (GTX 1060, Forward+)

Tête baa7e764 contre main 45a97127, worktrees, sim_bench --native --probe 240 s 1680x1011 (garde-fou coupé), médianes à partir de t = 60 s.

| Qualité | GPU méd / p99 #708 | GPU méd / p99 main | draw calls | primitives | images > 50 / > 100 ms (#708 / main) |
| --- | --- | --- | --- | --- | --- |
| low | 5,27 / 5,63 | 5,22 / 5,63 | 151 / 146 | 626k / 614k | 31 / 29 contre 31 / 30 |
| medium | 12,16 / 12,83 | 12,14 / 12,92 | 187 / 176 | 1379k / 1360k | 32 / 29 contre 32 / 29 |
| high | 14,47 / 15,11 | 14,48 / 15,01 | 191 / 179 | 1952k / 1935k | 33 / 29 contre 35 / 29 |

Images lentes : toutes « capture » (captures du banc), sauf une en low sur #708.
run_engine_tests.sh : RÉSULTAT ÉCHEC pour un seul test, render/test_rogue_style_sheet_render (8 vérifications, 0 échec, mais code de sortie non nul). Le reste passe, dont test_herbe_route (46 vérifications, route posée sur le sol, 7 parcours).
Planches : demo intégrée à 1 et 3 km, gauche main, droite #708.
