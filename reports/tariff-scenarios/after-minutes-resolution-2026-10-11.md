# TCC V9 — correction des frais différés et plafonds (11/10/2026)

## Résultat de l'audit initial

L'audit mondial [review-latest.json](review-latest.json) épinglait une ancienne version du moteur : `38ac26e029ba1c4779d4d8fa43e7d5d300858624` et signalait 84 offres potentiellement sous-calculées (78 Electra eMSP + 6 CPO/abonnements). Cette statistique historique n'est **pas** un diagnostic de la nouvelle version de production.

La version récente du moteur refusait déjà une majoration positive `afterMinutesRate` sans type de durée prouvé (`after_minutes_component_unverified`). La présente correction permet le calcul exact des six offres dont la source officielle fournit cette sémantique.

## Correction promue en production

Dépôt `tesla-charge-companion-stable`, [PR #142](https://github.com/yass3705/tesla-charge-companion-stable/pull/142), fusion `6608e7ff59407813e6bc5ec772003b3456f7948e`.

- **Plug Inn direct, Charge Pass Basic et Intense (3 offres)** : facturation du **temps connecté** au-delà de 60 minutes, 0,30 €/min.
- **SIGEIF 24 kW (1)** : temps connecté au-delà de 120 min, 0,20 €/min.
- **SIGEIF 50–100 kW (1)** : temps connecté au-delà de 60 min, 0,30 €/min.
- **SIGEIF 7–22 kW (1)** : temps connecté au-delà de 180 min, 0,05 €/min ; plafonnement de la **portion nocturne 20 h–8 h à 4 € par nuit**, avec découpage des sessions jour/nuit.
- Facturation `CONNECTED_TIME` explicitement distincte de `TIME` (recharge active) et `PARKING_TIME` (après la recharge).
- Plafonds nocturnes non documentés, sémantique absente, devise non EUR, heure ou fuseau requis manquants : **calcul incalculable / incomplet**, jamais zéro implicite. Le moteur conserve le calcul de minimum de session après les composantes.

## Tests

- [Run initial 38096083623](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38096083623) : 56/56.
- [Run garde-fous 38096184094](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38096184094) : 58/58.
- [Run exhaustif 38096306582](https://github.com/yass3705/tesla-charge-companion-data-lab/actions/runs/38096306582) : **130/130**, dont les 78 offres Electra une par une.
- Régression historique de **17/17** scénarios de prix validée sur le moteur corrigé.
- [Rapport de validation détaillé](after-minutes-staging-validation-2026-10-11.json).

## Reliquat Electra eMSP — 78 cas / 7 profils

**Aucun des 78 tarifs n'a été inventé** : lorsque la durée taxable n'est pas précisée, le moteur renvoie `after_minutes_component_unverified` ; ils devront s'afficher « Tarif incalculable ».

| Frais €/min | Déclenchement min | EVSE échantillonnés |
|---:|---:|---:|
| 0,033333 | 300 | 10 |
| 0,012 | 121 | 27 |
| 0,010 | 180 | 16 |
| 0,050 | 121 | 4 |
| 0,133333 | 240 | 2 |
| 0,110667 | 31 | 3 |
| 0,100 | 181 | 16 |
| **Total** | | **78** |

La prochaine étape consiste à obtenir la preuve du **type de temps facturé** (temps connecté, recharge active ou post-charge) et de son **point de départ** pour chacun des sept profils ; ne pas extrapoler une règle CPO directe à la plateforme eMSP.

## Portée

Les tests valident le moteur et les catalogues concernés. Ils ne valident pas automatiquement la disponibilité des EVSE, les identités IRVE, les tarifs des CPO d'autres pays ni l'interface d'affichage des résultats incomplets. La publication Pages doit être vérifiée séparément.
