# Lot PP3 – Écran « Ma puissance » dans le profil (contrat IPC 1.35)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Écran « Ma puissance » : courbe 6 mois et 6 semaines, FTP estimée et proposition, évolution | Python + GDScript | PP1, PP2, MJ8 | Moyenne | **Livré le 26 novembre** (PR #975) |

## 1. Objectif

Montrer au joueur, dans son profil, sa courbe de puissance (PP1) et sa FTP estimée (PP2), et lui proposer la FTP estimée sans jamais l'écrire seule (décisions Q2 et Q3 du 21 novembre ; plan `docs/6.0/PLAN_SERIE_PP.md` §4). Révision **1.35** du contrat, prise à la fusion au-dessus de la 1.34 de main (écrite 1.29 dans la branche jusqu'au 24 novembre).

## 2. Travail demandé

### 2.1 Contrat (révision 1.35)

- Commande `list_power_curve` `{}` ; réponse `power_curve` (schéma `docs/contracts/ipc/power_curve.schema.json`) : 13 points `{s, m6, w6}`, FTP réglée, FTP estimée et sa source en toutes lettres, confiance en mots, raison, proposition, signal à 5 %, évolution sur 6 mois, avertissements ; un seul datagramme de moins de 4 096 octets (noms de parcours raccourcis au besoin).
- `error` `busy` pendant une séance : rien de la courbe ne s'affiche pendant qu'on roule.
- La proposition s'accepte par `set_setting` `rider.ftp_w` (révision 1.3) : pas de commande nouvelle, même chemin que tout réglage du joueur (profil en cours, MJ4).

### 2.2 Écran

- Accès : accueil, ligne « Profil : … », puis « Ma puissance » juste sous le profil en cours dans « Qui roule ? ».
- Liste : « Période : 6 derniers mois » (A : 6 dernières semaines), « Utiliser 249 W comme FTP » (confirmation, « Non » par défaut), « Faire un test de rampe » (écran du test de FTP), « Évolution mois par mois », puis les 13 durées : « 5 min · 310 W » et « 28 oct. · Col du lacet · libre » (ou « ERG », avec le nom de l'entraînement) ; une durée sans effort : « aucun effort à fond depuis 6 semaines ».
- Carte de détail : tuiles « FTP réglée » et « FTP estimée · Indicative » (en or quand une proposition existe), courbe tracée par le code (échelle des durées logarithmique, points pleins pour la période choisie, points creux pour l'autre, FTP réglée en tirets dorés, watts gradués), source de l'estimation, ligne de la durée choisie, légende écrite (« ● 6 derniers mois ○ 6 dernières semaines - - FTP réglée ») et les deux avertissements. Les mots portent l'information ; la couleur ne la porte jamais seule.
- Profil sans séance : « Roule une première séance pour voir ta courbe » et le test de rampe.
- W/kg : pas affiché dans ce lot (le jeu ne distingue pas un poids réglé du poids par défaut) ; à reprendre avec PP5.

### 2.3 Banc des menus et captures

- En-tête `seances_courbe` du banc des menus : séances fabriquées d'un cycliste fictif à FTP 250 W (`python -m openride_core.tools.courbe_fictive`), sans aucune donnée réelle.
- Scénario `engine/tests/menu_scenarios/ma_puissance.json` : ligne de « Qui roule ? », courbe 6 mois puis 6 semaines, ligne ERG, évolution, confirmation et écriture de la FTP ; captures `ma_puissance_*`.

## 3. Critères d'acceptation

1. `(cd core && pytest -q)` passe, dont `core/tests/test_power_curve_ipc.py` (message du profil en cours conforme au schéma, profil vide, `busy` en roulant, datagramme sous 4 096 octets avec des noms très longs, commande reçue).
2. Tests de l'engine : `engine/tests/unit/test_power_menu.gd` (ligne, liste, mots « libre » et « ERG », carte et courbe, période, confirmation « Non » puis « Oui », `set_setting`, courbe redemandée, évolution, test de rampe, profil vide, refus du core) ; `test_profiles_view_model.gd` mis à jour.
3. Banc des menus : scénario `ma_puissance` vert sur les trois voies.
4. **Captures low, medium et high validées par le propriétaire avant fusion** (menus seulement).

## 4. Livraison

- **Créés :** `core/src/openride_core/tools/courbe_fictive.py`, `core/tests/test_power_curve_ipc.py`, `docs/contracts/ipc/power_curve.schema.json`, `engine/scripts/power_view_model.gd`, `engine/tests/unit/test_power_menu.gd`, `engine/tests/menu_scenarios/ma_puissance.json`, ce cahier.
- **Modifiés :** `core/src/openride_core/ipc_lists.py` (`build_power_curve_message`), `session.py` (`_send_power_curve`), `ipc_server.py` (requête, révision 1.35), `docs/contracts/ipc_v1.md` et `cmd.schema.json` ; `engine/scripts/menu_flow.gd`, `profiles_view_model.gd`, `detail_card.gd` (courbe), `ipc_client.gd`, `main.gd` ; `engine/tests/menu_bench.py` (`seances_courbe`), scénario `profils.json` (ligne « Ma puissance ») ; guide d'utilisation, README, CLAUDE.md, suivi.
- Recette PC : catégorie **rendu des menus** (captures low, medium, high du scénario `ma_puissance`), après l'essai du 22 novembre.
