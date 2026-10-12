# TCC V9 — Rebaseline tarifaire neuf pays avant audit EVSE exhaustif

Date de préparation : 12 octobre 2026. **État : audit documentaire reproductible en lecture seule, PAS inventaire actuel des EVSE et PAS publication V9.**

## Références et portée

Cette étape fige les preuves datées des rapports existants afin de ne pas confondre fichier source, connecteur, offre eMSP et scénario calculé. Commande de recalcul : `python scripts/v9_tariff_gap_baseline_20261012.py` ; contrôles : `python scripts/v9_tariff_gap_baseline_20261012.py --check` et `python -m unittest discover -s tests -p 'test_v9_tariff_gap_baseline_20261012.py'`.

- Rapports sources : `reports/tariff-scenarios/review-latest.json` (revu le 10/10, run 38047584760), `reports/netherlands/nl-cpo-unpriced-evse-inventory-2026-10-11.json` (snapshot 10/10) et `reports/tariff-scenarios/after-minutes-production-verification-2026-10-11.json`.
- Inventaire mondial daté : **1 312 fichiers recensés, 1 306 analysés, six non analysés**, et **1 179 stations Tesla déclarées dans la source utilisée par l'audit historique**. Ni le décompte de fichiers ni celui des stations Tesla ne prouve le nombre d'EVSE tarifés, actifs ou accessibles.
- Fichiers sources classés par pays dans ce rapport historique : FR **740**, IT **12**, CH **142**, DE **6**, ES **12**, NL **48**, UK **61**, MA **227**, BE **28**. La classification n'est pas un décompte de bornes et n'est pas nécessairement une partition sans recouvrement. L'audit devra ensuite couvrir les sous-répertoires non attribués et les sources non analysées.
- Les neuf pays sont présents, mais la profondeur et la fraîcheur des fichiers ne sont pas comparables. **Aucune couverture tarifaire nationale intégrale n'est déduite de ces chiffres.**

## Pays-Bas : revoir l'ancienne cible « 5 246 »

Le rapport du 11 octobre portant **exclusivement sur quatre CPO** compte :

| CPO | Connecteurs sans tarif direct | Parmi eux AVAILABLE ou CHARGING |
| --- | ---: | ---: |
| Laadnet (LNT) | 504 | 438 |
| Agri Go Charge (AGO) | 2 578 | 2 375 |
| StellaPower (SPA) | 0 | 0 |
| WattHub (WAT) | 124 | 63 |
| **Total de ce sous-ensemble** | **3 206** | **2 876** |

Ce ne sont **pas** 3 206 scénarios « incalculables » : la plupart sont **sans référence tarifaire nationale directe**, ce qui correspond à « prix non disponible ». Il reste impérativement à vérifier **sur un nouveau snapshot DOT-NL**, au niveau EVSE/connecteur : prises Type 2 et CCS seulement, statut disponible ou occupé, accès effectivement public et composants tarifaires applicables. Les 5 246 cas annoncés antérieurement concernent une autre population et doivent être **recalculés**, sans soustraire ni additionner ces chiffres entre eux.

DOT-NL prime sur les tarifs directs lorsque la référence appartient au CPO de la borne et est cohérente. Les tarifs eMSP restent dans des canaux indépendants. La règle vaut pour tous les CPO, y compris Agri Go, et ne justifie pas de vérifier chaque prix national existant dans une application tierce.

## France : frais différés

Sur les **84 offres réelles historiques** étudiées, **6** règles directes/abonnements disposent d'une preuve suffisante, et **78 offres Electra eMSP** n'ont pas de preuve sur la nature de la durée facturée (`CONNECTED_TIME`, `TIME` ou `PARKING_TIME`). Ces 78 ne doivent fournir **aucun total inventé** : « Tarif incalculable » tant que leur contrat propre n'est pas établi. Les preuves d'un tarif CPO direct ne se substituent pas aux conditions d'un eMSP tiers.

## Prochain audit calculatoire à produire (nouvelle passe, neuf pays)

Pour chaque pays, mesurer séparément, **sur les versions exactes courantes des sources et du moteur** : (a) EVSE accessibles au public et en service (disponibles ou occupés), (b) connecteurs Type 2 / CCS, (c) présence de tarif direct CPO, abonnement, Electra eMSP ou Electroverse eMSP, (d) motifs de prix indisponible, tarif ambigu ou tarif incalculable, (e) taux de scénarios effectivement calculables par famille énergie/minute/frais/horaires/paliers/plafonds/SOC80 et devise. Conserver la puissance et l'identité EVSE ; **ne jamais agréger les prix d'une station**.

Priorité : **NL** pour le recensement exhaustif et les 5 246 cas à requalifier ; puis **France Electra/Electroverse** (dont Lidl/Allego et 78 frais différés) ; enfin balayage neuf pays en conservant les sources Tesla, OCPI/PCPR, les fuseaux horaires et les spécificités MA. Utiliser les collectes courantes seulement après validation du statut de publication et de provenance.

**Aucun tarif, snapshot ou moteur n'est changé par ce dossier.** Les limites des anciennes mesures sont affichées, sans présenter ce pré-audit comme une solution exhaustive.
