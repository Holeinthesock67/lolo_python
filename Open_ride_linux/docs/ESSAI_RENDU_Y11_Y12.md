# Essai de rendu mesuré : chaussée, herbe, lumières et particules (Y11, Y12)

**Statut : validé le 27 octobre** : étape 0 après Y1, étape 1 après Y2 (Godot 4.7). But : remplacer les coûts **estimés** des cahiers `docs/lots/LOT_Y11_chaussee_herbe_relief.md` et `LOT_Y12_lumieres_particules.md` par des coûts **mesurés** sur le PC cible (GTX 1060), en `medium` d'abord (préréglage quotidien du propriétaire), puis en `low` (budget de la spécification). Consigne du propriétaire du 27 octobre : **utiliser les outils de test de la série X** développés pour les autotests ; les résultats sont consignés dans ce fichier (§6), les données brutes restent dans `~/OpenRide/`.

## 1. Outils utilisés (déjà sur `main`)

| Outil | Lot | Rôle dans l'essai |
| --- | --- | --- |
| `scripts/recette_pc.py --rapide` | X4 | État de départ : tous les tests passent sur le PC avant de mesurer ; à nouveau à la fin |
| `engine/tests/sim_bench.py --native --probe --quality Q` | Banc simulé + sonde X13 | Séance réelle (core sur Bluetooth simulé, vraie scène) ; par seconde : temps d'image p50 et p99, temps CPU et **GPU** de la vue, appels de dessin, primitives, VRAM ; nvidia-smi ; captures à positions fixes |
| `engine/tests/perf_probe.py report DOSSIER` | X13 | Médianes, p99 et dérive (`sonde.txt`), courbes (`rapport.html`) |
| `OPENRIDE_PERF=strict PERF_CSV=… engine/tests/run_engine_tests.sh` | X2 | Budgets de temps des tests (création des matériaux et des émetteurs ajoutés par les lots) |
| `engine/tests/run_visual_tests.sh --native` | Bancs visuels | Captures de la scène face au faux core et comparaison aux images de référence : seul ce qui est voulu change |
| `sim_bench.py --native --scenario endurance --quality medium` | X16 | Une heure sans dérive de mémoire ni saccade, à la fin de chaque lot |
| `scripts/privacy/privacy_scan.py --commits origin/main..HEAD` | Confidentialité | Avant de committer ce fichier de résultats |

## 2. Scénarios et mesures

- **Monde** `village` (bâtiments, montée et descente, eau) et **scénario** `montee_descente`, limité à 5 minutes (`--duration 300`), captures toutes les 15 s (`--every 15`) : mêmes positions d'un essai à l'autre.
- **Monde** `demo` (relief) en complément pour l'herbe et le brouillard.
- **Thème** : `default` (rendu procédural, sans pack) puis un pack CC0 de test (`make_texture_theme.py`, étendu aux normales et rugosités le jour du lot).
- **Valeur retenue** : médiane de 3 passages, sans les 20 premières secondes. Colonnes : images/s moyennes, temps d'image p50 et p99, **temps GPU médian** (la vraie mesure du coût d'un effet), appels de dessin, VRAM.
- **Règle de décision** (celle de la série Y) : un effet est gardé dans un préréglage s'il tient dans l'enveloppe du cahier (Y11 : +1,0 ms GPU en `medium` ; Y12 : +1,5 ms ; ensemble : +2,5 ms ; p99 au plus +1 ms) ; sinon il descend d'un préréglage ou il est abandonné.

## 3. Étape 0 : référence, sans code (possible dès maintenant)

Mesure de la scène actuelle, à refaire après Y1 (brouillard à 6 km en `medium`) puis après Y2 (Godot 4.7) pour que les comparaisons partent de la bonne base.

```bash
cd ~/Games/lolo_python && git pull && cd Open_ride_linux
python3 scripts/recette_pc.py --rapide
for q in medium low; do
  for i in 1 2 3; do
    python3 engine/tests/sim_bench.py --native --probe --quality $q --world village \
      --scenario montee_descente --duration 300 --every 15 --muet \
      --out ~/OpenRide/essai_rendu/reference_${q}_$i
  done
done
```

Durée : environ 35 minutes sans le vélo (fenêtre à l'écran, ne pas y toucher).

## 4. Étape 1 : maquette mesurée (petit code d'essai, à valider)

Pour mesurer un effet, il faut qu'il existe. La maquette est **le strict minimum pour mesurer**, rangée là où le lot la gardera :

- une variable d'environnement `OPENRIDE_ESSAI_RENDU` (liste d'identifiants des cahiers, par exemple `A1,A3,H1,H3,L1,L2,P1`) lue par `render_quality.gd`, transmise telle quelle par `sim_bench.py` (qui garde déjà l'environnement) ; vide par défaut : rendu inchangé, aucun test existant ne bouge ;
- les effets les plus simples à poser et les plus chers à deviner : A1 + A2 + A3 procéduraux dans `road_markings.gdshader`, H1 + H3 dans `terrain.gdshader`, L1 glow, L2 rayons radiaux, L3 ombre des nuages en `medium`, P1 poussière et P4 éclaboussures (pluie forcée par le thème d'essai), H6 coquilles d'herbe en `high` ;
- la sonde X13 gagne une colonne `essai` (liste active) et `particles` (particules actives) ; `perf_probe.py` gagne `compare DOSSIER_A DOSSIER_B` (écart des médianes et du p99, tableau prêt à coller au §6).

Puis, pour chaque effet seul, puis tous ensemble, en `medium` puis en `low` :

```bash
for e in A1 A3 H1 H3 L1 L2 L3 P1 P4 "A1,A2,A3,H1,H3,L1,L2,L3,P1,P4"; do
  OPENRIDE_ESSAI_RENDU=$e python3 engine/tests/sim_bench.py --native --probe --quality medium \
    --world village --scenario montee_descente --duration 300 --every 15 --muet \
    --out ~/OpenRide/essai_rendu/medium_${e//,/+}
done
python3 engine/tests/perf_probe.py compare ~/OpenRide/essai_rendu/reference_medium_1 ~/OpenRide/essai_rendu/medium_*
```

Ensuite : `run_engine_tests.sh` avec `OPENRIDE_PERF=strict` (X2), `run_visual_tests.sh --native` (les captures sans `OPENRIDE_ESSAI_RENDU` doivent être identiques aux références), endurance X16 d'une heure en `medium` avec tous les effets, `privacy_scan.py` puis commit de ce fichier. Durée côté propriétaire : environ 1 h 15 (sans le vélo) plus l'heure d'endurance, qui peut tourner seule.

**Regarder aussi** (dans `rapport.html` du banc, planche des captures) : route au soleil bas de face, herbe en vent fort, contre-jour sous les arbres, sortie de forêt, pluie ; noter si un effet est trop fort, trop discret ou de mauvais goût.

## 5. Ce qui n'est pas mesuré par l'essai

Les effets qui demandent Godot 4.6 ou plus (SSR refait L5, glow de 4.6) : leur coût sur 4.3 ne dit rien ; ils sont mesurés dans les lots, après Y2. Les décalques (A6) et la parallaxe (A5), qui demandent un pack de textures.

## 6. Résultats (à remplir)

GTX 1060, 1920×1080 en plein écran sauf mention ; pilote et version de Godot notés à chaque série.

| Date | Préréglage | Effets | Images/s | p50 (ms) | p99 (ms) | GPU médian (ms) | Δ GPU (ms) | Appels de dessin | VRAM (Mo) | Décision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | `medium` | référence | | | | | — | | | — |
| | `low` | référence | | | | | — | | | — |
