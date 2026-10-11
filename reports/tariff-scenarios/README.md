# TCC — Inventaire global des formats tarifaires et pilote de calcul France

**Accès permanent aux résultats publiés par le workflow GitHub** `global-tariff-scenario-review.yml`.

## Fichiers

- **[review-latest.json](review-latest.json)** : résumé consolidé, neuf pays, familles de tarifs, défaillances, versions du moteur, contrôles et empreintes des rapports.
- **[global-inventory-latest.json](global-inventory-latest.json)** : couverture des sources par pays, décompte des documents parcourus, limites déclarées, familles tarifaires.
- **[source-shapes-latest.json](source-shapes-latest.json)** : chaque fichier source inspecté, pays, étape de publication, champs/structures, familles et indicateur d'échantillonnage ; les données trop grandes ou illisibles restent listées comme telles.
- **[france-pricing-pilot-latest.json](france-pricing-pilot-latest.json)** : résultats des **17 cas déterministes**, des échantillons d'offres Electra/Electroverse publiées et des offres V9 CPO directes / abonnements, erreurs, manque de contexte et champs possiblement ignorés.
- **[france-real-offer-fixtures.json](france-real-offer-fixtures.json)** : offres eMSP françaises réelles et inchangées servant à reproduire le test (échantillon par structure).
- **[france-runtime-offer-fixtures.json](france-runtime-offer-fixtures.json)** : échantillons d'offres **CPO directs et abonnements** du runtime V9 épinglé et du Data Lab, sans identifiants EVSE massifs inutiles au calcul.
- **[france-runtime-offers-inventory.json](france-runtime-offers-inventory.json)** : nombre des offres compilées directes et abonnements par source.
- **[history.jsonl](history.jsonl)** et **[snapshots/](snapshots/)** : archivage daté après chaque exécution validée. Versions intégrales récupérables dans l'historique Git.

## Règles de lecture

Ce rapport est un **inventaire des scénarios et des formes de prix** sur les pays `FR, CH, IT, DE, ES, NL, UK, MA, BE`. Il ne prouve pas que toutes les bornes ont un tarif public, ni qu'une simulation est exacte dans toutes les situations.

- Distinguer **CPO direct/ad-hoc**, **eMSP** et **abonnements**.
- Les catalogues `candidate`, `staging`, données brutes, observations non validées et archives techniques sont **décrits**, pas admis dans la tarification V9.
- Le test réel français porte sur un **échantillon** d'offres source, dans **un scénario de session explicitement indiqué** ; il ne constitue pas un test exhaustif de tous les horaires, puissances et profils.
- `computed_with_unmodeled_source_fields` signifie que le moteur a produit un montant **sans preuve qu'il applique toutes les composantes de la source** : ne pas afficher ce tarif comme définitivement validé.
- Le moteur V9 existant est testé **sans le modifier**, épinglé à une version immuable pour comparer les futures corrections.
- Un EVSE hors service n'est pas réactivé par un prix présent ; l'identité et les états actifs restent gérés par la [SOP IRVE figée](../../docs/france-irve-tariff-coverage-frozen-sop-v1.md).

**Déploiement prévu :** pilote France, puis CH/IT, UK/NL/ES, DE/MA/BE après validation des cas par pays. Aucune modification du moteur de prix production dans cette étape.

## Mise au point — moteur V9 courant (11/10/2026)

- **L'audit initial des 84 offres** utilisait des fixtures historiques épinglées au 9–10 octobre ; il ne démontre pas que les mêmes champs sont encore manquants en production.
- Le moteur courant a passé les 9 tests de frais différés et plafonds ; [audit du moteur courant](current-v9-after-minutes-audit-2026-10-11.json).
- Les **6 offres** Plug Inn direct, SIGEIF direct (3) et Charge Pass Basic/Intense contiennent maintenant `afterMinutesComponent: CONNECTED_TIME` dans les catalogues stables réels. SIGEIF 7/22 kW définit `afterMinutesCapMode: night_window_local_per_night`. **21/21 tests** passés sur les fichiers réellement publiés : [rapport](current-v9-after-minutes-official-six-2026-10-11.json).
- Les **78 offres Electra eMSP de l'échantillon historique** n'ont toujours pas de dimension de facturation justifiée. Regroupement par familles et PK dans [l'inventaire](electra-emsp-afterminutes-78-unresolved-2026-10-11.json). Ne pas appliquer les conditions du CPO direct à Electra eMSP.
- Sans preuve indiquant si le temps est CONNECTED_TIME / TIME / PARKING_TIME, conserver le résultat **tarif incalculable** ; ne pas ignorer les frais ni annoncer la correction de 78 offres.
- Vérification de la **couverture du dernier overlay Electra** nécessaire après chaque actualisation ; les 78 sont un inventaire de test et non un total national actuel.
