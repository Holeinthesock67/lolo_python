---
name: podcast-ecriture
description: Écrit les scripts des podcasts du propriétaire (débat ou revue) à partir du Google Sheet « Configuration podcasts » et des fichiers de veille déposés sur Drive.
---

# Écriture des scripts de podcast

Tu écris le script d'un ou plusieurs podcasts personnels du propriétaire, en français, lus ensuite par des voix de synthèse neuronales (edge-tts) sur un Raspberry Pi. Ces voix rendent bien l'intonation d'une vraie conversation, à condition que le texte soit écrit comme on parle. Un podcast n'est jamais un résumé des sources : sa valeur ajoutée, c'est le croisement des points de vue, la vérification des thèses et l'analyse.

## 1. Lire la configuration

1. Avec le connecteur Google Sheets, lis le classeur « Configuration podcasts » (identifiant `1ZyEsoMNFtplLW5rgMwDsVHTmUF54CESJ-WAhivaVz0U`) : l'onglet `Émissions` en entier (`'Émissions'!A:Q`).
2. Choisis les émissions à traiter :
   - si l'utilisateur ou la tâche planifiée nomme une émission (par son nom ou son identifiant), uniquement celle-là, même si elle est inactive ou que ce n'est pas son jour ;
   - sinon, les émissions dont la colonne `Active` vaut `oui` et dont la colonne `Jour` est le jour d'aujourd'hui (heure de Paris ; demande la date et l'heure avec l'outil prévu pour ça, ne la devine pas).
3. S'il n'y a aucune émission à traiter, réponds en une ligne « Aucune émission à écrire aujourd'hui. » et arrête-toi là.
4. Pour chaque émission retenue, lis son onglet de sources (colonne `Onglet des sources`) : nom, camp et thèse de chaque source.

Colonnes utiles de l'onglet `Émissions` : `Nom`, `Format` (`debat` ou `revue`), `Durée (min)`, `Dossier Drive`, `Prénom A`, `Prénom B`, `Consignes`. Les consignes de l'émission complètent ce skill ; en cas de contradiction, elles l'emportent.

Traite les émissions l'une après l'autre, entièrement (sections 2 à 7), avant de passer à la suivante.

## 2. Trouver la matière

1. Le dossier de l'émission s'appelle comme la colonne `Dossier Drive`. Cherche-le dans le dossier `Podcasts` (identifiant `1K2xwn7U5MN-irF0ZSy3o6cTHKBkRhIOi`) ; s'il n'y est pas, cherche un dossier de ce nom dans tout le Drive.
2. Dans son sous-dossier `sources`, prends le fichier `AAAA-Wss_source.md` de la semaine en cours (semaine ISO, ex. `2026-W42_source.md`). Si l'utilisateur joint ou désigne un autre fichier, utilise celui-là.
   - S'il n'existe pas, n'écris rien pour cette émission et signale-le dans ta réponse : la veille du Pi n'a pas tourné ou n'a pas pu envoyer le fichier.
3. Dans le sous-dossier `scripts`, regarde si un script de cette semaine existe déjà (`AAAA-Wss_script.txt` ou `AAAA-Wss_script_v2.txt`…). Si oui et que la demande vient de la tâche planifiée, n'écris rien et signale-le : le script de la semaine est déjà fait. Si l'utilisateur demande explicitement une nouvelle version, écris-la (section 7).
4. Regarde aussi les scripts des 4 dernières semaines, pour ne pas refaire le même sujet et pouvoir y faire référence (« il y a trois semaines, on parlait de… »).
5. Le fichier source commence par la liste des sources avec leur camp et leur thèse. Sers-t'en pour savoir qui défend quoi.

## 3. Longueur

Compte environ 150 mots par minute. La durée visée est dans la colonne `Durée (min)` : 30 minutes donnent environ 4 500 mots, 15 minutes environ 2 250. Les proportions de chaque format sont données en pourcentage de ce total.

## 4. Format `debat`

**Sujets**
- Sujet du débat : celui qui est abordé par le plus de sources ET par des camps différents, et qui divise vraiment. Formule-le comme une question tranchée, par exemple « La bulle de l'IA va-t-elle éclater d'ici deux ans ? ».
- Revue : deux ou trois autres sujets marquants de la semaine, différents du débat.
- Si la semaine est pauvre (peu de sources, pas de vrai désaccord), dis-le dans l'ouverture et choisis le sujet le plus discutable plutôt que d'inventer une controverse.

**Rôles**
- A défend la thèse la plus forte de la semaine, B la conteste. Les rôles peuvent s'inverser d'une semaine à l'autre selon le sujet.
- Les deux sont sérieux, précis, de bonne foi : chacun présente la meilleure version des arguments de son camp, sans homme de paille, concède quand l'autre marque un point et pousse l'autre sur ses faiblesses.

**Structure**
1. `## OUVERTURE` (≈ 3 %) : A annonce la semaine, la question du débat et les sujets de la revue. B réagit tout de suite, en une phrase.
2. `## DEBAT` (≈ 67 %) :
   - exposé de la thèse par A, puis de l'antithèse par B ;
   - trois ou quatre rounds, chacun centré sur un argument précis (un chiffre, un fait, une prédiction), avec réponses directes ;
   - un passage « ce qui tient, ce qui relève de la spéculation » : les deux trient faits établis et paris sur l'avenir ;
   - conclusion : chacun résume sa position en deux phrases, puis dit ce qui le ferait changer d'avis.
3. `## REVUE` (≈ 27 %) : deux ou trois sujets, en dialogue plus court et plus rapide : ce qui s'est passé, pourquoi c'est important, ce qui est contesté.
4. `## CLOTURE` (≈ 3 %) : « Qu'est-ce que ça change concrètement ? » : une ou deux implications pour le quotidien ou le travail. Puis fin.

## 5. Format `revue`

**Sujets**
- Quatre à six faits marquants de la semaine, classés du plus important au moins important. L'importance se juge au nombre de sources qui en parlent et à la portée des conséquences, pas au bruit.
- Regroupe ce qui va ensemble : plusieurs annonces sur un même thème font un seul sujet.
- Si la semaine est calme, dis-le et fais moins de sujets, plus approfondis.

**Rôles**
- A mène la revue : elle présente chaque sujet et ce qui s'est passé.
- B apporte l'analyse : il replace le fait dans son contexte, pose les questions qui fâchent, relève ce qui est incertain ou contesté.
- Ils peuvent ne pas être d'accord, mais sans opposition forcée : le but est de comprendre, pas de débattre.

**Structure**
1. `## OUVERTURE` (≈ 5 %) : A annonce la semaine et les sujets, B donne en une phrase son impression générale.
2. `## REVUE` (≈ 85 %) : un sujet après l'autre. Pour chacun : les faits (qui, quoi, quand, avec la source), pourquoi c'est important, ce qui est contesté ou incertain, et ce qu'il faudra surveiller. Une transition courte et naturelle entre les sujets.
3. `## CLOTURE` (≈ 10 %) : la tendance de fond de la semaine en deux ou trois répliques, puis ce qu'il faudra suivre la semaine prochaine. Puis fin.

## 6. Règles communes

**Sources**
- Reformule toujours : ne lis jamais un article ou une transcription mot pour mot. Une citation exacte reste exceptionnelle et très courte (moins de 15 mots).
- Attribue les thèses à voix haute : « Ed Zitron soutient que… », « Selon Hasheur… », « Gary Marcus estime au contraire… ».
- N'invente rien : chiffres, dates, citations et faits viennent uniquement du fichier source. Si un argument a besoin d'un fait absent du fichier, présente-le comme une hypothèse, ou ne l'utilise pas.
- Distingue clairement les faits, les opinions et les prédictions.
- Les sources en anglais sont traduites et reformulées en français.
- Jamais de conseil financier ou d'investissement personnalisé (« il faut acheter », « c'est le moment de vendre »). Les cours et les prix cités sont datés (« mardi, le bitcoin cotait… »), puisque l'épisode est écouté plus tard. Signale les contenus sponsorisés ou les partenariats mentionnés dans les sources.

**Les deux voix**
- A et B portent les prénoms des colonnes `Prénom A` et `Prénom B`. Ils se tutoient et s'appellent de temps en temps par leur prénom, comme deux collègues qui se connaissent bien. Ils peuvent saluer le propriétaire dans l'ouverture.
- Ton : sérieux sur le fond, vivant dans la forme. Une pointe d'ironie est permise quand elle sert le propos. Pas d'humour forcé, pas de formules creuses (« c'est passionnant », « excellente question »).

**Rythme**
- Alterne les longueurs. La plupart des répliques font entre quinze et soixante mots. Un argument développé peut aller jusqu'à cent vingt mots, jamais plus, et jamais deux répliques longues d'affilée du même personnage.
- Après une réplique longue, l'autre réagit souvent court : « Non. Ça, je ne te l'accorde pas. » ou « D'accord. Mais alors explique-moi une chose. »
- Une phrase, une idée. Évite les subordonnées en cascade.

**Relances et réactions**
- Ils se posent de vraies questions : « Et concrètement, ça donne quoi ? », « Tu as un chiffre pour ça ? », « Qui dit ça, exactement ? ».
- Ils reprennent les mots de l'autre pour rebondir : « Tu dis "bulle". Moi, je dirais plutôt correction. »
- Ils concèdent à voix haute : « Là, tu marques un point. », « Je te l'accorde, mais… ».

**Interruptions**
- Format `debat` : une ou deux fois par round, une réplique est coupée. Elle se termine par des points de suspension au milieu d'une idée, et la suivante commence par l'interruption : « Attends, je t'arrête là. », « Pardon, mais non. ». L'interrompu reprend ensuite : « Laisse-moi finir. Je disais que… ». Pas plus de deux ou trois par round.
- Format `revue` : rares, et plutôt pour préciser ou demander une précision que pour contredire.

**Langue parlée**
- Préfère les connecteurs de l'oral : « mais », « et puis », « sauf que », « du coup » (avec modération), « en fait ». Bannis ceux de l'écrit : « par ailleurs », « en outre », « néanmoins », « cependant », « ainsi », « en effet ».
- Les petits mots de l'oral (« bon », « écoute », « franchement », « tu vois ») sont permis, au plus un par réplique et pas dans toutes. Varie-les.
- La ponctuation guide l'intonation des voix : un point d'interrogation pour une vraie question, des virgules pour respirer, des points de suspension pour une hésitation ou une coupure. Les points d'exclamation restent rares.

**Contraintes de la synthèse vocale**
- Pas de parenthèses, pas de listes, pas de markdown, pas d'émojis, pas d'URL, pas de guillemets décoratifs.
- Écris les sigles comme ils se prononcent ou explique-les à la première occurrence : « l'AGI, c'est-à-dire une intelligence artificielle générale ». Écris « IA » tel quel.
- Écris les grands nombres et les pourcentages en toutes lettres : « deux mille milliards de dollars », « quarante pour cent ».
- Évite les termes anglais quand un mot français existe ; sinon, glisse une courte explication.

**Exemple de ton visé** (ne pas réutiliser tel quel) :
```
A: Les investissements dans les centres de données ont encore grimpé ce trimestre. Pour moi, c'est le signe que les grands groupes y croient vraiment.
B: Ou le signe qu'ils ont peur de rater le train.
A: Ce n'est pas incompatible. Mais quand on met des centaines de milliards sur la table, on a quand même fait ses calculs…
B: Attends, je t'arrête. Ed Zitron dit justement l'inverse : les revenus ne suivent pas du tout. Tu as un chiffre de revenus, toi ?
A: Pas cette semaine, non. Je te l'accorde.
```

## 7. Format du fichier et dépôt

Le Pi découpe le script ligne par ligne, quel que soit le format. Respecte strictement :
- une réplique par ligne, préfixée par `A:` ou `B:`, suivie d'un espace ;
- les marqueurs de section seuls sur leur ligne, ceux du format choisi (`## OUVERTURE`, `## DEBAT`, `## REVUE`, `## CLOTURE`) ; le Pi y insère un court silence ;
- pas d'autre texte : pas de titre, pas de didascalies, pas de lignes vides superflues ;
- la toute dernière ligne est exactement `FIN`. Le Pi ignore tout script qui ne se termine pas par `FIN`.

Dépôt :
1. Nom du fichier : même identifiant de semaine que la source, suffixe `_script.txt` (ex. `2026-W42_script.txt`), en texte brut UTF-8.
2. Crée-le avec le connecteur Google Drive dans le sous-dossier `scripts` du dossier de l'émission (crée-le s'il n'existe pas), sans conversion en document Google (type `text/plain`). Si un fichier du même nom existe déjà, ne l'écrase pas : ajoute `_v2`, `_v3`…
3. Avant de déposer, vérifie :
   - la longueur, à dix pour cent près de la durée visée ;
   - toutes les lignes commencent par `A: `, `B: ` ou `## `, et la dernière ligne est `FIN` ;
   - aucune réplique ne dépasse cent vingt mots, et la majorité fait moins de soixante mots ;
   - aucun connecteur de l'écrit de la liste bannie ;
   - aucun nombre écrit en chiffres : tout est en toutes lettres ;
   - aucun chiffre n'est absent du fichier source.
4. Ne modifie ni ne supprime aucun autre fichier, et n'écris rien dans le Sheet.

## 8. Réponse

Pour chaque émission traitée, réponds en trois lignes au maximum : le nom de l'émission, les sujets retenus, et le nom du fichier déposé. Pour une émission non écrite, une ligne qui dit pourquoi.
