# Migration GitHub Actions updater-test → Data Lab — 2026-10-13

## Règle approuvée
Le dépôt historique `yass3705/tesla-stations-updater-test` doit conserver le processus Tesla/Mac distinct. La collecte CPO directe, les données nationales et les offres eMSP sont canoniques dans `yass3705/tesla-charge-companion-data-lab`. Supprimer les doublons **seulement après vérification fonctionnelle et de couverture**, et ne jamais arrêter une collecte sans remplacement établi. Ne pas mélanger les offres CPO et eMSP ; préserver ID EVSE exact, puissance, statuts et données validées.

## Audit initial et changements confirmés
- 92 fichiers de workflow recensés initialement dans updater-test ; 8 suppressions confirmées sur sa branche main ; 84 fichiers restant après action.
- Data Lab contient un catalogue nettement plus vaste (1000 entrées fournies par la première page d'API ; ce nombre n'est pas un inventaire exhaustif).
- Doublons supprimés : `electroverse-bootstrap-auto.yml`, `greenspot-france-extract.yml`, `gofast-audit.yml`, `swisscharge-full-collection.yml`, `switzerland-national-cpo-counts.yml`, `switzerland-powerup-full-scan.yml`, `switzerland-target-cpo-full-scan.yml`, `switzerland-target-cpo-second-pass.yml`.
- Dans updater-test, le bootstrap Electroverse historique était automatique toutes les deux heures, alors que son homonyme Data Lab utilise des événements différents ; migration fonctionnelle du processus de collecte vers Data Lab, et non identité de configuration.
- Les suppressions portent uniquement sur les YAML historiques : les données historiques et les scripts n'ont pas été effacés.
- GOFAST, Swisscharge, Greenspot et les contrôles suisses ont des workflows de même fonction dans Data Lab.
- Les anciennes collectes OZECAR et REVE ont encore des workflows programmés ; elles **ne sont pas supprimées à ce stade**, leur substitution exacte doit être établie.
- Un nom de fichier identique ne suffit pas à démontrer l'égalité de sortie, de calendrier ou de mise à jour ; aucun succès des prochains runs n'est présumé.

## Workflows conservés au titre du processus Tesla / validation Tesla
- `suc-tracker-weekly.yml`
- `update-station-lot.yml`
- `update-stations.yml`
- `validate-v9-preview-dispatch.yml`

## Maintenance ou export spécifique au dépôt, conservé
- `actions-storage-maintenance.yml`
- `export-charge-companion.yml`

## Autres workflows toujours présents, comparaison fonctionnelle et déclencheurs à finaliser
Ces fichiers sont inventoriés mais **non certifiés doublons**. La majorité paraît être des outils exploratoires/diagnostics historiques à la lecture du nom ; la présence d'un équivalent fonctionnel et d'un calendrier actif doit être vérifiée avant suppression.
- `adhoc-tariff-route-discovery.yml`
- `electroverse-adaptive-300.yml`
- `electroverse-direct-1000-benchmark.yml`
- `electroverse-direct-evse-lookup.yml`
- `electroverse-direct-singles-100.yml`
- `electroverse-direct-smoke.yml`
- `electroverse-france-inventory-count.yml`
- `electroverse-incremental-refresh.yml`
- `electroverse-incremental-selector.yml`
- `electroverse-irve-mapping.yml`
- `electroverse-physicalref-batch-benchmark.yml`
- `electroverse-tariff-cache-audit.yml`
- `electroverse-tariff-cache-pilot.yml`
- `electroverse-tariff-cache-recovery.yml`
- `electroverse-tariff-cache-shard-migrate.yml`
- `electroverse-tile-property-probe.yml`
- `energie360-anon-mobile-tariff.yml`
- `energie360-apk-inspect.yml`
- `energie360-config-decode.yml`
- `energie360-direct-probe.yml`
- `energie360-legacy-route-discovery.yml`
- `energie360-public-portal-probe.yml`
- `energie360-residual-evse-probe.yml`
- `energie360-tariff-group-reconcile.yml`
- `energie360-tenant-discovery.yml`
- `france-active-party-irve-batch311.yml`
- `france-cpo-reconcile-291.yml`
- `france-intercharge-direct-probe-batch301.yml`
- `france-intercharge-direct-probe.yml`
- `france-lineage-priority-batch318.yml`
- `france-lineage-promote-batch320.yml`
- `france-lineage-reconcile-batch319.yml`
- `france-mw1-vis-irve-batch304.yml`
- `france-mw1-vis-missing-batch306.yml`
- `france-mw1-vis-wii-dedupe-batch305.yml`
- `france-national-party-inventory-batch313.yml`
- `france-non-tesla-corrected-extraction.yml`
- `france-parera-irve-batch302.yml`
- `france-party-canonical-crosscheck-batch316.yml`
- `france-wii-irve-batch303.yml`
- `inspect-irve-canonical.yml`
- `irve-electroverse-spatial-candidates.yml`
- `irve-electroverse-spatial-uniqueness.yml`
- `irve-electroverse-spatial-validation.yml`
- `morocco-cpo-runtime-config-v4.yml`
- `move-apk-inspect.yml`
- `move-public-probe.yml`
- `ozecar-france-extract.yml`
- `reve-v2-api-scheduler.yml`
- `reve-v2-monthly-production-refresh.yml`
- `reve-v2-web-extraction.yml`
- `swiss-atlas-direct-semantics.yml`
- `swiss-price-atlas-api-sample.yml`
- `swiss-price-atlas-bbox-sample.yml`
- `swiss-price-atlas-collect.yml`
- `swiss-price-atlas-frontend.yml`
- `swiss-price-atlas-probe.yml`
- `swiss-price-atlas-query-decode.yml`
- `swisscharge-cloud-paths.yml`
- `swisscharge-e360-gap-bridge.yml`
- `swisscharge-portal-probe.yml`
- `swisscharge-probe.yml`
- `switzerland-current-gap-adhoc.yml`
- `switzerland-current-scope-reconcile.yml`
- `switzerland-exact-adhoc-residual.yml`
- `switzerland-final-residual-exhaustive.yml`
- `switzerland-final-residual-reconciliation.yml`
- `switzerland-residual-chargepoint-by-id.yml`
- `switzerland-residual-final-atlas.yml`
- `switzerland-residual-national-metadata.yml`
- `switzerland-residual-relationship-audit.yml`
- `switzerland-residual-retry.yml`
- `switzerland-residual-swisscharge-probe.yml`
- `switzerland-unresolved-summary.yml`
- `switzerland-unresolved-targeted.yml`
- `uk-apcoa-open-web-smoke.yml`
- `uk-validated-open-feeds-smoke.yml`
- `ze-watt-france-extract.yml`

## Suite obligatoire du protocole
1. Comparer les déclencheurs `schedule`/`push`/`workflow_dispatch`, scripts, sorties, consommateurs, et dernière réussite pour chacun des workflows non-Tesla restants.
2. Priorité aux collectes programmées : OZECAR, REVE et tout autre workflow encore actif.
3. Pour une vraie duplication prouvée, supprimer le YAML dans updater-test uniquement après confirmation que Data Lab collecte, préserve et publie de manière validée.
4. Enregistrer commits, runs, incidents et décisions dans `memory/CURRENT.md`, `memory/HISTORY.md` et ce rapport ; ne pas considérer les éléments non audités comme finalisés.

## 13 octobre, complément : traçage des consommateurs réels (pas seulement des schedules)

- Règle utilisateur : **ne pas déduire l'utilité d'une collecte de l'existence d'un workflow**. Pour chaque source, établir la chaîne depuis les sorties exactes du job jusqu'à un lecteur actif (script, workflow, snapshot compilé, site V9), avec preuve du dernier chemin exécuté. Un YAML peut être actif tout en étant orphelin ; un YAML supprimé peut avoir produit un fichier toujours référencé.
- Contrôle GitHub Production `main`, `config/refresh-policy.json` : `collection.cpoDirect.ownerRepo`, `collection.electra.ownerRepo` et `collection.electroverse.ownerRepo` désignent **Data Lab**. La politique de développement sélectionne le snapshot `2026-10-13-be-energyvision-official-cpo-candidate` au SHA Data Lab `94d4fc6785a0c1d2ed4df1d01b5a30d203bd4cd3` ; aucune promotion live automatique.
- Mais le snapshot sélectionné comporte encore des références de provenance à `legacyUpdater` au SHA `3e4c26b...` et à `germanyRecovery` au SHA `59573b8...` (branche `work/germany-v9-cpo-recovery`, PR #6). Ses jeux nationaux déclarent `primarySource=dataLab` pour FR/NL/CH/MA/DE/UK/BE et `stable` pour ES/IT/TESLA. **Ces références au dépôt historique ne prouvent ni consommation runtime, ni absence de dépendance de build** ; les champs de provenance restent à confronter aux scripts d'assemblage et aux manifestes exécutés.
- Le dépôt updater-test possède 1 228 éléments de tree Git versionné, dont 84 YAML après les huit suppressions. Production : 271 éléments versionnés et 51 YAML. Le listing Data Lab via l'API Contents atteint une première page de 1 000 workflows et ne doit PAS être traité comme un recensement exhaustif.
- **Conclusion provisoire seulement** : la politique de sélection des sources oriente les nouveaux snapshots CPO/eMSP vers Data Lab, mais le graphe complet des lecteurs et artefacts actifs n'est pas encore prouvé. Ne pas supprimer les 84 YAML restants, fichiers de données ni chemins de secours sur la seule base de la cadence ou des noms.
- Suite : pour chaque fichier produit par `updater-test`, relever ses lecteurs directs et indirects dans les quatre dépôts, les appels API/checkout d'un SHA historique, les dispatchs inter-dépôts, les runs et artefacts, puis classer `runtime active`, `build/pin active`, `historical provenance only`, `orphan proven`, ou `not yet proven`. Ne supprimer que les orphelins prouvés ou doublons couverts ; préserver Tesla/Mac.

## 13 octobre, revue consommateurs : REVE, OZECAR, Tesla et Electroverse

### REVE Espagne — dépendance inter-dépôts prouvée, **ne pas supprimer**
- Workflow historique `.github/workflows/reve-v2-monthly-production-refresh.yml` : checkout de la branche historique `reve-v2-web-extraction`, construction REVE, puis checkout du dépôt **`tesla-charge-companion-stable`** et copie vers `v9-production-runtime/data/v9/spain-static` et `spain-reve-offers`, commit/push sous validation. Exécution planifiée chaque premier du mois ; [échec 2026-10-01](https://github.com/yass3705/tesla-stations-updater-test/actions/runs/36847109484), réussite non présumée.
- Le manifeste Stable Espagne actuellement consulté a `generatedAt=2026-09-27T09:08:02.333Z`, `stationCount=13980`, `uniqueEvseIds=42887` et `ambiguousEvseIds=139` ; le snapshot Production de développement sélectionne `primarySource=stable` pour ES. **Dépendance de publication historique potentiellement encore nécessaire**, même si dernier run en échec.
- Data Lab dispose de `spain-reve-v9-stream-refresh.yml` avec cadence horaire, mais ce pipeline ne prouve pas à lui seul le remplacement du transfert vers Stable. Toute migration doit inclure consommation du snapshot ES, offers et garde d'équivalence.

### OZECAR — activité historique mais consommation Production non établie
- `ozecar-france-extract.yml` programmé chaque jeudi, écriture `data/ozecar/france/ozecar-france-current.json.gz` et rapport dans updater-test ; [run 2026-10-08 réussi](https://github.com/yass3705/tesla-stations-updater-test/actions/runs/37770196420). Aucun chemin de copie vers Production constaté dans le YAML inspecté. Un pipeline national WAAT/Monta Data Lab existe, mais équivalence d'IDs, prix et consommateurs OZECAR non prouvée. **Conserver** en attendant preuve.

### Autres
- `export-charge-companion.yml` fonctionne sur Mac self-hosted et compare un export Tesla à SuC Tracker ; conserver avec Tesla.
- `electroverse-incremental-refresh.yml` est manuel ou sur fichier trigger (pas de cadence schedule) et écrit dans l'ancien dépôt ; Data Lab dispose de `electroverse-france-daily-delta.yml` programmé. Ne pas déduire l'inutilité des caches historiques sans rechercher les lecteurs des chemins correspondants.
- `ze-watt-france-extract.yml` est manuel ou push sur script ; il publie un snapshot Ze-Watt dans l'ancien dépôt. Aucun homonyme direct trouvé lors du contrôle Data Lab ; **conserver en attendant analyse des consommateurs**.
- Huit suppressions antérieures portaient sur des YAML ; rien ne démontre encore que toutes les données déjà extraites soient devenues inutiles, donc garder les fichiers de données historiques.

## 13 octobre — correction de critère demandée : Production est l'unique destination de publication TCC V9

- **Stable ne doit plus être traité comme une destination finale justifiant à elle seule le maintien d'une collecte**. Stable peut servir de référence, archive, source transitoire de snapshot épinglé ou contrôle de parité, mais le critère d'utilité d'un workflow est sa contribution **effective et prouvée au dépôt Production et, s'il s'agit de publication live, au runtime déployé**.
- Le snapshot actuellement désigné par `tesla-charge-companion-production/config/refresh-policy.json`, `2026-10-13-be-energyvision-official-cpo-candidate`, utilise encore `primarySource=stable` pour **TESLA, ES et IT** ; le SHA Stable épinglé est `0a6d2c3415504397310d3dc92fae40be843b2435`. Il faut mesurer ces lectures réelles dans le build Production et migrer ce reliquat si Data Lab dispose des données vérifiées. **Ce n'est pas une autorisation à republier sur Stable**.
- Le workflow REVE mensuel de updater-test publie vers Stable ; cela explique une provenance ancienne mais **ne prouve pas l'actualisation de Production**, car Production utilise un snapshot candidat immuable avec SHA Stable explicite et les promotions sont manuelles. Réviser son statut : **candidat à retrait/migration**, sous réserve d'auditer le chemin de données effectif jusqu'à Production et la couverture REVE Data Lab. La conclusion précédente « conserver impérativement parce que Stable reçoit des données » était trop forte.
- Même règle pour OZECAR, Ze-Watt, Electroverse, GOFAST, Suisse, etc. : un workflow peut être actif, publier dans un dépôt et rester sans aucun lecteur dans le build Production. Ne pas déduire une dépendance des seules références de provenance, d'un nom identique, d'une production d'artefact ou de l'activité GitHub Actions.
- Classification demandée : (1) **consommateur direct Production démontré**, (2) **consommateur indirect dans un build Production démontré**, (3) **référence historisée / snapshot figé seulement**, (4) **aucun lien Production prouvé**, (5) **audit incomplet**. Ne supprimer les processus potentiellement utiles qu'après évaluation des pertes de données et de la migration, mais ne jamais considérer Stable comme une destination finale.

## 15 octobre 2026 — règle GLOBALE de validation des migrations, décision utilisateur

**Objectif : déplacer l'exécution des mises à jour non-Tesla vers Data Lab, pas analyser les changements opérationnels ordinaires des CPO.** S'applique à tous les collecteurs et workflows du chantier Updater Test/Stable → Data Lab (OZECAR, Ze-Watt, Electroverse, REVE, autres CPO/eMSP et sources nationales), et aux contrôles de cutover qui en dépendent.

- Mesurer la **couverture EVSE** en nombres comparables sur les mêmes règles de périmètre/filtrage, et la présence globale des données tarifaires correspondantes. Si le nombre d'EVSE est égal ou supérieur, la croissance du parc est normale et **ne déclenche pas d'audit EVSE par EVSE**.
- Une **baisse du nombre d'EVSE** déclenche une investigation de perte de couverture avant migration/retrait du legacy ; ne pas conclure automatiquement à une régression ou supprimer des EVSE légitimement disparus sans preuve.
- Les changements de prix, profils, règles horaires, nombre de grilles ou tarif d'une borne sont **normaux et non bloquants** : ne plus imposer la parité de montant, signature ou liste de prix entre deux dates différentes.
- Si les tarifs directs ou les tarifs de la catégorie collectée **disparaissent globalement**, investiguer et bloquer le cutover. Les prix manquants isolés restent gouvernés par les règles métier fail-closed, sans invention ni conversion de tarifs eMSP en CPO.
- Vérifier que les runs Data Lab exécutent et persistent réellement le bon snapshot, puis que les consommateurs utiles basculent vers cette source. Les garde-fous techniques indispensables (fichiers lisibles, clés, connecteurs autorisés, statut pertinent, indépendance de Tesla/Mac) restent valables ; ne pas confondre validation de migration et audit tarifaire métier.
- Ne désactiver les anciens déclencheurs qu'après preuve de remplacement et vérification des consommateurs ; conserver Tesla via Mac dans Updater Test, Stable comme référence/rollback si encore nécessaire.

**Cette décision remplace toute exigence antérieure de parité tarifaire exacte appliquée comme gate générique de migration.** Les rapports d'écarts prix peuvent rester informatifs mais ne doivent plus bloquer ni provoquer d'analyses systématiques.
