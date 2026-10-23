---
description: Prépare un essai sur le vélo puis analyse le journal de séance
argument-hint: [options de openride-dev.sh, ex. --gear 6]
---

Aide Laurent à faire un essai réel sur le JetBlack Victory avec le Zwift Click.

**Avant l'essai :**
1. Vérifie que `main` est à jour et que les tests du core passent (`cd core && pytest -q`).
2. Donne-lui la commande à copier, depuis `Open_ride_linux/` :
   `scripts/openride-dev.sh --trainer ftms --input click --autostart $ARGUMENTS`
3. Rappelle-lui :
   - de réveiller le Victory en pédalant ;
   - que Zwift et le téléphone doivent être déconnectés ;
   - si le Click ne répond pas : `bluetoothctl disconnect F4:C4:59:15:E1:E7`, puis appuyer sur un bouton.

**Après l'essai** (fenêtre fermée ou Ctrl+C), analyse `~/run_victory.log` (avec `python -m openride_core.tools.log_report ~/run_victory.log --json` depuis `core/`) :
- connexions, déconnexions et reconnexions du trainer et du Click, avec leurs heures ;
- pauses (`PAUSED`) et leur raison ;
- lignes `Perf`, comparées aux seuils de la SRS §14.1 (pas p99 > 5 ms, retard p99 > 20 ms, CPU > 15 % ; seuil atteint après trois relevés consécutifs) ;
- appuis du Click reconnus, et FIT produit (`~/OpenRide/Activities/`).

Résume en français, en 5 à 10 lignes : ce qui marche, ce qui ne marche pas, la cause probable, et la prochaine action. Note les faits nouveaux sur le matériel dans `docs/spikes.md` ou `docs/SUIVI_AVANCEMENT.md` (section « Ce qui reste à tester »).
