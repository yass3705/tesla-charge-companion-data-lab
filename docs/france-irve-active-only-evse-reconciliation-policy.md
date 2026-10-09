# France IRVE — filtre de vérification EVSE actifs (2026-10-09)

**Règle impérative : filtrer au niveau EVSE, jamais à l'échelle de la station.**

- `en_service` dans la source dynamique IRVE: EVSE éligible à la vérification/mise en correspondance.
- `hors_service`, `inconnu`, ou EVSE **absent** du flux dynamique: EVSE exclu de la **file de vérification prioritaire**; ne jamais supposer `en_service` par absence de négatif.
- Une station est **éligible** dès qu'au moins **un EVSE** du jeu national IRVE est explicitement `en_service`.
- Si aucun EVSE n'est explicitement `en_service`, la station n'entre pas dans l'audit actif, même si elle reste présente dans la base statique historique.
- Aucun EVSE ni station n'est physiquement supprimé des archives sources; les statuts peuvent changer quotidiennement.
- Refuser le filtrage actif si le snapshot IRVE dynamique manque, a plus de 72 heures, ou ne contient pas `enServicePdcIds`. Les statuts manquants sont des informations **non vérifiées**, et non des faits `hors_service`.
- Comparaison géographique de stations: distance <=10 m; EVSE counts identiques; tolérance de puissance AC max(2 kW,10 %), DC max(15 kW,10 %). Une correspondance GPS n'est pas une preuve d'identité définitive; vérifier CPO et adresse avant publication.
- Electra eMSP et Electroverse sont distincts d'Electra CPO. Tarification toujours liée à l'EVSE.

**Preuves et artefacts :**
- Collecteur: `scripts/france/build_france_irve_dynamic_status_v9.py` enregistre désormais `enServicePdcIds` (chaque PDC explicitement actif) en complément des `records` négatifs.
- Audit reproductible: `scripts/france/audit_active_irve_station_matches.py`.
- Dernière vérification au 2026-10-09 18:01 UTC: 94 586 EVSE en_service; 8 728 hors_service; 2 937 inconnu; 64 329 sans donnée dynamique; 26 490 stations avec au moins un EVSE en_service.
- Audit 5/10/15m en branche `audit/stations-irve-emsp-20261009`, [run 37970438638](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/37970438638).
- Ces règles concernent le **chantier de rapprochement / audit** ; l'intégration dans l'affichage V9 requiert une promotion dédiée.
