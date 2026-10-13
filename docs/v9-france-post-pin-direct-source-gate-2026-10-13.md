# Collectes directes France postérieures au pin V9 — 13 octobre 2026

## Référence

Le candidat de développement Production `2026-10-13-fr-spie-neuilly-timewindow-candidate` épingle Data Lab `e39a4466096b520b3c459e75539bf9b112235165`. Son rapport de validation est dans Production `docs/v9-technical-tariff-readiness-2026-10-13.md`. Les collectes ci-dessous ont avancé après ce pin ; leur présence dans Data Lab ne les publie pas dans V9.

| Source récente | Faits observés dans Data Lab `e2518cad4` | Décision pour le candidat |
| --- | --- | --- |
| `data/national/bump_direct_inventory_france.json.gz` | 1 605 stations, 2 516 points, 0 prix explicite, 2 516 tarifs classés `missing` | Inventaire seulement ; aucune nouvelle offre directe calculable. Les offres BUMP déjà validées restent intactes. |
| `data/national/etotem_direct_stations_france.json.gz` | 641 stations, 3 350 points, 0 texte tarifaire et 0 prix kWh analysé | Inventaire seulement ; aucun prix direct nouveau. |
| `data/national/waat_monta_public_tariffs_france.json.gz` | 588 stations IRVE étudiées, 550 avec rapprochement Monta direct, 407 groupes directs, 0 erreur API ; **0/407 groupes avec EVSE explicite**, 0/588 station `rankableDirect`. Les 550 rapprochements portent `pricing_normalization_pending`, les 38 autres `no_current_direct_waat_monta_match`. | Aucun prix Monta promu. Le rapprochement géographique/de station ne suffit pas à attribuer un groupe à chaque EVSE ; les champs de prix et frais doivent aussi être normalisés intégralement. |
| `data/national/waat_direct_tariffs_qualicharge_france.json.gz` | 7 663 stations QualiCharge parcourues, 0 station et 0 EVSE WAAT retenus, 0 prix direct classable | Aucune offre supplémentaire. Vérifier l'identité fournisseur et le périmètre QualiCharge avant de relancer cette piste. |

Le fichier publié historique `data/publish/waat_direct_tariffs_tcc_france.json` est **identique au pin** : horodatage `2026-08-26T12:11:04.230559+00:00`, 571 stations, 452 stations et 507 configurations classables. Il ne doit pas être présenté comme une intégration de la collecte Monta ou QualiCharge du 13 octobre. Les prix des groupes Monta peuvent comporter des frais distincts (exemple : `reservation_per_min`) ; un simple montant `price_label` ou un montant par kWh ne prouve pas le coût total.

## Seuil de reprise

Pour WAAT, obtenir une relation officielle groupe tarifaire → EVSE ou une correspondance station/puissance univoque démontrée, puis interpréter les composantes publiques complètes et leurs conditions. Rejouer la chaîne source → EVSE → prix calculable sur un échantillon avant un pin. Pour BUMP et ETotem, obtenir un tarif direct consommateur applicable à l'EVSE ; une collecte d'inventaire sans prix n'autorise aucune offre. Aucun pin Production ni publication Pages/Cloudflare n'a été changé par cet audit.
