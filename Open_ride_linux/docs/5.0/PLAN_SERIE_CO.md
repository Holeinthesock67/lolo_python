# Série CO – Séance conseillée par OpenRide (version 5.0)

7 novembre 2026. Demande du propriétaire du 7 novembre : « En v5 il faudrait ajouter dans le menu une préconisation de séance par le logiciel en fonction des sessions championnat en cours, du besoin du joueur en entraînement aérobie léger, aérobie intense, anaérobie. Voir comment identifier ces besoins. »

Lecture retenue : le jeu propose chaque jour **une séance** et dit **pourquoi**, à partir de ce qu'il sait déjà du joueur (séances passées, FTP, courses disputées, plan actif, prochaine course annoncée). La série s'appelle CO (« coach ») ; aucune lettre existante n'est reprise. Ce document est l'étude (lot CO0) : comment identifier les besoins, quelles règles, quel écran, quels lots. Rien n'est codé avant la validation des règles (§3) et de la maquette (§6).

Principes, repris des décisions passées :
- **Lisible avant d'être savant** (consigne du 7 novembre sur la Course tactique) : chaque conseil affiche sa raison en une phrase et les chiffres qui l'ont décidé ; pas de « boîte noire », pas de score magique.
- **Une seule source de calcul** : les zones, la NP, le TSS, les meilleures puissances et la CP viennent des outils existants (`session_summary`, `history`, `estimate_cp`), jamais d'une seconde formule.
- **Le joueur garde la main** : le conseil est une proposition ; un plan d'entraînement actif (O11) passe avant ; on peut toujours choisir un autre besoin.
- **Par profil de joueur** (série MJ) ; le profil d'essai `_essai` a ses propres conseils, jamais mélangés.
- **Confidentialité** : tests de la CI sur des historiques synthétiques générés par les tests, jamais de vrais FIT ni de vraies valeurs (poids, FTP) dans le dépôt.

## 1. Les trois besoins (et deux cas à part)

Zones de Coggan déjà calculées par `session_summary.py` (`ZONES`, % de la FTP) :

| Besoin | Zones | % FTP | Ce que ça travaille | Séances livrées aujourd'hui |
| --- | --- | --- | --- | --- |
| **Aérobie léger** | Z1, Z2 | < 75 % | endurance de base, capacité à durer, récupération entre efforts | `endurance_60` |
| **Aérobie intense** | Z3, Z4, Z5 | 75 à 120 % | tempo, sweet spot, seuil, VO2max (efforts de 3 à 60 min) | `tempo_2x15`, `sweet_spot_3x10`, `seuil_2x20`, `vo2_5x3` |
| **Anaérobie** | Z6, Z7 | > 120 % | capacité anaérobie (W′), sprints, relances, attaques (efforts de 10 s à 2 min) | aucune (à livrer, lot CO2) |
| Récupération | Z1 | < 55 %, 30 à 45 min | assimiler une course ou un bloc dur | aucune (à livrer, lot CO2) |
| Test de FTP | rampe | – | recaler les zones | `rampe_test` (O10) |

Choix proposé (question Q1) : la VO2max (Z5) est rangée dans l'aérobie intense, car elle se travaille en intervalles de 3 à 8 min comme le seuil ; l'anaérobie commence à 120 % de la FTP, là où la réserve W′ se vide vite.

Le temps passé par zone se compte **à la seconde de puissance** (comme le bilan), pas à la séance : une sortie libre avec trois montées compte en partie dans l'aérobie intense.

## 2. Comment identifier les besoins

Sept signaux, tous calculables depuis l'historique existant. Chacun donne un chiffre affiché tel quel au joueur.

| # | Signal | Calcul | Source | Ce qu'il dit |
| --- | --- | --- | --- | --- |
| S1 | **Répartition sur 4 semaines** | secondes par besoin (§1) sur 28 jours ÷ total | zones de `compute_summary`, par séance (cache de `history`) | le besoin le plus en retard sur la cible |
| S2 | **Forme** (charge chronique, aiguë, fraîcheur) | CTL = moyenne exponentielle du TSS quotidien sur 42 j ; ATL sur 7 j ; forme = CTL − ATL | TSS de `history` | fatigué (forme < −20), frais (> +5), reprise après coupure |
| S3 | **Dernière séance dure** | jours depuis la dernière séance avec ≥ 10 min en Z4–Z5, et depuis la dernière avec ≥ 6 efforts de ≥ 15 s au-dessus de 150 % | records 1 Hz des journaux | évite deux séances dures de suite ; relance une qualité oubliée |
| S4 | **Profil de puissance** | meilleures puissances 5 s, 1 min, 5 min, 20 min sur 90 j, en multiples de la FTP | `BEST_WINDOWS` de `session_summary`, `estimate_cp` (R16) | point faible relatif (départage seulement, voir prudence) |
| S5 | **Courses disputées** | où le joueur a perdu : lâché en montée, battu au sprint, craqué en fin de course, éliminé à une arche | lignes `survivor_summary` (DS), segments chronométrés (T4), journal des courses de la Course tactique (CT13), courses avec bots | le besoin qui coûte des places |
| S6 | **Prochaine course** | date de la prochaine manche annoncée (championnat, coupe, course par étapes) | calendrier du joueur (lot CO6) | affûtage avant, récupération après |
| S7 | **FTP à jour** | âge du dernier test de FTP accepté, FTP provisoire seulement | lignes `ftp_test` (O10), `ftp-test --history` | proposer un test avant de conseiller sur des zones fausses |

Prudence affichée (même avertissement qu'`estimate_cp`) : le profil de puissance S4 suppose des efforts maximaux ; il ne sert qu'à départager deux besoins proches et n'est lu que si l'historique contient un test ou une course de moins de 90 jours.

Signaux écartés pour la première livraison (question Q4) : la fréquence cardiaque (dérive cardiaque Pa:FC sur l'endurance, possible avec la FC relayée par le trainer mais absente d'une partie des séances) et le ressenti noté après la séance (échelle 1 à 10, nouvel écran à la fin de séance). Les deux peuvent venir plus tard comme signaux supplémentaires, sans changer les règles.

### Cibles de répartition

Cible par défaut : **polarisée**, en temps sur 4 semaines. Le joueur choisit son objectif dans le menu (§6) ; l'objectif ne change que les cibles.

| Objectif | Aérobie léger | Aérobie intense | Anaérobie |
| --- | --- | --- | --- |
| Endurance (par défaut, polarisé 80/20) | 80 % | 16 % | 4 % |
| Courses et championnat | 72 % | 20 % | 8 % |
| Grimpeur (cols, montées) | 75 % | 22 % | 3 % |
| Reprise (CTL < 20) | 90 % | 10 % | 0 % |

Le **retard** d'un besoin est `cible − part réelle`, en points ; le plus grand retard positif est le besoin du jour, sous réserve des règles de sécurité (§3, R1 à R4).

## 3. Règles proposées

Lues dans l'ordre, la première qui s'applique décide. Chaque règle a son identifiant, affiché dans « Détail du calcul » (pour que le joueur et nous puissions dire « c'est la règle R3 qui a parlé »). Les seuils sont dans une table unique `coach.toml` (dossier `data/` du core, lot CO1), pas dans le code.

| Règle | Condition | Conseil | Raison affichée (exemple) |
| --- | --- | --- | --- |
| R0 | moins de 3 séances sur 28 jours, ou aucune FTP | aérobie léger 45 min, puis test de FTP proposé | « Pas encore assez de séances pour te conseiller finement : on commence par l'endurance. » |
| R1 | course disputée hier, ou forme < −30 | récupération 30 à 45 min | « Tu as couru hier (TSS 95) : on récupère aujourd'hui. » |
| R2 | prochaine course dans 1 à 2 jours (S6) | activation : 45 min Z2 avec 3 × 1 min Z5 et 3 sprints de 10 s | « Course après-demain : séance courte pour garder la vivacité sans te fatiguer. » |
| R3 | forme entre −30 et −20, ou séance dure hier et avant-hier | aérobie léger | « Forme −24 : deux séances dures cette semaine, on roule tranquille. » |
| R4 | dernier test de FTP de plus de 6 semaines, ou FTP provisoire seulement, et forme > −10 | test de FTP | « Ta FTP date du 12 septembre : un test recalera tes zones. » |
| R5 | une séance d'un plan actif (O11) est prévue aujourd'hui | la séance du plan | « Séance du plan « Reprise 4 semaines », semaine 2. » |
| R6 | sinon : besoin au plus grand retard (S1), avec deux garde-fous : pas d'aérobie intense ni d'anaérobie si une séance dure date de moins de 48 h ; au plus 2 séances dures par 7 jours (3 avec l'objectif « Courses ») | le besoin retenu | « 9 % de ton temps en aérobie intense sur 4 semaines (cible 16 %), dernière séance intense il y a 6 jours. » |
| R7 | deux besoins à moins de 3 points d'écart | départage par les courses (S5), puis par le profil (S4), puis le moins récent | « Lâché 2 fois en montée sur tes 3 dernières courses : aérobie intense plutôt qu'anaérobie. » |

Choix de la séance une fois le besoin connu :
1. Les entraînements de la bibliothèque (livrés, importés, créés au menu, O12 et O30) sont **classés par besoin** à partir de leurs blocs et de la FTP : le besoin qui a le plus de temps au-dessus de Z2 dans la séance, la récupération si tout est sous 55 % (lot CO2).
2. Parmi ceux du besoin, la séance dont la durée est la plus proche du **temps disponible** (réglage, 60 min par défaut) ; à égalité, la moins faite sur 28 jours.
3. Sans entraînement du besoin dans la bibliothèque : un parcours conseillé à la place (aérobie léger : parcours plat le plus long sous le temps disponible ; aérobie intense : parcours avec la plus longue montée, fiches de O15), ou le message « aucune séance de ce besoin : installe le pack d'entraînements » (lien vers Réglages › Contenus, O25).

Le conseil est **calculé à l'ouverture de l'écran**, pas stocké ; il ne change pas pendant la journée sauf si une séance a été faite entre-temps (elle entre alors dans l'historique).

## 4. Courses et championnat

Il n'y a pas encore de championnat dans le jeu : la « coupe de trois manches » du Grand Prix (4.0, PLAN_SERIE_GP §10) et la course par étapes CT18 (5.0) sont des pistes. La série CO prévoit donc deux choses indépendantes :

- **Lire les courses déjà disputées** (S5, lot CO6) : un journal qui contient une course (bots, Dernier survivant, Course tactique, Cyber-Rogue) donne une « cause de perte » simple, quand on peut la dire :
  - lâché ou éliminé dans une montée (pente moyenne > 3 % sur la minute d'avant) → aérobie intense ;
  - battu dans les 300 derniers mètres ou à un sprint (T) avec moins de 2 s d'écart → anaérobie ;
  - plus de 10 % de puissance perdue entre le premier et le dernier quart de la course → aérobie léger (endurance) ;
  - sinon, aucune cause (rien n'est inventé).
  Le journal des courses CT13 (moments décisifs) en fournira de meilleures quand il existera ; CO6 ne dépend que de ce qui est déjà écrit dans les journaux.
- **Annoncer une course à venir** (S6) : dans l'écran de conseil, « Ma prochaine course » enregistre une date et un type (course, manche de championnat) dans le profil. Quand un mode championnat existera, il écrira lui-même la date de sa prochaine manche au même endroit.

## 5. Questions au propriétaire (réponses par défaut appliquées)

| # | Question | Défaut proposé |
| --- | --- | --- |
| Q1 | La VO2max (Z5, 105–120 %) est-elle « aérobie intense » ? | oui ; l'anaérobie commence à 120 % |
| Q2 | Cible par défaut | polarisée 80/16/4, objectif réglable au menu |
| Q3 | Le plan actif passe-t-il avant le conseil ? | oui (R5 après les règles de sécurité R1 à R4) ; le conseil s'affiche en « autre idée » |
| Q4 | Fréquence cardiaque et ressenti après séance dès la première livraison ? | non, plus tard en signaux facultatifs |
| Q5 | Où mettre l'écran ? | ligne « Séance conseillée » en tête de l'accueil, avant le plan (détail : besoin et séance) |
| Q6 | Nouvelles séances livrées | 3 : `recuperation_40`, `anaerobie_8x30s`, `sprints_10x10s` (contenus de départ O25) |
| Q7 | « Lancer cette séance » démarre-t-il directement en ERG ? | oui, comme « Entraînement » du menu ; un parcours conseillé démarre en SIM |

## 6. Écran (maquette à valider avant CO5)

Maquette de principe : `/mnt/project-files/menus/co-seance-conseillee/` (1280 × 720, jetons de `ui_theme.gd`). Deux écrans :

1. **Séance conseillée** (ligne de l'accueil) :
   - en tête, le besoin du jour en grand, en couleur du besoin (léger `OK`, intense `WARN`, anaérobie `DANGER`, récupération `DIM`) ;
   - la séance (nom, durée, TSS estimé) et la raison en une phrase ;
   - « Lancer cette séance » (A) ; « Une autre séance de ce besoin » ; « Choisir un autre besoin » (aérobie léger, aérobie intense, anaérobie, récupération, test de FTP) ; « Ma prochaine course » ; « Objectif » (Endurance, Courses et championnat, Grimpeur) ; « Temps disponible » (30 à 120 min) ; « Détail du calcul ».
2. **Détail du calcul** : barres de répartition sur 4 semaines avec la cible en repère, forme (CTL, ATL, forme), jours depuis la dernière séance dure, profil de puissance 5 s / 1 min / 5 min / 20 min, dernières causes de perte en course, règle qui a décidé.

## 7. Lots

| Lot | Contenu | Langage | Dépend de | Où |
| --- | --- | --- | --- | --- |
| CO0 | Cette étude, règles, questions, maquette de principe | docs | – | délégable |
| CO1 | Module pur `coach.py` : signaux S1 à S4 et S7, règles R0 à R7, table `coach.toml`, commande `openride-core coach [--json] [--date]`, historiques synthétiques des tests | Python | O28, O10, R16, MJ1 | délégable, CI |
| CO2 | Classement des entraînements par besoin + 3 séances livrées (Q6) | Python + .zwo | O12, O25 | délégable, CI |
| CO3 | Contrat : commande `get_coach`, message `coach`, réglages `[coach]` (objectif, temps disponible), prochaine course dans le profil | contrat | CO1 | propriétaire (révision IPC libre à la fusion) |
| CO4 | Maquettes au rendu du jeu, validées par le propriétaire | GDScript | CO0 | interne |
| CO5 | Écrans du menu (ligne de l'accueil, conseil, détail, autre besoin, prochaine course) | GDScript | CO3, CO4 | interne, captures low/medium/high |
| CO6 | Causes de perte des courses (S5) et prochaine course (S6), règles R1, R2, R7 complètes | Python | CO1, DS2, T4 (CT13 quand il existe) | délégable, CI |
| CO7 | Recette : deux semaines d'usage, le propriétaire juge chaque conseil (suivi / pas suivi / pourquoi) | – | CO5, CO6 | propriétaire, vélo |

Ordre : CO0 ──► CO1, CO2, CO4 ;  CO1 ──► CO3, CO6 ;  CO3, CO4 ──► CO5 ;  CO5, CO6 ──► CO7.

Fichiers partagés : `session_summary.py` (lecture seule : CO1 réutilise `compute_summary` et `BEST_WINDOWS`) ; `history.py` (CO1 réutilise son cache) ; `plans.py` (CO1 lit le plan actif) ; `contents.py` (CO2) ; `profile.py` (CO3, prochaine course) ; `menu_model.gd`, `menu_flow.gd` (CO5).

Coût de calcul : sur 90 jours de séances à 1 Hz, lecture par le cache de `history` (bilans) et `mmp.json` (meilleures puissances) ; seuls S3 et S5 relisent des journaux, ceux de 28 jours au plus. Calcul dans le core à la demande du menu, jamais pendant une séance.

## 8. Journal

| Date | Changement |
| --- | --- |
| 2026-11-07 | Création (lot CO0) : besoins, signaux, règles, questions Q1 à Q7, lots CO0 à CO7. |
