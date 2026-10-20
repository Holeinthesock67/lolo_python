from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

D = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", D + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", D + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVI", D + "DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("DVBI", D + "DejaVuSans-BoldOblique.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVBI")

ACC = colors.HexColor("#1F4E5F")
NEW = colors.HexColor("#E8F3EE")
body = ParagraphStyle("b", fontName="DV", fontSize=9.5, leading=13.5, spaceAfter=4)
bul = ParagraphStyle("bl", parent=body, leftIndent=12, bulletIndent=2, bulletFontName="DV")
sub = ParagraphStyle("sb", parent=bul, leftIndent=26, bulletIndent=16)
h1 = ParagraphStyle("h1", fontName="DVB", fontSize=17, leading=21, textColor=ACC, spaceAfter=4)
h2 = ParagraphStyle("h2", fontName="DVB", fontSize=12, leading=15, textColor=ACC, spaceBefore=10, spaceAfter=5)
meta = ParagraphStyle("m", parent=body, fontName="DVI", fontSize=8.5, textColor=colors.HexColor("#555555"))
cell = ParagraphStyle("c", fontName="DV", fontSize=7.8, leading=10)
cellb = ParagraphStyle("cb", parent=cell, fontName="DVB", textColor=colors.white)

S = []
P = lambda t, s=body: S.append(Paragraph(t, s))
B = lambda t: S.append(Paragraph(t, bul, bulletText="●"))
BB = lambda t: S.append(Paragraph(t, sub, bulletText="○"))

P("Synthèse Intégrale v2.3 : Performance, Entraînement, Home Gym, Nutrition et Santé (Homme, 45 ans)", h1)
P("Version 2.3 – 20 octobre 2026 – révisée selon l'état actuel de la littérature scientifique ; pilotage de l'intensité par la charge Garmin sur 4 semaines.", meta)
P("Ce document rassemble les métriques et principes essentiels pour piloter la performance, la charge "
  "d'entraînement, le home gym, la nutrition empirique et la santé cardiométabolique à 45 ans, en s'appuyant "
  "sur la montre Garmin 265, les pédales de puissance Favero Assioma, une balance, un mètre ruban, un "
  "tensiomètre et une approche probabiliste.")

P("1. Semainier de l'Athlète Hybride", h2)
P("<b>Toute l'année :</b> 5 séances, ≈ 5h05 par semaine, plus un 4×4 VO2max environ une semaine sur deux, au rythme fixé par la charge "
  "« aérobie intense » (voir jeudi soir). Un seul 4×4 par semaine, jamais la veille ni le lendemain du CrossFit. L'intensité se pilote par "
  "la répartition de la charge Garmin sur 4 semaines, pas par un décompte des séances intenses : le CrossFit, mal mesuré au poignet, le fausse.")
B("<b>Lundi soir – Home Gym (Séance A) :</b> pectoraux, dos et unique créneau quadriceps de la semaine (Bulgarian split squat). "
  "21 séries en supersets (blocs de 4 et 6 tours), ≈ 40 min. Pas de sauts : le CrossFit du mardi en contient déjà. Détail ci-dessous.")
B("<b>Mardi soir – CrossFit (ancre haute intensité) :</b> WOD métabolique, 4 séances par mois. "
  "Veto sur les mouvements balistiques d'épaule lourds (kipping, snatch) par prudence individuelle. "
  "<b>5e mardi du mois (sans CrossFit) :</b> 4×4 VO2max à la place ; cette semaine-là, pas de 4×4 le jeudi.")
B("<b>Mercredi – Repos actif :</b> marche de 30–60 min et mobilité légère, sans intensité. "
  "Récupération après le WOD et stabilisation de la VFC nocturne.")
B("<b>Jeudi midi – Piscine :</b> 45 min en Zone 2 (cardio porté, décharge articulaire). "
  "Zones FC abaissées d'environ 10 bpm par rapport au vélo (la FC est plus basse dans l'eau). "
  "Les semaines de 4×4 : nage courte et facile de 30 min, en récupération pure.")
B("<b>Jeudi soir – 4×4 VO2max (≈ 40 min) :</b> échauffement 10–15 min, 4 × 4 min à 90–95 % FCmax "
  "(≈ 106–120 % FTP), 3 min de récupération active entre chaque, retour au calme 5–10 min. Finir 1–2 h avant le coucher.")
BB("<b>Quand :</b> selon la charge « aérobie intense » de Garmin sur 4 semaines, comparée à la cible de l'onglet Réglages du carnet. "
   "Sous la cible → 4×4 au prochain créneau (jeudi soir ou 5e mardi), même une semaine où il n'était pas prévu, si aucun signal n'est levé ; "
   "dans la cible → une semaine sur deux (semaines ISO de l'onglet Réglages) ; au-dessus → remplacé par 45 min en Zone 2. "
   "L'indicateur couvre 4 semaines glissantes : il remonte lentement, ce n'est pas une raison d'enchaîner les 4×4.")
BB("<b>Hiver (novembre–mars) :</b> home trainer, piloté en watts, avec un ventilateur puissant.")
BB("<b>Été (avril–octobre) :</b> côte régulière d'au moins 4 min en extérieur, en soirée (jour jusqu'à 21h–21h30 de mai à août), "
   "pour éviter la chaleur du home trainer.")
B("<b>Vendredi soir – Home Gym (Séance B) :</b> épaules (V-taper), dos, pectoraux, bras et ischios. 21 séries en supersets, ≈ 40 min. "
  "Zéro charge sur les quadriceps avant le week-end. Détail ci-dessous.")
B("<b>Samedi – Repos / Mobilité.</b>")
B("<b>Dimanche matin – Vélo route (2h00), 100 % Zone 2 :</b> IF ≈ 0,60–0,65. Sortie identique chaque semaine, "
  "donc Efficiency Factor et découplage comparables d'un dimanche à l'autre.")
BB("<b>Dimanche dégradé :</b> pluie mais envie d'aérobie → 40–45 min de home trainer en Zone 2 (55–62 % du FTP, soit ≈ 140–160 W) ; "
   "envie de plein air mais pas de route → VTT ou footing souple de 35 min en Zone 2 ; fatigue ou démotivation → repos, sans culpabilité "
   "(et pas de recharge glucidique).")
B("<b>Quotidien :</b> objectif de 7 000–8 000 pas. Repère OMS 2020 : 150–300 min d'activité modérée ou 75–150 min d'activité intense par semaine, "
  "plus du renforcement musculaire au moins 2 jours par semaine (couvert par le semainier).")
P("<b>Repère de volume :</b> ≈ 10 séries par groupe musculaire et par semaine, CrossFit compris. "
  "En cas d'alerte VFC, le 4×4 est la première séance à supprimer (rester en Zone 2).")

h3 = ParagraphStyle("h3", fontName="DVB", fontSize=10.5, leading=13, textColor=ACC, spaceBefore=8, spaceAfter=4)
def seance(titre, lignes):
    blk = [Paragraph(titre, h3)]
    hd = ["#", "Exercice & matériel", "Rôle & consignes clés", "Volume & RIR"]
    dt = [[Paragraph(h, cellb) for h in hd]] + [[Paragraph(c, cell) for c in r] for r in lignes]
    tb = Table(dt, colWidths=[0.8*cm, 5.0*cm, 8.0*cm, 3.6*cm], repeatRows=1)
    tb.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), ACC), ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#BBBBBB")),
        ("VALIGN", (0,0), (-1,-1), "TOP"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F4F7F8")]),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3)]))
    blk.append(tb); S.append(KeepTogether(blk))

seance("Séance A – lundi soir (21 séries, ≈ 40 min)", [
 ["1A", "Développé incliné à 30° aux haltères réglables (banc à 30°)", "Haut des pectoraux. Prise semi-neutre, coudes à ≈ 30° du buste.", "4 × 8–10 (RIR 1–2)"],
 ["1B", "Tractions neutres (barre fixe)", "Grand dorsal et épaisseur du dos. Amplitude complète, sans balancier. À 4 × 8, ajouter du lest.", "4 × 5–8 (RIR 1–2)"],
 ["–", "Pull-apart à l'élastique (pendant les récupérations du bloc 1)", "Santé scapulaire et posture. Se fait pendant les récupérations, sans allonger la séance.", "4 × 15"],
 ["2A", "Bulgarian split squat (pied arrière sur le banc, une main à la barre fixe)", "Unique créneau quadriceps et fessiers. 6 tours en alternant les jambes. Départ à 24 kg dans la main libre, puis haltère réglable de plus en plus lourd. Genou avant aligné sur le pied ; arrêt en cas de douleur au genou.", "3 × 8–12 / jambe (RIR 1–2)"],
 ["2B", "Relevés de genoux suspendu (barre fixe)", "Anti-extension et caisson abdominal. Rétroversion du bassin, sans balancier. Enchaîné avec chaque série de 2A.", "6 × 5–8"],
])
seance("Séance B – vendredi soir (21 séries, ≈ 40 min)", [
 ["1A", "Élévations latérales à la poulie basse (poignée simple)", "Largeur d'épaules (V-taper). Buste incliné à 15°, bras à 30° vers l'avant dans le plan scapulaire. Tension continue, sans à-coup sur l'épaule droite.", "3 × 12–15 (RIR 1–2)"],
 ["1B", "B-Stance RDL aux 2 haltères réglables", "Ischios et fessiers sans les lombaires. Jambe arrière en simple appui, descente en 3 s. Progression de 2 × 16 kg vers 2 × 29 kg.", "3 × 8–12 / jambe (RIR 1–2)"],
 ["2", "Leg curl debout à la poulie basse (sangle de cheville)", "Ischios en flexion du genou, complément du RDL. Cuisse immobile, retour en 3 s. Même hauteur de poulie que 1A.", "2 × 10–15 / jambe (RIR 1–2)"],
 ["3A", "Lat prayer bilatéral à la poulie haute (barre ou corde)", "Grand dorsal sans les coudes. Bras quasi tendus (coudes fléchis à 10°, verrouillés). Si l'épitrochlée se plaint, passer à la corde (prise neutre).", "3 × 10–12 (RIR 1–2)"],
 ["3B", "Pompes lestées (sac à dos chargé de disques)", "Pectoraux. Corps gainé, coudes à ≈ 45°. Progression : sac plus lourd, puis pompes aux anneaux.", "3 × 8–15 (RIR 1–2)"],
 ["4A", "Triceps pushdown à la corde (poulie haute)", "Coudes serrés près du buste, écarter la corde en bas.", "2 × 10–12 (RIR 1)"],
 ["4B", "Curl marteau aux haltères de 8 kg", "Brachial antérieur, prise neutre. Zéro supination pour ménager les tendons des avant-bras.", "2 × 10–12 (RIR 1)"],
 ["5", "Rowing aux anneaux (poulie décrochée)", "Épaisseur du dos. Corps gainé, tirer les anneaux vers les côtes. Plus les pieds avancent, plus c'est dur.", "3 × 8–12 (RIR 1–2)"],
])
P("<b>Organisation :</b> les exercices A et B d'un même bloc s'enchaînent en superset (≈ 60–90 s de récupération après le B). "
  "Préparer les charges des haltères avant la séance. Ordre de la séance B pensé pour ne régler la poulie que deux fois (basse, puis haute), puis passer aux anneaux.")
P("<b>Progression (double progression) :</b> quand toutes les séries atteignent le haut de la fourchette avec un RIR de 2 ou plus, "
  "ajouter 1–2 kg par haltère ou passer à la variante plus dure. Charge de départ : celle qui laisse 1–2 reps en réserve en bas de la fourchette.")

P("2. Indicateurs de Performance & Efficacité Mécanique", h2)
B("<b>FTP (Watts/kg) :</b> juge de paix de la cylindrée aérobie (Favero Assioma), rapportée au poids moyen sur 15 jours. Test tous les 2–3 mois.")
B("<b>Efficiency Factor (Watts/FC) et découplage Pa:FC :</b> rapport puissance/FC en Zone 2, comparable uniquement "
  "à conditions similaires (même parcours, même durée, température proche). Compléter par le découplage Pa:FC "
  "sur la partie Zone 2 : cible &lt; 5 %.")
B("<b>VO2max :</b> estimation Garmin, à lire en tendance et non en valeur absolue. C'est l'un des plus forts prédicteurs de longévité.")
B("<b>TSS & IF :</b> quantification de la charge cycliste.")
B("<b>Modèle d'endurance :</b> vélo très majoritairement en Zone 2, avec un 4×4 environ toutes les deux semaines, ajusté selon la charge « aérobie intense » (modèle polarisé). "
  "Avec 2 h de vélo par semaine, le facteur limitant est le volume total plus que la répartition des intensités.")
B("<b>Course à pied (note pour plus tard) :</b> non pratiquée actuellement. En cas de reprise : 3–4 semaines de "
  "footings faciles avant toute intensité, et aucune sortie dépassant de plus de 10 % la plus longue des 30 derniers jours.")

P("3. Système Nerveux Autonome & Approche Probabiliste (Garmin 265)", h2)
B("<b>Statut VFC (rMSSD nocturne) :</b> moyenne glissante sur 7 jours par rapport au corridor de référence (3–4 semaines).")
B("<b>FC de repos :</b> moyenne sur 7 jours comparée à la moyenne sur 28 jours. Un écart de +3 bpm ou plus qui dure est un signal de fatigue "
  "(ou de maladie débutante), à croiser avec la VFC et le ressenti.")
B("<b>Approche probabiliste :</b> la physiologie n'est pas binaire. Une sortie de corridor sur plus de 3 jours est une "
  "alerte de gradient invitant à écouter ses sensations et le RPE, et non un ordre d'arrêt rigide.")

P("4. Charge d'Entraînement, Intégrité Articulaire & Home Gym", h2)
B("<b>Concurrence force/endurance :</b> les méta-analyses récentes montrent que l'endurance ne compromet ni l'hypertrophie "
  "ni la force maximale ; seule la puissance explosive peut être légèrement affectée. Espacer de plus de 3 h, ou placer "
  "sur des jours différents, force et endurance intense.")
B("<b>Suivi Home Gym (surcharge progressive & RIR) :</b> consigner les mouvements phares au format "
  "Poids × Séries × Reps @RIR. Viser 1–2 RIR.")
B("<b>Charge d'entraînement :</b> pour le cardio, rapport charge aiguë / charge chronique calculé par Garmin (basé sur la FC) : "
  "repère 0,8–1,3, au-delà de 1,3 c'est un signal, qui ne suffit jamais seul à imposer le repos. Pour la musculation et le CrossFit, "
  "où la FC au poignet sous-estime l'effort : charge session-RPE = RPE de la séance × durée en minutes (bilan du soir).")
B("<b>Répartition de la charge sur 4 semaines (Garmin) :</b> aérobie intense comparée à la cible de l'onglet Réglages (elle pilote le 4×4) ; "
  "anaérobie comparée au plafond de l'onglet Réglages ; aérobie léger : seul le minimum compte. Les cibles par défaut de Garmin, calibrées "
  "pour un programme d'endurance plus intense, ne sont pas utilisées. Les calories estimées par Garmin ne sont pas utilisées (erreur de 20 à 40 %).")

P("5. Anthropométrie, Santé Métabolique & Nutrition Empirique", h2)
B("<b>Ratio Tour de Taille / Taille (WHtR), mesure tous les 5 jours, moyenne sur 15 jours, repères NICE 2022 :</b> &lt; 0,50 sain ; 0,50–0,59 risque modérément accru ; "
  "≥ 0,60 risque élevé. Avec 176 cm, le seuil de 0,50 correspond à un tour de taille de 88 cm.")
B("<b>Masse grasse (formule US Navy : taille, tour de taille, tour de cou à remesurer tous les 2 mois) :</b> repères de Gallagher (2000), dérivés des seuils d'IMC de l'OMS, "
  "pour les hommes de 40–59 ans : 11–21 % sain ; 22–27 % surpoids ; ≥ 28 % obésité. Précision d'environ ±3–4 points : à suivre en tendance.")
B("<b>Poids moyen sur 15 jours (une pesée tous les 5 jours) :</b> lissage des fluctuations (eau, glycogène, sel) pour piloter le rapport Watts/kg. "
  "La créatine ajoute 1–2 kg d'eau : pour la composition corporelle, le tour de taille fait foi.")
B("<b>Phase actuelle : consolidation métabolique.</b> Objectif de perte de graisse atteint ; fin du déficit. "
  "Maintien autour de 84–85 kg et 88 cm de tour de taille (≈ 2 500 kcal/j, sans comptage).")
B("<b>Pilotage nutritionnel visuel (3 repas, sans collation, protéines 140–160 g/j) :</b>")
BB("<b>Assiette pivot :</b> petit-déjeuner [ 2 paumes P – 1 poing de fruit – 1 poing G ] ; déjeuner et dîner "
   "[ 2 paumes P – 2 poings V – 1 poing G ]. Soit ≈ 30–40 g de protéines par repas, pour atteindre le seuil de ≈ 2,5–3 g de leucine.")
BB("<b>Thermostat du poids :</b> si le poids moyen sur 15 jours passe sous 83,5 kg, déjeuner en [ 2 – 2 – 2 ].")
BB("<b>Thermostat glucidique (dimanche vélo 2 h) :</b> recharge [ 2P – 2V – 2G ] au dîner de la veille et au déjeuner qui suit la sortie. Pendant la sortie : eau + électrolytes "
   "en Zone 2 jusqu'à ≈ 2h15 ; 30–60 g de glucides/h seulement au-delà de 2h30 ou par forte chaleur. "
   "Règle miroir : si la sortie saute, retour au pivot 2-2-1.")
B("<b>Créatine monohydrate (optionnel) :</b> 3–5 g/j, le complément le mieux étayé (masse et force musculaires, os). "
  "Pause de 1–2 semaines avant chaque prise de sang (elle élève la créatinine et fausse l'estimation de la fonction rénale), ou prévenir le médecin.")

P("6. L'Angle Mort : Tension Artérielle, Sommeil, Biologie & Charge Mentale", h2)
B("<b>Tension artérielle (tensiomètre huméral) :</b> règle des 3 (3 mesures matin et soir pendant 3 jours, 2 à 4 fois par an). "
  "Cible : &lt; 120/70 mmHg (ESC 2024). Alerte à domicile : ≥ 135/85 mmHg.")
B("<b>Sommeil :</b> 7–9 h par nuit (National Sleep Foundation, 26–64 ans ; AASM : au moins 7 h), avec des horaires réguliers (±30 min).")
B("<b>Bilan biologique annuel :</b> bilan lipidique avec ApoB (cible selon le risque global, ESC/EAS) ; HbA1c (&lt; 5,7 % normal, "
  "5,7–6,4 % prédiabète, ≥ 6,5 % diabète, ADA/OMS) ; ferritine. Lp(a) une fois dans la vie (&gt; 50 mg/dL soit ≈ 105 nmol/L : risque accru, EAS 2022).")
B("<b>Avis cardiologique :</b> recommandé avant d'introduire le 4×4 régulier ; épreuve d'effort selon l'avis médical.")
B("<b>Charge mentale :</b> auto-évaluation quotidienne (1 à 5). En cas de stress psychosocial élevé, la VFC réagit comme "
  "un surentraînement : adapter (scaling) la séance.")

P("7. Matériel disponible (home gym)", h2)
P("Barre de traction fixe (prise neutre) ; banc inclinable (30°, 45°, 80°) ; 2 barres d'haltères filetées de 2 kg + 54 kg de fonte "
  "(8 × 5 kg, 4 × 2 kg, 8 × 1 kg), soit jusqu'à ≈ 29 kg par haltère ; kettlebell de 24 kg ; 2 kettlebells de 16 kg ; 2 haltères fixes de 8 kg ; "
  "4 poulies avec câbles et supports de lest, sangle de cheville ; anneaux de gymnastique ; élastiques ; corde à sauter. "
  "Cardio : vélo route Specialized Roubaix avec pédales Favero Assioma, VTT, VAE, home trainer ; montre Garmin Forerunner 265.")

P("<b>Outils de suivi :</b> carnet du coach (saisie sur téléphone) : claude.ai/artifact/WAux9mehWeAnC7DU3vJ65e ; "
  "saisies stockées dans la feuille Google « Coach – Carnet » de ton Drive ; script Garmin + météo (coach_snapshot.md) sur le Raspberry Pi.")

P("Tableau Récapitulatif Hiérarchisé", h2)
hdr = ["Niveau & priorité", "Indicateur clé", "Outil & fréquence", "Cible optimale", "Signal d'alerte / action"]
rows = [
 ["N1 Santé & SNA", "FC de repos (7 j / 28 j)", "Garmin 265 (nocturne)", "Écart < +3 bpm", "≥ +3 bpm durable → signal de fatigue"],
 ["N1 Santé & SNA", "Statut VFC (rMSSD 7 j)", "Garmin 265 (nocturne)", "Dans le corridor 3 sem.", "Sortie > 3 j → alerte de gradient, écoute des sensations"],
 ["N1 Santé & SNA", "Charge mentale", "Auto-évaluation (quotidien)", "Maîtrisée / flux stable", "Stress chronique ou RPE dissocié → scaling"],
 ["N1 Santé", "Sommeil", "Garmin + ressenti (quotidien)", "7–9 h (NSF), horaires ±30 min", "Dette répétée → alléger la semaine"],
 ["N1 Sécurité", "Tension artérielle", "Tensiomètre (2–4×/an)", "< 120/70 mmHg (ESC 2024)", "≥ 135/85 à domicile → avis médical"],
 ["N1 Sécurité", "Bilan biologique", "Prise de sang (1×/an)", "HbA1c < 5,7 % (ADA) ; Lp(a) < 50 mg/dL (EAS)", "Valeur hors norme → avis médical"],
 ["N2 Métabolisme", "Poids moyen (15 j)", "Balance → Garmin (1 pesée / 5 j)", "Stable (maintien)", "Variation > 0,8 %/sem."],
 ["N2 Métabolisme", "Ratio WHtR", "Mètre ruban (1×/5 j, moyenne 15 j)", "< 0,50 (NICE 2022)", "0,50–0,59 accru ; ≥ 0,60 élevé"],
 ["N2 Métabolisme", "Masse grasse (US Navy)", "Taille (1×/5 j) + cou (1×/2 mois)", "11–21 % (H 40–59 ans)", "22–27 % surpoids ; ≥ 28 % obésité"],
 ["N2 Activité", "Pas quotidiens", "Garmin (quotidien)", "7 000–8 000 ; OMS : 150–300 min/sem.", "Baisse durable"],
 ["N2 Nutrition", "Portions de main", "Visuel (3 repas)", "[2P-2V-1G] ou [2P-2V-2G]", "Dérive pondérale ou baisse des watts"],
 ["N3 Mécanique & force", "Surcharge home gym", "Carnet + Garmin", "1–2 RIR, 40 min par séance", "Stagnation, douleurs tendineuses, fatigue"],
 ["N3 Charge", "Cardio : aiguë / chronique Garmin ; muscu et CrossFit : RPE × durée", "Garmin + bilan du soir", "Rapport 0,8–1,3", "> 1,3 → signal (jamais seul pour imposer le repos)"],
 ["N4 Performance", "VO2max ; aérobie intense 4 sem.", "Garmin (tendance)", "Aérobie intense dans la cible (Réglages)", "Sous la cible → 4×4 au prochain créneau ; baisse durable du VO2max"],
 ["N4 Performance", "FTP & découplage", "Assioma + Garmin (FTP 2–3 mois)", "Progression, découplage < 5 %", "Baisse inexpliquée des W/kg"],
]
data = [[Paragraph(h, cellb) for h in hdr]] + [[Paragraph(c, cell) for c in r] for r in rows]
t = Table(data, colWidths=[2.8*cm, 3.2*cm, 3.4*cm, 3.6*cm, 4.6*cm], repeatRows=1)
t.setStyle(TableStyle([
 ("BACKGROUND", (0,0), (-1,0), ACC),
 ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#BBBBBB")),
 ("VALIGN", (0,0), (-1,-1), "TOP"),
 ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F4F7F8")]),
 ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
]))
S.append(t)



def footer(c, d):
    c.saveState(); c.setFont("DV", 7.5); c.setFillColor(colors.grey)
    c.drawString(2*cm, 1.2*cm, "Synthèse Intégrale v2.3 – octobre 2026 – ne remplace pas un avis médical")
    c.drawRightString(A4[0]-2*cm, 1.2*cm, str(d.page)); c.restoreState()

doc = SimpleDocTemplate("Synthese_Integrale_v2-3.pdf", pagesize=A4, leftMargin=1.8*cm, rightMargin=1.8*cm,
                        topMargin=1.6*cm, bottomMargin=1.8*cm, title="Synthèse Intégrale v2.3")
doc.build(S, onFirstPage=footer, onLaterPages=footer)
