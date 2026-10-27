# Lot R16 – Estimation de CP et W' à partir des séances passées

## 1. Objectif

Décision Q5 : W' vaut 20 kJ par défaut, se règle dans `config.toml` et dans les menus, et **s'estime à partir des séances passées**. Ce lot estime CP et W' depuis la courbe de puissance de l'historique, avec une mesure de confiance, et propose la valeur au joueur sans jamais écraser sa configuration.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/2.0/PLAN_SERIE_R.md` §2 (Q5) et §5 (risque 3), `docs/lots/LOT_R2_wbal_postures.md`.
2. Code : `core/src/openride_core/tools/history.py` (lecture des séances passées, cache), `core/src/openride_core/recorder.py` (journal JSONL à 1 Hz), `core/src/openride_core/tools/session_summary.py`.

## 3. Prérequis

Aucun (R2 pour utiliser le résultat).

## 4. Travail demandé

### 4.1 Courbe de puissance

- Sources : séances du journal d'OpenRide (JSONL) et FIT présents dans le dossier de l'historique, des 90 derniers jours (`--days`, défaut 90). Séances rejouées (`replay`) exclues.
- Meilleure puissance moyenne (MMP) pour 180, 300, 480, 720 et 1 200 s, toutes séances confondues ; la courbe par durée est mise en cache avec le cache de `history.py`.

### 4.2 Modèle et confiance

- Modèle à deux paramètres : travail = CP × t + W', régression linéaire sur les couples (t, MMP × t) des durées du §4.1.
- Estimation **acceptée** seulement si : au moins 3 durées, R² ≥ 0,98, CP entre 0,8 et 1,2 × FTP, W' entre 5 et 40 kJ. Sinon : pas d'estimation, avec la raison (« pas d'effort maximal de 3 min dans les 90 derniers jours »…).
- Avertissement toujours affiché : l'estimation suppose des efforts maximaux ; elle est basse si l'historique n'en contient pas.

### 4.3 Usage

- Outil `python -m openride_core.tools.estimate_cp` (texte ou `--json`) : CP, W', R², durées utilisées, date de l'effort de chaque durée.
- Le core calcule l'estimation au lancement, hors de la boucle à 50 Hz, et la met dans `hello_ack.config.rogue.w_prime_estimate_j` (T1) ; le menu de départ (R13) la propose. La configuration n'est écrite que si le joueur la choisit (réglages du core, O3).
- Aucune donnée personnelle dans les tests : séances fabriquées.

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/tools/estimate_cp.py`, `core/tests/test_estimate_cp.py`.
- **Modifiés :** `core/src/openride_core/tools/history.py` (MMP dans le cache), `README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune (le champ `w_prime_estimate_j` est ajouté par T1).

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. Séances fabriquées depuis un modèle CP = 250 W, W' = 20 kJ (efforts maximaux de 3, 5, 8, 12 et 20 min) : CP à ± 3 % et W' à ± 10 %.
3. Historique sans effort de plus de 5 min : pas d'estimation, raison lisible.
4. Séance rejouée exclue ; séance de plus de 90 jours exclue.
5. 200 séances lues en moins de 5 s grâce au cache (deuxième lancement).

## 8. Hors périmètre

- Modèles à trois paramètres, estimation de la FTP (lot O10).
