# OpenRide Linux – Audit de cohérence globale de la spécification

27 octobre 2026. Lecture seule de `main` (commit `8817bc8`, après la fusion de P1, PR #283), des 50 pull requests ouvertes ce matin et des issues GitHub. Aucun code n'est modifié ; ce rapport ne corrige aucun document, il dit quoi corriger et ce qu'il faut trancher.

Documents relus : [SPECIFICATION_GENERALE.md](SPECIFICATION_GENERALE.md), [SRS_v1.1.md](SRS_v1.1.md), [contracts/ipc_v1.md](contracts/ipc_v1.md) et ses schémas, [lots/00_INDEX.md](lots/00_INDEX.md), [SUIVI_AVANCEMENT.md](SUIVI_AVANCEMENT.md), les plans [R](2.0/PLAN_SERIE_R.md), [T](2.0/PLAN_SERIE_T.md), [V](2.0/PLAN_SERIE_V.md), [W](2.0/PLAN_SERIE_W.md), [U](3.0/PLAN_SERIE_U.md), le [README de la 2.0](2.0/README.md), le GDD du Cyber-Rogue et les cahiers des séries N, O, P, Q, R, S, T, V et W. La série X n'a pas de plan dans le dépôt (cahiers écrits au démarrage de chaque lot, issues #199 à #229).

## 1. En bref

- **Contrat IPC.** La révision 1.3 (P1) est sur `main`, avec la limite de 4 096 octets pour `state` et le champ `rev`. Mais quatre PR encore ouvertes ajoutent des lignes « révision 1.2 » au journal des changements (#248, #233, #288, #287) et sont toutes en conflit avec `main`. Il faut dire comment on les range (décision 1).
- **Boutons.** Le plan commun du §7.1 est respecté par les cahiers R, mais pas encore partout : la PR #287 fait de Z le « retour » des menus, le plan T dit encore « A reste libre », le changement des boutons ERG n'a ni lot ni issue, et le cahier W1 n'a pas l'appui long sur A (décisions 2 et 3).
- **Caméra.** Les quatre vues du §7.2 n'ont aucun lot ; le cahier V6 n'en prévoit que deux, au clavier et au menu, sans le bouton A. Le lot S1 suppose une caméra qui regarde toujours devant (décision 5).
- **Suivi.** Aucune ligne cochée n'a disparu du suivi, de l'index ou du README sur les 60 derniers commits de `main` : les pertes dues aux fusions « ours » ont été rétablies. En revanche, T4, T6 et T16, fusionnés, n'ont jamais eu de ligne dans le suivi, et l'index ne marque pas « Livré » T2, T4, T6, T16, V2, V3, V3b, V4, Q1 et Q3.
- **Spécification générale.** Une vingtaine de statuts sont périmés depuis les fusions du 26 et du 27 octobre (§4.4), et le point C10 est réglé.

## 2. Décisions pour le propriétaire

Une seule liste, de la plus urgente à la moins urgente. Chaque fois, la proposition recommandée vient en premier.

| # | Question | Proposition recommandée | Autre choix |
| --- | --- | --- | --- |
| 1 | Les ajouts « 1.2 » encore en revue (réglages O3/O4 #248, précisions X25 #233, `bad_args`, imports d'entraînements et arrondi #288, `PLUS_UNCLEAR` #287) arrivent après la 1.3, déjà fusionnée | **Garder l'étiquette 1.2**, comme le dit la décision D2 (« la 1.2 se ferme à la sortie de la 1.0 »), ranger leurs lignes avant celle de la 1.3 dans le journal et écrire au §5 du contrat qu'un programme qui annonce `rev` « 1.3 » connaît toute la 1.2. Le champ `rev` n'est que journalisé, donc rien ne casse | Renuméroter ces ajouts en 1.3 (quatre PR à reprendre) |
| 2 | Bouton Z dans les menus : la PR #287 en fait le « retour » (A = valider), alors que le §7.1 réserve Z à l'action du mode et donne le retour à B long | **Accepter Z = retour dans les menus comme exception écrite au §7.1** : un menu n'a pas d'action de mode, et un retour en un appui répond à la gêne relevée le 26 octobre (« impossible de valider au Click ») | Z sans effet dans les menus, retour par B long seulement |
| 3 | Changement des boutons ERG du §7.1 (± long = biais ± 10 %, Z = bloc suivant) : aucun lot, aucune issue | **Créer un petit lot core et le livrer avant la 1.0**, avant le guide O6 et la recette O8 : sinon le guide et les notes de version décrivent un geste qui change juste après | Le garder en mise à jour 1.x, comme l'écrit le §7.1 |
| 4 | Contrat 1.4 (R1, T1, V1) : P1 étant fusionné, rien ne le bloque plus. D2 et V-Q4 disent « un seul lot de contrat », mais l'index a deux lignes (R1, V1) et T1 n'a ni cahier ni issue | **Rédiger maintenant le cahier T1, puis un seul lot et une seule PR « contrat 1.4 »** qui réunit R1, T1 et V1, avec `Z_SHORT`, `Z_LONG`, `A_SHORT`, `A_LONG`. Le contrat peut fusionner avant la 1.0 (ajouts compatibles, sans effet) ; le branchement des modes attend la 1.0 | Attendre la publication de la 1.0 pour tout le contrat |
| 5 | Vues de caméra (2.0-CAM-1 et 2) : aucun lot ; le cahier V6 prévoit deux vues (subjective et suivi) basculées au clavier et au menu Garage | **Créer un lot « vues de caméra » après V6**, avec les quatre vues, A court et une touche du clavier dédiée (par exemple C) ; les flèches haut et bas du boîtier gauche ne servent que de complément tant que Q6 n'est pas réglé, comme pour les branches (décision D8). Corriger V6 et V-Q11 dans ce sens | Garder deux vues en 2.0 et reporter les vues éloignées |
| 6 | Le clavier « double chaque bouton » (§7.1), mais ses flèches haut et bas valent déjà + et − (SRS §4.2, PR #287) | **Garder les flèches du clavier pour + et −** et donner des touches propres aux vues et à Z et A (celles de R1 : Z, A, maintien 0,9 s pour l'appui long) ; l'écrire au §7.1 | Aligner le clavier sur le Click (flèches = vues) et déplacer le braquet sur + et − |
| 7 | Série Q : Q2 #191, Q4 #194 et Q5 #195 sont ouvertes depuis le 25 octobre et en conflit avec `main` (README, SRS, suivi) ; Q6 #193 fusionne proprement. Q4 bloque R0 et R8 | **Demander à la session qui tient la série Q de reprendre ces PR** (je n'y touche pas, comme convenu) | Les laisser jusqu'à la recette O8 |
| 8 | Neuf issues X sont fermées « terminées » alors que leur PR est encore ouverte : X2 (#236), X4 (#237), X5 (#245), X8 (#295), X13 (#280), X16 (#294), X23 (#234), X25 (#233), X29 (#296) | **Rouvrir ces neuf issues** ; elles se refermeront à la fusion de leur PR | Les laisser fermées et suivre seulement les PR |
| 9 | Lots sans issue : V1, V5 à V11 ; T1, T7 à T13, T15 ; N15 et N16 (PR ouvertes) | **Ouvrir maintenant les issues de V1, V5 à V11 et T1** (cahiers sur `main` ou à écrire tout de suite) ; les autres lots T à leur cahier ; N15 et N16, internes, sans issue | Tout ouvrir d'un coup, y compris R0 à R17 (prévues après la 1.0 sous #117) |
| 10 | Accueil de N15 (#230) : l'entrée « Monde » choisit un parcours, alors que le monde ouvert de la 2.0 s'appelle aussi « monde » ; la 1.3 demande d'afficher les modes de `hello_ack.config.modes` | **Renommer l'entrée « Parcours »**, réserver « Monde ouvert » à la série W, et faire filtrer l'accueil par `modes` | Garder « Monde » et renommer plus tard |
| 11 | Demi-tour sur la route et réglage des bots par appui long (SRS §14) : envisagés, mais dans aucune série, et le plan de boutons ne leur laisse plus de geste | **Les marquer « abandonnés » dans la spécification générale** (ou les ranger dans une future série menus) | Les garder en évolution envisagée |

### 2.1 Réponses du propriétaire (27 octobre) et suite donnée

Principe donné par le propriétaire : **on évite les exceptions ; on préfère réécrire pour mettre au propre et assurer la cohérence.** Il s'applique à toutes les décisions et remplace les propositions « exception » ci-dessus.

| # | Réponse | Fait dans cette PR | Reste à faire ailleurs |
| --- | --- | --- | --- |
| 1 | « Au plus propre » | Révisions dans l'ordre des fusions : la 1.2 (Q1, N13) est fermée ; la 1.3 (P1) reste ouverte jusqu'à l'étiquette `v1.0.0` et reçoit tous les ajouts de la 1.0 (spécification générale §6.1, contrat §8) | Les PR #248, #249, #288 et #287 renomment leurs lignes « 1.2 » en « 1.3 » ; X25, fusionné entre-temps, est corrigé dans cette PR |
| 2 | Mettre au propre l'affectation des boutons, notamment Z | Tableau unique du §7.1 réécrit sans exception, menus compris : ± déplacent, A court passe à l'option suivante et A long valide, Y revient en arrière, Z ne fait que l'action du mode (rien dans un menu). Les événements de tous les boutons entrent une seule fois dans la 1.3. SRS §4.2, §4.4, §4.5 et §6, plans R et T, cahiers R8, T6, W1 et W9 (et R1, fondu depuis dans T1) renvoient à ce tableau | La PR #287 réécrit les menus selon le tableau (A = valider, Z = retour y sont remplacés) et ajoute les événements ; la PR #282 (W1) retire de son schéma les événements déjà en 1.3 |
| 3 | Mettre à jour | Cahier [O17](lots/LOT_O17_boutons_erg.md), exigence 1.0-ERG-5, notes dans la SRS | Issue du lot O17 ; développement après la PR #287 |
| 4 | OK | Cahier [T1](lots/LOT_T1_contrat_1_4.md) : un seul contrat 1.4 pour les séries R, T et V ; cahiers R1 et V1 retirés, leurs renvois (plans R, T et V, cahiers R3 à R17, V2 à V11, index, suivi) pointent vers T1 | Issue #378 mise à jour ; #370 (V1) fermée en double de #378 |
| 5 | Lot dédié avec les vues | Cahier [V12](lots/LOT_V12_vues_camera.md) (quatre vues, A et flèches haut et bas, A long = vue par défaut, `[render] camera`) ; V6 réécrit sans caméra ; S1 trie selon la caméra active ; V-Q11 réglée ; exigences 2.0-CAM-1 à 2.0-CAM-5 rattachées à V12 et S1 | Issue #387 |
| 6 | OK | Tableau du clavier dans la spécification générale §7.1 (touche pour touche, mêmes seuils, synonymes Page haut et bas, Maj+A, Entrée, Maj+Z, Échap ; plus de P ni d'Espace) ; SRS §4.2 et §4.5 ; lot O17 étendu au clavier (module `key_map.gd`) | Issue #367 mise à jour ; la PR #287 n'ajoute pas de touches propres aux menus |
| 7 | Sans objet | — | Q2, Q4, Q5 et Q6 corrigées et fusionnées le 27 octobre, Q1 terminée (PR #388) : la série Q est entièrement sur `main` |
| 8 | Sans objet | Ligne X25 du journal du contrat en révision 1.3 | — |
| 9 | OK | — | Issues de V1, V5 à V11, T1, O17, N17 et N18 |
| 10 | OK | Exigence 1.0-UI-2 (« Parcours », modes annoncés) | La PR #230 (N15) renomme l'entrée et filtre l'accueil par `modes` |
| 11 | « Prévois ça dans les menus » | Lots [N17](lots/LOT_N17_demi_tour_menu.md) (demi-tour depuis l'écran de pause) et [N18](lots/LOT_N18_bots_menu.md) (bots réglés au menu), version 1.x ; exigences 1.x-UI-1 et 1.x-UI-2 ; SRS §4.4 et §14 | Issues de N17 et N18 |

Toutes les décisions sont réglées.

## 3. Constats par thème

### 3.1 Numérotation de l'IPC (1.2 à 1.5)

| Révision | État réel | Écart |
| --- | --- | --- |
| 1.2 | Q1 et N13 sur `main` ; O3/O4 (#248), X25 (#233), D4/D5/D9 et N16 (#288, #249), `PLUS_UNCLEAR` (#287) en revue | Les quatre PR écrivent « révision 1.2 » et sont en conflit avec le journal de `main` (décision 1) |
| 1.3 | P1 sur `main` : `wind`, `draft`, `draft_bot`, `state` à 4 096 octets, `rev`, `modes` ; `CONTRACT_REV = "1.3"` dans le core et l'engine | La spécification générale dit encore « Spécifié » (§6.1) et garde C10 ouvert (§9) |
| 1.4 | Cahiers R1 et V1 sur `main`, T1 non rédigé | Trois lots au lieu d'un (décision 4) |
| 1.5 | W1 en revue (#282), numéro validé par le propriétaire le 26 octobre (D2) | La spécification générale écrit « reste à confirmer » (§6.1) ; le journal de #282 dit bien « validé » |
| U | Spécification générale : « aucun ajout prévu » | L'issue #331 (U1) annonce une « IPC 1.6 provisoire » : à revérifier (§5) |

Traces de l'ancienne numérotation encore présentes : l'issue fermée #125 (P1) s'intitule « IPC v1.2 » (sans conséquence) ; le plan T §3.5 dit que les bots enrichis « tiennent dans 1 400 octets » alors que la limite de `state` est de 4 096 octets depuis la 1.3.

### 3.2 Limite de la trame `state`

Cohérent sur `main` : contrat §2 (4 096 octets depuis la 1.3), §3 (`wind` jamais dans la même trame que `devices`), `ipc_server.py` (`MAX_STATE_DATAGRAM_SIZE = 4096`, 1 400 pour les autres messages, 60 000 pour les listes). Reste à fusionner l'arrondi des flottants de la décision D1 (dans #288) et l'allègement de trame de X25 (#233), qui ne prend son sens qu'avec une limite à 1 400 : à relire à la reprise de #233 (les trames de référence de X25 doivent passer à 4 096). Point C10 de la spécification générale : réglé.

### 3.3 Boutons du Click (plan commun du §7.1)

| Où | Ce qui est écrit | Écart avec le §7.1 |
| --- | --- | --- |
| Plan T §3.3 | « Y met en pause, Z active le bonus ; A reste libre » | A change de vue de caméra en classique |
| SRS §4.4 et §6, CHANGELOG 0.9.0, cahier F | ERG : + long = bloc suivant, − long = pause | Normal tant que le lot ERG n'existe pas (décision 3) ; à changer avec lui |
| PR #287 (menus) | A = valider, Z = retour, toute durée | Z (décision 2) ; A « valider » reste dans la famille « choisir et valider » |
| Cahier W1 (`main` et #282) | `LEFT_SHORT`, `RIGHT_SHORT`, `A_SHORT` | Pas d'`A_LONG` (« valider la branche tout de suite »), que le §7.1 attribue à W1 |
| Cahiers R1, R8, R13, R14, GDD | Y = pause, Z = attaque et carte active, A = couloirs, ± long = ± 3 | Conformes |
| Cahier T6 | Z = bonus, événement `Z_SHORT` attendu de T1 ou R1 | Conforme |

### 3.4 Vues de caméra (§7.2)

- Aucun lot pour 2.0-CAM-1 (quatre vues) et 2.0-CAM-2 (changement au Click, `[render] camera`) ; la clé `[render] camera` manque aussi au §6.3.
- Le cahier V6 fait une caméra de suivi (4 m derrière, 1,8 m de haut) et une bascule au clavier et au menu (V8), sans le bouton A ni les vues éloignées.
- Aucun événement d'entrée n'existe pour les flèches haut et bas du boîtier gauche, et ce boîtier reste muet tant que Q6 n'est pas réglé.
- Le cahier S1 écarte ce qui est « derrière la caméra », qui regarde toujours devant à 1,4 m : avec une vue latérale ou en hauteur, ce tri doit suivre la vue active. À écrire dans S1 avant son démarrage (2.0-CAM-5).

### 3.5 Versions 1.0, 1.x, 2.0 et 3.0

- §1 de la spécification générale : la 1.0 compte « les séries A à O et Q », mais S1 (exigence 1.0-RND-3) et les outils de la série X utiles à la recette (X30, tableau de recette 1.0) n'y sont pas nommés.
- §5.1 : « Tous les lots attendent la publication de la 1.0 » ; le propriétaire a lancé la série P le 26 octobre, P1 est fusionné et P2 à P21 sont en revue (l'index le dit déjà).
- README de la 2.0 : « Rien de ceci n'est commencé » (C2, toujours pas corrigé) alors que T2, T4, T6, T16, V2, V3, V3b et V4 sont fusionnés ; la série V y est annoncée « lots V1 à V10 » au lieu de V1 à V11.
- Index §3 (règles communes) : « aucun accès réseau à l'exécution, sauf dans le lot B2 » ; contredit par le compilateur OSM (I3, I4), les lots W et la règle R-NET-1 à R-NET-3 adoptée le 26 octobre (C4).
- Suivi : la section « Après la 1.0 : décor vivant, vent et aspiration » garde ce titre, et le suivi n'a aucune section pour les séries T, W, R et X.

### 3.6 Dépendances entre lots

- P1 fusionné débloque R1, T1 et V1 (décision 4), puis R8, R10, V11, V6, V8 et V9 ; l'index et les plans les donnent encore « après P1 ».
- R0 et R8 dépendent de Q4 (#194), fusionnée depuis le 27 octobre.
- P17 dépend d'O7 (bots à l'écran, facultatif, non commencé) : la PR #321 le dit et branche l'abri sans silhouette. Cohérent, à garder en tête pour O7.
- O10 (test de FTP) attend #248 ; N16 (#249) suit la décision D4 de #288 : fusionner #288, puis #248, puis #249.
- La chaîne W2 à W13 reste empilée sur W1, qui fusionne après la 1.4 (choix du propriétaire du 27 octobre) : la 1.4 est donc sur le chemin critique de la série W.
- Les fichiers `README.md` et `docs/SUIVI_AVANCEMENT.md` sont en conflit dans presque toutes les PR ouvertes (testé avec `git merge-tree` : Q2, Q4, Q5, N15, N16, W2 notamment).

**Ordre de fusion conseillé** (pour limiter les conflits du contrat et du suivi) : #288 (audit IPC, arrondi, D4), #248 (O3/O4), #233 (X25), #287 (menus), #230 (N15), #249 (N16), puis les PR Q ; ensuite la chaîne P (P2, P4, P5, P6, P9, P10, P16, puis P3, P8, P11 à P15, P21, P17) ; T5 #326, T14 #328, T3 #330 ; enfin le contrat 1.4, puis W1 et la chaîne W. À chaque fusion d'un document en conflit : prendre le côté de `main` et remettre seulement ses propres lignes, puis recompter les tests.

### 3.7 Lignes de suivi et fusions « ours »

Vérification sur les 60 derniers commits de `main` (premier parent) :

- aucune ligne cochée `[x]` du suivi n'a disparu ; aucune ligne du tableau de l'index ni aucun statut « Livré » n'a été perdu ; aucun titre du README n'a disparu (les pertes du 26 et du 27 octobre ont été rétablies par #289 et le commit `8a92306`) ;
- **oublis** (jamais écrits, pas effacés) : aucune ligne du suivi pour T4, T6 et T16 ; l'index ne marque pas « Livré » T2, T4, T6, T16, V2, V3, V3b, V4, ni Q1 et Q3 (C9) ;
- le fichier `CLAUDE.md` liste bien `segments.py`, `segment_timing.py`, `powerups.py` et `gaps.py`.

### 3.8 Lots sans cahier ou sans issue

| Lot | Cahier sur `main` | Issue | Remarque |
| --- | --- | --- | --- |
| N15, N16 | Non (cahier dans #230 et #249) | Non | Internes ; exigence 1.0-UI-2 |
| Lot ERG du §7.1 | Non | Non | Pas même un numéro (décision 3) |
| Vues de caméra | Non | Non | Décision 5 |
| T1 | Non | Non | Débloqué par P1 |
| T3, T5, T14 | Non (cahiers dans #330, #326, #328) | #329, #325, #327 | En revue |
| T7 à T13, T15 | Non | Non | Décisions du 27 octobre dans le plan T §6 |
| V1, V5 à V11 | Oui | Non | Décision 9 |
| R0 à R17 | Oui | Non | Prévu après la 1.0, sous #117 |
| U1 à U22 | Non (thread en cours) | #331 à #352 | §5 |
| X1 à X31 | Non (écrits au démarrage) | #199 à #229 | Neuf issues fermées trop tôt (décision 8) |
| Option « gravel » | Non | #350 à #352 (U20 à U22) | La spécification générale dit encore « pas encore de lot » |

### 3.9 Questions restées ouvertes

Sur `main`, toutes les questions des plans sont tranchées : R-Q1 à R-Q10, T-Q1 à T-Q6, V-Q1 à V-Q13 (V-Q10 remplacée par les pièces à l'effort), W-Q1 à W-Q5, U-Q1 à U-Q5, U-G1, U-G2, C4 à C7. Restent :

- les décisions 1 à 11 ci-dessus ;
- l'index (paragraphe de la série V) dit encore « questions V-Q5 à V-Q13 ouvertes » ;
- essais matériels non faits : recette E3/E4 sur la GTX 1060, vérification des cols d'O16 (± 5 %), O13 sur un PC au repos, essais Q (fin de chaque lot Q), R0 (délai du frein).

## 4. Corrections sans décision, à faire dans un lot de documentation

Ces corrections suivent des décisions déjà prises. Elles peuvent aller dans une seule PR de documentation après la fusion des PR en cours, pour ne pas ajouter de conflits.

### 4.1 Spécification générale

| § | Ligne | Correction |
| --- | --- | --- |
| 1 | Versions | Nommer S1 et la série X (outils, X30 pour la recette 1.0) |
| 4 | 1.0-ERG-3 | O11 livré ; O10 et O12 restent |
| 4 | 1.0-CMP-2 | Livré (O5 fusionné) |
| 4 | 1.0-CMP-3 | Livré (O15, O16) ; vérification des cols sur le PC à faire |
| 4 | 1.0-UI-4 | O13 livré ; O14 spécifié |
| 4 | 1.0-INS-2 | O2 livré ; O6 spécifié |
| 4 | 1.0-UI-2 | N15 et N16 en revue (#230, #249), sans cahier sur `main` |
| 5.1 | Introduction et lignes 1.x | Série P lancée le 26 octobre ; P1 livré ; P2 à P21 en revue |
| 5.2 | 2.0-SEG-1 à 3, BON-1, BOT-2, BOT-3 | T2, T4, T6, T16 livrés ; T5 (#326), T14 (#328), T3 (#330) en revue |
| 5.2 | 2.0-PRG-1 à 3 | V2, V3, V3b, V4 livrés (modules purs, branchés par V11) |
| 5.2 | Phrases « cahiers en revue » | Cahiers R (#244), V (#238) et W (#272) fusionnés |
| 5.2 | 2.0-ROG-1 | Outil X5 en revue (#245), issue #203 fermée trop tôt |
| 5.3 | 3.0-GRV-1 | Lots U20 à U22 (issues #350 à #352) |
| 6.1 | 1.3 | Livré (P1, #283) |
| 6.1 | Règles | Numérotation confirmée par le propriétaire le 26 octobre (D2) ; ajouter la règle de la décision 1 |
| 6.2 | P1 | Livré |
| 6.3 | Configuration | Ajouter `[render] camera` (2.0-CAM-2) |
| 7.1 | Menus et clavier | Selon les décisions 2 et 6 |
| 9 | C1, C2, C9, C10 | C1 fait pour P1, à faire pour le plan T §3.5 ; C2 toujours à faire ; C9 étendu à T et V ; C10 réglé (D1, 1.3) |

### 4.2 Autres documents

- Plan T : §3.3 « A reste libre » → A = vue de caméra ; §3.5 « 1 400 octets » → 4 096 octets (1.3).
- README de la 2.0 : état réel des séries T, V et W ; « lots V1 à V11 ».
- Index : statuts « Livré » de T2, T4, T6, T16, V2, V3, V3b, V4, Q1, Q3 ; paragraphe V (questions réglées le 27 octobre) ; paragraphe T (T3, T5 et T14 en revue, T1 débloqué) ; §3 « Hors ligne » → règle R-NET ; paragraphe de la série U à ajouter avec ses cahiers ; lignes N15 et N16.
- Suivi : lignes T4, T6, T16 ; sections T, W, R et X ; titre de la section P.
- Cahier W1 : `A_LONG` (valider la branche) ; cahier V6 : selon la décision 5 ; cahier S1 : tri selon la vue active.

## 5. À revérifier quand les cahiers U et T1 seront écrits

- **U1 et l'IPC :** l'issue #331 annonce une « IPC 1.6 provisoire » ; la spécification générale (§6.1) dit « aucun ajout prévu » et renvoie le forçage du biome (U16) à la révision suivante. Choisir l'un ou l'autre et aligner les deux.
- **Nombre de lots U :** le plan U s'arrête à U18 ; les issues vont jusqu'à U22 (U19 parcours fictifs par biome, U20 à U22 gravel). Mettre à jour le plan U, l'index et le §5.3.
- **Gravel :** 3.0-GRV-1 veut une résistance de 2 à 3 fois celle du bitume, en supplément de pente sous le même plafond que le vent (4 points), et vitesse seule en ERG ; vérifier que U21 reprend ces trois points et qu'il partage le plafond avec P2.
- **Format `.world` :** couche `biome`, surface `gravel`, eau `sea` et côte : vérifier le numéro de mineur après celui de W1 et de T1 (couche `segments`).
- **Thème 2.0 :** le §6.2 parle d'un « thème 2.0 en pack de biomes » alors que P1 a fait le thème 1.2 ; vérifier que U1 lit les thèmes 1.x (3.0-BIO-7).
- **T1 :** qu'il porte `Z_SHORT`, `Z_LONG`, `A_SHORT`, `A_LONG` pour tout le monde, `segment`, `powerup`, `segment_result`, les champs des bots à profil, `gap_s`, `bot_ahead`, `bot_behind`, la couche `segments` (`segments.json` = liste de `Segment.to_dict()`), et la place des événements des vues de caméra (décision 5). Vérifier ensuite la taille de la pire trame 1.4 contre 4 096 octets avec l'outil de X25.
- **Boutons :** une fois T1 et le lot ERG écrits, refaire le tableau du §7.1 mode par mode.
